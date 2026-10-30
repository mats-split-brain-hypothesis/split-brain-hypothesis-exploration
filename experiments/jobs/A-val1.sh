#!/bin/bash
# night-2 A (j-lens-mean-2e): S14 val confirmation (k = 64 chosen on fit), strict, all 11 families.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/val," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms \
  "s14t64@fit|cos,s14t64@fit|rms,s14fam64@fit|cos,s14fam64@fit|rms,s14r64@fit|cos,s14famr64@fit|rms,s14t128@fit|cos"
