#!/bin/bash
# S18 fit screen (instance e1): sparse fam, its complement, random coordinates, wikitext values. Stops at the first failure.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS="s18k8@self|cos,s18k32@self|cos,s18k128@self|cos,s18k512@self|cos,s18c8@self|cos,s18c32@self|cos,s18c128@self|cos,s18r32@self|cos,s18r512@self|cos,s18w8@self|cos,s18w32@self|cos,s18ww32@self|cos,s18ww128@self|cos"
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S18-fit --split fit --arms "$ARMS" --refs "zero|cos,fam@self|cos" --decode-g --device cuda
