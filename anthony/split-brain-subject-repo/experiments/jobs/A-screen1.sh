#!/bin/bash
# night-2 A (j-lens-mean-2e): S13 / S14 / S15 fit screen, strict, all 11 families (one lens load).
set -euo pipefail
PY=.venv/bin/python
FAMS=${FAMS:-"typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"}
BANKS=$(for f in $FAMS; do printf "%s/fit," "$f"; done); BANKS=${BANKS%,}
C=""
for c in s13uni s13wiki s13:unigram-norobots:0.5 s13:unigram-norobots:2 s13:unigram-norobots:4 s13:unigram-norobots:1:cos:r256 \
         s13:unigram-norobots:1:fam s13:unigram-norobots:2:fam \
         s14t16 s14t64 s14t128 s14fam16 s14fam64 s14fam128 s14r16 s14r64 s14r128 s14famr16 s14famr64 s14famr128 \
         s15top8 s15top32 s15top128 s15famtop32 s15r32; do C="$C$c@self|cos,"; done
for c in s13uni s13:unigram-norobots:1:rms s13:unigram-norobots:2:rms s14t64 s14fam16 s14fam64 s15top32; do C="$C$c@self|rms,"; done
$PY experiments/evaluate.py --banks "$BANKS" --arms "${C%,}" --device cuda
# the shuffled-prior control last: its pullback needs the eigendecompositions (pb-eig) on the volume
$PY experiments/s13_shuffled_prior.py
[ -e out/priors/pullback/unigram-norobots-shuf0-cos-rfull.pt ] || \
  $PY experiments/precompute_pullback.py --priors unigram-norobots-shuf0 --readouts cos,rms --ranks full --device cuda
$PY experiments/evaluate.py --banks "$BANKS" --arms "s13:unigram-norobots-shuf0:1@self|cos,s13:unigram-norobots-shuf0:4@self|cos" --device cuda
