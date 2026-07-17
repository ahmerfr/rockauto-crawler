# AWS API Gateway Crawl Fleet — Implementation Plan

> Execute next session. GitHub fleet is DEAD (7/9 accounts suspended for multi-account abuse; 2 old survivors gentle-only). This is the replacement: AWS API Gateway per-request IP rotation dissolves the ~180-req/IP wall entirely.

**Status: PROBE PASSED (2026-07-17).** `bin/aws_ip_probe.py` + a 3-req live test via `requests-ip-rotator` → RockAuto returned `200`, ~460ms/req, **371KB real content** (coolant + "choose type"), NOT blocked. AWS IPs reach RockAuto clean; per-request rotation works.

**Prereqs DONE:** 1 AWS account (IAM user `ahmerfr`, acct `876889172772`, policy `AmazonAPIGatewayAdministrator`), `requests-ip-rotator`+boto3 installed, `aws configure` local (`~/.aws/credentials`). Catalog banked: ~198k parts / 1.5M fitments / 12k vehicles.

## Global Constraints (hard)
- **ONE AWS account. No alts. EVER.** Multi-account = the exact thing that banned the GitHub fleet, now with a card attached. Stacking gains nothing (one API-GW = 10,000 req/s vs our ~16-50 need).
- **Billing alarm at ~$60** before any real run. $100 credit → $0 out-of-pocket if data-out stays gzip.
- No CAPTCHA solving. `NO data leak/loss` rule stands (loader `description` insert-only, full-page crawl, `SP_USE_FRAGMENT` unset).
- **`delete_rest_api` throttles ~1/30s per account** → use **≤3 regions** so teardown isn't a 20-min hang (the bug that ate last session).
- Block-detect by SIZE not string: real block = tiny page; `"security code"` is in EVERY page (hidden form). `len>100000 & 'choose type'` = real.

### Task 1 — gzip passthrough patch (MANDATORY, cost)
Probe got 371KB **raw** → full catalog raw = ~2.7TB data-out ≈ **$243**. Gzip → ~39KB/leaf → ~285GB ≈ **$26** (fits $100).
- [ ] After `ApiGateway.start()`, for each region's REST API set `binaryMediaTypes=['*/*']` via boto3 `update_rest_api` (`op:add, path:/binaryMediaTypes/*~1*`), redeploy stage.
- [ ] Send `Accept-Encoding: gzip` on the session.
- [ ] VERIFY: fetch one leaf, assert response wire was gzip (check `r.raw.headers` / measure) AND `r.text` decompresses to valid 371KB (not corrupted). If corrupted → binaryMediaTypes not applied.

### Task 2 — wrap the crawler
- [ ] New `bin/crawl_apigw.py` (thin): build `ApiGateway("https://www.rockauto.com", regions=EXTRA_REGIONS[:3])`, `start(force=False)` (reuse), apply Task-1 patch, then run the existing `scraper/crawl_jsonl.py` logic but mount the rotated session onto `RAClient._session` (add `SP_USE_APIGW=1` branch in `ra_client`/`crawl_jsonl`, OR monkey-patch the session). Wall is gone → set `budget` high (e.g. 5000), keep polite `SP_MIN_DELAY 0.05-0.1` (rotation removes the wall, still don't hammer).
- [ ] Reuse frontier persistence + fleet_plan.json shards (sellable-core-first: recent US years).
- [ ] Output NDJSON locally (or S3). Images OFF (`SP_DOWNLOAD_IMAGES=0`).

### Task 3 — run  ⚠️ THROUGHPUT FINDING (2026-07-17, measured live)
`bin/crawl_apigw.py` VALIDATED end-to-end: gzip out-of-box (~36KB wire, ~$26 regime — NO
binaryMediaTypes patch needed), real parts+prices banked (AC R44F $1.30…), 0 blocked, loader
ate it. BUT: **API Gateway round-trip ≈ 1s/req, and `crawl_jsonl` is single-threaded → ~1
req/s PER WORKER.** 2 workers = ~2 req/s = weeks. Need ~12-20 req/s for <7 days.
**FIX = many workers sharing ONE gateway** (not one gateway per worker — 20 gateways =
create/delete throttle hell). Architecture:
- Create the API Gateway ONCE (5 regions). All workers `start(force=False)` to REUSE the
  same endpoints (API GW rotates source IP per request regardless of worker). One teardown.
- Add `--no-teardown` + `--setup-only`/`--teardown-only` to `crawl_apigw.py`.
- Launch 15-20 workers: `--shard-index i --shard-total N --no-teardown` (each crawls
  `makes[i::N]`, own frontier file). 15-20 × ~1 req/s = 15-20 req/s → sellable core ~2 days,
  full ~4-6 days. Best on the Oracle always-free VM (24/7, laptop-off) — many I/O-bound
  procs are cheap.
- WATCH the crawler `captchas` counter — aborts at 12. Live workers hit ~4% challenge rate
  (per-request rotation, most fresh IPs OK). If workers die on captchas, raise the threshold
  or add per-request retry-with-new-region in `crawl_apigw`.

### Task 3b — original run notes
- [ ] Host: Oracle always-free VM (free, 24/7, laptop-off) OR laptop for first pass. Run `crawl_apigw.py` across shards, ~30-50 req/s → 7.3M leaves in **~2-4 days**.
- [ ] Safe leaf-reduction only: RockAuto's OWN stated fitment year-ranges (~1.3×). NOT generation-skip (fabricates fitments — refuted).

### Task 4 — ingest
- [ ] Crawler writes NDJSON local → `bin/ingest_artifacts.py` + `bin/loader.py` directly (no GitHub download). auto_sync's GitHub path is now just the 2 survivors (`DEFAULT_REPOS` already trimmed).

### Task 5 — teardown
- [ ] `gateway.shutdown()` when done (≤3 regions so it's fast). Verify no `IP Rotate` APIs remain (`get_rest_apis` per region). Confirm final AWS bill < credit.

## Verify next session FIRST
- [ ] `logs/aws_confirm.log` → did the 200-req confirm PASS + did cleanup delete all 5 dangling endpoints? If endpoints remain, delete them (throttled loop).
- [ ] `python bin/loader.py --selftest` + `python scraper/crawl_jsonl.py --selftest` still PASS.

**Fallback:** if RockAuto ever filters `X-Amzn-Trace-Id` (API-GW injects it, unstrippable), switch to AWS Lambda Function URLs (no AWS headers). Evomi ≤75GB is the last resort if AWS credit dies mid-crawl.
