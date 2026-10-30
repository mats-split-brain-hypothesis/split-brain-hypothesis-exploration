#!/bin/bash
# Side capture of the final residual (output of block 63, before the norm) at the bench's read
# cells, then the Taylor-point J-lens screen (experiments/taylor_screen.py) on it. One 80 GB GPU, minutes.
#   tmux new -s final
#   FAMILY=directed_modulation bash tools/final_pod.sh      # LIMIT=3 for a smoke run
# -> out/captures/<family>-final.pt, out/taylor/<family>*.jsonl (+ provenance). Log: out/final-<family>.log
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/workspace/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"   # the container's cgroup allows fewer cores than it shows
FAMILY="${FAMILY:-directed_modulation}"
LIMIT="${LIMIT:-0}"
mkdir -p out
LOG="out/final-${FAMILY}$([ "$LIMIT" != 0 ] && echo "-limit$LIMIT").log"
exec > >(tee -a "$LOG") 2>&1
step() { echo "[final $(date '+%H:%M:%S')] $*"; }

step "bootstrap"; bash tools/bootstrap.sh || { step "FAILED bootstrap"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
.venv/bin/python experiments/m1_run.py --family "$FAMILY" --limit "$LIMIT" --stages capture \
  --layers 63 --capture-suffix=-final || { step "FAILED capture"; exit 1; }
step "taylor screen"
.venv/bin/python experiments/taylor_screen.py --family "$FAMILY" --limit "$LIMIT" --device cuda \
  || { step "FAILED screen"; exit 1; }
step "ALL DONE"; ls -la out/captures/"$FAMILY"*-final* out/taylor/
