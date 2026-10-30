#!/bin/bash
# S20y (instance e1): S20x's correction on top of A's S14 template removal; fit then val (alpha = 1 from S20x's fit).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s14t64@self|cos,sched:40:fam+s14t64@self|cos,s20xon:1:s14t64@self|cos,sched:40:fam+s20xon:1:s14t64@self|cos,sched:40:s20xt:1+s20xon:1:s14t64@self|cos" --device cuda --no-sem
ARMS="s20xon:1:s14t64@fit|cos,sched:40:fam+s20xon:1:s14t64@fit|cos,sched:40:s20xt:1+s20xon:1:s14t64@fit|cos"
$PY experiments/evaluate.py --banks "$VAL" --arms "s14t64@fit|cos,sched:40:fam+s14t64@fit|cos,s20xt:1@fit|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S20y-val --split val --arms "$ARMS" --refs "fam@fit|cos,s20xt:1@fit|cos,sched:40:fam+s14t64@fit|cos"
