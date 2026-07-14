#!/usr/bin/env python
"""probe_fragment.py — navnode_fetch listing fragment vs full page (the $30 decider).

Full mirror = ~12.7M parttype fetches. At the full-page 16KB each that is 208GB=$239.
RockAuto's UI loads listings via catalogapi func=navnode_fetch (a chrome-less HTML
fragment). If that fragment averages <=2KB gzipped, the mirror fits in ~26GB (~$30).

This drills a real vehicle to its parttype nodes, then fetches each BOTH ways and
reports gzipped size + part-count parity, so we know the true per-parttype byte cost.
Run on a US runner (local IP is rate-limited). Byte size is IP-independent.
"""
from __future__ import annotations
import gzip, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, parsers  # noqa: E402
import crawl as C  # noqa: E402
from ra_client import RAClient  # noqa: E402
from proxy_manager import ProxyManager  # noqa: E402

VEH = "/en/catalog/acura,2010,zdx,3.7l+v6,1445611"


def gz(s: str) -> int:
    return len(gzip.compress((s or "").encode("utf-8", "replace")))


def main() -> int:
    os.environ.setdefault("SP_USE_PROXIES", "0")
    client = RAClient(ProxyManager())

    print(f"[1] GET vehicle page {VEH}")
    vhtml = client.get(VEH)
    m = re.search(r'id="max_group_index"[^>]*value="(\d+)"', vhtml) or \
        re.search(r'max_group_index[^0-9]{0,20}(\d+)', vhtml)
    mgi = int(m.group(1)) if m else 0
    groups = [n for n in parsers.parse_nav(vhtml) if n.get("nodetype") == "groupname"]
    print(f"    max_group_index={mgi}, groups={len(groups)}")

    # collect parttype nodes from the first few groups
    parttypes = []
    for g in groups[:5]:
        try:
            gh = client.get(g["href"])
        except Exception as exc:  # noqa: BLE001
            print(f"    group {g.get('label')} fetch failed: {exc}"); continue
        pts = [n for n in parsers.parse_nav(gh) if n.get("nodetype") == "parttype"]
        parttypes.extend(pts)
        if len(parttypes) >= 15:
            break
    parttypes = parttypes[:15]
    print(f"[2] measuring {len(parttypes)} parttypes both ways\n")

    tot_full = tot_frag = n_ok = 0
    print(f"    {'parttype':10} {'full_gz':>8} {'frag_gz':>8} {'pf':>3} {'pg':>3}")
    for pt in parttypes:
        jsn = pt.get("jsn") or {}
        ctx = C.listing_ctx({"jsn": jsn, "ctx": {}})
        try:
            full = client.get(pt["href"])
        except Exception:
            full = ""
        try:
            frag = client.fetch_listings(jsn, mgi)
        except Exception as exc:  # noqa: BLE001
            frag = f"(err {type(exc).__name__})"
        gf, gg = gz(full), gz(frag)
        pf = len(parsers.parse_listings(full, ctx)) if full else -1
        pg = len(parsers.parse_listings(frag, ctx)) if frag and not frag.startswith("(err") else -1
        print(f"    {jsn.get('parttype','?'):10} {gf:8d} {gg:8d} {pf:3d} {pg:3d}")
        if gf:
            tot_full += gf; tot_frag += gg; n_ok += 1

    if n_ok:
        af, ag = tot_full / n_ok, tot_frag / n_ok
        print(f"\n  avg full-page gz : {af:7.0f} B/parttype")
        print(f"  avg fragment gz  : {ag:7.0f} B/parttype   ({af/max(1,ag):.1f}x smaller)")
        for label, per in (("full page", af), ("fragment", ag)):
            gb = 12_698_470 * per / 1e9
            print(f"  full mirror via {label:10}: {gb:6.1f} GB = ${gb*1.15:5.0f}")
        print(f"\n  $30 budget = 26GB -> need <= {26e9/12_698_470:.0f} B/parttype gzipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
