#!/bin/bash
# night-2 A (j-lens-mean-2e): S14n val, S14b with kmx64 from 25 % of the fit groups (the smallest share that held on fit), 3 draws.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/val," "$f"; done); B=${B%,}
C=""
for d in 0 1 2; do C="${C}sched:40:kmx64n25d${d}+s14:template:64:mean=kmx64n25d${d}:a=0.5@fit|cos,"; done
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "${C%,}"
