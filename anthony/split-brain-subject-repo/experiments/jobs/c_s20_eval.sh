#!/bin/bash
# S20: read val through the full pipeline (echo, prompt masking, next-token, sem) with the saved ceilings, into
# out/analysis/S20/eval (never out/eval). Then the decode of the learned constants.
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
FAMS="${FAMS:-typo association multihop multilingual basic_readout multihop_mt multilingual_mt typo_mt basic_readout_mt directed_modulation user_modeling}"
B=$(for f in $FAMS; do printf "%s/val," "$f"; done); B=${B%,}
.venv/bin/python experiments/evaluate.py --banks "$B" --out out/analysis/S20/eval \
  --arms "zero|cos,fam@fit|cos,ceil.const@fit|cos,rand.ceil.const@fit|cos,ceil.tok@fit|cos,ceil.proj16@fit|cos" --device cuda \
  || { echo "[s20eval] FAILED evaluate"; exit 1; }
.venv/bin/python experiments/s20_decode.py --device cuda || { echo "[s20eval] FAILED decode"; exit 1; }
echo "[s20eval] done"
