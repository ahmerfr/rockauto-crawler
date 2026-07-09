"""
bin/ingest_artifacts.py — load NDJSON crawl artifacts (from the GitHub Actions
fleet) into stg_listings / stg_fitment, so the existing bin/loader.py can
canonicalize them unchanged.

    python bin/ingest_artifacts.py artifacts/*.ndjson
    python bin/ingest_artifacts.py --selftest

Each line of an artifact is one Listing dict (the exact shape crawl_jsonl.py /
parsers.parse_listings emit). We reuse scraper/crawl.py's stage_listings() so the
staging path is identical to the DB crawler. Staging is a landing zone: re-ingest
appends rows, but bin/loader.py dedupes on the deterministic sku, so canonical
data stays clean. Prints "staged N" (regex-parseable, matching import_logs).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

# Put scraper/ on the path so we can reuse db + crawl.stage_listings.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scraper"))

import db          # noqa: E402
import crawl       # noqa: E402  (stage_listings, make_batch_id)


def _iter_listings(paths: list[str]):
    """Yield Listing dicts from every NDJSON file, skipping blank/bad lines."""
    for pattern in paths:
        for path in (glob.glob(pattern) or [pattern]):
            if not os.path.isfile(path):
                print(f"[warn] not a file: {path}")
                continue
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except ValueError:
                        print(f"[warn] bad json line in {path}")


def ingest(paths: list[str], batch_id: str | None = None) -> int:
    batch_id = batch_id or ("art_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    listings = list(_iter_listings(paths))
    if not listings:
        print("staged 0 (no listings found)")
        return 0
    conn = db.connect()
    try:
        staged = crawl.stage_listings(conn, listings, batch_id)
    finally:
        conn.close()
    print(f"staged {staged} rows into stg_listings (batch {batch_id})")
    return staged


def _count_selftest_rows() -> int:
    """Fresh connection each call so we never read a stale REPEATABLE-READ snapshot."""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM stg_listings WHERE part_number LIKE 'SELFTEST-%'")
            return cur.fetchone()["c"]
    finally:
        conn.close()


def _cleanup_selftest_rows() -> None:
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stg_listings WHERE part_number LIKE 'SELFTEST-%'")
            cur.execute("DELETE FROM stg_fitment WHERE sku LIKE 'selftestbrand-selftest-%'")
        conn.commit()
    finally:
        conn.close()


def _selftest_vehicles() -> bool:
    """Vehicle-only (dimension) rows — the --tree-only crawl shape: make/model/year/
    engine but NO part_number/brand_name. Stage 2 distinct vehicles, run the loader,
    assert 2 vehicles materialize (and no junk part), then ROLL BACK so nothing
    persists. Mirrors loader.selftest's transaction-and-rollback pattern."""
    import loader  # local import: reuse Loader + vehicle_slug without a load-time dep
    conn = db.connect()
    batch = "selftest_veh_batch"
    rows = [
        {"make_name": "SELFTESTVEH Make", "model_name": "SELFTESTVEH Model",
         "year": 2019, "engine_name": "1.5L L4 Turbo"},
        {"make_name": "SELFTESTVEH Make", "model_name": "SELFTESTVEH Model",
         "year": 2020, "engine_name": "2.0L L4"},
    ]
    try:
        conn.begin()
        cur = conn.cursor()
        for r in rows:
            cur.execute(
                "INSERT INTO stg_listings (source, make_name, model_name, `year`, "
                "engine_name, batch_id, processed) VALUES (%s,%s,%s,%s,%s,%s,0)",
                ("rockauto", r["make_name"], r["model_name"], r["year"],
                 r["engine_name"], batch))
        counts = loader.Loader(conn).process_batch(batch)
        slugs = [loader.vehicle_slug(r["make_name"], r["model_name"], r["year"],
                                     r["engine_name"], None) for r in rows]
        cur.execute(
            "SELECT COUNT(*) n FROM vehicles WHERE slug IN (%s,%s)", slugs)
        n_veh = cur.fetchone()["n"]
        ok = (counts["listings_ok"] == 2 and n_veh == 2)
        print(f"  [{'PASS' if ok else 'FAIL'}] 2 vehicle-only rows -> "
              f"{n_veh} vehicles, listings_ok={counts['listings_ok']}")
        return ok
    finally:
        try:
            conn.rollback()   # never persist selftest dimensions
        except Exception:     # noqa: BLE001
            pass
        conn.close()


def _selftest() -> bool:
    if not db.ping():
        print("SKIP (DB unreachable)")
        return True
    ok = _selftest_vehicles()
    tmp = os.path.join(_ROOT, "scraper", "_selftest_artifact.ndjson")
    rows = [
        {"source": "rockauto", "source_url": "https://www.rockauto.com/x",
         "make_name": "Honda", "model_name": "Accord", "year": 2015,
         "engine_name": "2.4L L4", "category_path": "Brake & Wheel Hub>Brake Pad",
         "brand_name": "SELFTESTBrand", "part_number": "SELFTEST-0001",
         "name": "Selftest Pad", "price": 42.42, "image_urls": [], "attributes": []},
        {"source": "rockauto", "source_url": "https://www.rockauto.com/y",
         "make_name": "Honda", "model_name": "Accord", "year": 2015,
         "brand_name": "SELFTESTBrand", "part_number": "SELFTEST-0002",
         "name": "Selftest Rotor", "price": 99.00, "image_urls": [], "attributes": []},
    ]
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    try:
        _cleanup_selftest_rows()                 # start clean
        before = _count_selftest_rows()
        n = ingest([tmp], batch_id="selftest_batch")
        after = _count_selftest_rows()           # fresh connection -> sees the commit
        ok = ok and (n == 2) and (after - before == 2)
        print(f"  [{'PASS' if ok else 'FAIL'}] ingested 2 selftest part rows (before={before} after={after})")
    finally:
        _cleanup_selftest_rows()
        try:
            os.remove(tmp)
        except OSError:
            pass
    print("PASS" if ok else "FAIL")
    return ok


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Ingest NDJSON crawl artifacts into stg_listings.")
    p.add_argument("paths", nargs="*", help="NDJSON files or globs")
    p.add_argument("--batch", default=None)
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return 0 if _selftest() else 1
    if not args.paths:
        p.error("give at least one NDJSON path (or --selftest)")
    ingest(args.paths, args.batch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
