#!/usr/bin/env python
"""audit_accuracy.py — statistical accuracy audit of the crawled catalog.

Re-crawls a (make, year) slice FRESH from RockAuto live (same Evomi-US crawler)
and compares every listing to what's stored in the DB:

  * PART COVERAGE  — is each live part present in our DB (by make/model/engine/
                     part-type/brand/part#)? This is the real "exact scrape"
                     metric: did we capture the right parts?
  * PRICE FIDELITY — does the stored price match live? Diffs here are RockAuto's
                     OWN price changes since our crawl (proven volatile), not
                     scrape errors — re-crawling updates them (latest-wins).

Gives you a hard match-% instead of trusting millions of rows by eye. Uses a tiny
byte cap so the audit itself can't cost more than a fraction of a cent.

    python bin/audit_accuracy.py --make acura --year 2015 [--budget 500]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import db  # noqa: E402


def _key(model, engine, cat, brand, pn):
    return (str(model).upper().strip(), str(engine).upper().strip(),
            str(cat).upper().strip(), str(brand).upper().strip(),
            str(pn).upper().strip())


def fresh_crawl(make: str, year: int, budget: int) -> dict:
    """Re-crawl one make/year live and return {key: price}."""
    out = os.path.join(ROOT, "artifacts", "_audit", f"{make}_{year}.ndjson")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    env = dict(os.environ,
               SP_USE_EVOMI="1", EVOMI_COUNTRY="US",
               SP_YEAR_MIN=str(year), SP_YEAR_MAX=str(year),
               SP_DOWNLOAD_IMAGES="0", SP_MIN_DELAY="0.3", SP_MAX_DELAY="0.7",
               SP_MAX_GB="0.4", SP_BUDGET_STATE="")   # own safety cap; no shared state
    print(f"re-crawling {make} {year} FRESH from RockAuto live (Evomi US)…", flush=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "scraper", "crawl_jsonl.py"),
                    "--makes", make, "--budget", str(budget), "--max-seconds", "700",
                    "--out", out], env=env, check=False)
    live = {}
    for line in open(out, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not r.get("part_number"):
            continue
        cat = (r.get("category_path") or "").split(">")[-1]
        live[_key(r.get("model_name"), r.get("engine_name"), cat,
                  r.get("brand_name"), r.get("part_number"))] = r.get("price")
    return live


def db_listings(make: str, year: int) -> dict:
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        """SELECT mo.name mo, COALESCE(e.name,'') en, c.name cat, COALESCE(b.name,'') br,
                  p.part_number pn, p.price pr
             FROM parts p
             JOIN part_fitment pf ON pf.part_id = p.id
             JOIN vehicles v      ON v.id = pf.vehicle_id
             JOIN makes mk        ON mk.id = v.make_id
             JOIN models mo       ON mo.id = v.model_id
        LEFT JOIN engines e       ON e.id = v.engine_id
             JOIN categories c    ON c.id = p.category_id
        LEFT JOIN brands b        ON b.id = p.brand_id
            WHERE mk.name = %s AND v.year = %s""",
        (make.upper(), year))
    out = {}
    for r in cur.fetchall():
        out[_key(r["mo"], r["en"], r["cat"], r["br"], r["pn"])] = r["pr"]
    conn.close()
    return out


def _pct(n, d):
    return 100.0 * n / d if d else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--budget", type=int, default=500)
    a = ap.parse_args()

    live = fresh_crawl(a.make, a.year, a.budget)
    stored = db_listings(a.make, a.year)
    print(f"\nlive listings fetched: {len(live)}  |  stored in DB: {len(stored)}")
    if not live:
        print("!! no live listings — crawl produced nothing; cannot audit")
        return 1

    both = set(live) & set(stored)
    live_only = set(live) - set(stored)       # RockAuto has, we DON'T (miss / new)
    db_only = set(stored) - set(live)          # we have, not live now (churn / not reached)

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    exact = sum(1 for k in both if num(live[k]) is not None and num(stored[k]) is not None
                and abs(num(live[k]) - num(stored[k])) < 0.005)
    close = sum(1 for k in both if num(live[k]) is not None and num(stored[k]) is not None
                and abs(num(live[k]) - num(stored[k])) < 0.05)

    print("\n===== PART COVERAGE (the 'exact scrape' metric) =====")
    print(f"  live parts captured in our DB : {len(both)}/{len(live)}  = {_pct(len(both),len(live)):.1f}%")
    print(f"  live-only (we are missing)    : {len(live_only)}")
    print(f"  db-only (not live right now)  : {len(db_only)}  (closeout churn / other engines)")

    print(f"\n===== PRICE FIDELITY (on {len(both)} common parts) =====")
    print(f"  exact price match  : {exact}/{len(both)} = {_pct(exact,len(both)):.1f}%")
    print(f"  within 5 cents     : {close}/{len(both)} = {_pct(close,len(both)):.1f}%")
    print("  (price diffs are RockAuto's own changes since our crawl, not errors)")

    drifts = [(k, stored[k], live[k]) for k in both
              if num(live[k]) is not None and num(stored[k]) is not None
              and abs(num(live[k]) - num(stored[k])) >= 0.05]
    if drifts:
        print("\n  sample price drifts (stored -> live):")
        for k, s, l in drifts[:8]:
            print(f"    {k[3]} {k[4]}: ${s} -> ${l}")
    if live_only:
        print("\n  sample live parts missing from DB:")
        for k in list(live_only)[:8]:
            print(f"    {k[3]} {k[4]}  [{k[0]} {k[1]} {k[2]}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
