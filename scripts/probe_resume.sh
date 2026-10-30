#!/bin/bash
# Resume the eval-probe runs cut by the 2026-10-21 pause (each skips answers already in its output file).
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
D=logs/eval_probe
$PY src/eval_probe.py run $D/p1_netline.jsonl --out $D/a1_netline.jsonl --probes purpose_mc:30,eval_binary:10 --budget 0.4
$PY src/eval_probe.py run $D/p2_a7false.jsonl --out $D/a2_a7false.jsonl --probes purpose_mc:3,eval_binary:1 --budget 0.4
$PY src/eval_probe.py run $D/p2_goodfire_notau.jsonl --out $D/a2_goodfire.jsonl --probes purpose_mc:3,eval_binary:1 --budget 8
echo "ALL DONE"
