#!/usr/bin/env bash
# Hardware scale from the repo's own history (agent 6). The ticket and CHANGELOG give upstream's timings for three
# engine versions on their 2-CPU Modal sandboxes: pre-DASH-1150 ~13s, post-DASH-1150 ~1s, post-DASH-1178 (shipped)
# ~250ms. This benches each version here with the shipped scripts/bench.ts, so one scale factor can be checked against
# all three anchors. Host side:
#   docker run --rm --network none --cpus 2 --memory 4g \
#     -v <worktree>/aie_envs/dashboard_perf/calibration:/calib:ro aie-dashboard-pr:efd0826 bash /calib/run_history_tiers.sh [reps]
set -euo pipefail
REPS="${1:-1}"
cp -a /home/dev/analytics-dashboard /tmp/h
cd /tmp/h
c1150=$(git log --format=%H --grep='^DASH-1150' -n 1)
for i in $(seq 1 "$REPS"); do
  for tier in shipped v1 v0; do
    git checkout -q HEAD -- src/rendering
    if [ "$tier" = v1 ]; then git checkout -q "$c1150" -- src/rendering; fi
    if [ "$tier" = v0 ]; then git checkout -q "$c1150~1" -- src/rendering; fi
    echo "=== rep $i tier $tier $(date -u +%H:%M:%S)"
    timeout 900 npm run --silent bench 2>&1 | grep -E "run [0-9]|render:|output vs" || echo "(bench failed or timed out)"
  done
done
