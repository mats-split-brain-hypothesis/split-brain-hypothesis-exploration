#!/bin/bash
# Rebuild every rule-based table of the grader-beliefs tab, in dependency order (no API calls).
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python
PC=/private/tmp/claude-501/-Users-biancaganescu-Code-split-brain-hypothesis/ea4b9a7d-bd86-4d47-84d0-d2b40ad6ba06/scratchpad/mf_data/runs
$PY src/grader_actions.py logs/data > logs/grader/actions_report.txt
$PY src/grader_swe_order.py logs/data > logs/grader/swe_order_report.txt
$PY src/grader_hack_timeline.py logs/data > logs/grader/hack_timeline_report.txt
$PY src/grader_why.py logs/data > logs/grader/why_report.txt
$PY src/grader_chasing.py logs/data > logs/grader/chasing_report.txt
$PY src/grader_label_rates.py logs/data > logs/grader/label_rates.out
$PY src/grader_examples.py logs/data "$PC" > /dev/null
$PY src/precommit_shortcut_reasoning.py "$PC" > logs/grader/precommit_shortcut_report.txt
$PY src/eval_probe_dashboard.py > logs/grader/probe_dashboard_report.txt
$PY src/grader_dashboard.py > logs/grader/dashboard_report.txt
echo "rebuilt"
