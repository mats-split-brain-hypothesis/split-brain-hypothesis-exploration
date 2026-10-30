"""Grader role, first lexical pass: how a run names the reader of contribution.md (pilots/grader-role/NOTES.md).

Per thinking-carried run (tc-reading/codes.tsv, dumps in ~/split-brain-run/dumps, tool-call lines dropped): counts of
role words for the grader (grader / judge / evaluator / scorer) and of person words (author, reviewer, colleague,
Anthony, the user, he / she / him / his / her), and fn_share = role / (role + person). Crude: pronouns are noisy,
"self-authored" is removed, quotes of TASK.md count as the run's own words. No LLM reader.

    python3 grader_role.py        # writes grader-role/lexical.tsv, prints per-arm medians and the cheats
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DUMPS = Path.home() / "split-brain-run" / "dumps"
OUT = HERE / "grader-role" / "lexical.tsv"
HID = {"misattributed", "uncredited"}

ROLE = re.compile(r"\b(grader|judge|evaluator|scorer)s?\b", re.I)
PERSON = re.compile(r"\b(author|reviewer|colleague|anthony|the user|he|she|him|his|her)\b", re.I)


def text(run):
    p = DUMPS / f"{run}.txt"
    if not p.exists():
        return None
    t = "\n".join(l for l in p.open() if not l.lstrip().startswith("->"))
    return t.replace("self-authored", "")


def main():
    rows = []
    for r in csv.DictReader((HERE / "tc-reading" / "codes.tsv").open(), delimiter="\t"):
        m = re.search(r"-(A\d+[ab]?)-([a-z0-9]+)-tc", r["run"])
        t = text(r["run"])
        if not m or t is None:
            continue
        role, person = len(ROLE.findall(t)), len(PERSON.findall(t))
        rows.append({"run": r["run"], "arm": m.group(1), "model": m.group(2), "outcome": r["outcome"], "role": role,
                     "person": person, "fn_share": f"{role / (role + person):.2f}" if role + person else ""})
    with OUT.open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    by = defaultdict(list)
    for x in rows:
        by[x["arm"]].append(x)
    for arm in sorted(by, key=lambda a: (len(a), a)):
        s = sorted(float(x["fn_share"]) for x in by[arm] if x["fn_share"])
        cheats = [f'{x["run"]} {x["fn_share"]}' for x in by[arm] if x["outcome"] in HID]
        print(f"{arm:5} n={len(by[arm]):2} median={s[len(s) // 2]:.2f}  " + "; ".join(cheats))


if __name__ == "__main__":
    main()
