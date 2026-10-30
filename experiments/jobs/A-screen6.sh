#!/bin/bash
# night-2 A (j-lens-mean-2e): S14s on fit. s14t64 at mid depth, fam above layer L (and the swapped control).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for L in 40 44 48; do C="${C}sched:$L:s14t64+fam@self|cos,sched:$L:fam+s14t64@self|cos,"; done
C="${C}sched:44:s14t64+s14fam64@self|cos,sched:44:s14t64+fam@self|rms"
$PY experiments/evaluate.py --banks "$B" --arms "$C" --device cuda
