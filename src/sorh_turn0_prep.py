"""v2 1h: label the first reply's reasoning wherever it is still unlabelled, so the "already in the first reply" and
"right after the first grader message" numbers count the same episodes (notes, "Pre-registration v2").

  python src/sorh_turn0_prep.py      # writes logs/sorh_persistence/label_turn0/ and only_t0.csv
  python src/cot_labels_pinned.py c3eccac label logs/sorh_persistence/label_turn0 \
      --out logs/sorh_persistence/cot_turn0_v34.jsonl --only logs/sorh_persistence/only_t0.csv --budget 1.5

The first reply is shared by every variant of a (turn-1 kind, prompt, sample); one episode per first reply is copied.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_persist as P  # noqa: E402
import sorh_persist_dash as D  # noqa: E402
import cot_labels as C  # noqa: E402

OUT = P.ROOT / "logs" / "sorh_persistence"
D.precede()
need = {}
for key, turn, idx, t1lab, k1 in D.precede.positions:
    v, t, s = key.split("/")
    if not t1lab:
        need.setdefault((P.VARIANTS[v][0], t, s), key)
dst = OUT / "label_turn0"
if dst.exists():
    shutil.rmtree(dst)
for (kind, t, s), key in sorted(need.items()):
    v = key.split("/")[0]
    p = dst / v / t / f"{s}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(P.RAW / v / t / f"{s}.json", p)
n = 0
with open(OUT / "only_t0.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id"])
    for ep in C.load(str(dst)):
        for u in C.units(ep):
            if u["turn"] == 0 and u["channel"] == "reasoning":
                w.writerow([f"{ep['id']}|{u['turn']}|{u['channel']}|{u['unit']}"])
                n += 1
print(f"{len(need)} first replies copied to {dst}; {n} reasoning units in only_t0.csv")
