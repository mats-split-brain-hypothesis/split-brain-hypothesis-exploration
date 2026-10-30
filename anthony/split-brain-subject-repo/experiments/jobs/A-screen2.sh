#!/bin/bash
# night-2 A (j-lens-mean-2e): screen 2 on fit. S13d (head-only unigram prior), S14 token-set variants (chatonly: no
# bench data; randfreq0: frequency-matched random tokens, the card's control), rms controls for s14, and the shuffled
# prior control on the seven single-cell families (screen 1 ran it on the _mt four only).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
SEVEN="typo association basic_readout multihop multilingual user_modeling directed_modulation"
banks() { local b; b=$(for f in $1; do printf "%s/fit," "$f"; done); echo "${b%,}"; }
$PY experiments/s13_shuffled_prior.py --head 2000
$PY experiments/s13_shuffled_prior.py --seed 0
[ -e out/priors/pullback/unigram-norobots-head2000-cos-rfull.pt ] || \
  $PY experiments/precompute_pullback.py --priors unigram-norobots-head2000 --readouts cos --ranks full --device cuda
[ -e out/priors/pullback/unigram-norobots-shuf0-cos-rfull.pt ] || \
  $PY experiments/precompute_pullback.py --priors unigram-norobots-shuf0 --readouts cos --ranks full --device cuda
$PY experiments/precompute_pullback.py --template-tokens chatonly --readouts cos --ks 16,64,128,256 --device cuda
$PY experiments/precompute_pullback.py --template-tokens randfreq0 --readouts cos --ks 16,64,128 --device cuda
C=""
for c in s13:unigram-norobots-head2000:0.5 s13:unigram-norobots-head2000:1 s13:unigram-norobots-head2000:2 \
         s14:chatonly:16 s14:chatonly:64 s14:chatonly:128 s14:chatonly:256 s14:chatonly:64:fam \
         s14:randfreq0:16 s14:randfreq0:64 s14:randfreq0:128 s14:randfreq0:64:fam; do C="$C$c@self|cos,"; done
for c in s14r64 s14famr16 s14famr64 s14t16 s14t128 s14fam128 s14:chatonly:64; do C="$C$c@self|rms,"; done
$PY experiments/evaluate.py --banks "$(banks "$ALL")" --arms "${C%,}" --device cuda
$PY experiments/evaluate.py --banks "$(banks "$SEVEN")" --arms "s13:unigram-norobots-shuf0:1@self|cos,s13:unigram-norobots-shuf0:4@self|cos" --device cuda
