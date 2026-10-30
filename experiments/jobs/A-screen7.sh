#!/bin/bash
# night-2 A (j-lens-mean-2e): S14c on fit. Token sets from the uncentred lens's top 10 on chat-corpus cells (no bench
# data): build them, their bases, and screen s14 with them (alone, and late under fam as S14s found best).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/s14_chatread_tokens.py --device cuda
$PY experiments/precompute_pullback.py --template-tokens chatread --readouts cos --ks 16,64,128 --device cuda
$PY experiments/precompute_pullback.py --template-tokens chatreadlate --readouts cos --ks 16,64,128 --device cuda
C=""
for s in chatread chatreadlate; do for k in 16 64 128; do C="${C}s14:$s:$k@self|cos,"; done; done
C="${C}sched:40:fam+s14:chatread:64@self|cos,sched:40:fam+s14:chatreadlate:64@self|cos"
$PY experiments/evaluate.py --banks "$B" --arms "$C" --device cuda
