#!/bin/bash
# J-lens fit mean + the OLS-vs-J check (experiments/fit_mean.py) on one 80 GB GPU; forward passes only, minutes.
#   tmux new -s fm
#   bash tools/fitmean_pod.sh            # N=8 TEST_FROM=6 for a smoke run
# -> out/fitmean/{mu.pt,ols_beta.pt,summary.json}. Log: out/fitmean.log
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/root/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
N="${N:-1000}"; TEST_FROM="${TEST_FROM:-800}"
mkdir -p out
OUTDIR=out/fitmean; [ "$N" != 1000 ] && OUTDIR=out/smoke/fitmean
LOG="out/fitmean$([ "$N" != 1000 ] && echo "-n$N").log"
exec > >(tee -a "$LOG") 2>&1
step() { echo "[fm $(date '+%H:%M:%S')] $*"; }
step "bootstrap"; bash tools/bootstrap.sh || { step "FAILED bootstrap"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
.venv/bin/python experiments/fit_mean.py --device cuda --n-prompts "$N" --test-from "$TEST_FROM" --out "$OUTDIR" \
  || { step "FAILED fit_mean"; exit 1; }
step "ALL DONE"; ls -la "$OUTDIR"
