#!/bin/bash
# Milestone 1 on the pod (one 80 GB GPU, ~150 GB on /workspace). Run inside tmux:
#   tmux new -s m1
#   FAMILY=directed_modulation LIMIT=3 bash tools/m1_pod.sh     # smoke: 3 items, every reader
#   FAMILY=directed_modulation bash tools/m1_pod.sh             # full family
#   FAMILY=typo STAGES=capture,verbal VERBALIZERS=olens-s390 NLA=0 bash tools/m1_pod.sh
# Each stage skips outputs that already exist, so a rerun resumes. Log: out/m1-<family>.log
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/workspace/hf}"
# The container shows the host's cores but its cgroup allows far fewer; cap BLAS threads.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
FAMILY="${FAMILY:?set FAMILY}"
LIMIT="${LIMIT:-0}"
K="${K:-1}"
BATCH="${BATCH:-32}"
STAGES="${STAGES:-capture,token,blackbox,verbal}"   # probed-model stages; the NLA runs after
VERBALIZERS="${VERBALIZERS:-olens-s390,olens-s050,modlens}"
NLA="${NLA:-1}"
mkdir -p out
LOG="out/m1-${FAMILY}$([ "$LIMIT" != 0 ] && echo "-limit$LIMIT").log"
exec > >(tee -a "$LOG") 2>&1
step() { echo "[m1 $(date '+%H:%M:%S')] $*"; }

step "bootstrap"; bash tools/bootstrap.sh || { step "FAILED bootstrap"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
df -h "$HF_HOME" 2>/dev/null | tail -1

run() {
  step "stages=$1"
  .venv/bin/python experiments/m1_run.py --family "$FAMILY" --limit "$LIMIT" --k "$K" \
    --batch-size "$BATCH" --verbalizers "$VERBALIZERS" --stages "$1" || { step "FAILED stages=$1"; exit 1; }
}
# One process for everything on the probed model, then the NLA (a separate model) on its own.
run "$STAGES"
[ "$NLA" = 1 ] && run nla
step "ALL DONE"; ls -la out/readouts/*/"${FAMILY}.jsonl"
