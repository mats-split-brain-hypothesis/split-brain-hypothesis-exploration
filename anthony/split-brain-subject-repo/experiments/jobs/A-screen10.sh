#!/bin/bash
# night-2 A (j-lens-mean-2e): S14b on fit. kmx64 up to L40, above it the template projection of h minus alpha x kmx64.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for a in 0.25 0.5 0.75 1; do C="${C}sched:40:kmx64+s14:template:64:mean=kmx64:a=$a@self|cos,"; done
C="${C}sched:40:kmx64+s14:template:64:mean=kmxr64:a=0.5@self|cos"
$PY experiments/evaluate.py --banks "$B" --arms "$C" --device cuda
