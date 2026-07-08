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
    from ra_client import RAClient, Blocked
    from proxy_manager import ProxyManager
except ImportError:  # pragma: no cover - package layout
    from scraper import config, images, parsers  # type: ignore
    from scraper import crawl as C  # type: ignore
    from scraper.ra_client import RAClient, Blocked  # type: ignore
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


def process(client, node: dict) -> tuple[list[dict], list[dict]]:
    """Fetch + expand one node. Returns (listings, child_nodes).

    Mirrors crawl._process_node but returns data instead of touching a DB.
    """
    payload = node.get("payload") or {}
    href = node.get("href")
    jsn = payload.get("jsn")
    ntype = node.get("node_type")

    if href:
        html = client.get(href)
    elif jsn:
        html = client.fetch_children(jsn)
    else:
        raise ValueError("node has neither href nor jsn")

    if ntype in C.LEAF_TYPES:
        listings = parsers.parse_listings(html, C.listing_ctx(payload))
        return listings, []

    children = parsers.parse_nav(html)
    kids = []
    for child in children:
        if not C.should_enqueue(child):
            continue
        kids.append({
            "node_type": child.get("nodetype", "node"),
            "href": child.get("href"),
            "payload": C.build_child_payload(child, payload),
        })
    return [], kids


def run(shard_index: int, shard_total: int, out_path: str,
        makes_override: list[str] | None = None,
        budget: int = 400, max_seconds: int = 18000) -> dict:
    """Crawl this shard, writing Listing rows as NDJSON to `out_path`."""
    started = time.monotonic()
    stats = {"nodes": 0, "listings": 0, "captchas": 0, "blocked": 0, "requests": 0,
             "images": 0}
    img_root = os.path.join(os.path.dirname(out_path) or ".", "images")

    proxies = ProxyManager()
    if config.PROXY.get("enabled", True):
        try:
            proxies.refill()
        except Exception as exc:  # noqa: BLE001
            print(f"[proxy] refill skipped: {exc}", flush=True)
    client = RAClient(proxies)

    # Seed: explicit makes, else discover + shard the full catalog make list.
    if makes_override:
        seeds = make_seed_nodes([{"make": m, "href": C.seed_href(m)} for m in makes_override])
    else:
        all_makes = discover_makes(client)
        mine = shard(all_makes, shard_index, shard_total)
        print(f"[shard] {shard_index}/{shard_total}: {len(mine)}/{len(all_makes)} makes", flush=True)
        seeds = make_seed_nodes(mine)

    frontier: deque = deque(seeds)
    visited: set[str] = set()

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as out:
        while frontier:
            if stats["requests"] >= budget:
                print(f"[stop] request budget {budget} reached", flush=True)
                break
            if time.monotonic() - started > max_seconds:
                print(f"[stop] max runtime {max_seconds}s reached", flush=True)
                break
            if stats["blocked"] >= 3:
                print("[stop] IP appears burned (3 blocks) — abort for a fresh runner", flush=True)
                break

            # DFS (pop from the right): drill straight down to part-listing leaves
            # so a job produces real listings early, instead of expanding the whole
            # make/year/model breadth first (which never reaches a leaf on a budget).
            node = frontier.pop()
            key = node.get("href") or json.dumps(node.get("payload", {}).get("jsn"), sort_keys=True)
            if key in visited:
                continue
            visited.add(key)

            stats["requests"] += 1
            try:
                listings, kids = process(client, node)
            except Blocked:
                stats["blocked"] += 1
                stats["captchas"] += 1
                frontier.append(node)  # re-queue; a later fresh IP may get it
                continue
            except Exception as exc:  # noqa: BLE001 - never die on one node
                print(f"[warn] node error: {exc}", flush=True)
                continue

            stats["blocked"] = 0  # reset the consecutive-block counter on success
            stats["nodes"] += 1
            for lst in listings:
                # Self-host the thumbnail: download it (unblocked here) and rewrite
                # the URL to the local storefront path so it loads on the user's box.
                if DOWNLOAD_IMAGES and lst.get("image_urls"):
                    local = images.download(client._session, lst["image_urls"][0], img_root)
                    if local:
                        lst["image_urls"] = [local]
                        stats["images"] += 1
                    else:
                        lst["image_urls"] = []
                out.write(json.dumps(lst, ensure_ascii=False) + "\n")
                stats["listings"] += 1
            for kid in kids:
                kkey = kid.get("href") or json.dumps(kid.get("payload", {}).get("jsn"), sort_keys=True)
                if kkey not in visited:
                    frontier.append(kid)

            if stats["nodes"] % 20 == 0:
                out.flush()
                print(f"[progress] nodes={stats['nodes']} listings={stats['listings']} "
                      f"frontier={len(frontier)} reqs={stats['requests']} "
                      f"captchas={stats['captchas']}", flush=True)
            time.sleep(_polite_delay())

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
    print("PASS" if ok else "FAIL")
    return ok


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.selftest:
        return 0 if _selftest() else 1
    makes = [m.strip().lower() for m in args.makes.split(",")] if args.makes else None
    run(args.shard_index, args.shard_total, args.out, makes, args.budget, args.max_seconds)
    return 0


if __name__ == "__main__":
    # No args -> offline self-test (never crawls the live site by accident).
    if len(sys.argv) > 1:
        sys.exit(main())
    sys.exit(0 if _selftest() else 1)
