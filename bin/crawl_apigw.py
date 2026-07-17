#!/usr/bin/env python
"""crawl_apigw.py — run the RockAuto crawler through AWS API Gateway per-request IP
rotation (requests-ip-rotator), which dissolves the ~180-req/IP wall entirely.

Replaces the (now-banned) GitHub Actions fleet. ONE AWS account only — no alts.
The gateway assigns a fresh AWS-pool source IP per request, so the crawler needs no
proxy rotation and no fresh-runner churn. Frontier persistence + fleet_plan shards reused.

    python bin/crawl_apigw.py --only-makes ac --budget 30            # small live test
    python bin/crawl_apigw.py --only-makes chevrolet --budget 5000   # real shard

Cost note: API Gateway data-out is the bill driver. If responses come back RAW (~370KB
/leaf) instead of gzip (~39KB), the full catalog costs ~$243 vs ~$26. Run --check-gzip to
see which regime you're in; if RAW, the gzip binaryMediaTypes patch is needed (see plan).
"""
import argparse
import os
import sys

os.environ.setdefault("SP_USE_PROXIES", "0")      # gateway handles IPs; no proxy rotation
os.environ.setdefault("SP_DOWNLOAD_IMAGES", "0")  # images fetched separately (not IP-walled)
os.environ.setdefault("SP_YEAR_MIN", "1900")      # ALL years (default 2010-2024 drops vintage)
os.environ.setdefault("SP_YEAR_MAX", "2035")
os.environ.setdefault("SP_MARKETS", "")           # worldwide
os.environ.setdefault("SP_MAX_BLOCKED", "60")     # per-request IP rotation = transient blocks
os.environ.setdefault("SP_MAX_CAPTCHAS", "500")   # don't abort a worker on rotation noise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

SITE = "https://www.rockauto.com"


def _mount_gateway(gw):
    """Mount the API Gateway adapter on EVERY RAClient session — the initial one and any
    rebuilt on rotation — so all requests egress through a fresh AWS IP."""
    import ra_client
    orig = ra_client.RAClient._build_session

    def build(self):
        s = orig(self)
        s.mount(SITE, gw)
        s.headers["Accept-Encoding"] = "gzip"
        return s
    ra_client.RAClient._build_session = build


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-makes", default=None, help="comma list (e.g. ac,chevrolet)")
    ap.add_argument("--shard-index", type=int, default=0, help="this worker's slice")
    ap.add_argument("--shard-total", type=int, default=1, help="total parallel workers (makes[i::N])")
    ap.add_argument("--budget", type=int, default=30)
    ap.add_argument("--max-seconds", type=int, default=600)
    ap.add_argument("--out", default="artifacts/apigw_test.ndjson")
    ap.add_argument("--regions", type=int, default=3)
    ap.add_argument("--min-delay", default="0.05")
    ap.add_argument("--max-delay", default="0.15")
    ap.add_argument("--frontier-file", default=None)
    ap.add_argument("--frontier-out", default=None)
    ap.add_argument("--check-gzip", action="store_true",
                    help="fetch one leaf, report whether the wire was gzip (cost regime)")
    ap.add_argument("--setup-only", action="store_true",
                    help="create the shared gateway endpoints and exit (no crawl, no teardown)")
    ap.add_argument("--teardown-only", action="store_true",
                    help="delete ALL 'IP Rotate' endpoints across all regions and exit")
    ap.add_argument("--no-teardown", action="store_true",
                    help="worker mode: reuse the shared gateway, do NOT delete it on exit")
    a = ap.parse_args()

    from requests_ip_rotator import ApiGateway, EXTRA_REGIONS
    if a.teardown_only:
        import boto3, time as _t
        for reg in EXTRA_REGIONS:
            c = boto3.client("apigateway", region_name=reg)
            for x in c.get_rest_apis().get("items", []):
                if "IP Rotate" in x.get("name", ""):
                    for _ in range(12):
                        try:
                            c.delete_rest_api(restApiId=x["id"]); print(reg, "deleted", flush=True); break
                        except Exception as e:  # noqa: BLE001
                            if "TooMany" in str(e) or "Rate exceeded" in str(e): _t.sleep(31)
                            else: print(reg, str(e)[:45], flush=True); break
        print("teardown done", flush=True); return 0
    os.environ["SP_MIN_DELAY"] = a.min_delay
    os.environ["SP_MAX_DELAY"] = a.max_delay

    gw = ApiGateway(SITE, regions=EXTRA_REGIONS[:a.regions])
    print(f"[apigw] starting {a.regions} region(s) (reuse if present)...", flush=True)
    gw.start(force=False)
    if a.setup_only:
        print("[apigw] setup-only: shared endpoints live. Launch workers with --no-teardown. "
              "Not deleting.", flush=True)
        return 0
    _mount_gateway(gw)
    print("[apigw] gateway mounted on crawler session.", flush=True)

    try:
        if a.check_gzip:
            import requests
            s = requests.Session(); s.mount(SITE, gw); s.headers["Accept-Encoding"] = "gzip"
            leaf = SITE + "/en/catalog/ac,1947,two-litre,2.0l+122cid+l6,1486554,cooling+system,coolant+/+antifreeze,11393"
            r = s.get(leaf, timeout=20)
            enc = r.headers.get("Content-Encoding", "(none)")
            wire = int(r.headers.get("Content-Length", 0)) or len(r.content)
            print(f"[gzip-check] status={r.status_code} Content-Encoding={enc} "
                  f"wire~{wire//1024}KB decoded={len(r.text)//1024}KB "
                  f"-> {'GZIP (cheap ~$26)' if 'gzip' in enc.lower() else 'RAW (need binaryMediaTypes patch, ~$243)'}",
                  flush=True)
            return 0

        import crawl_jsonl
        only = [m.strip().lower() for m in a.only_makes.split(",")] if a.only_makes else None
        print(f"[apigw] crawling only_makes={only} budget={a.budget}...", flush=True)
        stats = crawl_jsonl.run(a.shard_index, a.shard_total, a.out, budget=a.budget,
                                max_seconds=a.max_seconds, only_makes=only,
                                frontier_file=a.frontier_file, frontier_out=a.frontier_out)
        print(f"[apigw] done: {stats}", flush=True)
        return 0
    finally:
        if a.no_teardown:
            print("[apigw] --no-teardown: leaving shared endpoints up for other workers.", flush=True)
            return 0
        print("[apigw] shutdown (deleting endpoints)...", flush=True)
        try:
            gw.shutdown()
        except Exception as exc:  # noqa: BLE001
            print(f"[apigw] shutdown warning: {exc} (check API Gateway console for leftovers)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
