#!/bin/bash
# night-2 A (j-lens-mean-2e): B's S23b suggestion on fit: S14b's late form at every layer (no schedule), alpha grid.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for a in 0.25 0.5 0.75; do C="${C}s14:template:64:mean=kmx64:a=$a@self|cos,"; done
C="${C}s14:template:64:mean=kmx64:a=0.5@self|rms"
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "$C"
