"""
crawl_jsonl.py — self-contained RockAuto crawler that writes NDJSON, for the
GitHub Actions distributed-IP fleet.

Why a separate crawler? GitHub-hosted runners are ephemeral and cannot reach the
user's LOCAL MariaDB. So each runner crawls a disjoint SHARD of makes on its own
fresh Azure IP, stages Listing rows to a newline-delimited JSON file, and uploads
it as an artifact. Locally, `bin/ingest_artifacts.py` loads those NDJSON files into
stg_listings, and the existing `bin/loader.py` canonicalizes them — unchanged.

    python scraper/crawl_jsonl.py --shard-index 3 --shard-total 20 --out shard3.ndjson

Design:
  * In-memory BFS frontier (no DB) — mirrors crawl.py's tree logic, reusing its
    pure helpers (scope filters, ctx accumulation, sku/slug) so behavior matches
    the DB crawler exactly.
  * Make discovery: fetch /en/catalog/ once, parse the make list, then keep only
    makes[shard_index :: shard_total] (disjoint slice per runner).
  * Politeness: config.RATE delays. Bounded by a per-job request BUDGET and a max
    runtime so each IP stays under RockAuto's per-IP threshold and the job fits
    inside GitHub's 6h ceiling.
  * Anti-bot: RAClient now OCR-solves securimage walls; if the IP is ultimately
    burned (repeated Blocked), the job aborts cleanly — the next scheduled run
    gets a brand-new IP and re-crawls the shard (the loader dedupes via uq sku).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone

# scraper/ on sys.path when run as a script; package import as a fallback.
try:
    import config
    import crawl as C
    import images
    import parsers
    from ra_client import RAClient, Blocked, BudgetExceeded, BUDGET
    from proxy_manager import ProxyManager
except ImportError:  # pragma: no cover - package layout
    from scraper import config, images, parsers  # type: ignore
    from scraper import crawl as C  # type: ignore
    from scraper.ra_client import RAClient, Blocked, BudgetExceeded, BUDGET  # type: ignore
    from scraper.proxy_manager import ProxyManager  # type: ignore

# Self-host thumbnails: the GitHub runner (unblocked) downloads each part photo so
# it lands on the user's own server (their IP is blocked from rockauto.com).
DOWNLOAD_IMAGES = os.getenv("SP_DOWNLOAD_IMAGES", "1") == "1"


def discover_makes(client) -> list[dict]:
    """Fetch the catalog root and return its make nodes (TreeNode dicts)."""
    html = client.get(config.CATALOG_ROOT)
    nodes = parsers.parse_nav(html)
    return [n for n in nodes if n.get("nodetype") == "make"]


def shard(items: list, index: int, total: int) -> list:
    """Disjoint slice for this runner: every `total`-th item from `index`."""
    if total <= 1:
        return items
    return items[index::total]


def _make_cap(budget: int, n_makes: int) -> int:
    """Per-make request ceiling: split the run budget across this shard's makes so
    DFS can't drill ONE make until the whole budget dies (which left every make
    past ~Honda undiscovered). Floor of 50 keeps a make reachable when budget is
    tiny."""
    return max(50, budget // max(1, n_makes))


def _seed_make_key(seed: dict) -> str:
    """The make slug of a seed node (matches --priority-makes entries)."""
    slug = (seed.get("href") or "").rstrip("/").split("/")[-1]
    if slug:
        return slug.lower()
    return str(((seed.get("payload") or {}).get("ctx") or {}).get("make") or "").lower()


def order_seeds(seeds: list[dict], priority: list[str] | None) -> list[dict]:
    """Reorder so priority makes drain FIRST. The frontier is a DFS stack popped
    from the right, so priority seeds go at the TAIL (reversed) to pop first, in
    the given order; non-priority makes stay at the head (the alpha tail)."""
    if not priority:
        return seeds
    rank = {m.strip().lower(): i for i, m in enumerate(priority) if m.strip()}
    pri = [s for s in seeds if _seed_make_key(s) in rank]
    rest = [s for s in seeds if _seed_make_key(s) not in rank]
    pri.sort(key=lambda s: rank[_seed_make_key(s)], reverse=True)  # rank 0 popped first
    return rest + pri


def make_seed_nodes(makes: list[dict]) -> list[dict]:
    """Turn make TreeNodes into BFS frontier nodes."""
    seeds = []
    for m in makes:
        slug = (m.get("href") or "").rstrip("/").split("/")[-1] or (m.get("make") or "").lower()
        href = m.get("href") or C.seed_href(slug)
        seeds.append({
            "node_type": "make",
            "href": href,
            "payload": {"ctx": {"make": m.get("make") or slug}, "nodetype": "make",
                        "jsn": m.get("jsn")},
        })
    return seeds


def _vehicle_record(child: dict) -> dict:
    """A carcode nav node -> one vehicle NDJSON row (no part fields). The model
    page's carcode jsn already carries make/model/year/engine/carcode/markets, so
    no further fetch is needed to know the vehicle (tree-only mode)."""
    mkts = child.get("markets")
    return {
        "source": "rockauto",
        "make_name": child.get("make"),
        "model_name": child.get("model"),
        "year": child.get("year"),          # parse_nav already coerced to int
        "engine_name": child.get("engine"),
        "carcode": child.get("carcode"),
        "market": (",".join(mkts) if mkts else None),
    }


def process(client, node: dict, tree_only: bool = False) -> tuple[list[dict], list[dict]]:
    """Fetch + expand one node. Returns (rows, child_nodes).

    Mirrors crawl._process_node but returns data instead of touching a DB. In
    tree_only mode a carcode child is NOT enqueued (no groupname/parttype/leaf
    fetch); instead one vehicle row is emitted for it — enumerating every vehicle
    by fetching only make+year+model pages.
    """
    payload = node.get("payload") or {}
    href = node.get("href")
    jsn = payload.get("jsn")
    ntype = node.get("node_type")

    # LEAF (parttype listings): prefer the compact catalogapi `navnode_fetch` fragment
    # (~half the bytes of the full page, same parts — verified). Needs the node jsn +
    # the vehicle's max_group_index (threaded down from the carcode page). Fall back to
    # the full page only when the fragment errors or yields nothing.
    if ntype in C.LEAF_TYPES:
        ctx = C.listing_ctx(payload)
        if href and not ctx.get("source_url"):
            ctx["source_url"] = (config.BASE.rstrip("/") + href
                                 if href.startswith("/") else href)
        mgi = payload.get("mgi")
        listings = []
        if jsn is not None and mgi is not None:
            try:
                frag = client.fetch_listings(jsn, int(mgi))
                listings = parsers.parse_listings(frag, ctx)
            except Exception:  # noqa: BLE001
                listings = []
        if not listings:   # fragment errored/empty -> confirm via full page
            html = client.get(href) if href else client.fetch_children(jsn)
            listings = parsers.parse_listings(html, ctx)
        return listings, []

    if href:
        html = client.get(href)
    elif jsn:
        html = client.fetch_children(jsn)
    else:
        raise ValueError("node has neither href nor jsn")

    # The vehicle/carcode page carries max_group_index; thread it to descendants so
    # their parttype leaves can use the compact fragment endpoint. Inherit when a
    # level (e.g. a nav fragment) doesn't restate it.
    m = re.search(r'id="max_group_index"[^>]*value="(\d+)"', html)
    mgi = m.group(1) if m else payload.get("mgi")

    children = parsers.parse_nav(html)
    rows, kids = [], []
    for child in children:
        if not C.should_enqueue(child):
            continue
        if tree_only and child.get("nodetype") == "carcode":
            rows.append(_vehicle_record(child))   # emit vehicle, don't descend
            continue
        cp = C.build_child_payload(child, payload)
        if mgi is not None:
            cp["mgi"] = mgi
        kids.append({
            "node_type": child.get("nodetype", "node"),
            "href": child.get("href"),
            "payload": cp,
        })
    return rows, kids


def _load_visited(path: str | None) -> set[str]:
    """Prior runs' crawled node keys (from the shared Actions cache) so this run
    SKIPS them and reaches new ground — the key to cumulative full-catalog coverage."""
    if not path or not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}
    except OSError:
        return set()


def run(shard_index: int, shard_total: int, out_path: str,
        makes_override: list[str] | None = None,
        budget: int = 400, max_seconds: int = 18000,
        visited_file: str | None = None, visited_out: str | None = None,
        tree_only: bool = False, priority: list[str] | None = None,
        only_makes: list[str] | None = None) -> dict:
    """Crawl this shard, writing Listing rows (or vehicle rows in tree_only) as
    NDJSON to `out_path`."""
    started = time.monotonic()
    stats = {"nodes": 0, "listings": 0, "captchas": 0, "blocked": 0, "requests": 0,
             "images": 0, "skipped": 0, "capped": 0}
    img_root = os.path.join(os.path.dirname(out_path) or ".", "images")

    if os.getenv("SP_USE_EVOMI") == "1":
        from proxy_manager import EvomiProxyManager
        proxies = EvomiProxyManager()
        print("[proxy] using Evomi residential gateway (rotating IPs)", flush=True)
        if os.getenv("SP_MAX_GB"):
            BUDGET.configure(os.getenv("SP_MAX_GB"),
                             os.getenv("SP_BUDGET_STATE", "coverage/bytes_spent.txt"))
    else:
        proxies = ProxyManager()
        if config.PROXY.get("enabled", True):
            try:
                proxies.refill()
            except Exception as exc:  # noqa: BLE001
                print(f"[proxy] refill skipped: {exc}", flush=True)
    client = RAClient(proxies)
    # RockAuto rate-limits per IP (~250 req). Evomi hands out unlimited fresh IPs
    # per connection, so proactively start a new session (new IP) every N requests
    # to stay under the ceiling instead of only reacting once blocked.
    rotate_every = int(os.getenv("SP_ROTATE_EVERY") or (80 if os.getenv("SP_USE_EVOMI") == "1" else 0))

    # Seed: explicit makes, else discover + shard the full catalog make list.
    # The byte cap can trip during this warm-up/discovery (e.g. a resumed shard
    # whose persisted counter already meets the cap) — catch it so the shard exits
    # cleanly (0 new work) instead of crashing the job.
    pre_exhausted = False
    try:
        if makes_override:
            seeds = make_seed_nodes([{"make": m, "href": C.seed_href(m)} for m in makes_override])
        else:
            all_makes = discover_makes(client)
            if only_makes:
                # Balanced plan: keep only this shard's assigned makes, matched by
                # name against RockAuto's OWN discovered nodes (so we reuse their
                # exact hrefs — no name->URL reconstruction to get wrong).
                want = {m.strip().lower() for m in only_makes}
                mine = [n for n in all_makes if (n.get("make") or "").strip().lower() in want]
                print(f"[plan] {len(mine)}/{len(all_makes)} makes for this shard", flush=True)
            else:
                mine = shard(all_makes, shard_index, shard_total)
                print(f"[shard] {shard_index}/{shard_total}: {len(mine)}/{len(all_makes)} makes", flush=True)
            seeds = make_seed_nodes(mine)
    except BudgetExceeded:
        print("[stop] byte budget already reached before crawling (resumed at/over cap) — clean exit", flush=True)
        seeds = []
        pre_exhausted = True

    seeds = order_seeds(seeds, priority)
    if priority:
        print(f"[priority] draining first: {','.join(priority)}", flush=True)
    if tree_only:
        print("[tree-only] emitting a vehicle row per carcode; not crawling leaves", flush=True)

    make_cap = _make_cap(budget, len(seeds))
    per_make: dict[str, int] = {}         # requests spent per make this run
    print(f"[cap] per-make request ceiling = {make_cap}", flush=True)
    frontier: deque = deque(seeds)
    prior = _load_visited(visited_file)   # LEAF keys crawled in earlier runs (from cache)
    seen_this_run: set[str] = set()       # in-run dedup (all node types)
    new_keys: set[str] = set()            # leaf keys first crawled in THIS run (merged into cache)
    print(f"[resume] loaded {len(prior)} previously-crawled leaves — will skip them", flush=True)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    exit_reason = "byte_budget" if pre_exhausted else "drained"   # 'drained' iff the frontier empties naturally
    with open(out_path, "w", encoding="utf-8") as out:
        while frontier:
            if stats["requests"] >= budget:
                exit_reason = "budget"
                print(f"[stop] request budget {budget} reached", flush=True)
                break
            if time.monotonic() - started > max_seconds:
                exit_reason = "time"
                print(f"[stop] max runtime {max_seconds}s reached", flush=True)
                break
            if stats["blocked"] >= 3:
                exit_reason = "blocked"
                print("[stop] IP appears burned (3 blocks) — abort for a fresh runner", flush=True)
                break
            # Consecutive-block resets on any success, so a merely RATE-LIMITED IP
            # (intermittent timeouts) could grind for hours. Cap total blocks too.
            if stats["captchas"] >= 12:
                exit_reason = "captchas"
                print(f"[stop] {stats['captchas']} total blocks — IP rate-limited, abort", flush=True)
                break

            # DFS (pop from the right): drill straight down to part-listing leaves
            # so a job produces real listings early, instead of expanding the whole
            # make/year/model breadth first (which never reaches a leaf on a budget).
            node = frontier.pop()
            key = node.get("href") or json.dumps(node.get("payload", {}).get("jsn"), sort_keys=True)
            if key in seen_this_run:
                continue
            ntype = node.get("node_type")
            is_leaf = ntype in C.LEAF_TYPES
            # Cross-run skip: a LEAF already crawled in a prior run — skip it so we
            # spend this run reaching NEW leaves. Branches are NEVER skipped (we must
            # re-traverse them to descend to their still-uncrawled leaves).
            if is_leaf and key in prior:
                seen_this_run.add(key)
                stats["skipped"] += 1
                continue

            # Per-make budget: once a make used its slice, defer its subtree so the
            # remaining budget spreads to OTHER makes. Without this, DFS drilled one
            # make till the global budget died and A–G makes were never discovered.
            # ponytail: fixed cap = budget/makes; raise it if depth-per-run matters
            # more than breadth (the leaf cache already deepens makes across runs).
            mk = ((node.get("payload") or {}).get("ctx") or {}).get("make") or "?"
            if per_make.get(mk, 0) >= make_cap:
                seen_this_run.add(key)
                stats["capped"] += 1
                continue

            stats["requests"] += 1
            per_make[mk] = per_make.get(mk, 0) + 1
            if rotate_every and stats["requests"] % rotate_every == 0:
                try:
                    client.new_session()   # fresh Evomi IP before the per-IP limit
                except Exception:          # noqa: BLE001 - rotation is best-effort
                    pass
            try:
                listings, kids = process(client, node, tree_only)
            except Blocked:
                stats["blocked"] += 1
                stats["captchas"] += 1
                frontier.appendleft(node)  # retry later (not marked seen, so it re-pops)
                continue
            except BudgetExceeded:
                exit_reason = "byte_budget"
                frontier.append(node)      # unfinished — next dispatch resumes it
                print(f"[stop] Evomi byte budget reached ({BUDGET.spent/1e9:.2f}GB) — clean exit",
                      flush=True)
                break
            except Exception as exc:  # noqa: BLE001 - never die on one node
                print(f"[warn] node error: {exc}", flush=True)
                seen_this_run.add(key)
                continue

            seen_this_run.add(key)
            if is_leaf:
                new_keys.add(key)     # record this leaf as crawled (for the shared cache)
            stats["blocked"] = 0  # reset the consecutive-block counter on success
            stats["nodes"] += 1
            for lst in listings:
                # Self-host EVERY product photo (RockAuto shows a carousel of them):
                # download each (unblocked here) and rewrite to local storefront paths
                # so they load on the user's box. Taking only [0] threw the rest away.
                # ponytail: downloads all photos per listing; if image bandwidth ever
                # dominates the crawl, cap with a slice here.
                if DOWNLOAD_IMAGES and lst.get("image_urls"):
                    locals_: list[str] = []
                    for url in lst["image_urls"]:
                        local = images.download(client._session, url, img_root)
                        if local:
                            locals_.append(local)
                            stats["images"] += 1
                    lst["image_urls"] = locals_
                out.write(json.dumps(lst, ensure_ascii=False) + "\n")
                stats["listings"] += 1
            for kid in kids:
                kkey = kid.get("href") or json.dumps(kid.get("payload", {}).get("jsn"), sort_keys=True)
                if kkey not in seen_this_run:
                    frontier.append(kid)

            if stats["nodes"] % 20 == 0:
                out.flush()
                print(f"[progress] nodes={stats['nodes']} listings={stats['listings']} "
                      f"new_leaves={len(new_keys)} skipped={stats['skipped']} "
                      f"frontier={len(frontier)} reqs={stats['requests']} "
                      f"captchas={stats['captchas']}", flush=True)
            time.sleep(_polite_delay())

    # Structured completeness signal for the loop-until-complete driver: this window
    # is DONE only when the frontier drained naturally with no capped/deferred branches.
    stats["exit_reason"] = exit_reason
    stats["frontier_remaining"] = len(frontier)
    stats["new_leaves"] = len(new_keys)
    stats["complete"] = (exit_reason == "drained" and stats["capped"] == 0 and not frontier)
    print(f"[result] exit_reason={exit_reason} complete={stats['complete']} "
          f"new_leaves={len(new_keys)} frontier_remaining={len(frontier)} "
          f"requests={stats['requests']} capped={stats['capped']}", flush=True)

    # Persist the leaf keys crawled this run so the next run skips them (shared cache).
    if visited_out:
        try:
            os.makedirs(os.path.dirname(visited_out) or ".", exist_ok=True)
            with open(visited_out, "w", encoding="utf-8") as fh:
                fh.write("\n".join(sorted(new_keys)))
        except OSError as exc:
            print(f"[warn] could not write visited_out: {exc}", flush=True)

    print(f"[final] {stats}  out={out_path}", flush=True)
    return stats


def _polite_delay() -> float:
    import random
    lo = float(config.RATE["min_delay_s"])
    hi = float(config.RATE["max_delay_s"])
    return random.uniform(lo, hi)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="RockAuto NDJSON shard crawler (GitHub Actions fleet).")
    p.add_argument("--shard-index", type=int, default=int(os.getenv("SHARD_INDEX", "0")))
    p.add_argument("--shard-total", type=int, default=int(os.getenv("SHARD_TOTAL", "1")))
    p.add_argument("--out", default=os.getenv("OUT_PATH", "shard.ndjson"))
    p.add_argument("--makes", default=None, help="comma list to override auto make-discovery")
    p.add_argument("--budget", type=int, default=int(os.getenv("SP_JOB_BUDGET", "400")))
    p.add_argument("--max-seconds", type=int, default=int(os.getenv("SP_JOB_MAX_SECONDS", "18000")))
    p.add_argument("--visited-file", default=os.getenv("VISITED_FILE"),
                   help="path to prior-runs' crawled leaf keys (skip them)")
    p.add_argument("--visited-out", default=os.getenv("VISITED_OUT"),
                   help="write this run's newly-crawled leaf keys here (merged into cache)")
    p.add_argument("--tree-only", action="store_true", default=os.getenv("TREE_ONLY") == "1",
                   help="enumerate every vehicle (one row per carcode) WITHOUT crawling leaf listings")
    p.add_argument("--priority-makes", default=os.getenv("PRIORITY_MAKES"),
                   help="comma list of makes to crawl FIRST (before the alpha tail)")
    p.add_argument("--only-makes", default=os.getenv("SHARD_MAKES"),
                   help="comma list: crawl ONLY these makes (balanced-plan shard); "
                        "filters RockAuto's discovered makes so their exact hrefs are reused")
    p.add_argument("--selftest", action="store_true")
    return p.parse_args(argv)


def _selftest() -> bool:
    """Offline: prove shard() partitions disjointly and seed nodes are well-formed."""
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    items = list(range(100))
    parts = [shard(items, i, 5) for i in range(5)]
    flat = sorted(x for part in parts for x in part)
    check("shards are disjoint + cover all", flat == items)
    check("shards roughly balanced", all(18 <= len(p) <= 22 for p in parts))
    seeds = make_seed_nodes([{"make": "HONDA", "href": "/en/catalog/honda"}])
    check("seed node shape", seeds[0]["node_type"] == "make"
          and seeds[0]["href"] == "/en/catalog/honda"
          and seeds[0]["payload"]["ctx"]["make"] == "HONDA")
    # cap splits budget across makes; floor keeps a make reachable on tiny budgets
    check("make cap splits budget", _make_cap(2500, 12) == 208)
    check("make cap floor", _make_cap(100, 50) == 50)

    # tree-only: a model page with 2 carcode nodes -> 2 vehicle rows, 0 children.
    MODEL_HTML = """
    <html><body>
      <input id="jsn[3309958]" value='{"nodetype":"carcode","make":"Honda",
        "year":"2015","model":"Accord","carcode":3309958,"engine":"2.4L L4",
        "jsdata":{"markets":[{"c":"US"}]},"href":"/en/catalog/honda,2015,accord,2.4l,3309958"}'>
      <input id="jsn[3309959]" value='{"nodetype":"carcode","make":"Honda",
        "year":"2015","model":"Accord","carcode":3309959,"engine":"3.5L V6",
        "jsdata":{"markets":[{"c":"US"},{"c":"CA"}]},"href":"/en/catalog/honda,2015,accord,3.5l,3309959"}'>
    </body></html>
    """

    class _FakeClient:
        def get(self, href): return MODEL_HTML
        def fetch_children(self, jsn): return MODEL_HTML

    model_node = {"node_type": "model", "href": "/en/catalog/honda,2015,accord",
                  "payload": {"ctx": {"make": "Honda"}}}
    rows, kids = process(_FakeClient(), model_node, tree_only=True)
    check("tree-only emits 2 vehicle rows", len(rows) == 2)
    check("tree-only enqueues NO children", kids == [])
    check("vehicle row shape", rows and rows[0]["source"] == "rockauto"
          and rows[0]["make_name"] == "Honda" and rows[0]["model_name"] == "Accord"
          and rows[0]["year"] == 2015 and rows[0]["carcode"] == "3309958"
          and rows[0]["engine_name"] == "2.4L L4" and rows[0]["market"] == "US"
          and "part_number" not in rows[0])
    check("vehicle row multi-market CSV", rows and rows[1]["market"] == "US,CA")
    # normal mode: the SAME page enqueues the carcodes as children, emits nothing.
    n_rows, n_kids = process(_FakeClient(), model_node, tree_only=False)
    check("full mode emits no vehicle rows", n_rows == [])
    check("full mode enqueues carcode children", len(n_kids) == 2
          and all(k["node_type"] == "carcode" for k in n_kids))

    # priority-makes: honda drains before the alpha tail -> honda seed at the TAIL
    # (DFS pops from the right), toyota just before it.
    pseeds = make_seed_nodes([{"make": "ACURA", "href": "/en/catalog/acura"},
                              {"make": "TOYOTA", "href": "/en/catalog/toyota"},
                              {"make": "HONDA", "href": "/en/catalog/honda"}])
    ordered = order_seeds(pseeds, ["honda", "toyota"])
    check("priority makes moved to tail", _seed_make_key(ordered[-1]) == "honda"
          and _seed_make_key(ordered[-2]) == "toyota"
          and _seed_make_key(ordered[0]) == "acura")
    check("order_seeds no-op without priority", order_seeds(pseeds, None) is pseeds)

    print("PASS" if ok else "FAIL")
    return ok


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.selftest:
        return 0 if _selftest() else 1
    makes = [m.strip().lower() for m in args.makes.split(",")] if args.makes else None
    priority = ([m.strip().lower() for m in args.priority_makes.split(",") if m.strip()]
                if args.priority_makes else None)
    only = ([m.strip().lower() for m in args.only_makes.split(",") if m.strip()]
            if args.only_makes else None)
    run(args.shard_index, args.shard_total, args.out, makes, args.budget, args.max_seconds,
        visited_file=args.visited_file, visited_out=args.visited_out,
        tree_only=args.tree_only, priority=priority, only_makes=only)
    return 0


if __name__ == "__main__":
    # No args -> offline self-test (never crawls the live site by accident).
    if len(sys.argv) > 1:
        sys.exit(main())
    sys.exit(0 if _selftest() else 1)
