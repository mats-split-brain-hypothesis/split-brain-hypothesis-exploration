#!/bin/bash
# Mention-only control on the pod (one 80 GB GPU): compliance + capture for data/mention-control.
#   tmux new -s mc
#   bash tools/mc_pod.sh            # LIMIT=3 for a smoke run
# Token readers run locally afterwards from out/captures/mention_control.pt. Log: out/mc.log
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/workspace/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"   # the container's cgroup allows fewer cores than it shows
LIMIT="${LIMIT:-0}"
FAMILY="${FAMILY:-mention_control}"   # or mention_many
K="${K:-4}"
mkdir -p out
LOG="out/mc-${FAMILY}$([ "$LIMIT" != 0 ] && echo "-limit$LIMIT").log"
exec > >(tee -a "$LOG") 2>&1
step() { echo "[mc $(date '+%H:%M:%S')] $*"; }

step "bootstrap"; bash tools/bootstrap.sh || { step "FAILED bootstrap"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
.venv/bin/python experiments/mc_run.py --family "$FAMILY" --stages compliance,capture --limit "$LIMIT" --k "$K" \
  || { step "FAILED mc_run"; exit 1; }
step "ALL DONE"; ls -la out/captures/"$FAMILY"* out/"${FAMILY//_/-}"/
