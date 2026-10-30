#!/bin/bash
# night-2 A (j-lens-mean-2e): S13t, larger beta (the indicator's pullback fits at 0.95-0.98: a weak shift per unit beta).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for b in 32 64 128 256; do C="${C}s13:ind-template-64:$b@self|cos,"; done
$PY experiments/evaluate.py --banks "$B" --arms "${C%,}" --device cuda
