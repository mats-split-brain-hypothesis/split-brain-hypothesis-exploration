#!/bin/bash
# Dev-bank captures on the pod (one 80 GB GPU). The repo is private: ship it as a bundle
# (git bundle create jlm.bundle <branch>; scp; git clone -b <branch> jlm.bundle /root/jlm). Inside tmux:
#   BANKS=typo/fit LIMIT=3 bash tools/capture_pod.sh          # smoke
#   BANKS=typo/fit,typo/val bash tools/capture_pod.sh
# Existing captures are skipped, so a rerun resumes. Copy out/captures/*.pt back to the Mac.
set -uo pipefail
cd "$(dirname "$0")/.."
# /workspace on these pods is a quota-limited shared mount; the 27B shards must go on the container disk.
export HF_HOME="${HF_HOME:-/root/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
export PATH="$HOME/.local/bin:$PATH"
BANKS="${BANKS:?set BANKS, e.g. typo/fit,typo/val}"
LIMIT="${LIMIT:-0}"
mkdir -p out
exec > >(tee -a "out/capture-pod.log") 2>&1
step() { echo "[capture $(date '+%H:%M:%S')] $*"; }

command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
WSBENCH_COMMIT=92d763e722377f5bfae045e829a308ab5919a820  # = umot.provenance.WSBENCH_COMMIT
if [ ! -d third_party/workspace-bench ]; then
  git clone -q https://github.com/camilablank/workspace-bench third_party/workspace-bench
fi
git -C third_party/workspace-bench checkout -q "$WSBENCH_COMMIT" || { step "FAILED wsbench checkout"; exit 1; }
uv sync || { step "FAILED uv sync"; exit 1; }
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

for b in ${BANKS//,/ }; do
  step "capture $b"
  .venv/bin/python experiments/capture.py --family "${b%/*}" --split "${b#*/}" --limit "$LIMIT" --device cuda \
    || { step "FAILED $b"; exit 1; }
done
step "ALL DONE"; ls -la out/captures/
