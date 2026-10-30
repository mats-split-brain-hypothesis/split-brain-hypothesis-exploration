#!/bin/bash
# Eval-probe second pass: full transcripts (~20 per condition) and agent 7's false-rejection run. tau-bench items were
# dropped (the researcher closed tau-bench on 2026-10-21): no tau airline pilot, no Goodfire tau3 (p2_goodfire_notau).
# Each run has its own budget cap; run() also stops if the key has < $10 left.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
D=logs/eval_probe
$PY src/eval_probe.py run $D/p2_wildchat20.jsonl --out $D/a2_wildchat20.jsonl --probes purpose_mc:3,eval_binary:1 --budget 1
$PY src/eval_probe.py run $D/p2_a7false.jsonl --out $D/a2_a7false.jsonl --probes purpose_mc:3,eval_binary:1 --budget 0.5
$PY src/eval_probe.py run $D/p2_ours.jsonl --out $D/a2_ours.jsonl --probes purpose_mc:3,eval_binary:1 --budget 2
$PY src/eval_probe.py run $D/p2_goodfire_notau.jsonl --out $D/a2_goodfire.jsonl --probes purpose_mc:3,eval_binary:1 --budget 8
echo "ALL DONE"
