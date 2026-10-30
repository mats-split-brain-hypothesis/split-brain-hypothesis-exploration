"""v2 1h result: over the same episodes, (a) a score-aimed draft already in the first reply's reasoning, and (b) the
first score-aimed draft after feedback falling in the first feedback turn. The first reply is shared by every variant
of a (turn-1 kind, prompt, sample), so its labels (from whichever episode was labelled) apply to all of them.

  python src/sorh_turn0_result.py
"""
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_persist as P  # noqa: E402
import sorh_persist_dash as D  # noqa: E402

t0 = {}  # (kind, prompt, sample) -> any new check-aimed unit in turn 0
# The first-reply labels live in cot_turn0_v34.jsonl, outside the cot_labels_v34* files that sorh_persist_dash.labels()
# reads: that function keys episodes by variant/prompt/sample, so a turn-0-only copy would replace an episode's
# feedback-turn labels (it did, once: 217 -> 181).
for f in glob.glob(str(P.ROOT / "logs" / "sorh_persistence" / "cot_labels_v34*.jsonl")) + \
        [str(P.ROOT / "logs" / "sorh_persistence" / "cot_turn0_v34.jsonl")]:
    if f.endswith(".raw.jsonl"):
        continue
    for line in open(f):
        u = json.loads(line)
        if u.get("turn") != 0 or u.get("channel") != "reasoning":
            continue
        m = re.search(r"/([a-z_0-9]+)/(sorh_\d+)/(\d+)\.json", u.get("episode", ""))
        if not m:
            continue
        v, t, s = m.groups()
        if v not in P.VARIANTS:
            continue
        k = (P.VARIANTS[v][0], t, s)
        hit = u.get("label") == "attempt" and u.get("target") == "check" and bool(u.get("new"))
        t0[k] = t0.get(k, False) or hit
D.precede()
pos = D.precede.positions
n = len(pos)
have = [p for p in pos if (P.VARIANTS[p[0].split("/")[0]][0], *p[0].split("/")[1:]) in t0]
already = sum(t0[(P.VARIANTS[p[0].split("/")[0]][0], *p[0].split("/")[1:])] for p in have)
first_turn = sum(p[1] == 1 for p in pos)
by_kind = {}
for p in have:
    kind = P.VARIANTS[p[0].split("/")[0]][0]
    a, b = by_kind.get(kind, (0, 0))
    by_kind[kind] = (a + t0[(kind, *p[0].split("/")[1:])], b + 1)
distinct = {(P.VARIANTS[p[0].split("/")[0]][0], *p[0].split("/")[1:]) for p in have}
per_kind = {}
for k in distinct:
    a, b = per_kind.get(k[0], (0, 0))
    per_kind[k[0]] = (a + t0[k], b + 1)
print(f"(a) per distinct first reply (the 217 episodes share {len(distinct)}): {per_kind}")
print(f"episodes with a score-aimed draft after feedback: {n}; first reply labelled: {len(have)}")
print(f"(a) score-aimed draft already in the first reply: {already}/{len(have)}  by first-reply kind: {by_kind}")
print(f"(b) first score-aimed draft after feedback is in the first feedback turn: {first_turn}/{n}")
out = P.ROOT / "logs" / "sorh_persistence" / "turn0_result.json"
out.write_text(json.dumps({"n": n, "first_reply_labelled": len(have), "already_in_first_reply": already,
                           "in_first_feedback_turn": first_turn, "by_kind": by_kind}, indent=1))
