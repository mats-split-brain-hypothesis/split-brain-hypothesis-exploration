#!/bin/bash
# S23 components (instance e1): every label-free centre of the set on fit and val, cos and rms (existing arms skipped).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
L="s14:template:64:mean=kmx64:a=0.5"
for r in cos rms; do
  $PY experiments/evaluate.py --banks "$FIT" --arms "zero|$r,fam@self|$r,kmx64@fit|$r,s14t64@self|$r,$L@self|$r,knnxs8@fit|$r" --device cuda --no-sem
  $PY experiments/evaluate.py --banks "$VAL" --arms "zero|$r,fam@fit|$r,kmx64@fit|$r,s14t64@fit|$r,$L@fit|$r,knnxs8@fit|$r" --device cuda --no-sem
done
