"""
leaf_probe.py — measure the REAL number of part-type leaf pages per vehicle, the
multiplier that decides the true catalog size (148k vehicles x THIS = leaf pages).

For ~10 diverse vehicles (spread across makes/years, modern + vintage), fetch the
carcode page -> count groupnames -> expand EACH groupname -> count part-types. Sum
= part-type leaf pages for that vehicle. Prints per-vehicle detail + the average.
"""
from __future__ import annotations
import json
import os
import statistics

try:
    import config, parsers
    from ra_client import RAClient, Blocked
except ImportError:
    from scraper import config, parsers  # type: ignore
    from scraper.ra_client import RAClient, Blocked  # type: ignore


def main():
    client = RAClient(None)
    client.new_session()

    def kids(url, ntype):
        return [n for n in parsers.parse_nav(client.get(url))
                if n.get("nodetype") == ntype and n.get("href")]

    makes = [n for n in parsers.parse_nav(client.get(config.CATALOG_ROOT))
             if n.get("nodetype") == "make" and n.get("href")]

    # Collect ~12 vehicles spread across makes + a mix of modern/old years.
    targets = []
    for m in makes[::22][:8]:
        try:
            years = kids(m["href"], "year")
        except Blocked:
            break
        if not years:
            continue
        for y in [years[0], years[len(years) // 2], years[-1]][:2]:
            try:
                models = kids(y["href"], "model")
            except Blocked:
                break
            for md in models[:1]:
                try:
                    ccs = kids(md["href"], "carcode")
                except Blocked:
                    break
                if ccs:
                    targets.append(ccs[0])
        if len(targets) >= 12:
            break

    results = []
    for cc in targets[:12]:
        try:
            gns = [n for n in parsers.parse_nav(client.get(cc["href"]))
                   if n.get("nodetype") == "groupname"]
        except Blocked:
            print("LEAF_NOTE blocked — stopping early", flush=True)
            break
        total_pt = 0
        fails = 0
        for g in gns:
            try:
                frag = client.fetch_children(g["jsn"]) if g.get("jsn") else ""
                total_pt += len([n for n in parsers.parse_nav(frag)
                                 if n.get("nodetype") == "parttype"])
            except Blocked:
                fails += 1
        r = {"make": cc.get("make"), "year": cc.get("year"),
             "groupnames": len(gns), "parttypes": total_pt, "group_fetch_fails": fails}
        results.append(r)
        print(f"LEAF {r['make']} {r['year']}: {r['groupnames']} groups -> {r['parttypes']} part-types"
              + (f" ({fails} fetch fails)" if fails else ""), flush=True)

    good = [r["parttypes"] for r in results if r["parttypes"] > 0]
    avg = statistics.mean(good) if good else 0
    total_carcodes = 148000
    out = {
        "vehicles_sampled": len(results),
        "avg_parttypes_per_vehicle": round(avg, 1),
        "min": min(good) if good else 0, "max": max(good) if good else 0,
        "total_carcodes": total_carcodes,
        "EST_TOTAL_LEAF_PAGES": int(avg * total_carcodes),
    }
    print("LEAF_RESULT " + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
