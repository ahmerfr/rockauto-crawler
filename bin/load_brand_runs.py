"""
load_brand_runs.py — isolated loader for single-brand VERIFICATION runs.

Loads completed 'RockAuto Single Brand' (brand.yml) runs into the LOCAL DB,
independently of auto_sync (which stays paused during verification). It NEVER
dispatches a crawl and NEVER touches the crawl.yml fleet runs — so the clean
single-brand slate can't be contaminated by the old full-catalog fleet.

Idempotent: records loaded run IDs in .brand_load_state.json and skips them.
Reuses auto_sync's download+ingest+load+image-copy helpers verbatim.

Runs from the 'RockAuto Brand Loader' scheduled task so the data lands even if
the laptop was shut down while the cloud crawl finished: it fires on next logon
and every 10 min, sees the now-completed run, and loads it.

    python bin/load_brand_runs.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import auto_sync as A  # reuse ensure_db / gh_json / process_run / log / GH / REPO / PY

WORKFLOWS = ["brand.yml", "brand_parallel.yml"]
STATE_FILE = os.path.join(ROOT, ".brand_load_state.json")


def load_state() -> set[str]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return set(str(x) for x in json.load(fh).get("processed", []))
    except (OSError, ValueError):
        return set()


def save_state(done: set[str]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({"processed": sorted(done)}, fh, indent=2)


def main() -> int:
    A.log("=== brand loader start ===")
    if not os.path.exists(A.GH):
        A.log(f"gh CLI not found at {A.GH} — cannot load.")
        return 1
    if not A.ensure_db():
        return 1
    runs = []
    try:
        for wf in WORKFLOWS:
            runs += A.gh_json(["run", "list", "--repo", A.REPO, "--workflow", wf,
                               "--limit", "40",
                               "--json", "databaseId,status,conclusion,createdAt"])
    except Exception as exc:  # noqa: BLE001
        A.log(f"could not list brand runs: {exc}")
        return 1

    done = load_state()
    # GitHub reports a CANCELLED run as status=completed. We cancel runs precisely
    # because their data is unwanted (e.g. crawled with a since-fixed parser), so a
    # cancelled run must never auto-load. Failures still load: with fail-fast:false
    # one bad shard fails the run while the others uploaded real data.
    new = [r for r in runs
           if r.get("status") == "completed"
           and r.get("conclusion") != "cancelled"
           and str(r["databaseId"]) not in done]
    new.sort(key=lambda r: r.get("createdAt", ""))
    if not new:
        A.log("no new completed brand runs — up to date.")
        A.log("=== brand loader done ===")
        return 0

    A.log(f"{len(new)} new brand run(s) to load: {[r['databaseId'] for r in new]}")
    for r in new:
        rid = str(r["databaseId"])
        try:
            if A.process_run(rid):
                done.add(rid)
                save_state(done)
                A.log(f"run {rid}: DONE (recorded)")
            else:
                A.log(f"run {rid}: load failed — will retry next cycle")
        except Exception as exc:  # noqa: BLE001
            A.log(f"run {rid}: error {exc} — will retry next cycle")
    A.log("=== brand loader done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
