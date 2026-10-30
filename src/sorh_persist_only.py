"""Unit list for `cot_labels.py label --only`: the reasoning units of the feedback turns (turn >= 1) of the episodes in
a label folder. The persistence-after-a-low-score, doubt and 'what precedes gaming' measures use only these; turn 0
is the same first reply for every variant of a prompt and sample, and the reply text is judged separately.

  python src/sorh_persist_only.py <label folder> <out.csv>
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cot_labels as C  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
n_ep = n_all = n_keep = 0
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id"])
    for ep in C.load(src):
        n_ep += 1
        for u in C.units(ep):
            n_all += 1
            if u["turn"] >= 1 and u["channel"] == "reasoning":
                w.writerow([f"{ep['id']}|{u['turn']}|{u['channel']}|{u['unit']}"])
                n_keep += 1
print(f"{n_ep} episodes: {n_keep} of {n_all} units kept ({n_keep / max(1, n_all):.0%})")
