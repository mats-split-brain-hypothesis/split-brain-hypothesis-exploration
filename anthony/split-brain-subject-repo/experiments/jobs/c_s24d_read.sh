#!/bin/bash
# S24d: the one registered strict read of val3 (mu-log card S24d), on the eval pod, refs = fit. Read once.
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
B=typo/val3,association/val3,multihop/val3
S14BL="sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5@fit|cos"
S14BX="sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos"
S21B="sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos"
ARMS="zero|cos,fam@fit|cos,$S14BL,$S14BX,s20xt:1@fit|cos,s20xon:1:kmx64@fit|cos,$S21B,rand.$S14BL,rand.s20xt:1@fit|cos,rand.s20xon:1:kmx64@fit|cos"
.venv/bin/python experiments/evaluate.py --banks "$B" --arms "$ARMS" --no-next --device cuda || { echo "[s24dread] FAILED"; exit 1; }
echo "[s24dread] done"
