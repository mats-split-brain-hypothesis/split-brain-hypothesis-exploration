#!/bin/bash
# night-2 A (j-lens-mean-2e): S14k on fit. Matched / label-free early centres, s14t64 late.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for e in knnx8 kmx64 pco16; do
  for L in 40 48; do C="${C}sched:$L:$e+s14t64@self|cos,"; done
  C="${C}sched:40:s14t64+$e@self|cos,"
done
$PY experiments/evaluate.py --banks "$B" --arms "${C%,}" --device cuda
