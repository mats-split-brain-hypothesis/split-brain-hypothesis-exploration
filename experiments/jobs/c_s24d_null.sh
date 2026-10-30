#!/bin/bash
# S24d post-read control (steward): fam + a random direction with the norm of each arm's change from fam, 3 seeds, on
# val2 and val3 (controls only; no selection).
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
B=typo/val2,association/val2,multihop/val2,typo/val3,association/val3,multihop/val3
S14BL="sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5"
A=""
for s in 0 1 2; do A="$A,famr:$s:s20xt:1@fit|cos,famr:$s:s20xon:1:kmx64@fit|cos,famr:$s:$S14BL@fit|cos"; done
.venv/bin/python experiments/evaluate.py --banks "$B" --arms "${A#,}" --no-next --no-sem --device cuda || { echo "[s24dnull] FAILED"; exit 1; }
echo "[s24dnull] done"
