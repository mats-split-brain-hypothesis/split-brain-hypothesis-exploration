#!/bin/bash
# U3 variant 5 fit screen (instance c0).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS="kdir1@fit|cos,kdir64@fit|cos,kproj1@fit|cos,kproj64@fit|cos"
$PY experiments/evaluate.py --banks "$FIT" --arms "$ARMS" --device cuda
$PY experiments/analyse.py --study U3v5-fit --split fit --arms "kmx1@fit|cos,kmx64@fit|cos,$ARMS" --refs "zero|cos,fam@self|cos,tok@fit|cos"
