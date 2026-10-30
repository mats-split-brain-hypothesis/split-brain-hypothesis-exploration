"""Test 3 post-run hand check (registered): 40 judged candidates from the final (hybrid) labels, seed 6: 20 cls=test,
10 cls=real, 10 use=justifies_violation (drawn in that order, without repeats). Prints short windows; verdicts are
recorded by hand in notes/test_excuse_check40.json.

  python src/test_excuse_check40.py logs/stakes/excuse
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_excuse import final_labels  # noqa: E402

out = Path(sys.argv[1])
C = {json.loads(l)["id"]: json.loads(l) for l in open(out / "candidates.jsonl")}
lab, src = final_labels(out)
rng = random.Random(6)
picked = []
for cond, k in ((lambda x: x["cls"] == "test", 20), (lambda x: x["cls"] == "real", 10),
                (lambda x: x["use"] == "justifies_violation", 10)):
    pool = sorted(i for i, x in lab.items() if cond(x) and i not in {p[0] for p in picked})
    rng.shuffle(pool)
    picked += [(i, lab[i]) for i in pool[:k]]
for n, (i, x) in enumerate(picked, 1):
    c = C[i]
    print(f"\n## {n}. {i} [{src[i]}] cls={x['cls']} hedged={x['hedged']} use={x['use']} cite={x.get('cls_cite')}/"
          f"{x.get('use_cite')} dismiss={x['dismisses_cue']}")
    for k, s in enumerate(c["window"]):
        print(f"  {'>>' if k == c['target'] else '  '}S{k + 1}: {s[:230]}")
