#!/bin/bash
# S20x transfer matrix (instance e1): each source family's correction alone (alpha 0.5: about dbar's norm), on fit.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS=""
for g in typo association basic_readout multihop multilingual directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt; do
  ARMS="$ARMS,s20x1:$g:0.5@self|cos"
done
$PY experiments/evaluate.py --banks "$FIT" --arms "${ARMS#,}" --device cuda --no-sem
