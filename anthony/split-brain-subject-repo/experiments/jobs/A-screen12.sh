#!/bin/bash
# night-2 A (j-lens-mean-2e): S14z on fit. The chat specials alone (first 5 / 8 template tokens).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/precompute_pullback.py --template-tokens template --readouts cos --ks 5,8 --device cuda
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "s14:template:5@self|cos,s14:template:8@self|cos,sched:40:kmx64+s14:template:5@self|cos"
