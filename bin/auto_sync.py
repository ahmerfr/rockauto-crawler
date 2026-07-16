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
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))
import db  # noqa: E402

# The 9-account free fleet. auto_sync pulls artifacts from EVERY account's fork
# (each crawls a disjoint slice, ACCOUNT_OFFSET 0..8). Override with SP_SYNC_REPOS.
DEFAULT_REPOS = [
    "ahmerfr/rockauto-crawler", "ahmerfraizada/rockauto-crawler",
    "ahmerfraizadas/rockauto-crawler", "ahmerfrr/rockauto-crawler",
    "ahmerfrsa/rockauto-crawler", "ahmerfrz/rockauto-crawler",
    "ahmerfrzz/rockauto-crawler", "ahmerfrzzz/rockauto-crawler",
    "haseeb-shoukat2029/rockauto-crawler",
]
REPOS = [r.strip() for r in os.getenv("SP_SYNC_REPOS", ",".join(DEFAULT_REPOS)).split(",") if r.strip()]
REPO = REPOS[0]  # primary (its bare run-ids in the legacy state file stay valid)


def _key(repo: str, rid: str) -> str:
    """Per-repo state key so run 123 in account A != run 123 in account B."""
    return f"{repo}#{rid}"


# Which crawl workflow to ingest. Default is the FREE fleet (crawl.yml). Set
# SP_SYNC_WORKFLOW=crawl_evomi.yml to ingest the paid Evomi run's artifacts — and
# ALWAYS pair that with SP_SYNC_NO_DISPATCH=1 so it never auto-dispatches a new
# (money-spending) Evomi round.
WORKFLOW = os.getenv("SP_SYNC_WORKFLOW", "crawl.yml")
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


def maybe_dispatch(repo: str) -> None:
    """Keep the crawl alive: dispatch a fleet run for `repo` if none is active/recent."""
    if os.getenv("SP_SYNC_NO_DISPATCH"):
        return
    try:
        runs = gh_json(["run", "list", "--repo", repo, "--workflow", WORKFLOW,
                        "--limit", "1", "--json", "createdAt,status"])
    except Exception as exc:  # noqa: BLE001
        log(f"{repo}: dispatch check skipped: {exc}")
        return
    if runs:
        r = runs[0]
        if r.get("status") in ("in_progress", "queued", "requested", "waiting", "pending"):
            return
        try:
            created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        except Exception:  # noqa: BLE001
            age_h = 999.0
        if age_h < DISPATCH_AFTER_HOURS:
            return
    log(f"{repo}: no recent run — dispatching one to keep coverage going.")
    subprocess.run([GH, "workflow", "run", WORKFLOW, "--repo", repo,
                    "-f", "budget=2500", "-f", "max_seconds=18000"], cwd=ROOT)


def load_state() -> set[str]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return set(str(x) for x in json.load(fh).get("processed", []))
    except (OSError, ValueError):
        return set()


def save_state(done: set[str]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({"processed": sorted(done)}, fh, indent=2)


def copy_artifact_images(dest: str) -> int:
    """Copy self-hosted thumbnails from a downloaded artifact tree into
    assets/parts/ (served by Apache at /RockAuto/assets/parts/...). The path
    after the '/images/' segment is the stable <n>/<basename> sub-path."""
    assets = os.path.join(ROOT, "assets", "parts")
    n = 0
    for src in glob.glob(os.path.join(dest, "**", "images", "**", "*"), recursive=True):
        if not os.path.isfile(src):
            continue
        after = src.replace("\\", "/").split("/images/", 1)
        if len(after) != 2:
            continue
        target = os.path.join(assets, after[1].replace("/", os.sep))
        if os.path.exists(target) and os.path.getsize(target) > 0:
            continue
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)
            n += 1
        except OSError:
            pass
    return n


def _run_artifact_names(repo: str, run_id: str) -> list[str] | None:
    """Names of every artifact GitHub has for this run (None on API failure)."""
    out = subprocess.run(
        [GH, "api", f"repos/{repo}/actions/runs/{run_id}/artifacts",
         "--paginate", "--jq", ".artifacts[].name"],
        capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        return None
    return [n.strip() for n in (out.stdout or "").splitlines() if n.strip()]


def _shard_in(path: str) -> bool:
    return bool(glob.glob(os.path.join(path, "**", "shard-*.ndjson"), recursive=True))


def process_run(repo: str, run_id: str) -> bool:
    """Download + ingest + load one fleet run. True on success.

    Downloads EACH artifact into its own subfolder. `gh run download` extracts
    every artifact into one directory, and the windows share image paths (the
    same part photo recurs across year windows), so a duplicate path makes gh
    error 'file exists' and abort the WHOLE download after a few artifacts — which
    silently dropped 12 of 15 shards. Per-artifact folders remove the collision.
    Returns False (run not recorded, retries next cycle) if any artifact is missing."""
    dest = os.path.join(DL_DIR, repo.split("/")[0], run_id)  # namespace by account
    os.makedirs(dest, exist_ok=True)

    names = _run_artifact_names(repo, run_id)
    if names is None:
        log(f"run {run_id}: could not list artifacts — will retry next cycle")
        return False
    if not names:
        log(f"run {run_id}: no artifacts — nothing to load")
        return True

    missing = []
    for name in names:
        sub = os.path.join(dest, name)
        if _shard_in(sub):
            continue                       # already have it (resumable)
        os.makedirs(sub, exist_ok=True)
        ok = False
        for attempt in range(3):
            r = subprocess.run([GH, "run", "download", run_id, "--repo", repo,
                                "-n", name, "-D", sub],
                               capture_output=True, text=True, cwd=ROOT)
            if r.returncode == 0 and _shard_in(sub):
                ok = True
                break
        if not ok:
            missing.append(name)
    if missing:
        log(f"run {run_id}: {len(missing)}/{len(names)} artifact(s) failed to download "
            f"({missing[:3]}) — will retry next cycle")
        return False

    files = glob.glob(os.path.join(dest, "**", "shard-*.ndjson"), recursive=True)
    if not files:
        log(f"run {run_id}: {len(names)} artifact(s) but no shard NDJSON — nothing to load")
        return True
    total_lines = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in files)
    log(f"run {run_id}: {len(files)} shard file(s), {total_lines} listing lines")
    copied = copy_artifact_images(dest)
    if copied:
        log(f"  self-hosted {copied} thumbnail(s) -> assets/parts/")
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
    done = load_state()
    for repo in REPOS:
        try:
            runs = gh_json(["run", "list", "--repo", repo, "--workflow", WORKFLOW,
                            "--limit", "40",
                            "--json", "databaseId,status,conclusion,createdAt"])
        except Exception as exc:  # noqa: BLE001
            log(f"{repo}: could not list runs: {exc}")
            continue

        # Load ANY finished run — not just conclusion=success. With fail-fast:false,
        # one bad shard makes the whole run "failure", but the other shards' artifacts
        # uploaded fine (if: always()) and hold real data. Legacy bare run-ids in the
        # state file count as already-done for the primary repo.
        def _is_done(rid: str) -> bool:
            return _key(repo, rid) in done or (repo == REPO and rid in done)
        new = [r for r in runs
               if r.get("status") == "completed" and not _is_done(str(r["databaseId"]))]
        new.sort(key=lambda r: r.get("createdAt", ""))
        if new:
            log(f"{repo}: {len(new)} new run(s): {[r['databaseId'] for r in new]}")
        for r in new:
            rid = str(r["databaseId"])
            try:
                if process_run(repo, rid):
                    done.add(_key(repo, rid))
                    save_state(done)
                    log(f"{repo} run {rid}: DONE (recorded)")
                else:
                    log(f"{repo} run {rid}: load failed — will retry next cycle")
            except Exception as exc:  # noqa: BLE001
                log(f"{repo} run {rid}: error {exc} — will retry next cycle")
        maybe_dispatch(repo)

    cleanup_staging()
    log("=== auto_sync done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
