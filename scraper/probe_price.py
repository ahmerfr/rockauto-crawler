#!/usr/bin/env python
"""probe_price.py — is the PRICE present in the navnode_fetch fragment or only the
full page? The fragment path yielded 13.5% priced vs 94% on full pages, so prices
are being lost. Fetch ONE parttype both ways via Evomi and compare priced counts +
dump the price markup, to decide: fix the fragment parse, or revert to full pages.
"""
from __future__ import annotations
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, parsers  # noqa: E402
import crawl as C  # noqa: E402
from ra_client import RAClient  # noqa: E402
from proxy_manager import EvomiProxyManager  # noqa: E402

VEH = "/en/catalog/acura,2010,zdx,3.7l+v6,1445611"


def priced(listings):
    return sum(1 for x in listings if x.get("price") is not None)


def main():
    os.environ["EVOMI_COUNTRY"] = "US"
    client = RAClient(EvomiProxyManager())
    vhtml = client.get(VEH)
    m = re.search(r'id="max_group_index"[^>]*value="(\d+)"', vhtml)
    mgi = int(m.group(1)) if m else 0
    groups = [n for n in parsers.parse_nav(vhtml) if n.get("nodetype") == "groupname"]
    # pick a group likely to have priced parts (Brake & Wheel Hub)
    g = next((x for x in groups if "Brake" in (x.get("label") or "")), groups[0])
    pts = [n for n in parsers.parse_nav(client.get(g["href"])) if n.get("nodetype") == "parttype"]
    print(f"group={g.get('label')} parttypes={len(pts)} mgi={mgi}\n")

    # dump the raw id format (placeholder vs numeric) for the first parttype
    dbg = client.fetch_listings(pts[0].get("jsn") or {}, mgi)
    dbgf = client.get(pts[0]["href"])
    for label, html in (("FRAG", dbg), ("FULL", dbgf)):
        ids = re.findall(r'id="(dprice\[[^\]]*\]\[v\]|listingtd\[[^\]]*\]\[price\]|listing-container-border[^"]*)"', html)[:4]
        print(f"  {label} id samples: {ids}")
    print()

    for pt in pts[:4]:
        jsn = pt.get("jsn") or {}
        ctx = C.listing_ctx({"jsn": jsn, "ctx": {}})
        frag = client.fetch_listings(jsn, mgi)
        full = client.get(pt["href"])
        lf = parsers.parse_listings(frag, ctx)
        lu = parsers.parse_listings(full, ctx)
        print(f"parttype {jsn.get('parttype'):>7}: FRAG parts={len(lf)} priced={priced(lf)}   "
              f"FULL parts={len(lu)} priced={priced(lu)}")
        # where is the price token in each?
        for label, html in (("FRAG", frag), ("FULL", full)):
            has_cls = ("listing-price" in html) or ("listing-final-price" in html)
            has_td = "listingtd[" in html
            dollars = len(re.findall(r"\$\s*[0-9][0-9,]*\.\d{2}", html))
            # is price in a JS data blob instead of rendered cells?
            blob = ("listing_data_essential" in html) or ('"price"' in html) or ("dprice[" in html)
            print(f"    {label}: listing-price_cls={has_cls} listingtd={has_td} "
                  f"$tokens={dollars} price_in_blob={blob}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
