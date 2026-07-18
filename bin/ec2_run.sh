#!/usr/bin/env bash
# ec2_run.sh — (re)start the swarm on the EC2 box. Ensures the venv has EVERY crawl
# dependency (requirements.txt covers pymysql/Pillow that the import chain needs even
# with images off; boto3 + requests-ip-rotator drive the AWS gateway), then launches
# the fleet FULLY DETACHED (setsid + </dev/null) so it survives the SSM/cloud-init
# command that started it exiting. Idempotent — safe to re-run.
#
#   sudo -u ubuntu WORKERS=110 bash bin/ec2_run.sh
set -eu
cd "$(dirname "$0")/.."
VENV=./venv
echo "[ec2_run] ensuring venv deps..."
$VENV/bin/pip install -q -r requirements.txt boto3 requests-ip-rotator
rm -f STOP_CRAWL
mkdir -p logs out fr
WORKERS="${WORKERS:-110}"
REGIONS="${REGIONS:-5}"      # gateway regions = distinct AWS IP pools (raise to dilute blocks)
echo "[ec2_run] launching fleet WORKERS=$WORKERS REGIONS=$REGIONS (detached)..."
# redirect setsid's OWN stdout/stderr to the log (not just the inner cmd) so the
# launching SSM/cloud-init command doesn't keep its pipe open and hang "InProgress".
setsid bash -c "PY=$VENV/bin/python REGIONS=$REGIONS WORKERS=$WORKERS bash bin/crawl_apigw_fleet.sh" </dev/null >> logs/fleet.log 2>&1 &
sleep 1
echo "[ec2_run] launched. monitor: tail -f logs/fleet.log  (and logs/w0.log)"
