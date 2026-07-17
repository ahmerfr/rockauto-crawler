# AWS EC2 Swarm Runbook — full RockAuto catalog in ~1 day (laptop-free)

Oracle's free ARM VM was out of capacity (Chicago = 1 AD, no fallback). This pivots
compute to a big AWS EC2 in the **same account** already used for API-Gateway IP
rotation. One cloud, one account, ~$40-55 of your $180 credit, **$0 out of pocket**.

## Why this hits ~1 day (the old fleet couldn't)
The crawler does **1 request at a time per process (~1 req/s)** and used to shard by
whole car-brand — so the biggest brand (Chevrolet ~10% of the catalog) was stuck on a
single 1-req/s worker ≈ 7 days by itself. The swarm fixes this: the catalog is split
into **5,454 (make × year-band) units** — disjoint + complete (proven live +
`crawl_apigw.py --selftest`) — dealt across ~150-250 lanes. Aggregate ≈ 150-250 req/s.
**The crawl/write loop is untouched**; units are fed only via `--only-makes` +
`SP_YEAR_MIN/MAX` env (the year-band mechanism the old GitHub fleet already proved).

- 150 lanes → ~150 req/s → full catalog **~13-30 h** (catalog est. 7-16M leaves).
- 250 lanes → ~250 req/s → **~8-18 h**.

## 1. Launch the EC2  *(you — one-time, ~5 min)*
1. **EC2 → Launch instance.** Region **us-east-1**.
2. AMI: **Ubuntu Server 22.04 (ARM / 64-bit Arm)**.
3. Instance type: **c7g.8xlarge** (32 vCPU, 64 GB — best for ~250 lanes). Cheaper option:
   **c7g.4xlarge** (16 vCPU, 32 GB) → run ~150 lanes.
4. Key pair: create/download (for SSH).
5. Storage: **100 GB gp3** (NDJSON accumulates — default 8 GB will fill).
6. Network: default security group is fine — the crawler only makes **outbound** requests.
7. Launch. Note the **Public IP**.

## 2. SSH in + install  *(you — paste this block)*
```bash
ssh -i your-key.pem ubuntu@<VM_PUBLIC_IP>
sudo apt update && sudo apt install -y python3-pip git awscli
pip3 install --user requests lxml beautifulsoup4 boto3 requests-ip-rotator
git clone https://github.com/ahmerfr/rockauto-crawler.git
cd rockauto-crawler
aws configure    # paste AWS key id + secret, region us-east-1 — stays on the VM only
```

## 3. (Optional) 60-sec confidence check
```bash
python3 bin/crawl_apigw.py --selftest        # unit plan disjoint + complete (offline)
python3 bin/crawl_apigw.py --check-gzip --regions 1   # expect GZIP (cheap ~$26 regime)
python3 bin/crawl_apigw.py --teardown-only            # clean that probe endpoint
```

## 4. Launch the swarm  *(you)*
```bash
# c7g.8xlarge (64 GB): 250 lanes.  c7g.4xlarge (32 GB): use WORKERS=150.
WORKERS=250 nohup bash bin/crawl_apigw_fleet.sh > logs/fleet.log 2>&1 &
```
- Builds the shared gateway (5 regions) + the 5,454-unit plan (`units.tsv`), then deals
  units across the lanes. Survives SSH disconnect.
- Each lane writes `out/s<lane>_<make>_<band>_c<chunk>.ndjson`, resumes via
  `fr/f<lane>_<...>.ndjson`, and marks `fr/done_<lane>_<...>` when a unit drains.

## 5. Watch hour 1, then scale  *(the "escalate if slow" step)*
```bash
# aggregate throughput (requests/sec across all lanes, last ~min):
grep -h '\[result\]' logs/w*.log | tail -50
# captcha/block health — should stay near 0. If it climbs, you're being throttled:
grep -h 'captchas=' logs/w*.log | tail -20
# progress:
ls out/*.ndjson | wc -l ;  cat out/*.ndjson | wc -l   # files / total listings
```
- **Clean (captchas ~0)** → you can push harder: raise `WORKERS` (kill + relaunch) or
  the box size. **Captchas climbing** → RockAuto is throttling; drop `WORKERS` and accept
  ~1.5-2 days. This is the honest unknown — 150-250 req/s at RockAuto is untested at scale.

## 6. Stop when done  *(IMPORTANT — teardown or endpoints linger)*
```bash
touch STOP_CRAWL                              # lanes finish current chunk + exit
python3 bin/crawl_apigw.py --teardown-only    # delete the shared API Gateway endpoints
```

## 7. Ingest into the storefront  *(laptop, whenever — crawl keeps running regardless)*
```bash
# on the VM: bundle first (thousands of small files → one transfer)
tar czf out.tgz out/
# on the LAPTOP:
scp -i your-key.pem ubuntu@<VM_PUBLIC_IP>:rockauto-crawler/out.tgz .
tar xzf out.tgz
python bin/ingest_artifacts.py out/*.ndjson --batch ec2
python bin/loader.py
```
Loader dedups (by SKU) and `description` is insert-only — re-running step 7 never loses
or clobbers data. Pull as often as you like.

## Cost + safety
- **Compute:** c7g.8xlarge ~$1.16/h → ~$28/day. c7g.4xlarge ~$0.58/h → ~$14/day.
- **Gateway data-out:** ~$26 (gzip). **Total ~$40-55**, covered by your $180 credit. Set an
  **AWS Budgets alarm at ~$70** (Billing → Budgets).
- **ONE AWS account. No alts.** (Multi-account is what killed the GitHub fleet.)
- **Kill switch:** `touch STOP_CRAWL`. Frontier + `fr/done_*` markers make everything
  resumable — a crash/reboot re-runs `bash bin/crawl_apigw_fleet.sh` and skips finished units.
- **No data loss by design:** disjoint+complete unit plan (asserted), distinct out file per
  chunk (never truncates), crawl/write loop unchanged, loader dedup + insert-only description.
