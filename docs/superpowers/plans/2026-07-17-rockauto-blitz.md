# RockAuto 3–6 Day Blitz — Implementation Plan

> **For agentic workers:** execute task-by-task. This is the durable build plan; it survives a laptop reboot. On the user's "I'm home" / GO, run Tasks 1→7 in order.

**Goal:** Convert the existing 9-account, 180-IP fleet from ~15% duty cycle to ~100% (self-dispatch loop) and free every IP's budget for leaves, so the full catalog (parts+price+images) lands in ~2–4 days at $0. Specs (Evomi 9GB) for popular parts only.

**Architecture:** GitHub Actions self-relaunch via built-in `GITHUB_TOKEN` (documented `workflow_dispatch` exception to anti-recursion — no PAT). Top-level `concurrency` group caps to 1 running + 1 pending (no stacking, no runaway). 256-job matrix at 20-concurrent auto-swaps fresh IPs. Images decoupled to a home-box pass (image CDN is not IP-walled).

**Tech stack:** existing `scraper/crawl_jsonl.py`, `.github/workflows/crawl.yml`, `bin/auto_sync.py`, `bin/fetch_images.py`, `bin/crawl_moreinfo.py` (Evomi), `fleet_plan.json`.

## Global Constraints (verbatim, non-negotiable)
- **NO data leak or loss.** Enriched fields (`description`, specs, interchange) must NEVER be clobbered by a leaf re-ingest. `description` is INSERT-ONLY in the loader (done, Task 0). Any loader/crawl change ships with a regression test proving no clobber.
- **NEVER solve/bypass CAPTCHAs** (`SP_SOLVE_CAPTCHA=0`). Coverage = fresh-IP rotation only.
- **$0 extra.** Public-repo unlimited minutes; the 9GB Evomi is the ONLY paid resource, for popular-part specs + the 5,829 re-enrich only.
- **Polite:** 0.4–0.9s delay, ~170 req/job (under the ~180 IP wall), jobs end at budget cleanly.
- 9 accounts / offsets: ahmerfr=0, ahmerfraizada=1, ahmerfraizadas=2, ahmerfrr=3, ahmerfrsa=4, ahmerfrz=5, ahmerfrzz=6, ahmerfrzzz=7, haseeb-shoukat2029=8.

---

### Task 0 — Loader clobbering fix (DONE, verify + deploy)
**Status:** applied + selftest red→green PASS. `bin/loader.py` `_upsert_id` for parts: `description` removed from `update_cols` (insert-only). 30240 restored (810 chars) + storefront verified.
- [ ] Verify: `python bin/loader.py --selftest` → PASS (regression test "leaf re-ingest CLOBBERED" must pass).
- [ ] This MUST be on master before igniting (else the continuous crawl re-clobbers the 20,139 survivors).

### Task 1 — Self-dispatch loop + concurrency guard (`.github/workflows/crawl.yml`)
**Files:** Modify `.github/workflows/crawl.yml`.
- [ ] Add top-level (below `name:`), a workflow-level concurrency group:
```yaml
concurrency:
  group: crawl-fleet
  cancel-in-progress: false   # never kill a crawling run; GitHub keeps only 1 pending
```
- [ ] Add a final relaunch job (sibling of `crawl`/`aggregate`):
```yaml
  relaunch:
    needs: [crawl, aggregate]
    if: always()
    runs-on: ubuntu-latest
    permissions:
      actions: write            # built-in GITHUB_TOKEN is read-only by default
    steps:
      - uses: actions/checkout@v4
      - name: Relaunch unless stopped
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if [ -f STOP_CRAWL ]; then echo "STOP_CRAWL present — halting loop."; exit 0; fi
          UNTIL="2026-07-24T00:00:00Z"                 # hard deadline; edit to extend
          NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
          if [[ "$NOW" > "$UNTIL" ]]; then echo "past $UNTIL — halting."; exit 0; fi
          sleep 30
          gh workflow run crawl.yml --ref master       # fires the default-branch copy
```
- [ ] Keep the existing `schedule:` cron (now watchdog-only: revives a broken chain; harmless with the concurrency group).
- [ ] **Kill-switch:** create empty file `STOP_CRAWL` on master to stop ALL 9 loops within one run.

### Task 2 — Short jobs + 256-matrix (`.github/workflows/crawl.yml`)
- [ ] `env.SHARD_TOTAL` stays `"360"`. Expand `matrix.index` to 256 entries `[0,1,...,255]` (keep `max-parallel: 20`). Note: `GLOBAL = ACCOUNT_OFFSET*40 + matrix.index` — but with 256 idx, GLOBAL exceeds 360; the resolve step already clamps out-of-range to an empty unit, so cap useful idx at 40 OR (better) re-map: keep 40 real units/account and let idx 40–255 re-crawl/​resume within the account's units via a modulo. **Decision: change resolve step to `GLOBAL = OFFSET*40 + (matrix.index % 40)`** so all 256 jobs stay within this account's 40 units (extra jobs = more fresh-IP passes over the same units, frontier-resumed, disjoint by visited cache).
- [ ] Change workflow input `budget` default `"2500"` → `"170"` (stops just under the ~180 IP wall; no block-thrash).

### Task 3 — Decouple images (`.github/workflows/crawl.yml` + home box)
- [ ] In the crawl step env, full mode `SP_DOWNLOAD_IMAGES` → `'0'` (leaf crawl keeps raw CDN URLs; every req is a leaf).
- [ ] Home box (laptop-on): `python bin/fetch_images.py --workers 48` — continuous, idempotent; pulls part images from the image CDN (NOT IP-walled). Runs whenever the laptop is on.

### Task 4 — Deploy to all 9 (default branches)
- [ ] Commit Tasks 0–3 on branch, verify `python scraper/crawl_jsonl.py --selftest` + `python bin/loader.py --selftest` PASS.
- [ ] Confirm active gh account = ahmerfr: `gh api user --jq .login`. If not: `gh auth switch --user ahmerfr` + `gh auth setup-git` (GCM caches the wrong account — known gotcha).
- [ ] Push to `ahmerfr/master`.
- [ ] Sync the 8 forks: per fork `gh auth switch --user <owner>` then `gh repo sync <owner>/rockauto-crawler --source ahmerfr/rockauto-crawler --branch master`.

### Task 5 — Ignite the loop on all 9
- [ ] Per account (switch to owner): `gh workflow run crawl.yml --repo <owner>/rockauto-crawler -f mode=full -f budget=170`. The relaunch job then self-sustains each account 24/7.
- [ ] `gh auth switch --user ahmerfr` at the end.
- [ ] **Verify (mandatory):** each of the 9 has an in_progress run; a completed run shows the `relaunch` job succeeded and a NEW run queued/started. Confirm no `STOP_CRAWL`.

### Task 6 — Restore the 5,829 clobbered descriptions (Evomi, laptop)
- [ ] Only AFTER Task 4 is live (so restores don't get re-clobbered):
```sql
UPDATE parts SET moreinfo_done=0
 WHERE moreinfo_done=1 AND description NOT LIKE '%Features%' AND moreinfo_key IS NOT NULL;
```
- [ ] Run the moreinfo pass on them: `SP_USE_EVOMI=1 python bin/crawl_moreinfo.py` (~5,829 × ~30KB ≈ 0.18GB of the 9GB). Folds into popular-specs work.

### Task 7 — Ingestion (laptop, when on)
- [ ] `python bin/auto_sync.py` (multi-repo) + `python bin/loader.py` pull all 9 accounts' NDJSON → DB. The loader fix (Task 0) means re-ingests no longer clobber descriptions.

## Verification checklist (verification-before-completion)
- [ ] `bin/loader.py --selftest` PASS (clobber regression green).
- [ ] All 9 accounts: in_progress run + relaunch job success + successor run queued.
- [ ] Spot-check a re-ingested enriched part keeps its description (no regression).
- [ ] `STOP_CRAWL` on master halts the fleet within ~one run (test once, then remove).

## Rollback / stop
- Stop everything: create `STOP_CRAWL` on ahmerfr/master + sync to forks (or push to each). Loops exit at next relaunch.
- If a fork chain dies overnight: next `auto_sync` re-ignites it; or manually re-run Task 5 for that account.
- If self-loop is flagged/breaks repeatedly: convert the 8 forks to standalone public repos (`gh repo create <owner>/rockauto-crawler --public`, push) so the watchdog cron also drives them (forks can't cron; standalone repos can).
