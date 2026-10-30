#!/bin/bash
# S20xu (instance e1): S20x with an 11th source (user_modeling's constant); fit only.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s20xu:1@self|cos" --device cuda --no-sem
