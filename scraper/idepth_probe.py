"""idepth_probe.py — the 5-minute GATE test for the request-slasher plan.

Question: does RockAuto's `idepth` knob on func=tab_fetch INLINE part-listing rows
(so ONE fetch per group returns every part-type's listings = ~11x fewer requests;
or per carcode = ~243x), or does it only pre-expand nav children (slasher dead)?

MUST run from an UNBLOCKED IP (GitHub Actions Azure runner) — local/datacenter IPs
are ASN-walled by RockAuto. Read-only, no writes, no code paths changed.

  python scraper/idepth_probe.py            # default carcode 3309958 (Honda Accord 2015)
  PROBE_CARCODE=<n> python scraper/idepth_probe.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import parsers  # noqa: E402
from proxy_manager import ProxyManager  # noqa: E402
from ra_client import RAClient  # noqa: E402


def _signal(tag: str, frag: str):
    """Raw listing-presence signal in a catalog fragment (no full parse needed)."""
    listingtd = len(re.findall(r"listingtd\[", frag))
    prices = len(re.findall(r"pricebreakdown\[|\$\d", frag))
    parttypes = len(re.findall(r'name=["\']?nvljs\[|navlabellink', frag))  # part-type headers/links
    try:
        listings = parsers.parse_listings(frag, {"markets": ["US"]})
    except Exception as exc:  # noqa: BLE001
        listings = []
        print(f"  [{tag}] parse_listings error: {exc}")
    cats = sorted({(l.get("category_path") or "") for l in listings})
    print(f"  [{tag}] frag={len(frag)}c  listingtd={listingtd}  price-markers={prices}  "
          f"parttype-markers={parttypes}  parsed_listings={len(listings)}  "
          f"distinct_category_paths={len(cats)}")
    if cats[:6]:
        print(f"      category_paths sample: {cats[:6]}")
    return {"listingtd": listingtd, "listings": len(listings), "cats": len(cats)}


def main() -> int:
    carcode = os.getenv("PROBE_CARCODE", "3309958")
    jsdata = {"markets": [{"c": "US"}], "mktlist": "US", "Show": 1}

    client = RAClient(ProxyManager())
    client.new_session()
    print(f"session warmed: _nck={'yes' if client._nck else 'NO'}  carcode={carcode}")

    # 1) carcode children (normal) -> its groups, to grab a REAL group jsn
    carnode = {"jsn": {"carcode": carcode, "nodetype": "carcode", "tab": "catalog", "jsdata": jsdata}}
    frag = client.fetch_children(carnode, max_group_index=363)
    groups = [n for n in parsers.parse_nav(frag) if (n.get("jsn") or {}).get("nodetype") == "groupname"]
    print(f"carcode {carcode}: {len(groups)} groups (fragment {len(frag)}c)")
    if not groups:
        print("!! no groups — carcode invalid or IP blocked; cannot probe. Raw head:")
        print(frag[:400])
        return 1
    g = groups[0]
    gname = (g.get("jsn") or {}).get("groupname") or g.get("label")
    print(f"probing group: {gname!r}\n")

    # 2) BASELINE — the group WITHOUT idepth (today's behaviour = nav children)
    print("A) BASELINE group, no idepth (expect nav children / few-or-no listings):")
    base = client.fetch_children({"jsn": dict(g["jsn"])}, max_group_index=363)
    _signal("base", base)

    # 3) THE TEST — group WITH idepth=8 (does it inline ALL part-types' listings?)
    print("\nB) group + idepth=8 (THE 11x TEST):")
    gj = dict(g["jsn"]); gj["idepth"] = 8
    deep = client.fetch_children({"jsn": gj}, max_group_index=363)
    grp = _signal("idepth8-group", deep)

    # 4) STRETCH — whole carcode + idepth=8 (the 243x test)
    print("\nC) carcode + idepth=8 (the 243x whole-vehicle test):")
    cj = dict(carnode["jsn"]); cj["idepth"] = 8
    veh = client.fetch_children({"jsn": cj}, max_group_index=363)
    car = _signal("idepth8-carcode", veh)

    print("\n===== VERDICT =====")
    if grp["listings"] > 0 and grp["cats"] > 1:
        print(f"GROUP-LEVEL 11x CONFIRMED: one group fetch returned {grp['listings']} listings "
              f"across {grp['cats']} part-types. -> $0 free-fleet plan.")
    elif grp["listings"] > 0:
        print(f"PARTIAL: group idepth returned {grp['listings']} listings but only {grp['cats']} "
              f"category path(s) — modest cut, verify it's not a single part-type.")
    else:
        print("GROUP idepth returned NO listings (nav-only). Slasher likely DEAD at group level.")
    if car["listings"] > 50 and car["cats"] > 3:
        print(f"VEHICLE-LEVEL 243x LIKELY: carcode idepth returned {car['listings']} listings "
              f"across {car['cats']} part-types — whole vehicle in ONE request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
