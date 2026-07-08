# Runbook — Free full-catalog RockAuto crawl via GitHub Actions

Your machine's IP gets blocked by RockAuto after a few hundred requests, and free
proxies can't beat it. The free way to crawl the **whole** catalog is to borrow
GitHub Actions' fresh Azure IPs: each matrix job = a new IP crawling a disjoint
slice of makes, OCR-solving the securimage wall when it appears. Staged rows come
back as NDJSON artifacts that you load locally.

## One-time setup
1. Put this project in a **public** GitHub repo (public = unlimited free Actions
   minutes; private = 2,000 min/month cap).
   ```
   git init && git add -A && git commit -m "RockAuto crawler"
   gh repo create rockauto-crawler --public --source=. --push
   ```
2. That's it — `.github/workflows/crawl.yml` is already in place.

## Run a crawl
1. GitHub → your repo → **Actions** → **RockAuto Crawl Fleet** → **Run workflow**.
   Inputs:
   - `shards`: parallel jobs (default 20 — GitHub free tier's concurrency ceiling).
   - `budget`: requests per job (default 400 — keep each IP polite/under the block threshold).
   - `max_seconds`: per-job runtime (default 18000 = 5h; hard ceiling is 6h).
2. Each job crawls makes `[shard_index :: shard_total]`, so 20 jobs split all
   ~350 makes. Watch progress live in the Actions UI.
3. When done, open the run → **Artifacts** → download each `rockauto-shard-*`
   (or `gh run download <run-id> -D artifacts`).

## Load the data locally
```bash
# 1. make sure MariaDB is up (XAMPP, port 3307)
# 2. stage the artifacts into stg_listings
python bin/ingest_artifacts.py artifacts/**/shard-*.ndjson
# 3. canonicalize staging -> parts/vehicles/fitment (idempotent; dedupes on sku)
python bin/loader.py
```
Re-running is safe: the loader upserts on the deterministic `sku`
(`slug(brand)-slug(part_number)`), so duplicate rows across shards/runs merge.

## Covering the whole catalog
- One run of 20 shards makes a big dent but won't finish the millions of leaf
  listings in a single pass (each job stops at its `budget`/time cap or when its
  IP is burned).
- Re-run the workflow (or enable the `schedule:` cron in `crawl.yml`) — each run
  gets **fresh IPs** and re-crawls the shards; the loader dedupes, so coverage
  accumulates over successive runs.
- To go wider, raise `shards` in successive runs and/or increase `budget`
  cautiously. Watch the job logs for `[stop] IP appears burned` — that shard just
  needs another run on a new IP.

## Tuning / knobs (env vars, all optional)
| Var | Default | Meaning |
|-----|---------|---------|
| `SP_JOB_BUDGET` | 400 | requests per job before it stops |
| `SP_JOB_MAX_SECONDS` | 18000 | per-job runtime cap |
| `SP_MIN_DELAY` / `SP_MAX_DELAY` | 3 / 6 | polite delay between requests (seconds) |
| `SP_SOLVE_CAPTCHA` | 1 | OCR-solve securimage walls (needs tesseract; the workflow installs it) |
| `SP_CAPTCHA_ATTEMPTS` | 5 | fresh-code retries per wall |
| `SP_YEAR_MIN` / `SP_YEAR_MAX` | 2010 / 2024 | year range in `scraper/config.py` SCOPE (widen for more) |

To crawl **every** year, set `SP_YEAR_MIN`/`SP_YEAR_MAX` wide (e.g. 1980–2026) in
the workflow `env:` block, and clear the `categories`/`makes` filters in
`scraper/config.py` SCOPE (empty list = all).

## Honest expectations
- **securimage OCR** solve rate is partial per image (~30–60%), but the crawler
  requests fresh codes up to `SP_CAPTCHA_ATTEMPTS` times, which compounds the odds.
- **GitHub IP reuse**: some Azure IPs are already captcha-tainted by other
  scrapers; those shards abort cleanly and succeed on a later run's fresh IP.
- **Not instant**: full catalog = many scheduled runs over days, but it's free,
  resumable, and hands-off once scheduled.
- This is unverified end-to-end against the live site (your IP is blocked right
  now); the first real GitHub run is the true test. Start with a small `shards`/
  `budget` to confirm rows land before scaling up.
