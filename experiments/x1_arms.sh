#!/usr/bin/env bash
# x1-mu-pos-concept: arms for the positional and abstract-concept centres on typo.
# Usage: bash experiments/x1_arms.sh fit|val [extra evaluate.py args...]
# fit reads the fit split with @self concept/norm refs (exploration, free scoring);
# val reads the val split with @fit refs (held out; run only after registering in
# notes/predictions.md).
set -euo pipefail
cd "$(dirname "$0")/.."
SPLIT=$1; shift || true

ANCHOR="zero|cos,zero|rms,fam@self|cos,fam@self|rms"
CORPUS="fam@corpus8|cos,fam@corpus8|rms,tok@corpus8|cos,tok@corpus8|rms,pos@corpus|cos,pos@corpus|rms,fam@sents|cos,fam@sents|rms"

if [ "$SPLIT" = fit ]; then
  REF=self
  CPT=""
  for a in 0.25 0.5 1 2; do CPT+="cpt:typo:$a@$REF|cos,cpt:typo:$a@$REF|rms,cptc:typo:$a@$REF|cos,cptc:typo:$a@$REF|rms,"; done
  for a in 0.25 0.5 1; do CPT+="cptc+:typo:$a@sents|cos,cptc+:typo:$a@sents|rms,"; done
  CPT+="cpt:misspelling:0.5@$REF|cos,cpt:misspelling:0.5@$REF|rms,cpt:misspelling:1@$REF|cos,cpt:misspelling:1@$REF|rms,"
  CPT+="cpt:spelling:1@$REF|cos,cpt:spelling:1@$REF|rms,cpt:error:1@$REF|cos,cpt:error:1@$REF|rms,"
  CPT+="cpt:giraffe:0.5@$REF|cos,cpt:giraffe:0.5@$REF|rms,cpt:giraffe:1@$REF|cos,cpt:giraffe:1@$REF|rms,cptc:giraffe:1@$REF|cos,cptc:giraffe:1@$REF|rms"
  ARMS="$ANCHOR,$CORPUS,$CPT"
else
  # val arms of record (registered in notes/predictions.md x1): anchors, the corpus/position
  # rungs, the fit-selected concept arms and the giraffe specificity controls.
  CPT="cpt:typo:0.5@fit|cos,cpt:typo:0.5@fit|rms,cpt:typo:1@fit|cos,cpt:typo:1@fit|rms"
  CPT+=",cpt:misspelling:1@fit|cos,cpt:misspelling:1@fit|rms,cptc:typo:1@fit|cos,cptc:typo:1@fit|rms"
  CPT+=",cpt:giraffe:0.5@fit|cos,cpt:giraffe:0.5@fit|rms,cpt:giraffe:1@fit|cos,cpt:giraffe:1@fit|rms"
  CPT+=",cptc:giraffe:1@fit|cos,cptc:giraffe:1@fit|rms"
  ARMS="$ANCHOR,fam@fit|cos,fam@fit|rms,$CORPUS,$CPT"
fi

exec .venv/bin/python experiments/evaluate.py --family typo --split "$SPLIT" --arms "$ARMS" "$@"
