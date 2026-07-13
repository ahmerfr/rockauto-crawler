"""idepth_probe.py — the GATE test for the request-slasher plan.

Question: does RockAuto's `idepth` knob on func=tab_fetch INLINE part-listing rows
(ONE fetch per group returns every part-type's listings = ~11x fewer requests; per
carcode = ~243x), or only pre-expand nav children (slasher dead)?

Drills the REAL tree (make->year->model->carcode->group) using live parse_nav jsn
at each level, then re-fetches a real group/carcode node with idepth=8 and checks
whether listings come back. MUST run from an unblocked IP (GitHub Actions Azure
runner). Read-only.
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import config  # noqa: E402
import parsers  # noqa: E402
from proxy_manager import ProxyManager  # noqa: E402
from ra_client import RAClient  # noqa: E402


def fetch(client, node) -> str:
    """Fetch a parse_nav node's page/fragment via href (GET) or jsn (tab_fetch)."""
    if node.get("href"):
        return client.get(node["href"])
    if node.get("jsn"):
        return client.fetch_children(node, max_group_index=363)
    return ""


def kids(client, node, want):
    """parse_nav children of `node` whose nodetype == want (or all if want None)."""
    ns = parsers.parse_nav(fetch(client, node))
    types = {}
    for n in ns:
        types[n.get("nodetype")] = types.get(n.get("nodetype"), 0) + 1
    sel = [n for n in ns if n.get("nodetype") == want] if want else ns
    return sel, types


def _signal(tag: str, frag: str):
    listingtd = len(re.findall(r"listingtd\[", frag))
    try:
        listings = parsers.parse_listings(frag, {"markets": ["US"]})
    except Exception as exc:  # noqa: BLE001
        listings = []
        print(f"  [{tag}] parse_listings error: {exc}")
    cats = sorted({(l.get("category_path") or "") for l in listings})
    print(f"  [{tag}] frag={len(frag)}c listingtd={listingtd} parsed_listings={len(listings)} "
          f"distinct_category_paths={len(cats)}")
    if cats[:8]:
        print(f"      cats: {cats[:8]}")
    return {"listingtd": listingtd, "listings": len(listings), "cats": len(cats)}


def main() -> int:
    client = RAClient(ProxyManager())
    client.new_session()
    print(f"session: _nck={'yes' if client._nck else 'NO'}")

    makes = [n for n in parsers.parse_nav(client.get(config.CATALOG_ROOT))
             if n.get("nodetype") == "make"]
    print(f"discovered {len(makes)} makes")
    make = next((m for m in makes if "acura" in ((m.get("href") or "") + str(m.get("make") or "")).lower()),
                makes[0] if makes else None)
    if not make:
        print("!! no makes"); return 1
    print(f"make: {make.get('make') or make.get('href')}")

    # drill make -> year -> model -> carcode -> group, retrying siblings until groups appear
    years, t = kids(client, make, "year")
    print(f"years: {len(years)}  (child types {t})")
    group = carcode = None
    for y in years[:6]:
        models, _ = kids(client, y, "model")
        for mo in models[:4]:
            ccs, _ = kids(client, mo, "carcode")
            for cc in ccs[:3]:
                grps, tt = kids(client, cc, "groupname")
                if grps:
                    carcode, group = cc, grps[0]
                    print(f"reached: year={y.get('year')} model={mo.get('model')} "
                          f"carcode={cc.get('carcode')} -> {len(grps)} groups (types {tt})")
                    break
            if group:
                break
        if group:
            break
    if not group:
        print("!! could not reach a carcode with groups"); return 1
    gname = (group.get("jsn") or {}).get("groupname") or group.get("label")
    print(f"probing group: {gname!r}\n")

    print("A) BASELINE group, no idepth:")
    _signal("base", fetch(client, group))

    print("\nB) group + idepth=8  (THE 11x TEST):")
    gnode = {"jsn": dict(group["jsn"])}; gnode["jsn"]["idepth"] = 8
    grp = _signal("idepth8-group", client.fetch_children(gnode, max_group_index=363))

    print("\nC) carcode + idepth=8  (the 243x whole-vehicle test):")
    cnode = {"jsn": dict(carcode["jsn"])}; cnode["jsn"]["idepth"] = 8
    car = _signal("idepth8-carcode", client.fetch_children(cnode, max_group_index=363))

    print("\n===== VERDICT =====")
    if grp["listings"] > 0 and grp["cats"] > 1:
        print(f"GROUP 11x CONFIRMED: 1 group fetch -> {grp['listings']} listings across "
              f"{grp['cats']} part-types. => $0 free-fleet plan.")
    elif grp["listings"] > 0:
        print(f"GROUP partial: {grp['listings']} listings, {grp['cats']} category path(s).")
    else:
        print("GROUP idepth = NO listings (nav-only). Slasher dead at group level -> residential fallback.")
    if car["listings"] > 50 and car["cats"] > 3:
        print(f"VEHICLE 243x LIKELY: carcode idepth -> {car['listings']} listings across "
              f"{car['cats']} part-types in ONE request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
