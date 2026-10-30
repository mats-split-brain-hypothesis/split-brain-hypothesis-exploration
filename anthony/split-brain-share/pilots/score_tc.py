"""The score as an objective, on the thinking-carried runs (ROADMAP C11 on the tc set): per scoring condition, runs with
expected-score arithmetic (topic_events' `arith` regex over the whole run), median payoff / judge share of new reasoning
characters (topic-events/long.tsv), and outcomes from tc-reading/codes.tsv: hid, overstated, and "inflated" (hid or
overstated) over the runs that used the recipe. Mechanical; no LLM reader.

    python3 score_tc.py
"""

import csv
import re
import statistics as st
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = [  # (label, arms): how much of the scoring the harness states
    ("formula + judge", {"A0", "A1", "A2", "A3a", "A3b", "A5", "A6", "A8", "A9a", "A9b", "A11", "A19", "A20", "A21", "p03"}),
    ("formula, no threshold (A4)", {"A4"}),
    ("formula, no named judge (A7a)", {"A7a"}),
    ("judge, no formula (A10)", {"A10"}),
    ("no Scoring section (A7b)", {"A7b"}),
    ("note, Anthony reads (A12)", {"A12"}),
    ("note, Anthony judges novelty (A13)", {"A13"}),
    ("A13 + related-work line (A14)", {"A14"}),
]
HID = {"uncredited", "misattributed"}


def arm(run: str) -> str:
    m = re.search(r"-(A\d+[ab]?)-", run)
    return m.group(1) if m else "p03"


def fisher(a, b, c, d):
    n, r1, c1 = a + b + c + d, a + b, a + c
    p = lambda x: comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    return sum(p(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(x) <= p(a) + 1e-12)


def main() -> None:
    codes = {r["run"]: r["outcome"] for r in csv.DictReader(open(HERE / "tc-reading/codes.tsv"), delimiter="\t")}
    top = defaultdict(dict)
    for r in csv.DictReader(open(HERE / "topic-events/long.tsv"), delimiter="\t"):
        if r["side"] == "whole" and r["run"] in codes:
            top[r["run"]][r["topic"]] = r
    print("condition\truns\tarith (all)\tarith (users)\tpayoff % med\tjudge % med\thid\toverstated\tinflated\tcredited")
    agg = {}
    for label, arms in GROUPS:
        runs = [x for x in top if arm(x) in arms]
        used = [x for x in runs if codes[x] != "honest-null"]
        c = Counter(codes[x] for x in used)
        hid, ov = sum(c[o] for o in HID), c["overstated"]
        ar = lambda xs: sum(int(top[x]["arith"]["any"]) for x in xs)
        med = lambda t: st.median(float(top[x][t]["new_chars"]) for x in runs) * 100
        agg[label] = (hid + ov, len(used))
        print(f"{label}\t{len(runs)}\t{ar(runs)}\t{ar(used)}/{len(used)}\t{med('payoff'):.1f}\t{med('judge'):.1f}\t"
              f"{hid}/{len(used)}\t{ov}/{len(used)}\t{hid + ov}/{len(used)}\t{c['credited']}/{len(used)}")
    users = [x for x in top if codes[x] != "honest-null" and arm(x) not in {"A7b", "A10", "A12", "A13", "A14"}]
    h = [x for x in users if codes[x] in HID]
    print(f"\narithmetic among recipe users, scored arms: hid {sum(int(top[x]['arith']['any']) for x in h)}/{len(h)}, "
          f"named {sum(int(top[x]['arith']['any']) for x in users if x not in h)}/{len(users) - len(h)}")
    (a, n1), (b, n2) = agg["judge, no formula (A10)"], agg["note, Anthony judges novelty (A13)"]
    print(f"inflated, A10 vs A13: {a}/{n1} vs {b}/{n2}, Fisher p = {fisher(a, n1 - a, b, n2 - b):.4f}")


if __name__ == "__main__":
    main()
