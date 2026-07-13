"""bytes_probe.py — measure the REAL billed bytes/request, FREE, before buying any proxy.

Residential proxies bill the gzipped WIRE bytes (both directions). Those bytes are
identical whether fetched from a free GitHub Azure IP or a paid residential IP — so
we can pin the exact full-catalog GB (and $) for $0, then buy precisely that much.

Drills to real part-type LEAF nodes and, for a sample, records the gzipped response
size (Content-Length) + request-body size per leaf, then extrapolates to the crawl.
Runs on an unblocked GitHub-Actions Azure IP.
"""
from __future__ import annotations

import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import config  # noqa: E402
import parsers  # noqa: E402
from proxy_manager import ProxyManager  # noqa: E402
from ra_client import RAClient  # noqa: E402

FULL_REQ = 5_700_000          # post images-off + year-twin dedup floor
DEDUP_REQ = 3_800_000         # ~1.5x partial engine-dedup (conservative)
RATE = 0.99                   # Evomi PAYG $/GB
VAT = 1.17                    # Pakistan VAT approx


def fetch(client, node):
    if node.get("href"):
        return client.get(node["href"])
    if node.get("jsn"):
        return client.fetch_children(node, max_group_index=363)
    return ""


def kids(client, node, want=None):
    ns = parsers.parse_nav(fetch(client, node))
    return [n for n in ns if n.get("nodetype") == want] if want else ns


def leaf_wire(client, ptnode):
    """Fetch one part-type leaf via the WORKING fetch_children path; measure the
    gzipped fragment (~= billed response wire) + the request-out body."""
    frag = client.fetch_children(ptnode, max_group_index=363) or ""
    raw = frag.encode("utf-8", "ignore")
    decomp = len(raw)
    wire = len(gzip.compress(raw)) if raw else 0          # gzipped response ~= billed down-bytes
    jsn = dict(ptnode.get("jsn") or {}); jsn["max_group_index"] = 363
    req_out = len(json.dumps(jsn)) + len(client._nck or "") + 120   # POST body up-bytes
    listings = parsers.parse_listings(frag, {"markets": ["US"]})
    return wire, decomp, req_out, len(listings)


def main() -> int:
    client = RAClient(ProxyManager())
    client.new_session()
    makes = [n for n in parsers.parse_nav(client.get(config.CATALOG_ROOT)) if n.get("nodetype") == "make"]
    make = next((m for m in makes if "acura" in ((m.get("href") or "") + str(m.get("make") or "")).lower()), makes[0])

    # collect real part-type leaves across a few vehicles
    leaves = []
    for y in kids(client, make, "year")[:3]:
        for mo in kids(client, y, "model")[:3]:
            for cc in kids(client, mo, "carcode")[:1]:
                for g in kids(client, cc, "groupname")[:4]:
                    for pt in kids(client, g, "parttype")[:3]:
                        leaves.append(pt)
                        if len(leaves) >= 40:
                            break
                    if len(leaves) >= 40:
                        break
            if len(leaves) >= 40:
                break
        if len(leaves) >= 40:
            break
    print(f"measuring {len(leaves)} real part-type leaf fetches...\n")

    tot_wire = tot_dec = tot_out = tot_list = 0
    n = 0
    for pt in leaves:
        try:
            wire, dec, out, nl = leaf_wire(client, pt)
        except Exception as exc:  # noqa: BLE001
            print("  leaf err:", exc); continue
        tot_wire += wire; tot_dec += dec; tot_out += out; tot_list += nl; n += 1
    if not n:
        print("!! no leaves measured"); return 1

    avg_wire = tot_wire / n; avg_dec = tot_dec / n; avg_out = tot_out / n; avg_list = tot_list / n
    # residential billed ~= gzipped response wire + request-out + ~0.8KB TLS/header overhead
    billed = avg_wire + avg_out + 800
    print(f"per-leaf: gzip_wire={avg_wire/1024:.1f}KB  decompressed={avg_dec/1024:.1f}KB  "
          f"req_out={avg_out/1024:.1f}KB  listings/leaf={avg_list:.1f}")
    print(f"=> effective BILLED bytes/req ~= {billed/1024:.1f}KB (wire + request + overhead)\n")

    for label, reqs in (("FULL 5.7M", FULL_REQ), ("dedup ~3.8M", DEDUP_REQ)):
        gb = reqs * billed / 1e9
        usd = gb * RATE
        print(f"{label}: {gb:.1f} GB  ->  ${usd:.0f} PAYG  (${usd*VAT:.0f} w/ Pakistan VAT)  "
              f"[under $30: {'YES' if usd*VAT <= 30 else 'NO'}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
