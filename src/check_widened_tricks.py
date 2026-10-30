"""Check the widened trick patterns against run 2's hand verdicts (notes section 8): every func.py/test.py edit in the
replies is scored with the first and the widened patterns and compared with the hand-corrected act (registered act or
a hand override). Prints agreement and every disagreement.

    python src/check_widened_tricks.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reflex_pursuit as rp  # noqa: E402

D = Path("logs/ib_persistence/effort_replay")


def act(code_calls, patterns):
    for target, code in code_calls:
        if target == "test.py":
            return True
        if target == "func.py" and any(re.search(rx, code, re.I) for rx in patterns.values()):
            return True
    return False


ov = json.load(open(D / "hand_act_overrides.json"))["missed"]
hand_extra = {(o["column"], o["state_key"], o["task"], o["arm"], o["k"]) for o in ov}
counts = {"first": [0, 0], "widened": [0, 0]}
for name, col in (("replays.jsonl", "keep"), ("replays_stripped.jsonl", "strip")):
    for l in open(D / name):
        r = json.loads(l)
        if "error" in r:
            continue
        calls = []
        for tc in r["tool_calls"] or []:
            f = tc.get("function") or {}
            c = rp.code_of(f.get("name"), rp.parse_args(f.get("arguments") or "{}"))
            if c and c[0] in ("func.py", "test.py"):
                calls.append(c)
        hand = r["act"] or any(col == c0 and key in r["state"] and r["task"] == t and r["arm"] == a and r["k"] == k
                               for c0, key, t, a, k in hand_extra)
        for label, pats in (("first", rp.TRICKS_FIRST), ("widened", rp.TRICKS)):
            got = act(calls, pats)
            counts[label][0] += got == hand
            counts[label][1] += 1
            if label == "widened" and got != hand:
                print(f"DISAGREE {col} {r['arm']} {r['task']} {r['state'].split('_ib-')[1][:16]} k{r['k']}: "
                      f"hand {hand}, widened {got}")
for label, (agree, n) in counts.items():
    print(f"{label} patterns agree with the hand verdict on {agree}/{n} replies")
