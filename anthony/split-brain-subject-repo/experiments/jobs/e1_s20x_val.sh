#!/bin/bash
# S20x (instance e1): the twin-out variant on fit (alpha grid), then val of the fit choice (alpha = 1) with its controls,
# both readouts, and the battery. Stops at the first failure.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s20xt:0.5@self|cos,s20xt:1@self|cos,s20xt:2@self|cos" --device cuda --no-sem
ARMS="s20x:1@fit|cos,s20xt:1@fit|cos,s20xr:1@fit|cos,shuf.s20x:1@fit|cos,s20x:1@fit|rms,s20xt:1@fit|rms"
$PY experiments/evaluate.py --banks "$VAL" --arms "zero|cos,fam@fit|cos,zero|rms,fam@fit|rms,knnx8@fit|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S20x-val --split val --arms "$ARMS" --refs "zero|cos,fam@fit|cos,knnx8@fit|cos" --decode-g --device cuda
