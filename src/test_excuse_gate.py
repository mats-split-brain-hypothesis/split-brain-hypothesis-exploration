"""Test 3 pilot gate (registered in notes/test_excuse.md): parse rate, citation validity, and a hand-check sample.

  python src/test_excuse_gate.py <out_dir> <labels.jsonl> <n_requested> [--show N]

Valid citation: cls_cite non-empty for cls in (test, real, grader_only), every number within 1..len(window), and at
least one cited sentence within one of the marked sentence. The hand-check sample (seed 6): the cls=test and
use=justifies_violation labels, up to --show, printed as short windows for a verdict by hand.
"""
import json
import random
import sys
from pathlib import Path

out, labs_path, n_req = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 0
C = {json.loads(l)["id"]: json.loads(l) for l in open(out / "candidates.jsonl")}
L = [json.loads(l) for l in open(labs_path)]
ok_parse = [x for x in L if x.get("cls") in ("test", "real", "grader_only", "none") and
            x.get("use") in ("justifies_violation", "justifies_restraint", "neutral")]
need = [x for x in ok_parse if x["cls"] != "none"]
valid = 0
for x in need:
    c = C[x["id"]]
    cites = [k for k in (x.get("cls_cite") or []) if isinstance(k, int)]
    if cites and all(1 <= k <= len(c["window"]) for k in cites) and any(abs((k - 1) - c["target"]) <= 1 for k in cites):
        valid += 1
print(f"parse {len(ok_parse)}/{n_req} = {len(ok_parse) / n_req:.0%} (bar 95%)")
print(f"valid citations {valid}/{len(need)} = {valid / max(1, len(need)):.0%} (bar 90%)")
from collections import Counter  # noqa: E402
print("cls", dict(Counter(x["cls"] for x in ok_parse)), "use", dict(Counter(x["use"] for x in ok_parse)))
if show:
    pool = [x for x in ok_parse if x["cls"] == "test" or x["use"] == "justifies_violation"]
    random.Random(6).shuffle(pool)
    for x in pool[:show]:
        c = C[x["id"]]
        print(f"\n## {x['id']} | cls={x['cls']} hedged={x['hedged']} use={x['use']} cite={x.get('cls_cite')}/"
              f"{x.get('use_cite')} dismiss={x['dismisses_cue']}")
        for k, s in enumerate(c["window"]):
            print(f"  {'>>' if k == c['target'] else '  '}S{k + 1}: {s[:240]}")
