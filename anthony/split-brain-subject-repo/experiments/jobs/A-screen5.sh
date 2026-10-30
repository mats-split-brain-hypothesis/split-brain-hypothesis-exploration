#!/bin/bash
# night-2 A (j-lens-mean-2e): S14e on fit. The cos map's own top-k reading directions over the whole vocabulary
# (eigenvectors of its gram, experiments/s14_eig_basis.py; bases pushed to the volume from the Mac), no token list.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms \
  "s14:eig:16@self|cos,s14:eig:64@self|cos,s14:eig:128@self|cos,s14:eig:64:fam@self|cos,s14:eig:64@self|rms"
