#!/usr/bin/env python
"""shard_plan.py — SIZE-balanced make->shard assignment from a tree sizing pass.

The crawl fleet used to shard makes by count (makes[i::N]), which dumped huge makes
(Ford, Chevy) and tiny ones into arbitrary shards — so under a flat per-shard byte
cap the big makes starved and came up incomplete. This reads the tree pass
(one NDJSON row per vehicle/carcode), counts vehicles per make, and LPT-packs the
makes into N shards so every shard carries ~equal total vehicles. A make bigger
than one shard's fair share is SPLIT across shards by year band so no single shard
is overloaded. Writes shards.json: [ {"makes":[...], "years":[lo,hi]|null}, ... ].

    python bin/shard_plan.py --ndjson "artifacts/_tree/**/*.ndjson" --shards 20
"""
from __future__ import annotations

import argparse
import glob
import json
import collections


def load_counts(patterns):
    c = collections.Counter()
    years = collections.defaultdict(list)   # make -> [years seen] (for splitting)
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
                    if r.get("year"):
                        years[mk].append(int(r["year"]))
    return c, years


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ndjson", nargs="+", required=True)
    ap.add_argument("--shards", type=int, default=20)
    ap.add_argument("--out", default="shards.json")
    a = ap.parse_args()

    counts, years = load_counts(a.ndjson)
    total = sum(counts.values())
    if not total:
        print("!! no vehicles counted — check the tree ndjson path"); return 1
    fair = total / a.shards
    print(f"{len(counts)} makes, {total} vehicles, fair share/shard = {fair:.0f}")

    # Build work units. A make that exceeds ~1.3x the fair share is split into
    # contiguous year bands, each a separate unit, so it spreads across shards.
    units = []   # (label, make, year_lo|None, year_hi|None, weight)
    for mk, n in counts.most_common():
        if n <= fair * 1.3 or not years[mk]:
            units.append((mk, mk, None, None, n))
            continue
        ys = sorted(years[mk])
        parts = max(2, round(n / fair))
        per = max(1, len(ys) // parts)
        for i in range(0, len(ys), per):
            band = ys[i:i + per]
            lo, hi = band[0], band[-1]
            units.append((f"{mk}[{lo}-{hi}]", mk, lo, hi, len(band)))

    # LPT greedy: heaviest unit -> currently-lightest shard.
    units.sort(key=lambda u: -u[4])
    shards = [{"makes": [], "years": None, "_load": 0, "_bands": []} for _ in range(a.shards)]
    for label, mk, lo, hi, w in units:
        s = min(shards, key=lambda x: x["_load"])
        s["_load"] += w
        if lo is None:
            s["makes"].append(mk)
        else:
            s["_bands"].append({"make": mk, "years": [lo, hi]})

    out = []
    loads = []
    for s in shards:
        loads.append(s["_load"])
        out.append({"makes": s["makes"], "bands": s["_bands"]})
    json.dump(out, open(a.out, "w"), indent=1)

    print(f"wrote {a.out}: shard loads min={min(loads)} max={max(loads)} "
          f"skew={max(loads)/max(1,min(loads)):.2f}x  (1.0 = perfect)")
    for i, (o, l) in enumerate(zip(out, loads)):
        tag = ", ".join(o["makes"][:3]) + (f" +{len(o['makes'])-3}" if len(o["makes"]) > 3 else "")
        if o["bands"]:
            tag += " | bands: " + ", ".join(b["make"] + str(b["years"]) for b in o["bands"][:2])
        print(f"  shard {i:2}: {l:6} veh  [{tag}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
