#!/usr/bin/env bash
# Time upstream's calibration tiers (shipped / mid / opt) and the agent-facing bench inside the task image, as `dev`,
# under the run's Docker limits (agent 6). Host side:
#   docker run --rm --network none --cpus 2 --memory 4g \
#     -v <worktree>/aie_envs/dashboard_perf/calibration:/calib:ro aie-dashboard-pr:efd0826 bash /calib/run_in_container.sh [reps]
# measure.ts imports ../task/analytics-dashboard/..., so the repo is linked into that layout under /tmp/c.
set -euo pipefail
REPS="${1:-1}"
mkdir -p /tmp/c/task
ln -s /home/dev/analytics-dashboard /tmp/c/task/analytics-dashboard
cp -r /calib /tmp/c/calibration
chmod -R a+rX /tmp/c
cd /home/dev/analytics-dashboard
for i in $(seq 1 "$REPS"); do
  echo "=== rep $i $(date -u +%H:%M:%S)"
  runuser -u dev -- npx tsx /tmp/c/calibration/measure.ts
  runuser -u dev -- npm run --silent bench
done
