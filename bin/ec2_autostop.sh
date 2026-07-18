#!/usr/bin/env bash
# ec2_autostop.sh — stop the EC2 the moment the crawl is FULLY done, not before.
#
# The fleet's main process (+ its lane subshells) all match "crawl_apigw_fleet.sh"
# and stay alive for the whole run; they exit only when every lane has drained its
# units (fleet.sh's `wait` returns). So "no crawl_apigw_fleet.sh process" == crawl
# complete. Double-check 90s apart to rule out a transient. Meant for root cron
# every ~10 min. `shutdown -h` => the instance STOPS (InstanceInitiatedShutdown
# Behavior=stop) => EBS + all crawled data persist for later ingest; nothing lost.
#
#   */10 * * * * /home/ubuntu/rockauto-crawler/bin/ec2_autostop.sh   # in root crontab
pgrep -f crawl_apigw_fleet.sh >/dev/null && exit 0
sleep 90
pgrep -f crawl_apigw_fleet.sh >/dev/null && exit 0
logger "rockauto-autostop: crawl fleet finished — stopping instance (data persists on EBS)"
/sbin/shutdown -h now
