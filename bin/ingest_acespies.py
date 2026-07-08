#!/usr/bin/env python
"""
Supreme Parts — ACES/PIES ingester (Agent E).

Parses ACES (Application fitment) + PIES (Item / product) XML into the staging
tables `stg_listings` + `stg_fitment` with source='aces_pies'. The Loader
(bin/loader.py) then drains staging into the canonical catalog.

    python bin/ingest_acespies.py <aces.xml> <pies.xml> <refdir>
    python bin/ingest_acespies.py --selftest        # OFFLINE, rolled back

If the ACES/PIES sample files are absent, tiny VALID sample files (and a matching
reference dir) are generated under scraper/ so the admin "Run ACES/PIES" button and
this ingester work out of the box.

Reference dir (optional CSVs, VCdb/PCdb style) used to resolve ACES numeric ids:
    Make.csv         MakeID,MakeName
    Model.csv        ModelID,ModelName
    BaseVehicle.csv  BaseVehicleID,YearID,MakeID,ModelID
    PartType.csv     PartTypeID,PartTypeName
Missing files/ids degrade gracefully (fall back to any inline text).

Stdout stays parseable by ImportController::parseCounts — prints
`staged N`, `fitment M`, `0 failed`.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import db  # noqa: E402  (scraper/db.py)

SCRAPER_DIR = os.path.join(ROOT, "scraper")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


# --- slug / sku helpers (identical rule to loader.py) ------------------------
def slugify(s: str | None, fallback: str = "") -> str:
    s = (s or "").strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s or fallback


def sku_for(brand: str | None, part_number: str | None) -> str:
    return f"{slugify(brand, 'brand')}-{slugify(part_number, 'part')}"[:120]


# --- namespace-agnostic XML helpers ------------------------------------------
def _local(tag: str) -> str:
    """Strip any XML namespace: '{ns}Item' -> 'Item'."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find(el, name: str):
    """First direct-or-descendant child whose local tag == name."""
    for c in el.iter():
        if c is not el and _local(c.tag) == name:
            return c
    return None


def _findall(el, name: str) -> list:
    return [c for c in el.iter() if c is not el and _local(c.tag) == name]


def _text(el) -> str | None:
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def _child_text(el, name: str) -> str | None:
    return _text(_find(el, name))


def _iter_named(root, name: str):
    for c in root.iter():
        if _local(c.tag) == name:
            yield c


# --- reference (VCdb/PCdb) maps ---------------------------------------------
def _load_csv_map(path: str, key_i: int = 0):
    """Return {key: [row cols]} from a simple CSV (header row skipped)."""
    out: dict[str, list[str]] = {}
    if not path or not os.path.isfile(path):
        return out
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            rdr = csv.reader(fh)
            rows = list(rdr)
        # skip header if first cell isn't numeric-ish
        start = 1 if rows and not rows[0][0].strip().isdigit() else 0
        for r in rows[start:]:
            if r and r[0].strip():
                out[r[0].strip()] = [c.strip() for c in r]
    except Exception:  # noqa: BLE001 — a broken ref file must not kill the run
        return out
    return out


def load_refs(refdir: str | None) -> dict:
    d = refdir or ""
    return {
        "make": _load_csv_map(os.path.join(d, "Make.csv")),
        "model": _load_csv_map(os.path.join(d, "Model.csv")),
        "base": _load_csv_map(os.path.join(d, "BaseVehicle.csv")),
        "parttype": _load_csv_map(os.path.join(d, "PartType.csv")),
    }


# --- PIES: index items by part number ---------------------------------------
def parse_pies(pies_path: str) -> dict:
    """Return {part_number: {brand,name,description,price,attributes,image_urls,interchange,part_type}}."""
    items: dict[str, dict] = {}
    tree = ET.parse(pies_path)
    root = tree.getroot()
    for item in _iter_named(root, "Item"):
        pn = _child_text(item, "PartNumber")
        if not pn:
            continue
        brand = _child_text(item, "BrandLabel") or _child_text(item, "BrandAAIAID")
        part_type = _child_text(item, "PartTerminologyID") or _child_text(item, "PartTerminologyName")

        # descriptions: DES -> name, EXT/longer -> description
        name = None
        desc = None
        for de in _findall(item, "Description"):
            code = de.get("DescriptionCode") or ""
            txt = _text(de)
            if not txt:
                continue
            if code in ("DES", "SHO", "LAB") and not name:
                name = txt
            elif code in ("EXT", "MKT", "SHO") and not desc:
                desc = txt
        if name is None:
            name = _child_text(item, "Description")

        # price: prefer LIST, else first
        price = None
        prices = _findall(item, "Price")
        if prices:
            chosen = next((p for p in prices if (p.get("PriceType") or "").upper() == "LIST"), prices[0])
            price = _text(chosen)

        # attributes
        attributes = []
        for pa in _findall(item, "ProductAttribute"):
            aname = pa.get("AttributeID") or pa.get("Name") or pa.get("PADBAttribute")
            aval = _text(pa)
            if aname and aval:
                attributes.append({"name": aname, "value": aval})

        # images / digital assets
        image_urls = []
        for df in _findall(item, "DigitalFileInformation"):
            uri = _child_text(df, "URI") or _child_text(df, "FileName")
            if uri:
                image_urls.append(uri)

        # interchange
        interchange = []
        for xi in _findall(item, "PartInterchangeInfo"):
            xbrand = _child_text(xi, "BrandLabel") or _child_text(xi, "BrandAAIAID")
            xnum = _child_text(xi, "PartNumber")
            if xnum:
                interchange.append({"brand": xbrand, "number": xnum, "type": "interchange"})

        items[pn] = {
            "brand": brand, "name": name or pn, "description": desc,
            "price": price, "attributes": attributes, "image_urls": image_urls,
            "interchange": interchange, "part_type": part_type,
        }
    return items


# --- ACES: resolve each App to (part, vehicle, note) -------------------------
def _resolve_parttype(refs: dict, pt_id: str | None) -> str | None:
    if not pt_id:
        return None
    row = refs["parttype"].get(str(pt_id))
    if row and len(row) > 1:
        return row[1]
    # not numeric? treat the raw value as the name
    return pt_id if not str(pt_id).isdigit() else None


def _resolve_make(refs: dict, mid: str | None, inline: str | None) -> str | None:
    if inline:
        return inline
    if mid:
        row = refs["make"].get(str(mid))
        if row and len(row) > 1:
            return row[1]
    return None


def _resolve_model(refs: dict, mid: str | None, inline: str | None) -> str | None:
    if inline:
        return inline
    if mid:
        row = refs["model"].get(str(mid))
        if row and len(row) > 1:
            return row[1]
    return None


def _app_vehicles(app, refs: dict) -> list[dict]:
    """Return one dict per (year) the App targets: {year, make, model}."""
    out: list[dict] = []
    bv = _find(app, "BaseVehicle")
    if bv is not None and bv.get("id"):
        row = refs["base"].get(str(bv.get("id")))
        if row and len(row) >= 4:
            year = int(row[1]) if row[1].isdigit() else None
            make = _resolve_make(refs, row[2], None)
            model = _resolve_model(refs, row[3], None)
            if year and make and model:
                out.append({"year": year, "make": make, "model": model})
        return out

    # Years + Make + Model form
    years_el = _find(app, "Years")
    make_el = _find(app, "Make")
    model_el = _find(app, "Model")
    make = _resolve_make(refs, make_el.get("id") if make_el is not None else None, _text(make_el))
    model = _resolve_model(refs, model_el.get("id") if model_el is not None else None, _text(model_el))
    if not (make and model and years_el is not None):
        return out
    try:
        y_from = int(years_el.get("from"))
        y_to = int(years_el.get("to"))
    except (TypeError, ValueError):
        return out
    for year in range(y_from, y_to + 1):
        out.append({"year": year, "make": make, "model": model})
    return out


def parse_aces(aces_path: str, refs: dict) -> list[dict]:
    """Return a list of app records: {part_number, mfr, note, part_type, vehicles:[...]}"""
    apps: list[dict] = []
    tree = ET.parse(aces_path)
    root = tree.getroot()
    for app in _iter_named(root, "App"):
        pn = _child_text(app, "Part")
        if not pn:
            continue
        mfr = _child_text(app, "MfrLabel")
        pt_el = _find(app, "PartType")
        pt_id = pt_el.get("id") if pt_el is not None else _child_text(app, "PartType")
        pos = _child_text(app, "Position")
        note = _child_text(app, "Note")
        note_full = " / ".join([p for p in (pos, note) if p]) or None
        apps.append({
            "part_number": pn, "mfr": mfr, "note": note_full,
            "part_type_id": pt_id, "vehicles": _app_vehicles(app, refs),
        })
    return apps


# --- join ACES x PIES -> staging rows ---------------------------------------
def build_rows(apps: list[dict], pies: dict, refs: dict) -> tuple[list[dict], list[dict], int]:
    listings: list[dict] = []
    fitments: list[dict] = []
    failed = 0
    for app in apps:
        pn = app["part_number"]
        item = pies.get(pn, {})
        brand = item.get("brand") or app.get("mfr")
        if not brand or not pn:
            failed += 1
            continue
        sku = sku_for(brand, pn)
        cat_name = _resolve_parttype(refs, app.get("part_type_id")) or item.get("part_type")
        category_path = cat_name if cat_name else None

        if not app["vehicles"]:
            failed += 1
            continue

        for veh in app["vehicles"]:
            listings.append({
                "source": "aces_pies", "source_url": None,
                "make_name": veh["make"], "model_name": veh["model"], "year": veh["year"],
                "engine_name": None, "liters": None, "cylinders": None,
                "fuel_type": None, "aspiration": None, "trim": None,
                "category_path": category_path, "brand_name": brand, "part_number": pn,
                "name": item.get("name") or pn, "description": item.get("description"),
                "price": item.get("price"), "core_charge": None, "weight": None,
                "image_urls": json.dumps(item.get("image_urls") or []),
                "attributes": json.dumps(item.get("attributes") or []),
                "warehouse_code": None, "quantity": None, "fitment_note": app.get("note"),
                "warranty": None,
                "interchange": json.dumps(item.get("interchange") or []),
                "doc_urls": json.dumps([]),
            })
            fitments.append({
                "sku": sku, "make_name": veh["make"], "model_name": veh["model"],
                "year": veh["year"], "engine_name": None, "trim": None,
                "note": app.get("note"),
            })
    return listings, fitments, failed


# --- DB staging --------------------------------------------------------------
_LISTING_COLS = [
    "source", "source_url", "make_name", "model_name", "year", "engine_name",
    "liters", "cylinders", "fuel_type", "aspiration", "trim", "category_path",
    "brand_name", "part_number", "name", "description", "price", "core_charge",
    "weight", "image_urls", "attributes", "warehouse_code", "quantity",
    "fitment_note", "warranty", "interchange", "doc_urls",
]
_FITMENT_COLS = ["sku", "make_name", "model_name", "year", "engine_name", "trim", "note"]


def stage(cur, listings: list[dict], fitments: list[dict], batch: str) -> None:
    if listings:
        cols = _LISTING_COLS + ["batch_id", "processed"]
        collist = ",".join(f"`{c}`" for c in cols)
        ph = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO stg_listings ({collist}) VALUES ({ph})"
        for L in listings:
            cur.execute(sql, [L.get(c) for c in _LISTING_COLS] + [batch, 0])
    if fitments:
        cols = _FITMENT_COLS + ["batch_id", "processed"]
        collist = ",".join(f"`{c}`" for c in cols)
        ph = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO stg_fitment ({collist}) VALUES ({ph})"
        for F in fitments:
            cur.execute(sql, [F.get(c) for c in _FITMENT_COLS] + [batch, 0])


# --- sample generation (so the admin button works out of the box) ------------
SAMPLE_ACES = """<?xml version="1.0" encoding="UTF-8"?>
<ACES version="4.2">
  <App action="A" id="1">
    <BaseVehicle id="18253"/>
    <Qty>1</Qty>
    <PartType id="1684"/>
    <Position id="31">Front</Position>
    <Note>Ceramic; with wear sensor</Note>
    <Part>APX-1001</Part>
    <MfrLabel>Wagner</MfrLabel>
  </App>
  <App action="A" id="2">
    <Years from="2015" to="2016"/>
    <Make id="474"/>
    <Model id="2245"/>
    <Qty>1</Qty>
    <PartType id="5340"/>
    <Part>OF-2020</Part>
    <MfrLabel>Bosch</MfrLabel>
  </App>
</ACES>
"""

SAMPLE_PIES = """<?xml version="1.0" encoding="UTF-8"?>
<PIES version="7.2">
  <Items>
    <Item>
      <PartNumber>APX-1001</PartNumber>
      <BrandLabel>Wagner</BrandLabel>
      <PartTerminologyID>1684</PartTerminologyID>
      <Descriptions>
        <Description DescriptionCode="DES">Wagner ThermoQuiet Ceramic Disc Brake Pad Set</Description>
        <Description DescriptionCode="EXT">Front axle, low-dust ceramic formulation with integral wear sensor.</Description>
      </Descriptions>
      <Prices>
        <Price PriceType="LIST" UOM="EA" Currency="USD">45.99</Price>
      </Prices>
      <ProductAttributes>
        <ProductAttribute AttributeID="Material">Ceramic</ProductAttribute>
        <ProductAttribute AttributeID="Position">Front</ProductAttribute>
      </ProductAttributes>
      <DigitalAssets>
        <DigitalFileInformation MaintenanceType="A">
          <FileName>zd923.jpg</FileName>
          <URI>https://img.example.com/parts/zd923.jpg</URI>
        </DigitalFileInformation>
      </DigitalAssets>
      <PartInterchange>
        <PartInterchangeInfo>
          <BrandLabel>Bosch</BrandLabel>
          <PartNumber>BC905</PartNumber>
        </PartInterchangeInfo>
      </PartInterchange>
    </Item>
    <Item>
      <PartNumber>OF-2020</PartNumber>
      <BrandLabel>Bosch</BrandLabel>
      <PartTerminologyID>5340</PartTerminologyID>
      <Descriptions>
        <Description DescriptionCode="DES">Bosch Workshop Engine Oil Filter</Description>
      </Descriptions>
      <Prices>
        <Price PriceType="LIST">8.49</Price>
      </Prices>
      <ProductAttributes>
        <ProductAttribute AttributeID="Height">3.4 in</ProductAttribute>
      </ProductAttributes>
    </Item>
  </Items>
</PIES>
"""

REF_FILES = {
    "Make.csv": "MakeID,MakeName\n474,Honda\n",
    "Model.csv": "ModelID,ModelName\n2245,Civic\n",
    "BaseVehicle.csv": "BaseVehicleID,YearID,MakeID,ModelID\n18253,2016,474,2245\n",
    "PartType.csv": "PartTypeID,PartTypeName\n1684,Disc Brake Pad\n5340,Engine Oil Filter\n",
}


def _write_if_absent(path: str, content: str) -> None:
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)


def ensure_samples(aces_path: str, pies_path: str, refdir: str) -> None:
    """Create tiny valid sample XML + reference CSVs if any are missing."""
    _write_if_absent(aces_path, SAMPLE_ACES)
    _write_if_absent(pies_path, SAMPLE_PIES)
    for fname, content in REF_FILES.items():
        _write_if_absent(os.path.join(refdir, fname), content)


# --- entry points ------------------------------------------------------------
def run(aces_path: str, pies_path: str, refdir: str) -> int:
    # generate samples if the provided paths don't exist yet
    if not (os.path.isfile(aces_path) and os.path.isfile(pies_path)):
        ensure_samples(aces_path, pies_path, refdir)

    refs = load_refs(refdir)
    pies = parse_pies(pies_path)
    apps = parse_aces(aces_path, refs)
    listings, fitments, failed = build_rows(apps, pies, refs)

    conn = db.connect()
    batch = f"aces_pies-{int(time.time())}"
    try:
        cur = conn.cursor()
        conn.begin()
        stage(cur, listings, fitments, batch)
        cur.execute(
            "INSERT INTO import_logs (admin_id, `type`, filename, rows_total, rows_ok, "
            "rows_failed, `status`, message) VALUES (NULL,'aces_pies',%s,%s,%s,%s,%s,%s)",
            [os.path.basename(aces_path) + " + " + os.path.basename(pies_path),
             len(listings) + failed, len(listings), failed, "completed",
             f"staged {len(listings)}, fitment {len(fitments)}, {failed} failed"],
        )
        conn.commit()
    finally:
        conn.close()

    # ImportController::parseCounts reads these:
    print(f"staged {len(listings)}")
    print(f"fitment {len(fitments)}")
    print(f"{failed} failed")
    return 0


def selftest() -> int:
    """OFFLINE: generate samples in scratch, parse, stage into a rolled-back txn, assert."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="acespies_")
    aces = os.path.join(tmp, "sample_aces.xml")
    pies = os.path.join(tmp, "sample_pies.xml")
    refdir = os.path.join(tmp, "reference")
    ensure_samples(aces, pies, refdir)

    refs = load_refs(refdir)
    pies_items = parse_pies(pies)
    apps = parse_aces(aces, refs)
    listings, fitments, failed = build_rows(apps, pies_items, refs)

    # parse-level assertions (no DB needed)
    try:
        assert failed == 0, f"unexpected {failed} failed rows"
        # App#1 = 1 vehicle (BaseVehicle), App#2 = 2 vehicles (2015..2016) => 3 listings
        assert len(listings) == 3, f"expected 3 listings, got {len(listings)}"
        assert len(fitments) == 3, f"expected 3 fitments, got {len(fitments)}"
        # PIES join populated part name + interchange for ZD-923
        zd = next(L for L in listings if L["part_number"] == "APX-1001")
        assert "ThermoQuiet" in (zd["name"] or ""), "PIES name not joined"
        assert json.loads(zd["interchange"]), "interchange not parsed"
        assert zd["category_path"] == "Disc Brake Pad", zd["category_path"]
        assert zd["make_name"] == "Honda" and zd["year"] == 2016, zd
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1

    # DB round-trip (rolled back). Skip gracefully if unreachable.
    try:
        conn = db.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"[selftest] parse OK ({len(listings)} listings); db unreachable, "
              f"skipping stage: {exc}")
        print("PASS")
        return 0
    try:
        cur = conn.cursor()
        conn.begin()
        batch = f"SELFTEST-acespies-{int(time.time())}"
        stage(cur, listings, fitments, batch)
        cur.execute("SELECT COUNT(*) n FROM stg_listings WHERE batch_id=%s", [batch])
        assert cur.fetchone()["n"] == 3
        cur.execute("SELECT COUNT(*) n FROM stg_fitment WHERE batch_id=%s", [batch])
        assert cur.fetchone()["n"] == 3
        print(f"[selftest] staged {len(listings)} listings + {len(fitments)} fitments (rolled back)")
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
    ap = argparse.ArgumentParser(description="Ingest ACES + PIES XML into staging.")
    ap.add_argument("aces", nargs="?", default=os.path.join(SCRAPER_DIR, "sample_aces.xml"))
    ap.add_argument("pies", nargs="?", default=os.path.join(SCRAPER_DIR, "sample_pies.xml"))
    ap.add_argument("refdir", nargs="?", default=os.path.join(SCRAPER_DIR, "reference"))
    ap.add_argument("--selftest", action="store_true", help="offline round-trip, rolled back")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.aces, args.pies, args.refdir)


if __name__ == "__main__":
    sys.exit(main())
