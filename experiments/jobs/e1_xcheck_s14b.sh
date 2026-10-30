#!/bin/bash
# Cross-check of A's S14b (instance e1, steward's card): k-means seeds, chat-corpus pool, and the late mean swapped for
# the fair other-carrier kNN (knnxs8) to size the DM caveat; val, strict.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
B="sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5"
A="$B@fit|cos"
for s in 1 2; do A="$A,sched:40:kmx64s$s+s14:template:64:mean=kmx64s$s:a=0.5@fit|cos"; done
A="$A,sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos,sched:40:kmx64+s14:template:64:mean=knnx8:a=0.5@fit|cos"
$PY experiments/evaluate.py --banks "$VAL" --arms "$A" --device cuda --no-sem
echo "== chat pool"
$PY experiments/evaluate.py --banks "$VAL" --arms "sched:40:kmch128+s14:template:64:mean=kmch128:a=0.5@fit|cos" --device cuda --no-sem
