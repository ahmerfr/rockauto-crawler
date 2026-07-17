#!/usr/bin/env bash
# Swarm crawl fleet — for a big AWS EC2 (c7g.4xlarge/8xlarge, 24/7, laptop-free).
#
# Breaks the per-BRAND bottleneck: the catalog is split into (make × year-band)
# UNITS — disjoint and complete by construction (see `crawl_apigw.py --selftest`) —
# and dealt round-robin across N lanes. A mega-make (Chevrolet ~10% of the catalog,
# one indivisible brand that used to grind on a single 1-req/s worker) becomes 18
# year-scoped units spread across many lanes. Each lane crawls its units one at a
# time, chunk-respawning per unit until the unit's frontier DRAINS (crawl_apigw exit
# 42), then moves to the next. ONE shared API Gateway rotates a fresh IP per request
# for every lane. The crawl/write loop is UNTOUCHED — units are fed only via
# --only-makes + SP_YEAR_MIN/MAX env (the year-band mechanism the old GitHub fleet
# proved), so there is zero new data-loss surface.
#
#   nohup bash bin/crawl_apigw_fleet.sh > logs/fleet.log 2>&1 &   # survives SSH disconnect
#   touch STOP_CRAWL      # graceful stop (each lane finishes its current chunk, exits)
#   python3 bin/crawl_apigw.py --teardown-only   # delete the shared endpoints after
#
# Env: WORKERS (lanes, default 150 — ~130MB each, so 150≈20GB RAM; c7g.8xlarge/64GB
#      fits ~300), REGIONS (default 5), PY (default python3), BUDGET (reqs/chunk,
#      default 20000), CHUNK_SECS (default 5400), MAXCHUNKS (per-unit spin cap, 60).
set -u
N="${WORKERS:-150}"
REGIONS="${REGIONS:-5}"
PY="${PY:-python3}"
BUDGET="${BUDGET:-20000}"
CHUNK_SECS="${CHUNK_SECS:-5400}"
MAXCHUNKS="${MAXCHUNKS:-60}"
UNITS="units.tsv"
cd "$(dirname "$0")/.." || exit 1
mkdir -p out fr logs
rm -f STOP_CRAWL

echo "[fleet] $(date -u) creating shared gateway ($REGIONS regions)..."
$PY bin/crawl_apigw.py --setup-only --regions "$REGIONS" 2>&1 | tee logs/fleet_setup.log

# Build the (make × year-band) unit plan ONCE (discovers makes through the gateway).
# The plan is disjoint+complete (asserted inside --gen-units); reused on restart.
if [ ! -s "$UNITS" ]; then
  echo "[fleet] building unit plan -> $UNITS ..."
  $PY bin/crawl_apigw.py --gen-units "$UNITS" --regions "$REGIONS" 2>&1 | tee logs/fleet_units.log
fi
TOTAL=$(wc -l < "$UNITS")
echo "[fleet] $TOTAL units across $N lanes (~$(( (TOTAL + N - 1) / N )) units/lane)"

echo "[fleet] launching $N lanes..."
for i in $(seq 0 $((N-1))); do
  (
    # This lane's disjoint slice = units[i::N] (every N-th line from index i).
    awk -v i="$i" -v n="$N" '(NR-1) % n == i' "$UNITS" | while IFS=$'\t' read -r MK LO HI; do
      [ -f STOP_CRAWL ] && break
      [ -z "$MK" ] && continue
      ukey=$(printf '%s' "${MK}_${LO}-${HI}" | tr -c 'A-Za-z0-9._-' '_')
      done_marker="fr/done_${i}_${ukey}"
      [ -f "$done_marker" ] && continue        # completed in a prior run — skip (resumable)
      fr="fr/f${i}_${ukey}.ndjson"
      c=0
      while [ ! -f STOP_CRAWL ] && [ "$c" -lt "$MAXCHUNKS" ]; do
        # Year-band in env BEFORE the process starts => config.SCOPE reads the right
        # band at import (proven mechanism). Distinct --out per chunk => never
        # truncates prior rows; shared frontier => resumes where the chunk left off.
        SP_YEAR_MIN="$LO" SP_YEAR_MAX="$HI" \
        $PY bin/crawl_apigw.py \
          --only-makes "$MK" --regions "$REGIONS" --no-teardown \
          --budget "$BUDGET" --max-seconds "$CHUNK_SECS" \
          --min-delay 0.02 --max-delay 0.06 \
          --out "out/s${i}_${ukey}_c${c}.ndjson" \
          --frontier-file "$fr" --frontier-out "$fr" \
          >> "logs/w${i}.log" 2>&1
        rc=$?
        c=$((c+1))
        [ "$rc" -eq 42 ] && touch "$done_marker" && break   # unit drained -> next unit
        sleep 2
      done
    done
    echo "[lane $i] done (units exhausted or STOP_CRAWL)" >> "logs/w${i}.log"
  ) &
done

echo "[fleet] $N lanes up. Data: out/*.ndjson  Frontier: fr/*.ndjson  Done: fr/done_*"
echo "[fleet] STOP: touch STOP_CRAWL   THEN teardown: $PY bin/crawl_apigw.py --teardown-only"
wait
echo "[fleet] $(date -u) all lanes exited. Run --teardown-only to delete endpoints."
