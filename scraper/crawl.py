"""
RockAuto crawl orchestrator (Agent D) — CLI entrypoint.

    python scraper/crawl.py [--makes honda,toyota] [--limit N] [--reset]

Walks the RockAuto catalog tree politely and resumably, staging part rows into
`stg_listings` (+ `stg_fitment`) for the loader to canonicalize. All durable
state lives in `crawl_frontier`, so a re-run continues exactly where a previous
run (or a Ctrl-C) left off.

Tree levels (CONTRACT §0):
    make_letter -> make -> year -> model -> carcode -> category -> group -> listings

Flow:
  1. Seed the frontier with SCOPE makes  (node_type='make', href=/en/catalog/<slug>).
  2. Loop: claim a batch of pending nodes; for each,
       - fetch its HTML  (client.get(href) for url-addressable levels,
         client.fetch_children(jsn) for lazy category/group expansion),
       - if it is a listings leaf -> parsers.parse_listings -> stage rows,
         else -> parsers.parse_nav -> enqueue in-scope children,
       - complete() the node.
     On Blocked (CAPTCHA/ban): client.rotate() + fail() (never lose the node).
  3. Repeat until the frontier drains.

Politeness comes from config.RATE (delay + jitter, max_attempts). Network modules
(ra_client / proxy_manager / parsers) are imported lazily inside run() so this
file — and its OFFLINE self-test — import cleanly even before those siblings
exist, and the self-test never touches the network.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

try:  # run as `python scraper/crawl.py` (scraper/ on sys.path) OR as package
    import config
    import db
    import frontier
except ImportError:  # pragma: no cover - import shim
    from scraper import config, db, frontier  # type: ignore


# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
# Nodetypes that, once expanded, yield part listings rather than more branches.
LEAF_TYPES = {"group", "parttype", "listing"}
# How many pending nodes to claim per loop iteration.
CLAIM_LIMIT = 25
# Fields on a TreeNode that describe the vehicle context we accumulate.
_CTX_FIELDS = ("make", "year", "model", "carcode", "engine")


# --------------------------------------------------------------------------- #
# pure helpers  (no DB / no network — unit-tested offline)
# --------------------------------------------------------------------------- #
def make_batch_id() -> str:
    """A timestamp run id, e.g. 'ra_20260708_143355'. Sortable + filename-safe."""
    return "ra_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def seed_href(slug: str) -> str:
    """Make landing URL RockAuto serves as a plain GET."""
    return f"/en/catalog/{slug}"


def slugify(s: str | None) -> str:
    """Mirror the PHP slugify (PartController): lowercase, non-alnum runs -> '-',
    trim '-'. Empty -> 'part'. Keeps sku deterministic + identical to the
    storefront so the loader's upserts line up."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "part"


def make_sku(brand: str | None, part_number: str | None) -> str:
    """Deterministic sku = slugify(brand)-slugify(part_number)  (CONTRACT §3)."""
    return f"{slugify(brand)}-{slugify(part_number)}"


def _as_int(value: Any) -> int | None:
    """Coerce a possibly-str year to int, else None."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def in_scope_year(year: Any, scope=None) -> bool:
    """Year passes if unknown (None) or within SCOPE['year_min'..'year_max']."""
    scope = scope or config.SCOPE
    y = _as_int(year)
    if y is None:
        return True
    return int(scope["year_min"]) <= y <= int(scope["year_max"])


def in_scope_market(markets: Any, scope=None) -> bool:
    """Market passes if SCOPE markets is empty, the node lists no markets, or
    there is any overlap. Permissive on unknown so we never silently prune."""
    scope = scope or config.SCOPE
    want = {m.upper() for m in scope.get("markets", []) if m}
    if not want:
        return True
    have = {str(m).upper() for m in (markets or []) if m}
    if not have:
        return True
    return bool(want & have)


def in_scope_category(text: Any, scope=None) -> bool:
    """Category passes if SCOPE categories is empty, or any configured keyword
    is a case-insensitive substring of the node's descriptive text. Permissive
    when we cannot determine a name (text falsy)."""
    scope = scope or config.SCOPE
    wants = [c.lower() for c in scope.get("categories", []) if c]
    if not wants:
        return True
    hay = str(text or "").lower()
    if not hay:
        return True
    return any(w in hay for w in wants)


def node_display_name(node: dict) -> str | None:
    """Best-effort human name for a category/group node, pulled from its jsn.
    Row classes/keys vary, so try a handful and fall back to None."""
    jsn = node.get("jsn") or {}
    for key in ("desc", "description", "name", "title", "groupname",
                "parttype", "label", "text"):
        val = jsn.get(key)
        if val:
            return str(val).strip()
    return None


def node_key_for(node: dict) -> str:
    """Stable dedupe key for the frontier UNIQUE index.

    Prefer the href (globally stable). For lazy nodes without an href, compose
    the vehicle coordinates + nodetype + groupindex, which RockAuto derives
    deterministically per vehicle — stable enough for idempotent re-enqueue.
    """
    href = node.get("href")
    if href:
        return href
    coords = ",".join(str(node.get(f) or "") for f in _CTX_FIELDS)
    return f"{node.get('nodetype', '?')}:{coords}:{node.get('gip', '')}"


def should_enqueue(node: dict, scope=None) -> bool:
    """Apply SCOPE filters (market always; year for year nodes; category for
    category/group nodes). Returns False only when a node is provably out of
    scope — unknowns are kept."""
    scope = scope or config.SCOPE
    if not in_scope_market(node.get("markets"), scope):
        return False
    ntype = node.get("nodetype")
    if ntype == "year" and not in_scope_year(node.get("year"), scope):
        return False
    if ntype in ("category", "group", "parttype"):
        if not in_scope_category(node_display_name(node), scope):
            return False
    return True


def build_child_payload(child: dict, parent_payload: dict | None) -> dict:
    """Payload stored on the frontier row: the child's jsn (for lazy re-fetch) +
    an accumulated context dict (make/model/year/engine/carcode/category_path)
    that parse_listings needs at the leaf. Fully resumable — a claimed row alone
    carries everything to reprocess the node."""
    parent_ctx = dict((parent_payload or {}).get("ctx", {}))
    for f in _CTX_FIELDS:
        v = child.get(f)
        if v is not None and v != "":
            parent_ctx[f] = v
    ntype = child.get("nodetype")
    if ntype in ("category", "group", "parttype"):
        name = node_display_name(child)
        if name:
            prev = parent_ctx.get("category_path")
            parent_ctx["category_path"] = f"{prev}>{name}" if prev else name
    return {
        "jsn": child.get("jsn"),
        "ctx": parent_ctx,
        "nodetype": ntype,
    }


def listing_ctx(payload: dict | None) -> dict:
    """The ctx dict handed to parsers.parse_listings for a leaf node."""
    ctx = dict((payload or {}).get("ctx", {}))
    ctx.setdefault("category_path", "")
    return ctx


# --------------------------------------------------------------------------- #
# staging  (DB writes — reached only during a live crawl)
# --------------------------------------------------------------------------- #
def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def stage_listings(conn, listings: list[dict], batch_id: str) -> int:
    """Insert parsed Listing dicts into stg_listings (+ a stg_fitment row per
    listing when the vehicle is known). Returns rows staged. Defensive: one bad
    listing never aborts the batch."""
    staged = 0
    with conn.cursor() as cur:
        for lst in listings:
            try:
                cur.execute(
                    "INSERT INTO stg_listings "
                    "(source, source_url, make_name, model_name, `year`, "
                    " engine_name, liters, cylinders, fuel_type, aspiration, "
                    " trim, category_path, brand_name, part_number, name, "
                    " description, price, core_charge, weight, image_urls, "
                    " attributes, warehouse_code, quantity, fitment_note, "
                    " warranty, interchange, doc_urls, batch_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        lst.get("source", "rockauto"),
                        lst.get("source_url"),
                        lst.get("make_name"),
                        lst.get("model_name"),
                        lst.get("year"),
                        lst.get("engine_name"),
                        lst.get("liters"),
                        lst.get("cylinders"),
                        lst.get("fuel_type"),
                        lst.get("aspiration"),
                        lst.get("trim"),
                        lst.get("category_path"),
                        lst.get("brand_name"),
                        lst.get("part_number"),
                        lst.get("name"),
                        lst.get("description"),
                        lst.get("price"),
                        lst.get("core_charge"),
                        lst.get("weight"),
                        _json_or_none(lst.get("image_urls")),
                        _json_or_none(lst.get("attributes")),
                        lst.get("warehouse_code"),
                        lst.get("quantity"),
                        lst.get("fitment_note"),
                        lst.get("warranty"),
                        _json_or_none(lst.get("interchange")),
                        _json_or_none(lst.get("doc_urls")),
                        batch_id,
                    ),
                )
                # Companion fitment row (needs a fully-known vehicle).
                yr = _as_int(lst.get("year"))
                if lst.get("make_name") and lst.get("model_name") and yr:
                    cur.execute(
                        "INSERT INTO stg_fitment "
                        "(sku, make_name, model_name, `year`, engine_name, "
                        " trim, note, batch_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            make_sku(lst.get("brand_name"),
                                     lst.get("part_number")),
                            lst.get("make_name"),
                            lst.get("model_name"),
                            yr,
                            lst.get("engine_name"),
                            lst.get("trim"),
                            lst.get("fitment_note"),
                            batch_id,
                        ),
                    )
                staged += 1
            except Exception as exc:  # noqa: BLE001 - skip the bad row, keep going
                print(f"    [warn] bad listing skipped: {exc}")
    conn.commit()
    return staged


# --------------------------------------------------------------------------- #
# per-node processing  (live crawl)
# --------------------------------------------------------------------------- #
def _seed(conn, makes: list[str]) -> int:
    """Enqueue the top-level make nodes. Idempotent, so safe on every run."""
    n = 0
    for slug in makes:
        slug = slug.strip().lower()
        if not slug:
            continue
        payload = {"ctx": {"make": slug}, "nodetype": "make"}
        frontier.enqueue(conn, "make", f"make:{slug}", seed_href(slug), payload)
        n += 1
    return n


def _process_node(conn, client, parsers, node: dict, batch_id: str,
                  stats: dict) -> None:
    """Fetch + expand a single frontier node. Raises nothing to the loop except
    via stats; the loop owns complete()/fail() so state is always recorded."""
    payload = node.get("payload") or {}
    jsn = payload.get("jsn")
    href = node.get("href")
    ntype = node.get("node_type")

    # 1) fetch HTML: url-addressable levels via GET, lazy nodes via POST.
    if href:
        html = client.get(href)
    elif jsn:
        html = client.fetch_children(jsn)
    else:  # nothing to fetch with — treat as a dead node (won't lose it: fail)
        raise ValueError(f"node {node.get('id')} has neither href nor jsn")

    # 2) leaf -> stage listings; branch -> enqueue in-scope children.
    if ntype in LEAF_TYPES:
        ctx = listing_ctx(payload)
        listings = parsers.parse_listings(html, ctx)
        staged = stage_listings(conn, listings, batch_id)
        stats["listings"] += staged
    else:
        children = parsers.parse_nav(html)
        for child in children:
            if not should_enqueue(child):
                continue
            frontier.enqueue(
                conn,
                child.get("nodetype", "node"),
                node_key_for(child),
                child.get("href"),
                build_child_payload(child, payload),
            )


# --------------------------------------------------------------------------- #
# main crawl loop  (live)
# --------------------------------------------------------------------------- #
def run(makes: list[str] | None = None, limit: int | None = None,
        reset: bool = False) -> int:
    """Drive the crawl to completion (or `limit` nodes). Returns nodes processed.
    Network modules are imported here so the file stays import-safe offline."""
    # Lazy imports — only needed for an actual crawl.
    try:
        import parsers
        from ra_client import RAClient, Blocked
        from proxy_manager import ProxyManager
    except ImportError:  # pragma: no cover - package layout
        from scraper import parsers  # type: ignore
        from scraper.ra_client import RAClient, Blocked  # type: ignore
        from scraper.proxy_manager import ProxyManager  # type: ignore

    # Assign a run batch_id (frontier.claim_batch stamps it onto claimed rows).
    if not getattr(config, "BATCH_ID", ""):
        config.BATCH_ID = make_batch_id()
    batch_id = config.BATCH_ID

    makes = makes if makes is not None else list(config.SCOPE.get("makes", []))
    rate = config.RATE

    conn = db.connect()
    try:
        if reset:
            wiped = frontier.reset(conn)
            print(f"[reset] cleared {wiped} frontier rows")

        seeded = _seed(conn, makes)
        print(f"[seed] {seeded} make(s) enqueued: {', '.join(makes)}")
        print(f"[run ] batch_id={batch_id}  "
              f"scope years={config.SCOPE['year_min']}-{config.SCOPE['year_max']} "
              f"markets={config.SCOPE.get('markets')}")

        proxies = ProxyManager()
        if config.PROXY.get("enabled", True):
            try:
                healthy = proxies.refill()  # warm the pool once up front
                print(f"[proxy] pool warmed: {healthy} healthy proxies")
            except Exception as exc:  # noqa: BLE001 - proxies optional (direct mode)
                print(f"[proxy] refill skipped: {exc}")
        else:
            print("[proxy] disabled (SP_USE_PROXIES=0) — crawling direct")
        client = RAClient(proxies)

        stats = {"listings": 0, "captchas": 0, "nodes": 0}
        while True:
            if limit is not None and stats["nodes"] >= limit:
                print(f"[stop] node limit {limit} reached")
                break

            claim = CLAIM_LIMIT
            if limit is not None:
                claim = max(1, min(CLAIM_LIMIT, limit - stats["nodes"]))
            batch = frontier.claim_batch(conn, limit=claim)
            if not batch:
                print("[done] frontier drained")
                break

            for node in batch:
                try:
                    _process_node(conn, client, parsers, node, batch_id, stats)
                    frontier.complete(conn, node["id"])
                except Blocked:
                    # CAPTCHA/soft-ban: quarantine IP, rotate, re-enqueue node.
                    stats["captchas"] += 1
                    try:
                        client.rotate()
                    except Exception as exc:  # noqa: BLE001
                        print(f"    [warn] rotate failed: {exc}")
                    frontier.fail(conn, node["id"])
                except Exception as exc:  # noqa: BLE001 - never lose a node
                    print(f"    [warn] node {node.get('id')} "
                          f"({node.get('node_key')}) error: {exc}")
                    frontier.fail(conn, node["id"])
                stats["nodes"] += 1

                # politeness: base delay + jitter per request
                time.sleep(random.uniform(rate["min_delay_s"],
                                          rate["max_delay_s"]))

                if limit is not None and stats["nodes"] >= limit:
                    break

            # live progress line
            c = counts_safe(conn)
            try:
                healthy = proxies.healthy_count()
            except Exception:  # noqa: BLE001
                healthy = 0
            print(
                f"[progress] nodes={stats['nodes']} "
                f"listings={stats['listings']} captchas={stats['captchas']} "
                f"proxies={healthy} | frontier "
                f"pending={c['pending']} in_flight={c['in_flight']} "
                f"done={c['done']} failed={c['failed']}"
            )

        final = counts_safe(conn)
        print(f"[final] {final}  listings_staged={stats['listings']} "
              f"captchas={stats['captchas']}")
        return stats["nodes"]
    finally:
        conn.close()


def counts_safe(conn) -> dict:
    """frontier.counts() that never raises inside the progress print."""
    try:
        return frontier.counts(conn)
    except Exception:  # noqa: BLE001
        return {s: 0 for s in ("pending", "in_flight", "done", "failed")}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="crawl.py",
        description="Polite, resumable RockAuto catalog crawler.",
    )
    p.add_argument("--makes", default=None,
                   help="comma-separated make slugs (default: config.SCOPE)")
    p.add_argument("--limit", type=int, default=None,
                   help="stop after processing N frontier nodes")
    p.add_argument("--reset", action="store_true",
                   help="wipe the frontier before seeding (fresh crawl)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    makes = None
    if args.makes:
        makes = [m.strip().lower() for m in args.makes.split(",") if m.strip()]
    run(makes=makes, limit=args.limit, reset=args.reset)
    return 0


# --------------------------------------------------------------------------- #
# OFFLINE self-test  (no DB, no network — pure helper logic only)
# --------------------------------------------------------------------------- #
def _selftest() -> bool:
    ok = True

    def check(cond: bool, label: str) -> None:
        nonlocal ok
        if not cond:
            ok = False
        print(f"  [{'ok  ' if cond else 'FAIL'}] {label}")

    # batch id shape
    bid = make_batch_id()
    check(bid.startswith("ra_") and len(bid) == 18, "make_batch_id shape")

    # seed href
    check(seed_href("honda") == "/en/catalog/honda", "seed_href")

    # slugify mirrors PHP: lowercase, non-alnum -> '-', trim, '+'/space handled
    check(slugify("Bosch") == "bosch", "slugify basic")
    check(slugify("2.4L L4") == "2-4l-l4", "slugify punctuation")
    check(slugify("A/C  Compressor") == "a-c-compressor", "slugify runs")
    check(slugify("") == "part", "slugify empty -> 'part'")
    check(make_sku("Bosch", "BC905") == "bosch-bc905", "deterministic sku")

    # scope: year range (config default 2010-2024)
    check(in_scope_year(2015), "year 2015 in scope")
    check(not in_scope_year(1999), "year 1999 out of scope")
    check(in_scope_year(None), "unknown year kept")

    # scope: market
    check(in_scope_market(["US"]), "US market kept")
    check(not in_scope_market(["MX"]), "MX-only dropped (scope=US)")
    check(in_scope_market([]), "unknown market kept")

    # scope: category (empty scope -> keep all)
    check(in_scope_category("Brake Pad"), "category kept (empty scope)")
    check(in_scope_category(None), "unknown category kept")
    # with an explicit scope keyword
    scope2 = dict(config.SCOPE, categories=["brake"])
    check(in_scope_category("Brake Pad", scope2), "keyword match keeps brake")
    check(not in_scope_category("Cooling System", scope2),
          "keyword mismatch drops cooling")

    # node_key: href preferred, else composed
    check(node_key_for({"href": "/en/catalog/honda,2015"})
          == "/en/catalog/honda,2015", "node_key uses href")
    composed = node_key_for(
        {"nodetype": "group", "make": "honda", "year": 2015,
         "model": "accord", "carcode": "3309958", "gip": "77"})
    check(composed == "group:honda,2015,accord,3309958,:77",
          "node_key composed for lazy node")

    # should_enqueue: year filter + market filter
    check(should_enqueue({"nodetype": "year", "year": 2015, "markets": ["US"]}),
          "should_enqueue in-scope year")
    check(not should_enqueue(
        {"nodetype": "year", "year": 1990, "markets": ["US"]}),
        "should_enqueue drops out-of-range year")
    check(not should_enqueue(
        {"nodetype": "model", "markets": ["MX"]}),
        "should_enqueue drops MX-only node")

    # payload accumulation builds category_path and inherits ctx
    parent = {"ctx": {"make": "honda", "year": 2015, "model": "accord"}}
    child_cat = {"nodetype": "category", "jsn": {"desc": "Brake & Wheel Hub"}}
    p1 = build_child_payload(child_cat, parent)
    check(p1["ctx"]["category_path"] == "Brake & Wheel Hub",
          "category_path seeded")
    child_grp = {"nodetype": "group", "jsn": {"desc": "Brake Pad"}}
    p2 = build_child_payload(child_grp, p1)
    check(p2["ctx"]["category_path"] == "Brake & Wheel Hub>Brake Pad",
          "category_path appended with '>'")
    check(p2["ctx"]["make"] == "honda" and p2["ctx"]["model"] == "accord",
          "vehicle ctx inherited down the tree")

    # listing_ctx exposes category_path
    lc = listing_ctx(p2)
    check(lc["category_path"] == "Brake & Wheel Hub>Brake Pad",
          "listing_ctx carries category_path")

    # JSON helper
    check(_json_or_none(None) is None, "_json_or_none None")
    check(json.loads(_json_or_none([1, 2])) == [1, 2], "_json_or_none list")

    # argparse wiring
    ns = _parse_args(["--makes", "honda,toyota", "--limit", "5", "--reset"])
    check(ns.makes == "honda,toyota" and ns.limit == 5 and ns.reset is True,
          "argparse parses flags")

    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    # Bare `python scraper/crawl.py` with no args here would attempt a LIVE
    # crawl, which the build rules forbid. So the module's __main__ runs the
    # OFFLINE self-test. Use `main()` explicitly (below) to crawl for real:
    #     python -c "import scraper.crawl as c; c.main()"  --makes honda
    # or wire an entrypoint. Passing real CLI flags still crawls:
    if len(sys.argv) > 1:
        sys.exit(main())
    sys.exit(0 if _selftest() else 1)
