#!/bin/bash
# J++ x finalists on val: the night-2 finalist centres (S24 / S24d arm list) read through the J++ map (jpp: prefix),
# cos and rms, with the random-direction controls of S14bL and S20x. The J-lens arms of the same centres are already on val.
# Template bases and S20x corrections are the J-lens-fitted caches, reused as-is through J++.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
B="s14:template:64:mean=kmx64:a=0.5"
S14BL="sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5"
COS="sched:40:kmx64+s14t64 sched:40:kmx64+$B sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5 $S14BL s20xt:1 s20xon:1:kmx64 sched:40:s20xon:1:kmx64+$B rand.$S14BL rand.s20xt:1"
RMS="sched:40:kmx64+s14t64 $S14BL s20xtrms:1 s20xonrms:1:kmx64 sched:40:s20xonrms:1:kmx64+$B"
ARMS=$( (for c in $COS; do printf "jpp:%s@fit|cos," "$c"; done; for c in $RMS; do printf "jpp:%s@fit|rms," "$c"; done) )
ARMS=${ARMS%,}
$PY experiments/evaluate.py --banks "$VAL" --arms "$ARMS" --device cuda
echo JPP_VAL_DONE
