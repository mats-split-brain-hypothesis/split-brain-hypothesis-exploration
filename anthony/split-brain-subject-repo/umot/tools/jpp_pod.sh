#!/bin/bash
# J++ comparison on the pod (one 80 GB GPU). Needs /root/jpp_lens at JPP_COMMIT with its own venv
# (uv sync --extra cu128 --frozen). Run inside tmux:
#   tmux new -s jpp
#   LIMIT=4 bash tools/jpp_pod.sh      # plumbing: 4 items per task, recipe layers only
#   bash tools/jpp_pod.sh              # full: capture, score every map x centre, native J++ parity
# Log: out/jpp.log
set -uo pipefail
cd "$(dirname "$0")/.."
export HF_HOME="${HF_HOME:-/workspace/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
LIMIT="${LIMIT:-0}"
JPP="${JPP:-/root/jpp_lens}"
PY="$JPP/.venv/bin/python"
mkdir -p out
LOG="out/jpp$([ "$LIMIT" != 0 ] && echo "-limit$LIMIT").log"
exec > >(tee -a "$LOG") 2>&1
step() { echo "[jpp $(date '+%H:%M:%S')] $*"; }

step "bootstrap"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
step "jpp_lens @ $(git -C "$JPP" rev-parse HEAD)"
if [ "$LIMIT" != 0 ]; then
  $PY experiments/jpp_compare.py --jpp-repo "$JPP" --limit "$LIMIT" --recipe-only || { step "FAILED jpp_compare"; exit 1; }
else
  $PY experiments/jpp_compare.py --jpp-repo "$JPP" || { step "FAILED jpp_compare"; exit 1; }
  # Their own pipeline on the released J++ lens and the logit lens: held-out:0, Readout Filtering, layers 8..56.
  step "native evaluate"
  LENS=$($PY -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('koayon/jpp-lenses','qwen3.6-27b/lens.pt',revision='6c96867a91c43c14cec17cf0f6d157b933c5fee5'))")
  OUT="$PWD/out/jpp/native"; mkdir -p "$OUT"
  (cd "$JPP" && $PY scripts/jpp_cli.py evaluate --lens "$LENS" logit --out "$OUT/ranks.csv") || { step "FAILED native evaluate"; exit 1; }
fi
step "ALL DONE"; ls -la out/jpp*/
