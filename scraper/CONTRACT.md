# RockAuto Scraper — Build Contract (verified 2026-07-08 via live recon)

All council modules MUST conform to the signatures and data shapes below so the
pieces integrate without rework. Read `scraper/config.py` and `scraper/db.py`
first — they already exist and are the source of truth for scope + DB access.

## 0. Verified RockAuto protocol (ground truth — do NOT re-guess)

Catalog tree levels (nodetype):
`make_letter → make → year → model → carcode → category → group(parttype) → listings`

- **Makes**: plain GET `/en/catalog/<slug>` (e.g. `/en/catalog/honda`). Full make
  list is embedded in the initial `/en/catalog/` HTML (~329 nodes).
- **Deeper nodes are URL-addressable**, e.g.
  `/en/catalog/honda,2015,accord,2.4l+l4,3309958` where `3309958` is the **carcode**
  (a specific engine/config; 2015 Accord: 2.0L=3309957, 2.4L=3309958, 3.5L V6=3309959).
- **Lazy children load via POST** to `CATALOG_API` (`/catalog/catalogapi.php`):
  - body: `func=tab_fetch&payload=<urlencoded JSON>&api_json_request=1&sctchecked=1&scbeenloaded=false&curCartGroupID=`
  - the `payload` JSON wraps the target node's `jsn` object + `"max_group_index": <int>`.
  - response: JSON `{"html_fill_sections": {"section-...[catalog]": "<HTML>"}}`.
- **Node encoding in HTML**: each node is
  `<div class="ranavnode" id="nav[GIP]">` containing
  `<input id="jsn[GIP]" value="{...JSON...}">`. The jsn JSON carries:
  `groupindex, nodetype, make, year, model, carcode, engine, idepth,
  parentgroupindex, jsdata.markets[], href`.
- **`_nck` nonce**: hidden `<input name="_nck" value="...">` (~364 chars). Required
  on catalogapi POSTs; harvest per session, refresh when a response rejects it.
- **Session cookies** (from GET): `PHPSESSID, saved_server, mkt_US/CA/MX, year_2006`.
  Send header `x-requested-with: XMLHttpRequest` + `origin`/`referer` on POSTs.
- **ANTI-BOT (confirmed)**: jumping straight to a deep leaf → 302 to
  `/captcha/?redirecturl=...` (securimage CAPTCHA). Mitigation rules:
  1. **Warm the session**: walk the tree progressively (make→year→…), don't teleport to leaves.
  2. **Detect** `/captcha/` in the final URL OR a `img.captchaimage` / `securimage` in the body → treat as a soft ban.
  3. On CAPTCHA/ban: quarantine that proxy, `captcha_backoff_s`, rotate IP+UA, re-enqueue the node (do NOT lose it).
  4. Free proxies can't solve CAPTCHAs — the design leans on rotation + politeness, not solving.

## 1. File ownership (each agent owns distinct files — no overlap)

| Module | File | Owner |
|---|---|---|
| Proxy pool | `scraper/proxy_manager.py` | Agent B |
| HTTP client | `scraper/ra_client.py` | Agent A |
| Parsers | `scraper/parsers.py` | Agent C |
| Frontier queue | `scraper/frontier.py` | Agent D |
| Crawl orchestrator | `scraper/crawl.py` | Agent D |
| Loader (staging→canonical) | `bin/loader.py` | Agent E |
| vPIC importer | `bin/import_vpic.py` | Agent E |
| ACES/PIES importer | `bin/ingest_acespies.py` | Agent E |

Already provided: `scraper/config.py`, `scraper/db.py`, `requirements.txt`.

## 2. Data shapes (the ONE canonical dict — matches `stg_listings` columns)

`parsers.parse_listings(...)` yields dicts with EXACTLY these keys (None if absent):

```python
Listing = {
  "source": "rockauto",
  "source_url": str,
  "make_name": str, "model_name": str, "year": int,
  "engine_name": str|None, "liters": float|None, "cylinders": int|None,
  "fuel_type": str|None, "aspiration": str|None, "trim": str|None,
  "category_path": str,          # "Brake & Wheel Hub>Brake Pad"
  "brand_name": str,             # e.g. "Bosch"
  "part_number": str,            # manufacturer part number
  "name": str, "description": str|None,
  "price": float|None, "core_charge": float|None, "weight": float|None,
  "image_urls": list[str],       # -> JSON
  "attributes": list[dict],      # [{"name":..,"value":..}] -> JSON
  "warehouse_code": str|None, "quantity": int|None,
  "fitment_note": str|None,
  "warranty": str|None,          # -> stg_listings.warranty
  "interchange": list[dict]|None,# [{"brand":..,"number":..,"type":"interchange"}] -> JSON
  "doc_urls": list[dict]|None,   # [{"type":"info","label":..,"url":..}] -> JSON
}
```

A `TreeNode` (from `parsers.parse_nav`) is a dict:
```python
{"gip": str, "nodetype": str, "make": str|None, "year": int|None,
 "model": str|None, "carcode": str|None, "engine": str|None,
 "href": str|None, "jsn": dict, "markets": list[str]}
```

## 3. Required module interfaces

### `scraper/proxy_manager.py` (Agent B)
```python
class ProxyManager:
    def __init__(self, cfg=config.PROXY): ...
    def get(self) -> str | None:            # "http://ip:port" or None (=direct)
    def report_bad(self, proxy: str) -> None
    def report_ok(self, proxy: str) -> None
    def quarantine(self, proxy: str, seconds: int) -> None
    def refill(self) -> int                  # fetch+health-check, return healthy count
    def healthy_count(self) -> int
```
Fetch from `cfg["sources"]`, dedupe, health-check concurrently against
`cfg["health_check_url"]` (HTTP 200 within `health_timeout_s`), persist pool to
`cfg["pool_cache"]`. Robust to dead sources.

### `scraper/ra_client.py` (Agent A)
```python
class Blocked(Exception): ...      # raised on CAPTCHA/ban
class RAClient:
    def __init__(self, proxies: ProxyManager|None = None): ...
    def new_session(self) -> None                       # fresh cookies+UA+proxy, harvests _nck
    def get(self, url: str) -> str                      # returns HTML; raises Blocked on /captcha
    def fetch_children(self, node: dict, max_group_index: int = 4) -> str
        # POST func=tab_fetch with node['jsn']+_nck; returns the catalog HTML fragment; raises Blocked
    def rotate(self) -> None                            # quarantine current proxy, new_session()
```
Retries with backoff up to `RATE["max_attempts"]`; rotates proxy on
`Blocked`/timeout; refreshes `_nck` when stale.

### `scraper/parsers.py` (Agent C)
```python
def parse_nav(html: str) -> list[dict]        # -> [TreeNode]; also extracts _nck if present
def extract_nck(html: str) -> str | None
def parse_listings(html: str, ctx: dict) -> list[dict]
    # ctx carries make/model/year/engine/carcode/category_path for the leaf.
    # -> [Listing]. Parse each part row: brand, part_number, name, price,
    #    core_charge, images, attributes, warranty, interchange, docs, fitment_note.
def is_captcha(html: str, final_url: str) -> bool
```
Use lxml/BeautifulSoup. Be defensive: RockAuto row classes vary
(`listing-final-manufacturer`, `listing-final-partnumber`, `span-link-out-desc`,
`listing-price`, `.ra-btn`); fall back to text/regex for `$\d+\.\d{2}` prices and
`data-*`/`href` for images and interchange. Never throw on a single bad row —
skip and continue.

### `scraper/frontier.py` (Agent D)
```python
def enqueue(conn, node_type, node_key, href=None, payload=None) -> None   # idempotent (uq_frontier_node)
def claim_batch(conn, limit=50) -> list[dict]     # flip pending->in_flight atomically, return rows
def complete(conn, id) -> None
def fail(conn, id) -> None                         # attempts++, ->pending if <max else 'failed'
def counts(conn) -> dict                           # {'pending':..,'in_flight':..,'done':..,'failed':..}
```
`crawl_frontier` columns: `id, node_type, node_key, href, status
(pending|in_flight|done|failed), attempts, batch_id, payload(JSON), updated_at`.
`payload` carries the node jsn + accumulated fitment context for full resumability.

### `scraper/crawl.py` (Agent D) — orchestrator, CLI entrypoint
`python scraper/crawl.py [--makes honda,toyota] [--limit N] [--reset]`
Loop: seed frontier from SCOPE makes → BFS expand each node
(make→year→model→carcode→category→group), staging `Listing` rows into
`stg_listings` (+ `stg_fitment`) at leaves. Fully resumable (re-run continues).
Print progress: nodes done, listings staged, captchas hit, healthy proxies.
Respect `RATE`. On `Blocked`, `client.rotate()` + re-enqueue.

### `bin/loader.py` (Agent E) — staging → canonical, idempotent
`python bin/loader.py [--batch <id>] [--limit N]`
Drain `stg_listings WHERE processed=0` into canonical tables, then `stg_fitment`.
Upsert order + idempotency anchors (see schema.sql / scrape_schema.sql):
- `makes` (uq slug), `models` (uq make_id+slug), `engines` (uq name),
  `vehicles` (uq slug — deterministic), `brands` (uq slug), `categories` (uq slug, build tree from category_path).
- `parts` (uq **sku** — deterministic sku from brand+part_number), set
  brand_id/category_id/price/core_charge/weight/warranty/source_url.
- `part_images`, `part_attributes`, `part_interchange` (uq part_id+number_norm),
  `part_documents`, `part_fitment` (uq part_id+vehicle_id), `inventory` (uq part_id+warehouse_code).
Mark rows `processed=1`. Use `INSERT ... ON DUPLICATE KEY UPDATE`. Transaction per
batch. Write an `import_logs` row (type='rockauto') with counts. MUST NOT break
existing `source='generated'` rows.
- `slug`/`sku` helpers: reuse the same slugify rule as the PHP side (lowercase,
  spaces/'+'→'-', strip non `[a-z0-9-]`). sku = `slugify(brand)-slugify(part_number)`.

### `bin/import_vpic.py` + `bin/ingest_acespies.py` (Agent E)
These are referenced by `app/Controllers/Admin/ImportController.php`:
- `import_vpic.py --makes "Honda,Toyota" --from 2020 --to 2021` → pull make/model/
  year from the free NHTSA vPIC API (`https://vpic.nhtsa.dot.gov/api/`) into
  makes/models/vehicles (canonical). Print `staged N` / `vehicles N`.
- `ingest_acespies.py <aces.xml> <pies.xml> <refdir>` → parse ACES fitment + PIES
  item XML into `stg_listings`/`stg_fitment` (source='aces_pies'). Print counts.
Keep stdout parseable by `ImportController::parseCounts` (regex `staged \d+`,
`vehicles \d+`, `fitment \d+`, `\d+ failed`).

## 4. Non-negotiables
- Python 3.13, stdlib + requirements.txt only. `from __future__ import annotations`.
- Idempotent + resumable everywhere (safe to Ctrl-C and re-run).
- Never lose a node on error — re-enqueue.
- No hard-coded secrets; DB via `scraper/db.py`, scope via `scraper/config.py`.
- Windows-friendly (paths, no os-specific shell calls).
