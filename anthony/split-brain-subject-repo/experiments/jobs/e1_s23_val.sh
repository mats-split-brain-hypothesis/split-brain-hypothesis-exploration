#!/bin/bash
# S23 val confirmation (instance e1): the fit-selected per-layer maps through the pipeline, cos and rms, battery.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$VAL" --arms "s23map:cos@fit|cos,s23map:rms@fit|rms" --device cuda --no-sem
B="sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5"
$PY experiments/analyse.py --study S23-val --split val --arms "s23map:cos@fit|cos" --refs "fam@fit|cos,$B@fit|cos"
$PY experiments/analyse.py --study S23-val-rms --split val --arms "s23map:rms@fit|rms" --refs "fam@fit|rms,$B@fit|rms"
