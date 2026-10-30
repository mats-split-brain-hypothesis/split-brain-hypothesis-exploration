#!/bin/bash
# night-2 A (j-lens-mean-2e): S14 val, the bench-free token set (chatonly, k = 128 chosen on fit) and the
# frequency-matched random-token control; then the battery with the removed component decoded.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/val," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "s14:chatonly:128@fit|cos,s14:randfreq0:64@fit|cos"
$PY experiments/analyse.py --study S14 --split val --device cuda --decode-g --refs "zero|cos,fam@fit|cos" \
  --arms "s14t64@fit|cos,s14t128@fit|cos,s14:chatonly:128@fit|cos,s14:randfreq0:64@fit|cos,s14fam64@fit|cos,s14r64@fit|cos"
