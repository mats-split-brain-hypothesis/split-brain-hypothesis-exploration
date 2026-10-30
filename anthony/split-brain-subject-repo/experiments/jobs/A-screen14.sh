#!/bin/bash
# night-2 A (j-lens-mean-2e): S14b with the other-carrier kNN mean late (B's xcheck-S14b suggestion), on fit.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for a in 0.25 0.5 0.75; do C="${C}sched:40:kmx64+s14:template:64:mean=knnxs8:a=$a@self|cos,"; done
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "${C%,}"
