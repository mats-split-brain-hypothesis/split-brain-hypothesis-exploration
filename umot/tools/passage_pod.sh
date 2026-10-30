#!/bin/bash
# Passage lens on the pod (one 80 GB GPU): J-lens top-K at every position, for the dashboard's token tracker.
#   tmux new -s pl
#   LIMIT=4 bash tools/passage_pod.sh     # smoke
#   bash tools/passage_pod.sh             # mention_control + directed_modulation
# Log: out/pl*.log; output out/passage/<family>/
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/workspace/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
LIMIT="${LIMIT:-0}"
FAMILIES="${FAMILIES:-mention_control,directed_modulation}"
mkdir -p out
LOG="out/pl$([ "$LIMIT" != 0 ] && echo "-limit$LIMIT").log"
exec > >(tee -a "$LOG") 2>&1
step() { echo "[pl $(date '+%H:%M:%S')] $*"; }

step "bootstrap"; bash tools/bootstrap.sh || { step "FAILED bootstrap"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
OUTDIR=out; [ "$LIMIT" != 0 ] && OUTDIR=out/smoke
.venv/bin/python experiments/passage_lens.py --families "$FAMILIES" --limit "$LIMIT" --out "$OUTDIR" \
  || { step "FAILED passage_lens"; exit 1; }
step "ALL DONE"; du -sh "$OUTDIR"/passage/*
