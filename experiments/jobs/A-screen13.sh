#!/bin/bash
# night-2 A (j-lens-mean-2e): S14o on fit (over-removal) and S14k with k = 128 late.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms \
  "s14:template:64:o=0.5@self|cos,s14:template:64:o=1@self|cos,s14:template:64:rand:o=1@self|cos,sched:40:kmx64+s14t128@self|cos,sched:40:kmx64+s14:template:64:o=0.5@self|cos"
