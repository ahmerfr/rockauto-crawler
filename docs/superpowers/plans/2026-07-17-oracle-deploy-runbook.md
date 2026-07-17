# Oracle Deploy Runbook — 30-worker AWS-rotation crawl fleet (24/7, laptop-free)

The crawl runs entirely on a free Oracle VM using your one AWS account's API Gateway for
per-request IP rotation. Laptop only needed later to pull data into the storefront DB.
Code lives at `https://github.com/ahmerfr/rockauto-crawler` (pushed).

## 1. Create the Oracle always-free VM  *(you — one-time, ~10 min)*
1. Sign up at **cloud.oracle.com** → "Always Free". (Card for identity check; $0 charged on Always-Free shapes.)
2. **Compute → Instances → Create instance.**
   - Image: **Ubuntu 22.04**.
   - Shape: **Ampere (VM.Standard.A1.Flex)** — set **4 OCPU / 24 GB** (all Always-Free).
   - Add your **SSH public key**.
   - Create. Note the **Public IP**.
3. No inbound ports needed — the crawler only makes *outbound* requests.
   *(If "out of capacity" for A1.Flex, retry another availability domain, or use a smaller VM.Standard.E2.1.Micro AMD free shape with WORKERS=15.)*

## 2. SSH in + install  *(you — paste this block)*
```bash
ssh ubuntu@<VM_PUBLIC_IP>
sudo apt update && sudo apt install -y python3-pip git awscli
pip3 install --user requests lxml beautifulsoup4 boto3 requests-ip-rotator
git clone https://github.com/ahmerfr/rockauto-crawler.git
cd rockauto-crawler
aws configure    # paste AWS key id + secret, region us-east-1 — stays on the VM only
```

## 3. (Optional) confirm before scaling  *(30 sec)*
```bash
python3 bin/crawl_apigw.py --check-gzip --regions 1
# expect: status=200 Content-Encoding=gzip -> GZIP (cheap ~$26)
python3 bin/crawl_apigw.py --teardown-only   # clean that 1 probe endpoint
```

## 4. Launch the fleet  *(you)*
```bash
nohup bash bin/crawl_apigw_fleet.sh > logs/fleet.log 2>&1 &
```
- 30 workers, 1 shared gateway (5 regions), 24/7, survives SSH disconnect.
- Monitor: `tail -f logs/w0.log` → look for `[progress] nodes=… listings=… new_leaves=…`.
- Tune workers: `WORKERS=20 bash bin/crawl_apigw_fleet.sh` (default 30).

## 5. Stop when done  *(you — IMPORTANT: teardown or endpoints linger)*
```bash
touch STOP_CRAWL                              # workers finish current chunk + exit
python3 bin/crawl_apigw.py --teardown-only    # delete the AWS API Gateway endpoints
```

## 6. Ingest into the storefront  *(laptop, whenever — crawl keeps running regardless)*
```bash
# on the LAPTOP:
scp -r ubuntu@<VM_PUBLIC_IP>:rockauto-crawler/out ./oracle_out
python bin/ingest_artifacts.py oracle_out/*.ndjson --batch oracle
python bin/loader.py
```
Data is safe on the VM until you pull it; re-run steps 6 as often as you like (loader dedups).

## Cost + safety
- **AWS:** ~$26–58 total for the full catalog (gzip data-out). Your **$180 credit** covers it. Set an **AWS Budgets alarm at ~$60** (Billing → Budgets).
- **ONE AWS account, ONE Oracle account. No alts** (that killed the GitHub fleet).
- **ETA:** 30 workers × ~1 req/s ≈ 30 req/s → full catalog **~2–3 days**, laptop-free.
- Kill switch: `touch STOP_CRAWL` on the VM. Frontier (`fr/*.ndjson`) makes everything resumable.
