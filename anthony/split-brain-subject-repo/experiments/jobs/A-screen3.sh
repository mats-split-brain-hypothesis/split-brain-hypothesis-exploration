#!/bin/bash
# night-2 A (j-lens-mean-2e): S13b on fit. The family mean (own group excluded) of the pulled-back next-token
# log-softmax of the reference cells (steward's round-2 precompute), alone and on top of fam, beta and rank grid.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for c in s13nt s13ntf s13:nt:0.5 s13:nt:2 s13:nt:1:r256 s13:ntf:0.5 s13:ntf:2 rand.s13nt shuf.s13nt; do C="$C$c@self|cos,"; done
for c in s13nt s13ntf s13:nt:1:rms s13:ntf:1:rms; do C="$C$c@self|rms,"; done
$PY experiments/evaluate.py --banks "$B" --arms "${C%,}" --device cuda
