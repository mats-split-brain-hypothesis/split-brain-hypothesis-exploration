#!/bin/bash
# S24b: the one registered strict read of val2b (mu-log card S24), on the eval pod, refs = fit. Read once.
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
B=multihop/val2b,multilingual/val2b
COS="zero|cos,fam@fit|cos,sched:40:kmx64+s14t64@fit|cos,sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos,sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos,s20xt:1@fit|cos,sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos,s14:template:64:mean=kmx64:a=0.5@fit|cos,s20xon:1:kmx64@fit|cos"
RMS="fam@fit|rms,s14:template:64:mean=kmx64:a=0.5@fit|rms,s20xonrms:1:kmx64@fit|rms"
.venv/bin/python experiments/evaluate.py --banks "$B" --arms "$COS,$RMS" --no-next --device cuda || { echo "[s24bread] FAILED"; exit 1; }
echo "[s24bread] done"
