#!/bin/bash
# Hidden intermediates (chain / brew): plain J-lens and J++, family and token centres, and the night-2 finalists, on
# fit / val / bench. Waits for the family's three captures (out/ is the shared volume). Inside tmux on a pod:
#   FAMILY=chain_intermediates bash experiments/jobs/hidden_intermediates_eval.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
export PATH="$HOME/.local/bin:$PATH" HF_HOME=/workspace/hf OMP_NUM_THREADS=8
FAMILY="${FAMILY:?}"
exec > >(tee -a "out/logs/hi-eval-$FAMILY.log") 2>&1
for s in fit val bench; do
  until [ -f "out/captures/$FAMILY-$s.provenance.json" ]; do sleep 20; done
done
B="s14:template:64:mean=kmx64:a=0.5"
KNNXS8="sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5"
S14BL="sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5"
BASE="zero|cos,zero|rms,fam@fit|cos,fam@fit|rms,tok@fit|cos,tok@fit|rms"
JPP="jpp:zero|cos,jpp:zero|rms,jpp:fam@fit|cos,jpp:tok@fit|cos"
FIN="$KNNXS8@fit|cos,$S14BL@fit|cos,$S14BL@fit|rms,s20xt:1@fit|cos,rand.$S14BL@fit|cos,jpp:$KNNXS8@fit|cos,jpp:$S14BL@fit|cos"
echo "[hi-eval $(date '+%H:%M:%S')] evaluate $FAMILY"
.venv/bin/python experiments/evaluate.py --banks "$FAMILY/fit,$FAMILY/val,$FAMILY/bench" --arms "$BASE,$JPP,$FIN" \
  --device cuda --keep-going && echo "[hi-eval $(date '+%H:%M:%S')] EVAL DONE" || echo "[hi-eval] EVAL FAILED"
