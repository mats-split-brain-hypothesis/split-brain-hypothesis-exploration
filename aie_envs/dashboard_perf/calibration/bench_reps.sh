#!/usr/bin/env bash
# N runs of the agent-facing bench on the unmodified engine, as `dev` (agent 6; src/dashboard_bar.py calls this).
#   docker run --rm --network none --cpus 2 --memory 4g -v <calibration>:/calib:ro aie-dashboard-pr:efd0826 \
#     bash /calib/bench_reps.sh 10
set -euo pipefail
cd /home/dev/analytics-dashboard
for i in $(seq 1 "${1:-10}"); do
  echo "=== rep $i $(date -u +%H:%M:%S)"
  runuser -u dev -- npm run --silent bench 2>&1 | tail -4
done
