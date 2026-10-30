"""Hand-check helper: print the passages the cheap model flagged, for reading and recording verdicts.

  python src/stakes_flagcheck.py <flag> [--per-trial 3] [--chars 320] [--skip-checked]

Prints, per trial, up to N flagged passages with their ids. Verdicts go in notes/stakes_flag_checks.json as
{"checks": {"<flag>": {"<passage id>": true | false}}}. src/stakes_analysis.py counts a trial for a hand-checked
flag only if one of its flagged passages is marked true there.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L = ROOT / "logs" / "stakes"

p = argparse.ArgumentParser()
p.add_argument("flag")
p.add_argument("--per-trial", type=int, default=3)
p.add_argument("--chars", type=int, default=320)
p.add_argument("--skip-checked", action="store_true")
a = p.parse_args()
passages = {json.loads(l)["id"]: json.loads(l) for l in open(L / "passages.jsonl")}
cpath = ROOT / "notes" / "stakes_flag_checks.json"
checked = json.load(open(cpath))["checks"].get(a.flag, {}) if cpath.exists() else {}
by = defaultdict(list)
for l in open(L / "reasoning_labels.jsonl"):
    lab = json.loads(l)
    if lab.get(a.flag) and not (a.skip_checked and lab["id"] in checked):
        by[passages[lab["id"]]["trial"]].append((lab, passages[lab["id"]]))
total = sum(len(v) for v in by.values())
print(f"{a.flag}: {total} flagged passages in {len(by)} trials")
for trial, items in sorted(by.items()):
    print(f"\n== {trial} ({len(items)} flagged)")
    for lab, ps in items[:a.per_trial]:
        reason = f" | {lab['reason']}" if lab.get("reason") else ""
        print(f"  [{lab['id'].split('|')[1]}] step {ps['step']}: {ps['text'][:a.chars]!r}{reason}")
