#!/bin/bash
# Evaluate arms on the pod's GPU (the Mac reads about 10x slower). No 27B model: only W_U, the
# final norm and the J-lens are downloaded. Captures are copied up into out/captures/ (and
# umot/out/captures/ for umot's bench captures) before running. Inside tmux:
#   BANKS=user_modeling/bench,directed_modulation/val ARMS="zero|cos,fam@fit|cos" bash tools/eval_pod.sh
# Copy out/eval/ back to the Mac afterwards; the Mac re-scores from the readouts in seconds.
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/root/hf}"  # /workspace on these pods is quota-limited
export PATH="$HOME/.local/bin:$PATH"
BANKS="${BANKS:?set BANKS}"
ARMS="${ARMS:?set ARMS}"
mkdir -p out
exec > >(tee -a out/eval-pod.log) 2>&1
step() { echo "[eval $(date '+%H:%M:%S')] $*"; }
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
WSBENCH_COMMIT=92d763e722377f5bfae045e829a308ab5919a820
[ -d third_party/workspace-bench ] || git clone -q https://github.com/camilablank/workspace-bench third_party/workspace-bench
git -C third_party/workspace-bench checkout -q "$WSBENCH_COMMIT" || { step "FAILED wsbench"; echo EVAL_EXIT=1; exit 1; }
uv sync -q || { step "FAILED uv sync"; echo EVAL_EXIT=1; exit 1; }
step "evaluate $BANKS"
.venv/bin/python experiments/evaluate.py --banks "$BANKS" --arms "$ARMS" --device cuda && echo EVAL_EXIT=0 || echo EVAL_EXIT=1
