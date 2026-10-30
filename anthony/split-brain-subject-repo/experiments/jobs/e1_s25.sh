#!/bin/bash
# S25 (instance e1): build the chat-corpus answer-position directions, then the fit screen on S14b-x (cos and rms).
set -euo pipefail
PY=.venv/bin/python
$PY experiments/s25_dirs.py
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
LATE="s14:template:64:mean=knnxs8:a=0.5"
for r in cos rms; do
  A="sched:40:kmx64+$LATE@self|$r"
  for c in cap content latin; do for a in 1 2 4; do A="$A,sched:40:s25on:$a:$c:kmx64+$LATE@self|$r"; done; done
  A="$A,sched:40:s25on:2:rand:kmx64+$LATE@self|$r"
  $PY experiments/evaluate.py --banks "$FIT" --arms "$A" --device cuda --no-sem
done
