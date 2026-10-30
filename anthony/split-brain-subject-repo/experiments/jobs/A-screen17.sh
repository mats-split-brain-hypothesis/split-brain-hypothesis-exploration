#!/bin/bash
# night-2 A (j-lens-mean-2e): S14n on fit. S14b with its kmx64 built from 10 / 25 / 50 % of the fit groups, 3 draws.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for p in 10 25 50; do for d in 0 1 2; do
  for r in cos rms; do C="${C}sched:40:kmx64n${p}d${d}+s14:template:64:mean=kmx64n${p}d${d}:a=0.5@self|$r,"; done
done; done
C="${C}sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@self|rms"
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "$C"
