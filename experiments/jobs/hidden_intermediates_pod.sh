#!/bin/bash
# Hidden-intermediate dev banks on a capture pod (tools/pod.sh setup first; run inside tmux from /root/jlm):
#   FAMILY=chain_intermediates BENCH= bash experiments/jobs/hidden_intermediates_pod.sh
#   FAMILY=brew_intermediates BENCH=chain_intermediates,brew_intermediates bash experiments/jobs/hidden_intermediates_pod.sh
# BENCH banks are captured first (they do not wait on the gate), then FAMILY is gated, frozen and its fit / val
# captured. Gate files land in out/gate (the volume); freeze is rebuilt on the Mac from them.
set -uo pipefail
cd "$(dirname "$0")/../.."
export PATH="$HOME/.local/bin:$PATH" HF_HOME=/workspace/hf OMP_NUM_THREADS=8
FAMILY="${FAMILY:?}"; BENCH="${BENCH:-}"; BATCH="${BATCH:-8}"  # 32 x 10 samples OOMs next to the 27B on 80 GB
mkdir -p out/logs
exec > >(tee -a "out/logs/hi-$FAMILY.log") 2>&1
step() { echo "[hi $(date '+%H:%M:%S')] $*"; }
for f in ${BENCH//,/ }; do
  step "capture $f/bench"
  .venv/bin/python experiments/capture.py --family "$f" --split bench --device cuda || { step "FAILED $f/bench"; exit 1; }
done
step "gate $FAMILY"
.venv/bin/python experiments/build_intermediates_dev.py gate --families "$FAMILY" --batch "$BATCH" || { step "FAILED gate"; exit 1; }
.venv/bin/python experiments/build_intermediates_dev.py freeze --families "$FAMILY" || { step "FAILED freeze"; exit 1; }
for s in fit val; do cp "data/dev/$FAMILY/$s.json" "out/gate/$FAMILY-$s.json"; done
for s in fit val; do
  step "capture $FAMILY/$s"
  .venv/bin/python experiments/capture.py --family "$FAMILY" --split "$s" --device cuda || { step "FAILED $FAMILY/$s"; exit 1; }
done
step "ALL DONE"
