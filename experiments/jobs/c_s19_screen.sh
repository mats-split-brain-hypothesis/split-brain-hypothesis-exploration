#!/bin/bash
# S19 screen on fit (@self = the fold model that never saw the cell's group), all 11 families, with rand. control.
#   ARMS="s19r16@self|cos,rand.s19r16@self|cos" bash experiments/jobs/c_s19_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
SPLIT="${SPLIT:-fit}"
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $FAMS; do printf "%s/$SPLIT," "$f"; done); B=${B%,}
.venv/bin/python experiments/evaluate.py --banks "$B" --arms "$ARMS" --device cuda || { echo "[s19screen] FAILED"; exit 1; }
echo "[s19screen] done"
