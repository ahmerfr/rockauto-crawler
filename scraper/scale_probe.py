"""
scale_probe.py — measure RockAuto's TRUE catalog size by sampling, so we can
decide the $50/3-day plan on a real number instead of a 15-40M guess.

Samples ~20 makes spread across all 301, counts years/models/carcodes, and
part-types per carcode, then extrapolates. One fresh IP, a few hundred requests
(well under the per-IP burn threshold). Prints a SCALE json line.
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

N_MAKES_SAMPLE = int(os.getenv("SCALE_MAKES", "20"))


def main():
    client = RAClient(None)
    client.new_session()

    def kids(url, ntype):
        return [n for n in parsers.parse_nav(client.get(url))
                if n.get("nodetype") == ntype and n.get("href")]

    makes = [n for n in parsers.parse_nav(client.get(config.CATALOG_ROOT))
             if n.get("nodetype") == "make" and n.get("href")]
    n_makes = len(makes)
    step = max(1, n_makes // N_MAKES_SAMPLE)
    sample = makes[::step][:N_MAKES_SAMPLE]

    per_make_carcodes = []
    leaves_per_carcode = []
    for m in sample:
        try:
            years = kids(m["href"], "year")
        except Blocked:
            print("SCALE_NOTE blocked mid-probe (IP burned) — partial", flush=True)
            break
        ny = len(years)
        if ny == 0:
            continue
        ysamp = years[::max(1, ny // 3)][:3]
        model_counts, cc_per_model = [], []
        for y in ysamp:
            try:
                models = kids(y["href"], "model")
            except Blocked:
                break
            model_counts.append(len(models))
            msamp = models[::max(1, len(models) // 2)][:2] if models else []
            for md in msamp:
                try:
                    ccs = kids(md["href"], "carcode")
                except Blocked:
                    break
                cc_per_model.append(len(ccs))
                # leaf sample: 1 carcode -> groupnames -> parttypes (a few groups)
                if ccs and len(leaves_per_carcode) < 6:
                    try:
                        gns = [n for n in parsers.parse_nav(client.get(ccs[0]["href"]))
                               if n.get("nodetype") == "groupname"]
                        pts = 0
                        gsamp = gns[:4]
                        for g in gsamp:
                            frag = client.fetch_children(g["jsn"]) if g.get("jsn") else ""
                            pts += len([n for n in parsers.parse_nav(frag)
                                        if n.get("nodetype") == "parttype"])
                        if gsamp:
                            pts = int(pts * len(gns) / len(gsamp))  # extrapolate to all groups
                        leaves_per_carcode.append(pts)
                    except Blocked:
                        pass
        if model_counts and cc_per_model:
            est = ny * statistics.mean(model_counts) * statistics.mean(cc_per_model)
            per_make_carcodes.append(est)

    avg_cc_make = statistics.mean(per_make_carcodes) if per_make_carcodes else 0
    total_carcodes = int(avg_cc_make * n_makes)
    avg_leaves = statistics.mean(leaves_per_carcode) if leaves_per_carcode else 0
    total_leaf_pages = int(total_carcodes * avg_leaves)

    out = {
        "makes": n_makes,
        "makes_sampled": len(per_make_carcodes),
        "avg_carcodes_per_make": round(avg_cc_make, 1),
        "est_total_carcodes": total_carcodes,
        "avg_parttype_leaves_per_carcode": round(avg_leaves, 1),
        "EST_TOTAL_LEAF_PAGES": total_leaf_pages,
        "est_nav_pages_for_full_tree": int(total_carcodes * 1.2),  # make+year+model fetches ~ carcodes
    }
    print("SCALE " + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
