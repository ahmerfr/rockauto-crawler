#!/usr/bin/env bash
# 30-worker shared-gateway RockAuto crawl fleet — for the Oracle always-free VM (24/7,
# laptop-free). ONE AWS account's API Gateway rotates a fresh IP per request (no ~180 wall);
# all workers REUSE the same endpoints (created once). Each worker crawls makes[i::N], runs
# bounded chunks, and RE-SPAWNS on exit (frontier persists → resumes) so captcha/budget exits
# self-heal. Writes a fresh NDJSON per chunk (never truncates prior data).
#
#   nohup bash bin/crawl_apigw_fleet.sh > logs/fleet.log 2>&1 &     # survives SSH disconnect
#   touch STOP_CRAWL      # graceful stop (workers finish their chunk then exit)
#   python3 bin/crawl_apigw.py --teardown-only   # delete the shared endpoints after
#
# Env: WORKERS (default 30), REGIONS (default 5), PY (default python3).
set -u
N="${WORKERS:-30}"
REGIONS="${REGIONS:-5}"
PY="${PY:-python3}"
cd "$(dirname "$0")/.." || exit 1
mkdir -p out fr logs
rm -f STOP_CRAWL

echo "[fleet] $(date -u) creating shared gateway ($REGIONS regions)..."
$PY bin/crawl_apigw.py --setup-only --regions "$REGIONS" 2>&1 | tee logs/fleet_setup.log

echo "[fleet] launching $N workers (makes[i::$N])..."
for i in $(seq 0 $((N-1))); do
  (
    run=0
    while [ ! -f STOP_CRAWL ]; do
      $PY bin/crawl_apigw.py \
        --shard-index "$i" --shard-total "$N" --regions "$REGIONS" --no-teardown \
        --budget 8000 --max-seconds 5400 --min-delay 0.02 --max-delay 0.06 \
        --out "out/s${i}_${run}.ndjson" \
        --frontier-file "fr/f${i}.ndjson" --frontier-out "fr/f${i}.ndjson" \
        >> "logs/w${i}.log" 2>&1
      run=$((run + 1))
      sleep 3
    done
    echo "[worker $i] stopped (STOP_CRAWL)" >> "logs/w${i}.log"
  ) &
done

echo "[fleet] $N workers up. Data: out/*.ndjson  Frontier: fr/*.ndjson"
echo "[fleet] STOP: touch STOP_CRAWL   THEN teardown: $PY bin/crawl_apigw.py --teardown-only"
wait
echo "[fleet] $(date -u) all workers exited. Run --teardown-only to delete endpoints."
