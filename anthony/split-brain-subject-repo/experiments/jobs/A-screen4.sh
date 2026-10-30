#!/bin/bash
# night-2 A (j-lens-mean-2e): S13t on fit. A constant g that lowers the first 64 template tokens by beta (the
# pullback of their indicator), the constant analogue of s14t64's projection.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/s13_shuffled_prior.py --indicator template:64
[ -e out/priors/pullback/ind-template-64-cos-rfull.pt ] || \
  $PY experiments/precompute_pullback.py --priors ind-template-64 --readouts cos --ranks full --device cuda
C=""
for b in 2 4 8 16; do C="${C}s13:ind-template-64:$b@self|cos,"; done
$PY experiments/evaluate.py --banks "$B" --arms "${C%,}" --device cuda
