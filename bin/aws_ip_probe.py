#!/usr/bin/env python
"""aws_ip_probe.py — make-or-break check BEFORE building the AWS crawl fleet.

Fires 220 requests (> the measured ~180-req/IP wall) at ONE RockAuto leaf through AWS
API Gateway's per-request IP rotation. If the wall is truly dissolved (fresh AWS IP per
request), all 220 succeed with zero CAPTCHA blocks — proving:
  1. AWS's IP pool is NOT pre-blocked by RockAuto, and
  2. per-request rotation removes the volume wall entirely.

Costs ~nothing (~220 API Gateway calls + a few MB) and self-cleans the endpoints.
Needs: `pip install requests-ip-rotator` + AWS creds via `aws configure` (never pasted
in chat — boto3 reads ~/.aws/credentials locally; this script never sees the secret).

    python bin/aws_ip_probe.py
"""
import time

TARGET = "https://www.rockauto.com"
LEAF = "/en/catalog/ac,1947,two-litre,2.0l+122cid+l6,1486554,cooling+system,coolant+/+antifreeze,11393"
N = 220  # deliberately > the ~180 single-IP wall, to prove rotation dissolves it


def main() -> int:
    try:
        from requests_ip_rotator import ApiGateway, EXTRA_REGIONS
        import requests
    except ImportError:
        print("!! pip install requests-ip-rotator first"); return 2

    regions = EXTRA_REGIONS[:5]
    print(f"[probe] creating API Gateway endpoints in {len(regions)} regions "
          f"(needs AWS creds from `aws configure`)...")
    gw = ApiGateway(TARGET, regions=regions)
    try:
        gw.start(force=True)
    except Exception as exc:  # noqa: BLE001
        print(f"!! could not start API Gateway: {exc}\n"
              f"   -> check `aws configure` ran + the IAM user has apigateway + "
              f"iam:CreateServiceLinkedRole permissions.")
        return 2

    s = requests.Session()
    s.mount(TARGET, gw)
    ok = block = err = 0
    try:
        for i in range(N):
            try:
                r = s.get(TARGET + LEAF, timeout=30)
                low = r.text.lower()
                if "security code" in low or "are you a human" in low or "verify you are" in low:
                    block += 1
                elif r.status_code == 200 and ("choose type" in low or "coolant" in low or "listing" in low):
                    ok += 1
                else:
                    err += 1
            except Exception:  # noqa: BLE001
                err += 1
            if i % 40 == 39:
                print(f"  [{i+1}/{N}] ok={ok} blocked={block} err={err}")
            time.sleep(0.3)   # polite
    finally:
        print(f"\n[probe] RESULT: ok={ok}  blocked={block}  err={err}  (of {N})")
        verdict = ("PASS ✅ — AWS IPs reach RockAuto and the ~180-req wall is DISSOLVED "
                   "(per-request rotation works). Safe to build the fleet."
                   if ok > 180 and block == 0 else
                   "REVIEW ⚠️ — see counts above (blocks>0 = AWS IPs filtered; many err = "
                   "gzip/parse or region issue).")
        print("[probe] VERDICT:", verdict)
        print("[probe] tearing down API Gateway endpoints (cleanup)...")
        try:
            gw.shutdown()
        except Exception as exc:  # noqa: BLE001
            print(f"   (shutdown warning: {exc} — check API Gateway console for leftover 'ip-rotator' APIs)")
    return 0 if (ok > 180 and block == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
