#!/bin/bash
# S20 (night-2 C): the in-sample / K-fold / val ceilings of every class of g, family by family, on one GPU.
#   FAMS="typo association" CLASSES=const,proj16 bash experiments/jobs/c_s20.sh
# Skips families whose out/analysis/S20/<family>-fit.json exists (FORCE=1 to redo). Stops at the first failure.
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
FAMS="${FAMS:-typo association multihop multilingual basic_readout multihop_mt multilingual_mt typo_mt basic_readout_mt directed_modulation user_modeling}"
CLASSES="${CLASSES:-const,tok,clu,proj16}"
mkdir -p out/analysis/S20
for f in $FAMS; do
  if [ -z "${FORCE:-}" ] && [ -f "out/analysis/S20/$f-fit.json" ]; then echo "[s20] skip $f"; continue; fi
  echo "[s20 $(date -u +%H:%M:%S)] $f"
  .venv/bin/python experiments/ceilings.py --family "$f" --split fit --val --classes "$CLASSES" --device cuda ${EXTRA:-} \
    || { echo "[s20] FAILED $f"; exit 1; }
done
echo "[s20 $(date -u +%H:%M:%S)] all done"
