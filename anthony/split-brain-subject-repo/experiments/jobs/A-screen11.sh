#!/bin/bash
# night-2 A (j-lens-mean-2e): S14r on fit. Token lists from the uncentred readouts of the fit cells (built on the Mac,
# committed), their bases, the screen (alone and in the S14k schedule).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/precompute_pullback.py --template-tokens benchread --readouts cos --ks 16,64,128 --device cuda
$PY experiments/precompute_pullback.py --template-tokens benchread6 --readouts cos --ks 64 --device cuda
$PY experiments/evaluate.py --banks "$B" --device cuda --arms \
  "s14:benchread:16@self|cos,s14:benchread:64@self|cos,s14:benchread:128@self|cos,s14:benchread6:64@self|cos,sched:40:kmx64+s14:benchread:64@self|cos"
