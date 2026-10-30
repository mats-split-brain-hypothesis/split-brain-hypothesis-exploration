#!/bin/bash
# Judge the open-ended purpose answers of the eval-probe first pass (Needham's consistency template, cheap judge).
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
D=logs/eval_probe
for f in a1_gf_ib a1_our_ib a1_wildchat a1_gf_swe_tau a1_sorh_persist a1_sorh_cues; do
  $PY src/eval_probe.py judge $D/$f.jsonl --budget 0.6
done
echo "JUDGED"
