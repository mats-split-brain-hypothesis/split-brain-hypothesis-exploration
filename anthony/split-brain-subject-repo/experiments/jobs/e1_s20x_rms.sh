#!/bin/bash
# S20x / S21 readout-matched (instance e1): corrections fitted through the rms map, read with rms. Fit alpha grid, then
# val at ALPHA (default 1, the cos choice; set ALPHA to the fit choice).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/s20x_dbar.py --readout rms
$PY experiments/evaluate.py --banks "$FIT" --arms "fam@self|rms,s20xtrms:0.5@self|rms,s20xtrms:1@self|rms,s20xtrms:2@self|rms" --device cuda --no-sem
a=${ALPHA:-1}
$PY experiments/evaluate.py --banks "$VAL" --arms "s20xtrms:$a@fit|rms,sched:40:s20xonrms:$a:kmx64+s14t64@fit|rms,sched:40:kmx64+s14t64@fit|rms" --device cuda --no-sem
