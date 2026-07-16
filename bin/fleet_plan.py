#!/usr/bin/env python
"""fleet_plan.py — expand the 20 balanced make-groups into a 360-unit fleet plan
for the 9-account × 40-job crawl fleet.

Whole-make packing (shards.json) can't balance the mega-makes: Chevrolet alone is
6,716 vehicles, ~10% of the catalog, one indivisible unit. On a single IP — even
with frontier persistence — it would grind for months. The fix is to scope each
mega-make across many IPs by YEAR: the crawler already prunes out-of-band `year`
nodes (crawl.should_enqueue -> in_scope_year), so (make-group × year-band) gives a
DISJOINT slice of the catalog per unit, no leaf overlap.

We cross the 20 groups with 18 recent-weighted year-bands = 360 units, and DEAL the
bands round-robin across the 9 accounts so each account gets exactly 2 bands of every
group (2 × 20 = 40 units) — balanced by both make-size and year-density by
construction, needing no per-year vehicle counts (which we don't have locally).

    python bin/fleet_plan.py                 # shards.json -> fleet_plan.json (360 units)
    python bin/fleet_plan.py --selftest

fleet_plan.json: [{ "makes": [...], "year_min": Y, "year_max": Y }, ...360...]
indexed by GLOBAL = ACCOUNT_OFFSET*40 + matrix.index in crawl.yml.
"""
from __future__ import annotations

import argparse
import json
import os

ACCOUNTS = 9
JOBS_PER_ACCOUNT = 40

# 18 inclusive, non-overlapping year-bands tiling [1900, 2036]. Recent model years
# get 1-year bands (dense listings + the parts customers actually buy); the vintage
# tail is lumped into one band so only ~1 IP per group works it.
BANDS: list[tuple[int, int]] = [
    (1900, 1989), (1990, 1996), (1997, 2000), (2001, 2003), (2004, 2005),
    (2006, 2007), (2008, 2009), (2010, 2011), (2012, 2012), (2013, 2013),
    (2014, 2014), (2015, 2015), (2016, 2016), (2017, 2017), (2018, 2018),
    (2019, 2019), (2020, 2021), (2022, 2036),
]


def build_plan(groups: list[dict]) -> list[dict]:
    """Cross groups × BANDS, dealing bands round-robin to accounts so each account
    gets 2 bands of every group. Returns 360 units ordered by account then group, so
    plan[offset*40 + idx] is exactly account `offset`'s job `idx`."""
    n_groups = len(groups)
    n_bands = len(BANDS)
    if n_groups * n_bands != ACCOUNTS * JOBS_PER_ACCOUNT:
        raise ValueError(f"{n_groups} groups × {n_bands} bands = {n_groups*n_bands}, "
                         f"need {ACCOUNTS*JOBS_PER_ACCOUNT}")
    per_account: list[list[dict]] = [[] for _ in range(ACCOUNTS)]
    for group in groups:
        for b_idx, (ymin, ymax) in enumerate(BANDS):
            acct = b_idx % ACCOUNTS          # 18 bands → each account gets bands acct, acct+9
            per_account[acct].append({
                "makes": group["makes"],
                "year_min": ymin,
                "year_max": ymax,
                "veh": group.get("veh", 0),  # group size (for reference/telemetry)
            })
    plan: list[dict] = []
    for acct in range(ACCOUNTS):
        plan.extend(per_account[acct])
    return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", default="shards.json", help="20-group balanced plan")
    ap.add_argument("--out", default="fleet_plan.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return 0 if _selftest() else 1

    groups = json.load(open(a.groups, encoding="utf-8"))["shards"]
    plan = build_plan(groups)
    json.dump(plan, open(a.out, "w"), indent=1)

    # Report per-account group-vehicle load (should be ~equal across the 9 accounts).
    loads = [sum(u["veh"] for u in plan[i*JOBS_PER_ACCOUNT:(i+1)*JOBS_PER_ACCOUNT])
             for i in range(ACCOUNTS)]
    print(f"wrote {a.out}: {len(plan)} units, {len(groups)} groups × {len(BANDS)} bands")
    print(f"per-account group-veh load: min={min(loads)} max={max(loads)} "
          f"skew={max(loads)/max(1,min(loads)):.3f}x (1.0=perfect)")
    return 0


def _selftest() -> bool:
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    # bands tile [1900, 2036] with no gaps or overlaps
    check("bands start at 1900", BANDS[0][0] == 1900)
    check("bands end at 2036", BANDS[-1][1] == 2036)
    check("bands contiguous, non-overlapping",
          all(BANDS[i][1] + 1 == BANDS[i + 1][0] for i in range(len(BANDS) - 1)))
    check("bands inclusive-valid", all(lo <= hi for lo, hi in BANDS))

    # 20 synthetic groups × 18 bands → 360 units, 40 per account
    groups = [{"makes": [f"MK{i}"], "veh": 100 * (i + 1)} for i in range(20)]
    plan = build_plan(groups)
    check("plan has 360 units", len(plan) == 360)
    check("each account has 40 units",
          all(len(plan[i*40:(i+1)*40]) == 40 for i in range(9)))

    # every account holds exactly 2 bands of every group (balanced by construction)
    acct0 = plan[0:40]
    mk_counts = {}
    for u in acct0:
        mk_counts[u["makes"][0]] = mk_counts.get(u["makes"][0], 0) + 1
    check("account 0 covers all 20 groups", len(mk_counts) == 20)
    check("account 0 has 2 bands per group", all(v == 2 for v in mk_counts.values()))

    # (make, year-band) coverage is disjoint AND complete across all 360 units
    seen = set()
    for u in plan:
        for mk in u["makes"]:
            key = (mk, u["year_min"], u["year_max"])
            check(f"no dup {key}", key not in seen) if key in seen else None
            seen.add(key)
    check("full coverage: 20 makes × 18 bands", len(seen) == 20 * 18)

    # per-account load is well balanced (skew < 1.05x)
    loads = [sum(u["veh"] for u in plan[i*40:(i+1)*40]) for i in range(9)]
    check("per-account load balanced (<1.05x skew)", max(loads) / min(loads) < 1.05)

    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    raise SystemExit(main())
