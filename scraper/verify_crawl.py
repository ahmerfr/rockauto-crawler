"""verify_crawl.py — ACCURACY CHECK: crawl a small live slice of RockAuto with the
REAL crawler (crawl_jsonl.run — the exact code that produced our 40k Acura parts),
then dump the parts grouped by vehicle so a human can compare them to RockAuto.com.

No dedup, no copying — every listing here was fetched DIRECTLY from RockAuto. Runs
on a GitHub-Actions Azure IP. Also reports total requests so we can gauge bytes.
"""
from __future__ import annotations

import collections
import json
import os

# Must be set before importing the crawler (config/crawl read env at import time).
os.environ.setdefault("SP_YEAR_MIN", os.getenv("PROBE_YEAR", "2015"))
os.environ.setdefault("SP_YEAR_MAX", os.getenv("PROBE_YEAR", "2015"))
os.environ["SP_DOWNLOAD_IMAGES"] = "0"          # data only

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import crawl_jsonl  # noqa: E402

OUT = "/tmp/verify.ndjson"


def main() -> int:
    make = os.getenv("PROBE_MAKE", "honda")
    budget = int(os.getenv("PROBE_BUDGET", "900"))
    print(f"crawling {make} {os.environ['SP_YEAR_MIN']} (budget {budget}, images off) — LIVE from RockAuto\n")
    stats = crawl_jsonl.run(0, 1, OUT, makes_override=[make], budget=budget, max_seconds=420)
    print(f"\nSTATS: requests={stats.get('requests')} listings={stats.get('listings')} "
          f"nodes={stats.get('nodes')} captchas={stats.get('captchas')}")

    rows = []
    try:
        for line in open(OUT, encoding="utf-8"):
            rows.append(json.loads(line))
    except OSError:
        pass
    print(f"total listing rows written: {len(rows)}\n")
    if not rows:
        print("!! no rows — check block/captcha above"); return 1

    byv = collections.defaultdict(collections.Counter)
    for r in rows:
        key = f"{r.get('year')} {r.get('make_name')} {r.get('model_name')} {r.get('engine_name')}"
        cat = (r.get("category_path") or "?").split(">")[-1].strip()
        byv[key][cat] += 1

    print(f"=== {len(byv)} vehicles crawled — parts per part-type (compare to RockAuto.com) ===")
    for key, cats in list(byv.items())[:5]:
        print(f"\n{key}: {sum(cats.values())} parts, {len(cats)} part-types")
        for cat, c in cats.most_common(12):
            print(f"    {cat}: {c}")

    print("\n=== SAMPLE PART ROWS (brand / part# / price / name) ===")
    for r in rows[:15]:
        print(f"  {r.get('brand_name','?'):18} {str(r.get('part_number','?')):16} "
              f"${r.get('price')}  {str(r.get('name',''))[:34]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
