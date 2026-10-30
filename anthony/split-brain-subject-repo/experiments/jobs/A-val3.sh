#!/bin/bash
# night-2 A (j-lens-mean-2e): S14s val (L = 40 chosen on fit), strict, all 11.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/val," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "sched:40:fam+s14t64@fit|cos,sched:40:s14t64+fam@fit|cos"
