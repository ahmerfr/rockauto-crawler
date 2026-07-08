"""
auto_sync.py — the hands-off bridge from the GitHub crawl fleet to the LOCAL DB.

Runs on a schedule (Windows Task Scheduler). Each run:
  1. Makes sure MariaDB is up (starts XAMPP's mysqld if it isn't).
  2. Asks GitHub for completed "RockAuto Crawl Fleet" runs we haven't loaded yet.
  3. Downloads each new run's NDJSON artifacts, ingests them into stg_listings,
     then runs the loader to canonicalize into parts/vehicles/fitment.
  4. Records processed run IDs so nothing is loaded twice, and logs everything to
     logs/auto_sync.log.

No manual commands, ever. It is idempotent and safe to run as often as you like:
new data flows in, already-loaded runs are skipped, and the loader dedupes on sku.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import db  # noqa: E402

REPO = "ahmerfr/rockauto-crawler"
WORKFLOW = "crawl.yml"
STATE_FILE = os.path.join(ROOT, ".auto_sync_state.json")
LOG_FILE = os.path.join(ROOT, "logs", "auto_sync.log")
DL_DIR = os.path.join(ROOT, "artifacts", "_autosync")
GH = r"C:\Program Files\GitHub CLI\gh.exe"
MYSQLD = r"C:\xampp\mysql\bin\mysqld.exe"
MYSQL_INI = r"C:\xampp\mysql\bin\my.ini"
PY = sys.executable  # same interpreter that launched us


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z  {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def ensure_db() -> bool:
    """True if MariaDB is reachable; start XAMPP's mysqld and wait if it isn't."""
    if db.ping():
        return True
    log("MariaDB down — starting mysqld…")
    try:
        # Detached so it keeps running after this script exits.
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([MYSQLD, f"--defaults-file={MYSQL_INI}", "--standalone"],
                         creationflags=flags, close_fds=True)
    except Exception as exc:  # noqa: BLE001
        log(f"could not launch mysqld: {exc}")
        return False
    for _ in range(20):
        time.sleep(1)
        if db.ping():
            log("MariaDB is up.")
            return True
    log("MariaDB did not come up in time — will retry next cycle.")
    return False


def gh_json(args: list[str]):
    out = subprocess.run([GH, *args], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
    return json.loads(out.stdout or "[]")


# If the newest fleet run is older than this, the local task dispatches one
# itself — so crawling continues even if GitHub's 6h cron gets disabled (GitHub
# disables scheduled workflows after 60 days with no commits). 7h > the 6h cron,
# so this only fires as a fallback when the cron didn't.
DISPATCH_AFTER_HOURS = 7


def maybe_dispatch() -> None:
    """Keep the crawl alive: dispatch a fleet run if none is active/recent."""
    try:
        runs = gh_json(["run", "list", "--repo", REPO, "--workflow", WORKFLOW,
                        "--limit", "1", "--json", "createdAt,status"])
    except Exception as exc:  # noqa: BLE001
        log(f"dispatch check skipped: {exc}")
        return
    if runs:
        r = runs[0]
        if r.get("status") in ("in_progress", "queued", "requested", "waiting", "pending"):
            log("a fleet run is already active — not dispatching.")
            return
        try:
            created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        except Exception:  # noqa: BLE001
            age_h = 999.0
        if age_h < DISPATCH_AFTER_HOURS:
            log(f"last run {age_h:.1f}h ago (< {DISPATCH_AFTER_HOURS}h) — cron has it.")
            return
    log("no recent fleet run — dispatching one to keep coverage going.")
    subprocess.run([GH, "workflow", "run", WORKFLOW, "--repo", REPO,
                    "-f", "budget=400", "-f", "max_seconds=18000"], cwd=ROOT)


def load_state() -> set[str]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return set(str(x) for x in json.load(fh).get("processed", []))
    except (OSError, ValueError):
        return set()


def save_state(done: set[str]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({"processed": sorted(done)}, fh, indent=2)


def process_run(run_id: str) -> bool:
    """Download + ingest + load one fleet run. True on success."""
    dest = os.path.join(DL_DIR, run_id)
    os.makedirs(dest, exist_ok=True)
    dl = subprocess.run([GH, "run", "download", run_id, "-D", dest],
                        capture_output=True, text=True, cwd=ROOT)
    # A run with no artifacts (all shards empty) is a success with nothing to do.
    files = glob.glob(os.path.join(dest, "**", "shard-*.ndjson"), recursive=True)
    if not files:
        log(f"run {run_id}: no NDJSON artifacts ({dl.stderr.strip()[:80]}) — nothing to load")
        return True
    total_lines = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in files)
    log(f"run {run_id}: {len(files)} shard file(s), {total_lines} listing lines")
    ing = subprocess.run([PY, os.path.join("bin", "ingest_artifacts.py"), *files],
                         capture_output=True, text=True, cwd=ROOT)
    log(f"  ingest: {(ing.stdout or ing.stderr).strip().splitlines()[-1] if (ing.stdout or ing.stderr).strip() else 'no output'}")
    if ing.returncode != 0:
        log(f"  ingest FAILED: {ing.stderr.strip()[:200]}")
        return False
    ld = subprocess.run([PY, os.path.join("bin", "loader.py")],
                        capture_output=True, text=True, cwd=ROOT)
    tail = (ld.stdout or ld.stderr).strip().splitlines()
    log(f"  loader: {tail[-1] if tail else 'no output'}")
    return ld.returncode == 0


STAGING_RETAIN_DAYS = 3


def cleanup_staging() -> None:
    """Trim the already-consumed staging buffer so it never grows unbounded over
    months of crawling. Only touches processed stg_* rows — canonical parts/
    vehicles/fitment are never affected."""
    try:
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM stg_listings WHERE processed=1 "
                "AND scraped_at < (NOW() - INTERVAL %s DAY)", [STAGING_RETAIN_DAYS])
            n1 = cur.rowcount
            cur.execute("DELETE FROM stg_fitment WHERE processed=1")
            n2 = cur.rowcount
        conn.commit()
        conn.close()
        if n1 or n2:
            log(f"staging cleanup: purged {n1} stg_listings + {n2} stg_fitment (already loaded)")
    except Exception as exc:  # noqa: BLE001
        log(f"staging cleanup skipped: {exc}")


def main() -> int:
    log("=== auto_sync start ===")
    if not os.path.exists(GH):
        log(f"gh CLI not found at {GH} — cannot sync.")
        return 1
    if not ensure_db():
        return 1
    try:
        runs = gh_json(["run", "list", "--repo", REPO, "--workflow", WORKFLOW,
                        "--status", "success", "--limit", "40",
                        "--json", "databaseId,createdAt"])
    except Exception as exc:  # noqa: BLE001
        log(f"could not list runs: {exc}")
        return 1

    done = load_state()
    new = [r for r in runs if str(r["databaseId"]) not in done]
    new.sort(key=lambda r: r.get("createdAt", ""))
    if not new:
        log("no new completed runs — up to date.")
        cleanup_staging()
        maybe_dispatch()
        log("=== auto_sync done ===")
        return 0

    log(f"{len(new)} new run(s) to load: {[r['databaseId'] for r in new]}")
    for r in new:
        rid = str(r["databaseId"])
        try:
            if process_run(rid):
                done.add(rid)
                save_state(done)
                log(f"run {rid}: DONE (recorded)")
            else:
                log(f"run {rid}: load failed — will retry next cycle")
        except Exception as exc:  # noqa: BLE001
            log(f"run {rid}: error {exc} — will retry next cycle")
    cleanup_staging()
    maybe_dispatch()
    log("=== auto_sync done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
