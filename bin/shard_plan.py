#!/usr/bin/env python
"""shard_plan.py — SIZE-balanced make->shard assignment from a tree sizing pass.

The crawl fleet used to shard makes by count (makes[i::N]), which dumped huge makes
(Ford, Chevy) and tiny ones into arbitrary shards — so under a flat per-shard byte
cap the big makes starved and came up incomplete. This reads the tree pass
(one NDJSON row per vehicle/carcode), counts vehicles per make, and LPT-packs the
makes into N shards so every shard carries ~equal total vehicles. Each shard also
records its vehicle count so the crawl can give it a byte cap PROPORTIONAL to its
share of the catalog — a big shard gets more bytes, a tiny one fewer, so nothing
starves and the total still can't exceed the budget.

    python bin/shard_plan.py --ndjson "artifacts/_tree/**/*.ndjson" --shards 20

Writes shards.json: {"total_veh": N, "shards": [ {"makes":[...], "veh": N}, ... ]}.
"""
from __future__ import annotations

import argparse
import glob
import json
import collections


def load_counts(patterns):
    c = collections.Counter()
    for pat in patterns:
        for f in glob.glob(pat, recursive=True):
            for line in open(f, encoding="utf-8"):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                mk = (r.get("make_name") or "").strip()
                if mk and r.get("carcode"):
                    c[mk] += 1
    return c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ndjson", nargs="+", required=True)
    ap.add_argument("--shards", type=int, default=20)
    ap.add_argument("--out", default="shards.json")
    a = ap.parse_args()

    counts = load_counts(a.ndjson)
    total = sum(counts.values())
    if not total:
        print("!! no vehicles counted — check the tree ndjson path"); return 1
    fair = total / a.shards
    print(f"{len(counts)} makes, {total} vehicles, fair share/shard = {fair:.0f}")

    # LPT greedy: assign the heaviest make to the currently-lightest shard. Makes stay
    # whole (never split) — the proportional byte cap, not balance alone, is what keeps
    # a big make from starving, so splitting by year band is unnecessary.
    shards = [{"makes": [], "veh": 0} for _ in range(a.shards)]
    for mk, n in counts.most_common():
        s = min(shards, key=lambda x: x["veh"])
        s["makes"].append(mk)
        s["veh"] += n

    json.dump({"total_veh": total, "shards": shards}, open(a.out, "w"), indent=1)

    loads = [s["veh"] for s in shards]
    biggest = counts.most_common(1)[0]
    print(f"wrote {a.out}: shard loads min={min(loads)} max={max(loads)} "
          f"skew={max(loads)/max(1,min(loads)):.2f}x  (1.0 = perfect); "
          f"biggest make {biggest[0]}={biggest[1]} ({100*biggest[1]/total:.1f}% of catalog)")
    for i, s in enumerate(shards):
        tag = ", ".join(s["makes"][:3]) + (f" +{len(s['makes'])-3}" if len(s["makes"]) > 3 else "")
        print(f"  shard {i:2}: {s['veh']:6} veh  [{tag}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
