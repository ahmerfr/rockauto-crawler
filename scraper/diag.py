"""
diag.py — one-shot structural probe of RockAuto's deep catalog, run on a GitHub
runner (unblocked IP) to capture what we could never see from the blocked dev box:
the real nodetypes at each level and a real part-listing leaf's HTML.

Drills Honda -> a year -> a model -> a carcode -> categories -> a group, dumping
at each step: parse_nav nodetype histogram, parse_listings count, and the raw
HTML. Writes everything under artifacts/diag/ for inspection.

    python scraper/diag.py
"""
from __future__ import annotations
import json
import os

try:
    import config, parsers
    from ra_client import RAClient
except ImportError:
    from scraper import config, parsers  # type: ignore
    from scraper.ra_client import RAClient  # type: ignore

OUT = "artifacts/diag"
os.makedirs(OUT, exist_ok=True)
summary = []


def dump(label, html):
    nodes = parsers.parse_nav(html)
    types = {}
    for n in nodes:
        t = n.get("nodetype")
        types[t] = types.get(t, 0) + 1
    try:
        listings = parsers.parse_listings(html, {"category_path": "", "source_url": ""})
    except Exception as exc:  # noqa: BLE001
        listings = []
        print(f"[{label}] parse_listings error: {exc}")
    with open(os.path.join(OUT, f"{label}.html"), "w", encoding="utf-8") as fh:
        fh.write(html or "")
    info = {"label": label, "html_len": len(html or ""), "node_count": len(nodes),
            "nodetypes": types, "listings": len(listings)}
    summary.append(info)
    print(f"[{label}] {json.dumps(info)}", flush=True)
    return nodes, listings


def first(nodes, ntype):
    for n in nodes:
        if n.get("nodetype") == ntype:
            return n
    return None


def main():
    client = RAClient(None)  # direct; the GitHub runner IP is fresh
    client.new_session()

    # 1) make page
    nodes, _ = dump("1_honda", client.get("/en/catalog/honda"))
    yr = first(nodes, "year")
    if not yr:
        print("no year node; stopping"); _finish(); return

    # 2) year page (GET the year href)
    nodes, _ = dump("2_year", client.get(yr["href"]) if yr.get("href")
                    else client.fetch_children(yr["jsn"]))
    md = first(nodes, "model")
    if not md:
        print("no model node; stopping"); _finish(); return

    # 3) model page
    nodes, _ = dump("3_model", client.get(md["href"]) if md.get("href")
                    else client.fetch_children(md["jsn"]))
    cc = first(nodes, "carcode")
    if not cc:
        print("no carcode node; stopping"); _finish(); return

    # 4) carcode page via GET (url-addressable)
    cc_nodes_get, _ = dump("4_carcode_GET",
                           client.get(cc["href"]) if cc.get("href")
                           else client.fetch_children(cc["jsn"]))
    # 4b) carcode expansion via catalogapi (do CATEGORIES appear only here?)
    if cc.get("jsn"):
        cc_nodes_api, _ = dump("4b_carcode_FETCHCHILDREN",
                               client.fetch_children(cc["jsn"]))
    else:
        cc_nodes_api = []

    # 5) first category (from whichever gave categories)
    cats = [n for n in (cc_nodes_api or cc_nodes_get)
            if n.get("nodetype") in ("category", "group", "parttype")]
    if not cats:
        print("NO category/group nodes found at carcode level (via GET or API).")
        _finish(); return
    cat = cats[0]
    nodes, _ = dump("5_category",
                    client.get(cat["href"]) if cat.get("href")
                    else client.fetch_children(cat["jsn"]))

    # 6) drill one more level toward listings
    grp = first(nodes, "group") or first(nodes, "parttype") or (nodes[0] if nodes else None)
    if grp:
        dump("6_group",
             client.get(grp["href"]) if grp.get("href")
             else client.fetch_children(grp["jsn"]))
    _finish()


def _finish():
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print("=== SUMMARY ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
