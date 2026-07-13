#!/usr/bin/env python
"""
Supreme Parts — Loader (staging -> canonical), Agent E.

Drains `stg_listings` (and then `stg_fitment`) rows WHERE processed=0 into the
canonical storefront tables using idempotent `INSERT ... ON DUPLICATE KEY UPDATE`
upserts, in FK-safe order:

    makes -> models -> engines -> vehicles -> brands -> categories
          -> parts -> part_images / part_attributes / part_interchange
          -> part_documents -> inventory -> part_fitment

One DB transaction per staging batch. Writes one `import_logs` row per batch with
rows_total / rows_ok / rows_failed. Fully idempotent + resumable: re-running only
re-touches rows that are still processed=0, and every canonical write dedupes on a
deterministic natural key, so it NEVER duplicates and NEVER deletes existing
`source='generated'` seed rows.

Usage:
    python bin/loader.py [--batch <id>] [--limit N]
    python bin/loader.py --selftest        # offline-ish DB round-trip, rolled back

Slug / sku rules mirror the PHP side (app/Controllers/Admin/*Controller.php) and the
seed data exactly, so scraped rows dedupe against the generated catalog:
    slug = lower -> [^a-z0-9]+ => '-' -> trim('-')
    sku  = slugify(brand)-slugify(part_number)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

# --- make scraper/ importable (db.py + config.py live there) ------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import db  # noqa: E402  (scraper/db.py)


# ---------------------------------------------------------------------------
# Slug / normalization helpers — MUST match app/Core + *Controller.php slugify.
# ---------------------------------------------------------------------------
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")


def slugify(s: str | None, fallback: str = "") -> str:
    """lowercase, non-alnum runs -> '-', trimmed. Matches PHP slugify()."""
    s = (s or "").strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s or fallback


def sku_for(brand: str | None, part_number: str | None) -> str:
    """Deterministic part sku = slugify(brand)-slugify(part_number)."""
    return _t(f"{slugify(brand, 'brand')}-{slugify(part_number, 'part')}", 120)


def norm_number(s: str | None) -> str:
    """Interchange match key: strip non-alnum, uppercase."""
    return _ALNUM_RE.sub("", (s or "")).upper()


def vehicle_slug(make: str | None, model: str | None, year, engine: str | None,
                 trim: str | None) -> str:
    """Deterministic vehicle slug, e.g. '2013-honda-civic-1-8l-l4-lx'."""
    parts = [str(year) if year else "", make or "", model or "", engine or "", trim or ""]
    return _t(slugify(" ".join(p for p in parts if p), "vehicle"), 180)


def _t(s, n: int):
    """Truncate a string to n chars (VARCHAR-safe). Pass-through for non-str."""
    if isinstance(s, str) and len(s) > n:
        return s[:n]
    return s


def _variant_code(v: dict, i: int = 0) -> str:
    """Deterministic natural key for a part variant — the (part_id, code) unique
    key. RockAuto's option `value` and the old positional `opt{i}` both drift
    between crawls, so the same logical option would upsert under two codes and
    duplicate. Derive the code from the stable option label (+ pack size) so one
    option always maps to one row. Used when the parsed variant carries no code."""
    base = slugify(v.get("type") or "", "")
    ps = v.get("pack_size")
    if ps:
        base = f"{base}-{ps}" if base else f"pack-{ps}"
    return _t(base, 64) or f"opt{i}"


def _jload(v, default):
    """Coerce a JSON column (str | already-decoded | None) into a Python value."""
    if v is None:
        return default
    if isinstance(v, (list, dict)):
        return v
    try:
        out = json.loads(v)
        return out if out is not None else default
    except (ValueError, TypeError):
        return default


def _f(v):
    """Float or None (blank/invalid -> None)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _i(v):
    """Int or None."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Loader — one instance per run; caches natural-key -> id within the txn.
# ---------------------------------------------------------------------------
class Loader:
    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
        # per-run identity caches (valid within the open transaction)
        self._make: dict[str, int] = {}
        self._model: dict[tuple, int] = {}
        self._engine: dict[str, int] = {}
        self._brand: dict[str, int] = {}
        self._vehicle: dict[str, int] = {}
        self._category: dict[str, int] = {}
        self._part: dict[str, int] = {}

    # -- generic idempotent upsert that returns the row id ------------------
    def _upsert_id(self, table: str, vals: dict, update_cols: list[str] | None = None,
                   update_exprs: dict[str, str] | None = None) -> int:
        """
        INSERT ... ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)[, col=VALUES(col)...].
        Returns the id of the inserted OR existing row (the standard MySQL trick).
        Relies on the table having an AUTO_INCREMENT `id` and a natural UNIQUE key.
        `update_exprs` overrides a column's update RHS (e.g. COALESCE to not clobber
        a known value with NULL).
        """
        cols = list(vals.keys())
        collist = ",".join(f"`{c}`" for c in cols)
        placeholders = ",".join(["%s"] * len(cols))
        updates = ["id=LAST_INSERT_ID(id)"]
        for c in (update_cols or []):
            updates.append(f"`{c}`=VALUES(`{c}`)")
        for c, expr in (update_exprs or {}).items():
            updates.append(f"`{c}`={expr}")
        sql = (f"INSERT INTO `{table}` ({collist}) VALUES ({placeholders}) "
               f"ON DUPLICATE KEY UPDATE {', '.join(updates)}")
        self.cur.execute(sql, [vals[c] for c in cols])
        return self.cur.lastrowid

    def _insert_absent(self, table: str, match: dict, vals: dict) -> None:
        """
        Insert vals only if no row already matches `match` (used for child tables
        that lack a UNIQUE key: part_images / part_attributes / part_documents).
        Keeps re-runs idempotent WITHOUT deleting existing (generated) children.
        """
        where = " AND ".join(f"`{k}`<=>%s" for k in match)  # <=> handles NULLs
        self.cur.execute(f"SELECT id FROM `{table}` WHERE {where} LIMIT 1",
                         list(match.values()))
        if self.cur.fetchone():
            return
        cols = list(vals.keys())
        collist = ",".join(f"`{c}`" for c in cols)
        placeholders = ",".join(["%s"] * len(cols))
        self.cur.execute(f"INSERT INTO `{table}` ({collist}) VALUES ({placeholders})",
                         [vals[c] for c in cols])

    # -- dimension resolvers (cached) --------------------------------------
    def make_id(self, name: str) -> int:
        key = slugify(name, "make")
        if key not in self._make:
            self._make[key] = self._upsert_id(
                "makes",
                {"name": _t(name, 80), "slug": _t(key, 100), "is_active": 1},
            )
        return self._make[key]

    def model_id(self, make_id: int, name: str) -> int:
        slug = slugify(name, "model")
        key = (make_id, slug)
        if key not in self._model:
            self._model[key] = self._upsert_id(
                "models",
                {"make_id": make_id, "name": _t(name, 100), "slug": _t(slug, 120),
                 "is_active": 1},
            )
        return self._model[key]

    def engine_id(self, name, liters, cylinders, fuel_type, aspiration) -> int | None:
        if not name:
            return None
        key = name.strip().lower()
        if key not in self._engine:
            self._engine[key] = self._upsert_id(
                "engines",
                {"name": _t(name, 80), "liters": _f(liters), "cylinders": _i(cylinders),
                 "fuel_type": _t(fuel_type, 30), "aspiration": _t(aspiration, 30)},
                update_cols=["liters", "cylinders", "fuel_type", "aspiration"],
            )
        return self._engine[key]

    def brand_id(self, name) -> int | None:
        if not name:
            return None
        key = slugify(name, "brand")
        if key not in self._brand:
            self._brand[key] = self._upsert_id(
                "brands",
                {"name": _t(name, 120), "slug": _t(key, 140), "is_active": 1},
            )
        return self._brand[key]

    def vehicle_id(self, make_id, model_id, year, engine_id, trim, veh_slug,
                   market=None) -> int:
        if veh_slug not in self._vehicle:
            self._vehicle[veh_slug] = self._upsert_id(
                "vehicles",
                {"make_id": make_id, "model_id": model_id, "year": _i(year),
                 "engine_id": engine_id, "trim": _t(trim, 80), "slug": veh_slug,
                 "market": _t(market, 64)},
                update_cols=["engine_id", "trim"],
                # never let a market-less path (stg_fitment) blank a known market
                update_exprs={"market": "COALESCE(VALUES(market), market)"},
            )
        return self._vehicle[veh_slug]

    def category_leaf_id(self, category_path: str | None) -> int | None:
        """Build the category tree from 'A>B>C'; return the leaf id."""
        if not category_path:
            return None
        names = [n.strip() for n in category_path.split(">") if n.strip()]
        if not names:
            return None
        parent_id = None
        leaf_id = None
        for i, name in enumerate(names):
            slug = _t(slugify(" ".join(names[: i + 1]), "category"), 140)
            if slug in self._category:
                leaf_id = self._category[slug]
                parent_id = leaf_id
                continue
            cid = self._upsert_id(
                "categories",
                {"parent_id": parent_id, "name": _t(name, 120), "slug": slug,
                 "position": i, "is_active": 1},
                update_cols=["parent_id"],
            )
            self._category[slug] = cid
            leaf_id = cid
            parent_id = cid
        return leaf_id

    # -- part upsert -------------------------------------------------------
    def part_id(self, brand_id, category_id, listing) -> int:
        brand = listing.get("brand_name")
        pn = listing.get("part_number")
        sku = sku_for(brand, pn)
        name = listing.get("name") or pn or sku
        slug = _t(slugify(f"{brand or ''} {name}", "part"), 255)
        vals = {
            "brand_id": brand_id,
            "category_id": category_id,
            "part_number": _t(pn or "", 100),
            "sku": sku,
            "name": _t(name, 255),
            "slug": slug,
            "description": listing.get("description"),
            # price stays NULL when RockAuto shows none (out of stock). `or 0` here
            # rendered every out-of-stock part as a real "$0.00" in the storefront.
            "price": _f(listing.get("price")),
            "core_charge": _f(listing.get("core_charge")) or 0,
            "weight": _f(listing.get("weight")),
            "warranty": _t(listing.get("warranty"), 160),
            "status": "active",
            "source_url": _t(listing.get("source_url"), 500),
        }
        pid = self._upsert_id(
            "parts", vals,
            update_cols=["brand_id", "category_id", "part_number", "name", "slug",
                         "description", "price", "core_charge", "weight", "warranty",
                         "status", "source_url"],
        )
        self._part[sku] = pid
        return pid

    # -- one staged listing -> canonical rows ------------------------------
    def load_listing(self, row: dict) -> None:
        # 1. vehicle dimensions (make/model/engine/vehicle) — only if we have a year
        vehicle_id = None
        make_name = row.get("make_name")
        year = row.get("year")
        if make_name and row.get("model_name") and year:
            mk = self.make_id(make_name)
            mo = self.model_id(mk, row["model_name"])
            eng = self.engine_id(row.get("engine_name"), row.get("liters"),
                                 row.get("cylinders"), row.get("fuel_type"),
                                 row.get("aspiration"))
            vslug = vehicle_slug(make_name, row["model_name"], year,
                                 row.get("engine_name"), row.get("trim"))
            vehicle_id = self.vehicle_id(mk, mo, year, eng, row.get("trim"), vslug,
                                         row.get("market"))

        # Vehicle-only dimension row (from the --tree-only crawl): the make/model/
        # engine/vehicle upsert above IS the whole payload — there is no part. Stop
        # before part_id, which would otherwise mint a junk "brand-part" sku.
        if not row.get("brand_name") and not row.get("part_number"):
            return

        # 2. brand + category + part
        brand_id = self.brand_id(row.get("brand_name"))
        category_id = self.category_leaf_id(row.get("category_path"))
        pid = self.part_id(brand_id, category_id, row)

        # 3. images (child, existence-guarded so we never dup or wipe seed rows)
        imgs = [str(u) for u in _jload(row.get("image_urls"), []) if u]
        for i, url in enumerate(imgs):
            path = _t(url, 255)
            self._insert_absent("part_images", {"part_id": pid, "path": path},
                                {"part_id": pid, "path": path, "position": i,
                                 "alt": _t(row.get("name"), 255)})
        # Set the storefront's main thumbnail from the first product photo — only
        # when it isn't set yet, so we never clobber an existing/seed image.
        if imgs:
            # Set the main thumbnail when it's unset, OR replace a broken remote
            # rockauto.com URL with our self-hosted local path. Never clobber an
            # existing local/seed image.
            self.cur.execute(
                "UPDATE parts SET primary_image_path=%s "
                "WHERE id=%s AND (primary_image_path IS NULL OR primary_image_path='' "
                "OR primary_image_path LIKE 'http%%rockauto%%')",
                [_t(imgs[0], 255), pid])

        # 4. attributes
        for attr in _jload(row.get("attributes"), []):
            if not isinstance(attr, dict):
                continue
            aname = _t(attr.get("name"), 120)
            aval = _t(attr.get("value"), 255)
            if not aname or aval is None:
                continue
            self._insert_absent("part_attributes",
                                {"part_id": pid, "name": aname, "value": aval},
                                {"part_id": pid, "name": aname, "value": aval})

        # 4b. "Choose Type" dropdown variants -> part_attributes rows the storefront
        # already renders. name="variant:<type>", value=per-each price (+ pack total).
        # Dropdown options -> part_variants (inventory tiers like "Regular Inventory"
        # / "Wholesaler Closeout", and "Choose Type" packs). `price` is authoritative
        # (RockAuto's pricebreakdown JSON); price_each is the per-each fallback.
        # price stays NULL for an option with no price (out of stock).
        for i, v in enumerate(_jload(row.get("variants"), [])):
            if not isinstance(v, dict) or not v.get("raw"):
                continue
            # Backward/robustness: crawls before the `code` field, and options
            # RockAuto lists with only a price (no label), still load. Fall back
            # to a position-stable code and a generic label.
            code = v.get("code") or _variant_code(v, i)
            vtype = v.get("type") or f"Option {i + 1}"
            vp = _f(v.get("price"))
            if vp is None:
                vp = _f(v.get("price_each"))
            self._upsert_id(
                "part_variants",
                {"part_id": pid, "code": _t(str(code), 64), "type": _t(vtype, 160),
                 "price": vp, "core_charge": _f(v.get("core")) or 0,
                 "oos": 1 if v.get("oos") else 0,
                 "is_default": 1 if v.get("selected") else 0,
                 "pack_size": _i(v.get("pack_size")),
                 "pack_total": _f(v.get("pack_total")), "position": i},
                update_cols=["type", "price", "core_charge", "oos", "is_default",
                             "pack_size", "pack_total", "position"],
            )

        # 5. interchange (has uq part_id+number_norm -> plain upsert)
        for x in _jload(row.get("interchange"), []):
            if not isinstance(x, dict):
                continue
            number = x.get("number") or x.get("part_number")
            nn = norm_number(number)
            if not nn:
                continue
            self._upsert_id(
                "part_interchange",
                {"part_id": pid, "brand_name": _t(x.get("brand"), 120),
                 "part_number": _t(number, 100), "number_norm": _t(nn, 100),
                 "type": _t(x.get("type") or "interchange", 20)},
                update_cols=["brand_name", "part_number", "type"],
            )

        # 6. documents (no uq key -> existence-guarded)
        for i, doc in enumerate(_jload(row.get("doc_urls"), [])):
            if not isinstance(doc, dict):
                continue
            url = doc.get("url")
            if not url:
                continue
            self._insert_absent("part_documents", {"part_id": pid, "url": _t(url, 500)},
                                {"part_id": pid, "type": _t(doc.get("type") or "info", 30),
                                 "label": _t(doc.get("label"), 160), "url": _t(url, 500),
                                 "position": i})

        # 7. inventory (uq part_id+warehouse_code)
        wh = row.get("warehouse_code")
        qty = row.get("quantity")
        if wh or qty is not None:
            self._upsert_id(
                "inventory",
                {"part_id": pid, "warehouse_code": _t(wh or "MAIN", 30),
                 "quantity": _i(qty) or 0},
                update_cols=["quantity"],
            )

        # 8. fitment implied by the leaf this listing was scraped under
        if vehicle_id is not None:
            self._upsert_id(
                "part_fitment",
                {"part_id": pid, "vehicle_id": vehicle_id,
                 "note": _t(row.get("fitment_note"), 255)},
                update_cols=["note"],
            )

    # -- one staged fitment row -> part_fitment ----------------------------
    def load_fitment(self, row: dict) -> None:
        # resolve part by sku (must already exist, from a listing in this or a prior run)
        sku = row.get("sku")
        pid = self._part.get(sku)
        if pid is None:
            self.cur.execute("SELECT id FROM parts WHERE sku=%s LIMIT 1", [sku])
            r = self.cur.fetchone()
            if not r:
                raise ValueError(f"fitment references unknown sku {sku!r}")
            pid = r["id"]
            self._part[sku] = pid

        # resolve/create the vehicle (make/model/year[/engine][/trim])
        make_name = row.get("make_name")
        model_name = row.get("model_name")
        year = row.get("year")
        if not (make_name and model_name and year):
            raise ValueError("fitment missing make/model/year")
        mk = self.make_id(make_name)
        mo = self.model_id(mk, model_name)
        eng = self.engine_id(row.get("engine_name"), None, None, None, None)
        vslug = vehicle_slug(make_name, model_name, year, row.get("engine_name"),
                             row.get("trim"))
        vid = self.vehicle_id(mk, mo, year, eng, row.get("trim"), vslug)

        self._upsert_id(
            "part_fitment",
            {"part_id": pid, "vehicle_id": vid, "note": _t(row.get("note"), 255)},
            update_cols=["note"],
        )

    # -- drain one batch (does NOT commit; caller owns the transaction) -----
    def process_batch(self, batch_id: str, limit: int | None = None) -> dict:
        counts = {"listings_seen": 0, "listings_ok": 0, "listings_failed": 0,
                  "fitment_seen": 0, "fitment_ok": 0, "fitment_failed": 0}

        # ---- listings ----
        sql = "SELECT * FROM stg_listings WHERE processed=0 AND batch_id=%s ORDER BY raw_id"
        params = [batch_id]
        if limit:
            sql += " LIMIT %s"
            params.append(int(limit))
        self.cur.execute(sql, params)
        rows = self.cur.fetchall()
        counts["listings_seen"] = len(rows)
        done = []
        for row in rows:
            self.cur.execute("SAVEPOINT sp_row")
            try:
                self.load_listing(row)
                self.cur.execute("RELEASE SAVEPOINT sp_row")
                counts["listings_ok"] += 1
                done.append(row["raw_id"])
            except Exception as exc:  # noqa: BLE001 — isolate a bad row, keep the batch
                self.cur.execute("ROLLBACK TO SAVEPOINT sp_row")
                counts["listings_failed"] += 1
                print(f"[loader] listing raw_id={row.get('raw_id')} failed: {exc}",
                      file=sys.stderr)
        if done:
            self._mark_processed("stg_listings", done)

        # ---- fitment ----
        self.cur.execute(
            "SELECT * FROM stg_fitment WHERE processed=0 AND batch_id=%s ORDER BY raw_id",
            [batch_id])
        frows = self.cur.fetchall()
        counts["fitment_seen"] = len(frows)
        fdone = []
        for row in frows:
            self.cur.execute("SAVEPOINT sp_fit")
            try:
                self.load_fitment(row)
                self.cur.execute("RELEASE SAVEPOINT sp_fit")
                counts["fitment_ok"] += 1
                fdone.append(row["raw_id"])
            except Exception as exc:  # noqa: BLE001
                self.cur.execute("ROLLBACK TO SAVEPOINT sp_fit")
                counts["fitment_failed"] += 1
                print(f"[loader] fitment raw_id={row.get('raw_id')} failed: {exc}",
                      file=sys.stderr)
        if fdone:
            self._mark_processed("stg_fitment", fdone)

        return counts

    def _mark_processed(self, table: str, raw_ids: list[int]) -> None:
        # Chunk the IN() list: a single UPDATE with ~200k placeholders exceeds
        # MySQL's max_allowed_packet and fails the whole batch.
        for i in range(0, len(raw_ids), 1000):
            chunk = raw_ids[i:i + 1000]
            marks = ",".join(["%s"] * len(chunk))
            self.cur.execute(
                f"UPDATE `{table}` SET processed=1 WHERE raw_id IN ({marks})", chunk)


# ---------------------------------------------------------------------------
# Batch discovery + import_logs bookkeeping
# ---------------------------------------------------------------------------
def pending_batches(cur, only_batch: str | None) -> list[str]:
    if only_batch:
        return [only_batch]
    seen: list[str] = []
    for tbl in ("stg_listings", "stg_fitment"):
        cur.execute(f"SELECT DISTINCT batch_id FROM {tbl} WHERE processed=0")
        for r in cur.fetchall():
            b = r["batch_id"]
            if b and b not in seen:
                seen.append(b)
    return seen


def batch_source(cur, batch_id: str) -> str:
    """Report the staging source of a batch for the import_logs `type` column."""
    cur.execute("SELECT source FROM stg_listings WHERE batch_id=%s LIMIT 1", [batch_id])
    r = cur.fetchone()
    return (r["source"] if r and r.get("source") else "rockauto")


def write_import_log(cur, batch_id: str, src: str, counts: dict) -> None:
    total = counts["listings_seen"] + counts["fitment_seen"]
    ok = counts["listings_ok"] + counts["fitment_ok"]
    failed = counts["listings_failed"] + counts["fitment_failed"]
    status = "completed" if failed == 0 else ("failed" if ok == 0 else "completed")
    msg = (f"batch={batch_id} listings ok={counts['listings_ok']} "
           f"failed={counts['listings_failed']}; fitment ok={counts['fitment_ok']} "
           f"failed={counts['fitment_failed']}")
    cur.execute(
        "INSERT INTO import_logs (admin_id, `type`, filename, rows_total, rows_ok, "
        "rows_failed, `status`, message) VALUES (NULL,%s,%s,%s,%s,%s,%s,%s)",
        [src, f"batch:{batch_id}", total, ok, failed, status, msg],
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def run(only_batch: str | None, limit: int | None) -> int:
    conn = db.connect()
    grand = {"listings_ok": 0, "listings_failed": 0, "fitment_ok": 0, "fitment_failed": 0}
    try:
        cur = conn.cursor()
        batches = pending_batches(cur, only_batch)
        if not batches:
            print("[loader] nothing to do (no processed=0 rows).")
            return 0
        remaining = limit
        for b in batches:
            conn.begin()
            ld = Loader(conn)
            counts = ld.process_batch(b, remaining)
            write_import_log(cur, b, batch_source(cur, b), counts)
            conn.commit()
            for k in grand:
                grand[k] += counts[k]
            print(f"[loader] batch {b}: listings {counts['listings_ok']}/"
                  f"{counts['listings_seen']} ok, fitment {counts['fitment_ok']}/"
                  f"{counts['fitment_seen']} ok, "
                  f"{counts['listings_failed'] + counts['fitment_failed']} failed")
            if remaining is not None:
                remaining -= counts["listings_seen"]
                if remaining <= 0:
                    break
        print(f"[loader] done: parts+fitment loaded ok listings={grand['listings_ok']} "
              f"fitment={grand['fitment_ok']} failed="
              f"{grand['listings_failed'] + grand['fitment_failed']}")
        return 0
    finally:
        conn.close()


def selftest() -> int:
    """
    Offline-ish round-trip: stage 2 synthetic source='rockauto' listings + 1 fitment
    with deterministic 'SELFTEST' keys, load them inside ONE transaction, assert a
    part + vehicle + fitment materialized, then ROLL BACK so nothing persists.
    Prints PASS / FAIL / SKIP.
    """
    try:
        conn = db.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"SELFTEST SKIP (db unreachable: {exc})")
        return 0

    batch = f"SELFTEST-{int(time.time())}"
    try:
        cur = conn.cursor()
        conn.begin()

        # --- stage two synthetic listings (deterministic, prefixed SELFTEST) ---
        listings = [
            {
                "source": "rockauto", "source_url": "https://example/selftest/1",
                "make_name": "SELFTEST Make", "model_name": "SELFTEST Model",
                "year": 2021, "engine_name": "2.0L L4", "liters": 2.0, "cylinders": 4,
                "fuel_type": "Gas", "aspiration": "NA", "trim": "SE",
                "category_path": "SELFTEST Cat>SELFTEST Sub",
                "brand_name": "SELFTEST Brand", "part_number": "SELFTEST-0001",
                "name": "SELFTEST Brake Pad Set", "description": "self test",
                "price": 42.50, "core_charge": 0, "weight": 3.2,
                "image_urls": json.dumps(["https://example/selftest/img1.jpg"]),
                "attributes": json.dumps([{"name": "Material", "value": "Ceramic"}]),
                "variants": json.dumps([
                    {"code": "0-0-1-1", "type": "Wholesaler Closeout", "price": 6.15,
                     "price_each": 6.15, "pack_total": None, "pack_size": None,
                     "core": 0, "oos": False, "selected": True,
                     "raw": "[Wholesaler Closeout] ($6.15)"},
                    {"code": "0-0-0-1", "type": "Regular Inventory", "price": 6.09,
                     "price_each": 6.09, "pack_total": 36.54, "pack_size": 6,
                     "core": 0, "oos": True, "selected": False,
                     "raw": "[Regular Inventory] ($6.09/Each) {6}+ $36.54"}]),
                "warehouse_code": "MAIN", "quantity": 7, "fitment_note": "Front",
                "warranty": "12 months",
                "interchange": json.dumps([{"brand": "OtherCo", "number": "OC-99",
                                            "type": "interchange"}]),
                "doc_urls": json.dumps([{"type": "info", "label": "Spec",
                                         "url": "https://example/selftest/spec.pdf"}]),
            },
            {
                "source": "rockauto", "source_url": "https://example/selftest/2",
                "make_name": "SELFTEST Make", "model_name": "SELFTEST Model",
                "year": 2021, "engine_name": "2.0L L4", "liters": 2.0, "cylinders": 4,
                "fuel_type": "Gas", "aspiration": "NA", "trim": "SE",
                "category_path": "SELFTEST Cat>SELFTEST Sub",
                "brand_name": "SELFTEST Brand", "part_number": "SELFTEST-0002",
                "name": "SELFTEST Rotor", "description": None,
                "price": 88.00, "core_charge": 10, "weight": 12.0,
                "image_urls": None, "attributes": None,
                "warehouse_code": None, "quantity": None, "fitment_note": None,
                "warranty": None, "interchange": None, "doc_urls": None,
            },
            {
                # Out-of-stock: RockAuto shows no price at all. price MUST stay NULL,
                # never collapse to 0.00 (which the storefront renders as "$0.00").
                "source": "rockauto", "source_url": "https://example/selftest/3",
                "make_name": "SELFTEST Make", "model_name": "SELFTEST Model",
                "year": 2021, "engine_name": "2.0L L4", "liters": 2.0, "cylinders": 4,
                "fuel_type": "Gas", "aspiration": "NA", "trim": "SE",
                "category_path": "SELFTEST Cat>SELFTEST Sub",
                "brand_name": "SELFTEST Brand", "part_number": "SELFTEST-0003",
                "name": "SELFTEST Out Of Stock", "description": None,
                "price": None, "core_charge": None, "weight": None,
                "image_urls": None, "attributes": None,
                "warehouse_code": None, "quantity": None, "fitment_note": None,
                "warranty": None, "interchange": None, "doc_urls": None,
            },
        ]
        cols = list(listings[0].keys()) + ["batch_id", "processed"]
        collist = ",".join(f"`{c}`" for c in cols)
        ph = ",".join(["%s"] * len(cols))
        for L in listings:
            vals = [L.get(c) for c in listings[0].keys()] + [batch, 0]
            cur.execute(f"INSERT INTO stg_listings ({collist}) VALUES ({ph})", vals)

        # --- one extra fitment row for a DIFFERENT vehicle on part #1 ---
        sku1 = sku_for("SELFTEST Brand", "SELFTEST-0001")
        cur.execute(
            "INSERT INTO stg_fitment (sku, make_name, model_name, `year`, engine_name, "
            "trim, note, batch_id, processed) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0)",
            [sku1, "SELFTEST Make", "SELFTEST Model", 2022, "2.0L L4", "SE",
             "Rear", batch])

        # --- load ---
        ld = Loader(conn)
        counts = ld.process_batch(batch)

        # --- assertions ---
        cur.execute("SELECT id FROM parts WHERE sku=%s", [sku1])
        part = cur.fetchone()
        assert part, "part not created"
        pid = part["id"]

        vslug = vehicle_slug("SELFTEST Make", "SELFTEST Model", 2021, "2.0L L4", "SE")
        cur.execute("SELECT id FROM vehicles WHERE slug=%s", [vslug])
        veh = cur.fetchone()
        assert veh, "vehicle not created"

        cur.execute("SELECT COUNT(*) n FROM part_fitment WHERE part_id=%s", [pid])
        fit = cur.fetchone()["n"]
        assert fit >= 2, f"expected >=2 fitments (leaf + staged), got {fit}"

        cur.execute("SELECT COUNT(*) n FROM part_interchange WHERE part_id=%s", [pid])
        assert cur.fetchone()["n"] == 1, "interchange not loaded"
        cur.execute("SELECT code, `type`, price, oos, is_default, pack_size, pack_total "
                    "FROM part_variants WHERE part_id=%s ORDER BY position", [pid])
        pv = cur.fetchall()
        assert len(pv) == 2, f"expected 2 part_variants, got {pv}"
        d = pv[0]
        assert d["code"] == "0-0-1-1" and d["is_default"] == 1 and d["oos"] == 0 \
            and float(d["price"]) == 6.15, f"default variant wrong: {d}"
        r = pv[1]
        assert r["code"] == "0-0-0-1" and r["is_default"] == 0 and r["oos"] == 1 \
            and r["pack_size"] == 6 and float(r["pack_total"]) == 36.54, \
            f"pack/oos variant wrong: {r}"
        # Fallback variant code must be deterministic + content-based (never the
        # volatile positional opt{i}), so a re-crawl can't duplicate the option.
        assert _variant_code({"type": "Regular Inventory"}, 3) == "regular-inventory", \
            _variant_code({"type": "Regular Inventory"}, 3)
        assert _variant_code({"type": "Regular Inventory"}, 3) \
            == _variant_code({"type": "Regular Inventory"}, 9), "variant code must ignore position"
        assert _variant_code({"type": "Concentrated", "pack_size": 6}, 0) == "concentrated-6", \
            _variant_code({"type": "Concentrated", "pack_size": 6}, 0)
        cur.execute("SELECT COUNT(*) n FROM part_images WHERE part_id=%s", [pid])
        assert cur.fetchone()["n"] == 1, "image not loaded"
        cur.execute("SELECT quantity FROM inventory WHERE part_id=%s", [pid])
        assert cur.fetchone()["quantity"] == 7, "inventory not loaded"

        # out-of-stock part keeps a NULL price (not a fake $0.00)
        sku3 = sku_for("SELFTEST Brand", "SELFTEST-0003")
        cur.execute("SELECT price FROM parts WHERE sku=%s", [sku3])
        oos = cur.fetchone()
        assert oos, "out-of-stock part not created"
        assert oos["price"] is None, f"out-of-stock price must be NULL, got {oos['price']!r}"

        assert counts["listings_ok"] == 3, counts
        assert counts["fitment_ok"] == 1, counts

        print(f"[selftest] loaded part id={pid}, vehicle id={veh['id']}, "
              f"fitments={fit}, counts={counts}")
        print("PASS")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1
    finally:
        # never persist selftest data — undo everything
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Drain staging -> canonical (idempotent).")
    ap.add_argument("--batch", default=None, help="only process this batch_id")
    ap.add_argument("--limit", type=int, default=None, help="max listing rows per batch")
    ap.add_argument("--selftest", action="store_true", help="offline round-trip, rolled back")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.batch, args.limit)


if __name__ == "__main__":
    sys.exit(main())
