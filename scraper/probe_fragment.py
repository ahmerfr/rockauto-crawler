#!/usr/bin/env python
"""probe_fragment.py — compact catalogapi fragment vs full-page bytes, directly.

Decides the under-$30 full-mirror question. Leaf listings are currently fetched as
FULL catalog pages via get(href) (~16KB gzipped). RockAuto's own UI loads the same
listings via a catalogapi.php XHR returning just the parts fragment. If that
fragment is <=2KB, a 12.7M-page full mirror fits in ~26GB (~$30) of paid bytes.

Byte SIZE is IP-independent (prices vary by country, sizes don't), so this is valid
from anywhere. Takes a KNOWN group page, parses its parttype children to get a real
`jsn`, then fetches that ONE leaf both ways and compares gzipped size + part parity.
"""
from __future__ import annotations
import gzip, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, parsers  # noqa: E402
import crawl as C  # noqa: E402
from ra_client import RAClient  # noqa: E402
from proxy_manager import ProxyManager  # noqa: E402

# A real 2010 Acura ZDX group page (from the measured crawl) — lists parttype leaves.
GROUP_HREF = "/en/catalog/acura,2010,zdx,3.7l+v6,1445611,wiper+&+washer"


def gz(s: str) -> int:
    return len(gzip.compress(s.encode("utf-8", "replace")))


def main() -> int:
    os.environ.setdefault("SP_USE_PROXIES", "0")
    client = RAClient(ProxyManager())

    print(f"[1] GET group page: {GROUP_HREF}")
    ghtml = client.get(GROUP_HREF)
    nodes = parsers.parse_nav(ghtml)
    leaves = [n for n in nodes if n.get("nodetype") in ("parttype", "listing")]
    print(f"    parsed {len(nodes)} nav nodes, {len(leaves)} parttype leaves")
    if not leaves:
        print("!! no parttype nodes on the group page — cannot measure fragment")
        return 1

    leaf = leaves[0]
    jsn = leaf.get("jsn")
    href = leaf.get("href")
    label = leaf.get("label")
    print(f"[2] leaf: {label!r}  href={href}")

    ctx = C.listing_ctx({"jsn": jsn, "ctx": {}})

    full = client.get(href) if href else ""
    frag = client.fetch_children(jsn)

    gf, gg = gz(full) if full else 0, gz(frag)
    nf = len(parsers.parse_listings(full, ctx)) if full else -1
    ng = len(parsers.parse_listings(frag, ctx))

    print(f"\n  FULL page : gz={gf:6d} bytes   parts={nf}")
    print(f"  FRAGMENT  : gz={gg:6d} bytes   parts={ng}")
    if gg and gf:
        ratio = gf / gg
        print(f"\n  ==> fragment is {ratio:.1f}x smaller ({gg/1024:.1f} KB vs {gf/1024:.1f} KB)")
        print(f"  ==> part parity: full={nf} frag={ng} -> {'SAME DATA' if nf == ng and ng > 0 else 'MISMATCH'}")
        leaves_total = 12_698_470          # measured catalog-wide leaf estimate
        gb = leaves_total * gg / 1e9
        print(f"\n  ==> full mirror at this fragment size: {gb:.1f} GB = ${gb*1.15:.0f} on Evomi")
        print(f"      (budget 26GB/$30 -> need <= {26e9/leaves_total:.0f} bytes/leaf)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
