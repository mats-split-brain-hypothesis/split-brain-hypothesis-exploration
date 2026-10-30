#!/bin/bash
# Round-2 infrastructure on a pod (cards S13-S20): the chat-format corpus capture, the per-cell next-token pullbacks
# and the lens caches, all onto the shared volume (/workspace/out). One 80 GB GPU; about an hour. Inside tmux:
#   bash experiments/jobs/round2_precompute.sh                 # everything
#   STEPS=priors,ctx bash experiments/jobs/round2_precompute.sh # a subset: ctx | priors | pullback | nexttoken
# Afterwards on the Mac: python tools/hfdata.py push priors lens   (and pull on the other machine).
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
STEPS="${STEPS:-ctx,priors,pullback,nexttoken}"
PY=.venv/bin/python
mkdir -p out/priors/pullback
exec > >(tee -a out/priors/pullback/round2-pod.log) 2>&1
step() { echo "[round2 $(date '+%H:%M:%S')] $*"; }
has() { [[ ",$STEPS," == *",$1,"* ]]; }

if has ctx; then
  step "chat corpus capture (no_robots renders, every position)"
  $PY experiments/capture_ctx.py --corpus chat --n 2048 --seq 128 --device cuda || { step "FAILED chat corpus"; exit 1; }
  step "bank context captures (skips existing)"
  $PY experiments/capture_ctx.py --banks all --device cuda || { step "FAILED bank ctx"; exit 1; }
fi
if has priors; then
  step "unigram priors and the template-token set (tokenizer only)"
  $PY experiments/build_priors.py --unigram chat && $PY experiments/build_priors.py --unigram wikitext \
    && $PY experiments/build_priors.py --template-tokens || { step "FAILED priors"; exit 1; }
fi
if has pullback; then
  step "lens caches: eigendecompositions, prior pullbacks, template bases, J SVDs"
  $PY experiments/precompute_pullback.py --eig --priors unigram-norobots,unigram-wikitext --ranks full,256 \
    --template-tokens template --ks 16,64,128 --jsvd --device cuda || { step "FAILED pullback"; exit 1; }
fi
if has nexttoken; then
  step "per-cell next-token pullbacks for every family x fit/val (needs out/ctx)"
  $PY experiments/precompute_pullback.py --next-token all --ranks full,256 --device cuda || { step "FAILED next-token"; exit 1; }
fi
step "ALL DONE"; ls -la out/priors out/priors/pullback | head -40
