"""Strand 4 of agent 7's stage 0: do persistence (new attempts), check-aimed work and doubt change after a rejection?

  python src/rejection_persistence.py <stage0 dir> <labels.jsonl> <sample.json> <out json>

Labels: the shared labeller (src/cot_labels.py) on agent 4's stratified Qwen sample of Goodfire's ImpossibleBench
episodes (logs/ib_persistence/sample.json; labels logs/ib_persistence/labels/ib_v34.jsonl, prompt v3.4, luna_med;
the main pass is unchanged in v3.5). Only the 40 impossible-split episodes. Provisional: task/check is unreliable on
honest episodes until hand labels exist (notes/definitions.md).

Per turn: counts of units by measure, divided by the turn's characters (model text). Compared: turns written before
any rejection (turn index >= 5) vs the turn right after a rejection vs later turns after one, and a Mantel-Haenszel
rate ratio (after >=1 rejection vs none yet) over strata of the exact turn index.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import rejection_stage0 as r0  # noqa: E402

MEASURES = {
    "new_task": lambda u: u["label"] == "attempt" and u["target"] == "task" and u["new"],
    "new_check": lambda u: u["label"] == "attempt" and u["target"] == "check" and u["new"],
    "check_attempt": lambda u: u["label"] == "attempt" and u["target"] == "check",
    "doubt_legitimacy": lambda u: u["label"] == "doubt_legitimacy",
    "doubt_correctness": lambda u: u["label"] == "doubt_correctness",
    "obstacle": lambda u: bool(u.get("obstacle")),
}
NAMES = {"new_task": "new task-aimed candidates (persistence)", "new_check": "new check-aimed candidates",
         "check_attempt": "check-aimed attempt units", "doubt_legitimacy": "weighing a shortcut (as labelled)",
         "doubt_correctness": "correctness doubt units", "obstacle": "noticed-obstacle units"}


def mh_rate(d, col, exposed, strata="turn"):
    num = den = 0.0
    for _, s in d.groupby(strata):
        x, y = s[s[exposed]], s[~s[exposed]]
        if not len(x) or not len(y):
            continue
        t1, t0 = x.kchars.sum(), y.kchars.sum()
        T = t1 + t0
        num += x[col].sum() * t0 / T
        den += y[col].sum() * t1 / T
    return num / den if den else float("nan")


def main(d, labels, sample, out):
    t, e = r0.load(d)
    ids = {x["id"] for x in json.load(open(sample))["episodes"] if x["set"] == "IB impossible"}
    counts = defaultdict(lambda: defaultdict(int))
    for l in open(labels):
        u = json.loads(l)
        if u["episode"] not in ids or u.get("label") is None:
            continue
        k = (int(u["episode"].split("|")[1]), u["turn"])
        for m, f in MEASURES.items():
            counts[k][m] += bool(f(u))
    rows = [dict(row=r, turn=k, **v) for (r, k), v in counts.items()]
    c = pd.DataFrame(rows).fillna(0)
    q = t[(t.model == "Qwen") & t.imp].merge(c, on=["row", "turn"], how="inner")
    q["kchars"] = q.chars / 1000
    q["rej"] = q.n_rej > 0
    print("episodes", q.row.nunique(), "turns", len(q))
    res = []
    late = q[q.turn >= 5]
    for m in MEASURES:
        for lab, s in [("no rejection yet (turn 5+)", late[~late.rej]),
                       ("turn right after a rejection", q[q.rej & q.just_rej]),
                       ("later turns after a rejection", q[q.rej & ~q.just_rej])]:
            res.append(dict(measure=NAMES[m], when=lab, units=int(s[m].sum()), kchars=round(s.kchars.sum(), 1),
                            turns=len(s), episodes=s.row.nunique(),
                            per_1k_chars=round(s[m].sum() / s.kchars.sum(), 3) if s.kchars.sum() else None))
        res.append(dict(measure=NAMES[m], when="turn-matched rate ratio, after >=1 rejection vs none",
                        per_1k_chars=round(mh_rate(q, m, "rej"), 2)))
    df = pd.DataFrame(res)
    print(df.to_string(index=False))
    Path(out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
