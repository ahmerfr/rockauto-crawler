"""dedup_probe.py — VALIDATION 1 (free) for the engine-dedup cost cut.

Claim: within a (make,model,year), engine-INDEPENDENT part-types (brakes, body,
electrical, suspension, wheel) return IDENTICAL part rows across the model-year's
engine carcodes — so we can fetch them ONCE per model-year (2.4x fewer requests),
while engine-DEPENDENT types (engine, cooling, fuel, exhaust) must stay per-carcode.

This drills to real part-type leaves for TWO carcodes of one model-year and diffs
the part numbers per group, tagging each group invariant vs engine-variant. Free,
~a few dozen requests, must run from an unblocked GitHub-Actions Azure IP.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import config  # noqa: E402
import parsers  # noqa: E402
from proxy_manager import ProxyManager  # noqa: E402
from ra_client import RAClient  # noqa: E402

INVARIANT_HINT = ("brake", "body", "lamp", "electrical", "suspension", "wheel", "steering", "interior")
VARIANT_HINT = ("engine", "cooling", "fuel", "air", "exhaust", "emission", "ignition", "belt", "transmission")


def fetch(client, node):
    if node.get("href"):
        return client.get(node["href"])
    if node.get("jsn"):
        return client.fetch_children(node, max_group_index=363)
    return ""


def kids(client, node, want=None):
    ns = parsers.parse_nav(fetch(client, node))
    return ([n for n in ns if n.get("nodetype") == want] if want else ns)


def skus_for_group(client, carnode_group):
    """All part numbers under one group of one carcode (drill group->parttypes->listings)."""
    out = {}
    for pt in kids(client, carnode_group, "parttype"):
        frag = fetch(client, pt)
        listings = parsers.parse_listings(frag, {"markets": ["US"]})
        pname = (pt.get("jsn") or {}).get("parttype") or pt.get("label") or "?"
        out[pname] = sorted({(l.get("part_number") or "") + "|" + (l.get("make_name") or l.get("brand_name") or "")
                             for l in listings})
    return out


def main() -> int:
    client = RAClient(ProxyManager())
    client.new_session()
    makes = [n for n in parsers.parse_nav(client.get(config.CATALOG_ROOT)) if n.get("nodetype") == "make"]
    make = next((m for m in makes if "honda" in ((m.get("href") or "") + str(m.get("make") or "")).lower()), makes[0])
    print(f"make: {make.get('make')}")

    # find a model-year with >=2 carcodes (engines)
    pair = None
    for y in kids(client, make, "year")[:8]:
        for mo in kids(client, y, "model")[:6]:
            ccs = kids(client, mo, "carcode")
            if len(ccs) >= 2:
                pair = (y.get("year"), mo.get("model"), ccs[0], ccs[1])
                break
        if pair:
            break
    if not pair:
        print("!! no model-year with 2+ engine carcodes found"); return 1
    yr, model, ccA, ccB = pair
    print(f"model-year: {model} {yr}  carcodeA={ccA.get('carcode')} carcodeB={ccB.get('carcode')} "
          f"engines={ccA.get('engine')!r} vs {ccB.get('engine')!r}\n")

    groupsA = {(g.get("jsn") or {}).get("groupname") or g.get("label"): g for g in kids(client, ccA, "groupname")}
    groupsB = {(g.get("jsn") or {}).get("groupname") or g.get("label"): g for g in kids(client, ccB, "groupname")}
    shared = [g for g in groupsA if g in groupsB]
    print(f"shared groups: {len(shared)}")

    invariant = variant = 0
    # probe a handful: some invariant-hint, some variant-hint
    picks = ([g for g in shared if any(h in g.lower() for h in INVARIANT_HINT)][:3] +
             [g for g in shared if any(h in g.lower() for h in VARIANT_HINT)][:2])
    for gname in picks:
        skA = skus_for_group(client, groupsA[gname])
        skB = skus_for_group(client, groupsB[gname])
        pts = sorted(set(skA) | set(skB))
        same = sum(1 for p in pts if skA.get(p) == skB.get(p))
        tag = "INVARIANT" if same == len(pts) and pts else "ENGINE-VARIANT"
        if tag == "INVARIANT":
            invariant += 1
        else:
            variant += 1
        print(f"  [{tag:14}] group {gname!r}: {len(pts)} part-types, {same}/{len(pts)} identical across engines")

    print(f"\n===== VERDICT =====")
    print(f"invariant groups: {invariant} | engine-variant groups: {variant}")
    if invariant > 0:
        print("engine-dedup is REAL: invariant groups can be fetched once per model-year. "
              "Fetch each group for both carcodes and diff at load time; keep failing groups per-carcode.")
    else:
        print("no invariant groups seen in this sample — widen the sample or keep per-carcode (cost drifts up).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
