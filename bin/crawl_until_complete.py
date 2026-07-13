"""crawl_until_complete.py — loop-until-complete driver for ONE make.

The crawl windows (brand_parallel.yml) each stop at a request budget, so a dense
year leaves later models/categories uncrawled. But each window RESUMES from its
per-window visited-leaf cache, and crawl_jsonl now emits a [result] line per run
(exit_reason / complete / new_leaves). This driver simply re-dispatches the make's
windows until EVERY window reports complete=True — i.e. it drained its subtree —
or a whole round adds 0 new leaves (converged / nothing left).

  python bin/crawl_until_complete.py [make] [--budget 8000] [--max-rounds 8]

Safe to re-run: state lives in the GitHub Actions per-window cache, not here, so a
killed/re-started driver just dispatches another round and the windows resume.
Runs for hours (each GH run is up to ~5.3h); intended to run in the background.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

GH = r"C:\Program Files\GitHub CLI\gh.exe"
REPO = "ahmerfr/rockauto-crawler"
WF = "brand_parallel.yml"
REF = os.getenv("SP_CRAWL_REF", "crawl-loop-until-complete")  # branch carrying the [result] engine change
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def gh(*args):
    return subprocess.run([GH, *args], capture_output=True, text=True, cwd=ROOT)


def latest_run_id():
    r = gh("run", "list", "--repo", REPO, "--workflow", WF, "--limit", "1", "--json", "databaseId")
    try:
        d = json.loads(r.stdout or "[]")
        return str(d[0]["databaseId"]) if d else None
    except ValueError:
        return None


def dispatch(make, budget):
    before = latest_run_id()
    gh("workflow", "run", WF, "--repo", REPO, "--ref", REF, "-f", f"make={make}", "-f", f"budget={budget}")
    for _ in range(45):               # wait for the new run to register
        time.sleep(4)
        rid = latest_run_id()
        if rid and rid != before:
            return rid
    raise SystemExit("dispatched run never appeared in the run list")


def wait_for(rid, poll=90):
    while True:
        r = gh("run", "view", rid, "--repo", REPO, "--json", "status,conclusion")
        try:
            d = json.loads(r.stdout or "{}")
        except ValueError:
            d = {}
        if d.get("status") == "completed":
            return d.get("conclusion")
        time.sleep(poll)


def parse_results(rid):
    """Per-window [result] lines from the run log. gh prefixes each line with the
    job name (the matrix window), so we recover which window each result is for."""
    log = gh("run", "view", rid, "--repo", REPO, "--log").stdout or ""
    out = []
    for line in log.splitlines():
        if "[result]" not in line:
            continue
        m = re.search(r"complete=(\w+).*?new_leaves=(\d+).*?frontier_remaining=(\d+)", line)
        if not m:
            continue
        win = line.split("\t", 1)[0].strip() if "\t" in line else "?"
        out.append({"window": win, "complete": m.group(1) == "True",
                    "new_leaves": int(m.group(2)), "frontier": int(m.group(3))})
    return out


def main() -> int:
    args = sys.argv[1:]
    make = next((a for a in args if not a.startswith("-")), "acura")
    def opt(name, default):
        return int(args[args.index(name) + 1]) if name in args else default
    budget = opt("--budget", 8000)
    max_rounds = opt("--max-rounds", 8)

    print(f"=== loop-until-complete: make={make} budget={budget} max-rounds={max_rounds} ===", flush=True)
    for rnd in range(1, max_rounds + 1):
        rid = dispatch(make, budget)
        print(f"[round {rnd}] dispatched run {rid} — waiting (each run up to ~5.3h)…", flush=True)
        concl = wait_for(rid)
        results = parse_results(rid)
        done = [r for r in results if r["complete"]]
        total_new = sum(r["new_leaves"] for r in results)
        incomplete = [r["window"] for r in results if not r["complete"]]
        print(f"[round {rnd}] run {rid} {concl}: {len(done)}/{len(results)} windows complete, "
              f"{total_new} new leaves. incomplete={incomplete[:12]}", flush=True)
        if results and not incomplete:
            print(f"[DONE] all {len(results)} windows drained — {make} provably complete.", flush=True)
            return 0
        if total_new == 0:
            print(f"[DONE] 0 new leaves this round — converged (no more reachable leaves).", flush=True)
            return 0
    print(f"[stop] hit max-rounds {max_rounds} without full convergence — re-run to continue.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
