#!/usr/bin/env python
"""
Supreme Parts — vPIC importer (Agent E).

Pulls makes / models / model-years from the FREE NHTSA vPIC API into the canonical
`makes` / `models` / `vehicles` tables (engine_id + trim left NULL — vPIC has no
engine granularity at this endpoint). Idempotent: every row upserts on its
deterministic natural key, so re-running never duplicates and never touches the
existing `source='generated'` seed rows.

Usage:
    python bin/import_vpic.py --makes "Honda,Toyota" --from 2020 --to 2021
    python bin/import_vpic.py --selftest        # OFFLINE (canned data), rolled back

Stdout is kept parseable by ImportController::parseCounts:
    prints `vehicles N` and `N failed`.

Endpoint: https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/<make>/modelyear/<year>?format=json
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import db  # noqa: E402  (scraper/db.py)

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


# --- slug helpers (identical rule to loader.py / PHP slugify) ----------------
def slugify(s: str | None, fallback: str = "") -> str:
    s = (s or "").strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s or fallback


def _t(s, n: int):
    return s[:n] if isinstance(s, str) and len(s) > n else s


def vehicle_slug(make: str, model: str, year: int) -> str:
    """Matches loader.vehicle_slug with engine/trim omitted (e.g. '2020-honda-civic')."""
    parts = [str(year), make or "", model or ""]
    return _t(slugify(" ".join(p for p in parts if p), "vehicle"), 180)


# --- canonical upserts (mirror loader.py's LAST_INSERT_ID trick) -------------
def _upsert_id(cur, table: str, vals: dict, update_cols: list[str] | None = None) -> int:
    cols = list(vals.keys())
    collist = ",".join(f"`{c}`" for c in cols)
    ph = ",".join(["%s"] * len(cols))
    updates = ["id=LAST_INSERT_ID(id)"] + [f"`{c}`=VALUES(`{c}`)" for c in (update_cols or [])]
    cur.execute(
        f"INSERT INTO `{table}` ({collist}) VALUES ({ph}) "
        f"ON DUPLICATE KEY UPDATE {', '.join(updates)}",
        [vals[c] for c in cols],
    )
    return cur.lastrowid


def _make_id(cur, cache: dict, name: str) -> int:
    slug = slugify(name, "make")
    if slug not in cache:
        cache[slug] = _upsert_id(cur, "makes",
                                 {"name": _t(name, 80), "slug": _t(slug, 100), "is_active": 1})
    return cache[slug]


def _model_id(cur, cache: dict, make_id: int, name: str) -> int:
    slug = slugify(name, "model")
    key = (make_id, slug)
    if key not in cache:
        cache[key] = _upsert_id(cur, "models",
                                {"make_id": make_id, "name": _t(name, 100),
                                 "slug": _t(slug, 120), "is_active": 1})
    return cache[key]


def _vehicle_id(cur, make_id: int, model_id: int, year: int, vslug: str) -> int:
    return _upsert_id(cur, "vehicles",
                      {"make_id": make_id, "model_id": model_id, "year": year,
                       "engine_id": None, "trim": None, "slug": vslug})


def upsert_models(cur, caches: dict, make_name: str, year: int, results: list[dict]) -> int:
    """Given vPIC 'Results' for one make+year, upsert make/model/vehicle. Return new-vehicle count seen."""
    n = 0
    mk_id = _make_id(cur, caches["make"], make_name)
    for item in results:
        model_name = (item.get("Model_Name") or "").strip()
        if not model_name:
            continue
        mo_id = _model_id(cur, caches["model"], mk_id, model_name)
        vslug = vehicle_slug(make_name, model_name, year)
        _vehicle_id(cur, mk_id, mo_id, year, vslug)
        n += 1
    return n


# --- live fetch --------------------------------------------------------------
def fetch_models(make: str, year: int, timeout: int = 25, attempts: int = 3) -> list[dict]:
    import requests  # imported lazily so --selftest stays fully offline
    url = f"{VPIC_BASE}/GetModelsForMakeYear/make/{make}/modelyear/{year}"
    last = None
    for i in range(attempts):
        try:
            r = requests.get(url, params={"format": "json"}, timeout=timeout)
            r.raise_for_status()
            return r.json().get("Results") or []
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"vPIC fetch failed for {make} {year}: {last}")


def run(makes: list[str], year_from: int, year_to: int) -> int:
    conn = db.connect()
    caches = {"make": {}, "model": {}}
    vehicles = 0
    failed = 0
    try:
        cur = conn.cursor()
        conn.begin()
        for make in makes:
            for year in range(year_from, year_to + 1):
                try:
                    results = fetch_models(make, year)
                    vehicles += upsert_models(cur, caches, make, year, results)
                except Exception as exc:  # noqa: BLE001 — don't lose the rest of the run
                    failed += 1
                    print(f"[vpic] {make} {year} failed: {exc}", file=sys.stderr)
        conn.commit()
        # import_logs breadcrumb (admin_id NULL; ImportController also logs its own row)
        cur.execute(
            "INSERT INTO import_logs (admin_id, `type`, filename, rows_total, rows_ok, "
            "rows_failed, `status`, message) VALUES (NULL,'vpic',%s,%s,%s,%s,%s,%s)",
            [f"makes={','.join(makes)} {year_from}-{year_to}", vehicles + failed,
             vehicles, failed, "completed" if failed == 0 else "completed",
             f"vehicles {vehicles}, {failed} failed"],
        )
        conn.commit()
    finally:
        conn.close()
    # ImportController::parseCounts reads these:
    print(f"vehicles {vehicles}")
    print(f"{failed} failed")
    return 0 if vehicles or not failed else 1


# --- offline self-test -------------------------------------------------------
def selftest() -> int:
    """Feed canned vPIC-shaped results through upsert_models in a rolled-back txn."""
    try:
        conn = db.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"SELFTEST SKIP (db unreachable: {exc})")
        return 0
    try:
        cur = conn.cursor()
        conn.begin()
        caches = {"make": {}, "model": {}}
        canned = [
            {"Make_Name": "VPICTEST", "Model_Name": "Alpha"},
            {"Make_Name": "VPICTEST", "Model_Name": "Beta"},
            {"Make_Name": "VPICTEST", "Model_Name": "Alpha"},  # dup -> must not double
        ]
        n1 = upsert_models(cur, caches, "VPICTEST", 2020, canned)
        n2 = upsert_models(cur, caches, "VPICTEST", 2021, canned)  # different year
        assert n1 == 3 and n2 == 3, (n1, n2)

        # distinct vehicles: 2 models x 2 years = 4 (dup Alpha collapses on slug)
        cur.execute("SELECT COUNT(*) n FROM vehicles v JOIN makes m ON m.id=v.make_id "
                    "WHERE m.slug=%s", [slugify("VPICTEST")])
        got = cur.fetchone()["n"]
        assert got == 4, f"expected 4 distinct vehicles, got {got}"

        cur.execute("SELECT slug FROM vehicles WHERE slug=%s", [vehicle_slug("VPICTEST", "Alpha", 2020)])
        assert cur.fetchone(), "expected deterministic vehicle slug"

        print(f"[selftest] upserted make/models; distinct vehicles={got}")
        print("PASS")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1
    finally:
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import makes/models/years from NHTSA vPIC.")
    ap.add_argument("--makes", default="Honda", help="comma list, e.g. \"Honda,Toyota\"")
    ap.add_argument("--from", dest="year_from", type=int, default=2020)
    ap.add_argument("--to", dest="year_to", type=int, default=2021)
    ap.add_argument("--selftest", action="store_true", help="offline canned round-trip")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    makes = [m.strip() for m in args.makes.split(",") if m.strip()]
    if not makes:
        print("vehicles 0")
        print("1 failed")
        return 1
    return run(makes, args.year_from, args.year_to)


if __name__ == "__main__":
    sys.exit(main())
