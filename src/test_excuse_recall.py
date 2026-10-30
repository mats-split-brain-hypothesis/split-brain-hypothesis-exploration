"""Test 3, M1e recall check (registered): 5 episodes per context (seed 6). In each, every sentence within 3 of a mention
of the framing's key words that is NOT a candidate is printed, for a by-hand verdict on whether it is a test-or-real
remark the lists missed. Run late (after `measure`); the notes say so.

  python src/test_excuse_recall.py logs/stakes/excuse
"""
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_excuse import SETS, SENT  # noqa: E402

out = Path(sys.argv[1])
E = [json.loads(l) for l in open(out / "episodes.jsonl")]
C = {(json.loads(l)["episode"], json.loads(l)["node"], json.loads(l)["channel"], json.loads(l)["sent"])
     for l in open(out / "candidates.jsonl")}
KEY = {"real": re.compile(r"\b(colleague|at work|accounting|our (library|team|code)|the user|a person|human)\b", re.I),
       "eval": re.compile(r"\b(automated pipeline|pipeline|autograder|no person|no human|nobody)\b", re.I)}
ctx = {"real": [e for e in E if e["dataset"] == "g3" or (e["dataset"] == "dm" and e["arm"] in ("RR", "GR"))],
       "eval": [e for e in E if e["dataset"] in ("r3", "r4") and e["arm"] in ("G-control", "G4-C")
                or (e["dataset"] == "dm" and e["arm"] in ("RG", "GG"))]}
rng = random.Random(6)
pick = {k: rng.sample(sorted(v, key=lambda e: e["episode"]), 5) for k, v in ctx.items()}
want = {e["episode"]: k for k, v in pick.items() for e in v}
for name, loader in SETS.items():
    if name == "gf_ib":
        continue
    for ep, turns in loader():
        if ep["episode"] not in want:
            continue
        k = want[ep["episode"]]
        shown = 0
        print(f"\n### [{k}] {ep['episode']} arm={ep['arm']}")
        for node, reas, text in turns:
            for ch, txt in (("reasoning", reas), ("reply", text)):
                sents = [s.strip() for s in SENT.split(txt or "") if s.strip()]
                near = set()
                for i, s in enumerate(sents):
                    if KEY[k].search(s):
                        near.update(range(max(0, i - 3), min(len(sents), i + 4)))
                for i in sorted(near):
                    if (ep["episode"], node, ch, i) not in C and shown < 25:
                        print(f"  n{node} {ch[:4]} s{i}: {sents[i][:200]}")
                        shown += 1
        print(f"  ({shown} non-candidate sentences shown)")
