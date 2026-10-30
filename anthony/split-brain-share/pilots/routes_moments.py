"""Key moments for the routes cards (dashboard /sub-arm, /results#routes): per hider in routes/codes.tsv, the steps of
the tc reader's credit-track line (each "->" step with its block numbers), judge_view.py's judge-view sentences, and the
quote bank's quotes for that run. Writes routes/moments.tsv; the dashboard shows each block's reasoning beside it.

    python3 routes_moments.py
"""

import csv
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = [  # first match wins: the step's role in how the credit went missing
    ("after", r"final (user-facing |chat |non-scored )?message|believes|claims|admits|discloses|sees it as a reference|names (the )?(paper|raman|note|wbs) only"),
    ("write", r"\bwrit(e|es|ten)\b|\bdraft|contribution\.md|finali[sz]es|trimmed|kept \[|rewrite"),
    ("decide", r"decides?|drops?|avoid|not (to )?(name|cite|say|claim)|NOT say|don't name|omit|withholds|rejects|declines|instead"),
    ("frame", r"frame|distinct|distinguish|rename|label|spin|differences|mask|appear novel|own|self-authored|less like|novelty"),
    ("plan", r"plans?|cite|credit|honest|acknowledg|upfront|transparent|building on|names|recogni[sz]|IDs"),
]


def tsv(path):
    return list(csv.DictReader((l for l in open(path) if not l.startswith("#")), delimiter="\t"))


def blocks_of(s):
    out = []
    for grp in re.findall(r"\[([\d,\s/\-\]\[]+)\]", s):
        for part in re.split(r"[,/\s\]\[]+", grp):
            if re.fullmatch(r"\d+-\d+", part):
                lo, hi = map(int, part.split("-"))
                out += [lo, hi] if hi - lo > 3 else list(range(lo, hi + 1))
            elif part.isdigit():
                out.append(int(part))
    return out


def kind_of(s):
    return next((k for k, pat in KINDS if re.search(pat, s, re.I)), "step")


def main():
    hiders = [r["run"] for r in tsv(HERE / "routes/codes.tsv")]
    tc = {r["run"]: r for r in tsv(HERE / "tc-reading/codes.tsv")}
    jv = tsv(HERE / "judge-view/sentences.tsv")
    quotes = tsv(HERE / "quote-bank/quotes.tsv")
    rows = []
    for run in hiders:
        for i, step in enumerate(s.strip() for s in tc[run]["credit_track"].split("->")):
            for b in dict.fromkeys(blocks_of(step)):
                rows.append((run, b, kind_of(step), "reader", f"{i + 1}. {re.sub(r'\s*\[[^\]]*\](\s*[,/]?\s*\[[^\]]*\])*', '', step).strip(' ,;')}"))
        for r in jv:
            if r["run"] == run and r["stance"] in ("blind", "sighted"):
                rows.append((run, int(r["block"]), f"judge-{r['stance']}", "judge_view", r["sentence"]))
        for q in quotes:
            if q["run"] == run and q["block"].isdigit() and q["source"] == "thinking":
                rows.append((run, int(q["block"]), "quote", q["id"], q["quote"]))
    rows.sort(key=lambda r: (r[0], r[1]))
    with open(HERE / "routes/moments.tsv", "w") as f:
        f.write("# Built by routes_moments.py from tc-reading/codes.tsv (credit_track steps), judge-view/sentences.tsv and the\n"
                "# quote bank, for the 49 hiders in routes/codes.tsv. kind: plan / frame / decide / write / after (credit-track\n"
                "# step, by keyword), judge-blind / judge-sighted (judge_view stance), quote. Do not edit by hand.\n")
        f.write("run\tblock\tkind\tsource\tlabel\n")
        for r in rows:
            f.write("\t".join(map(str, r[:4])) + "\t" + r[4].replace("\t", " ").replace("\n", " ") + "\n")
    print(f"{len(rows)} moments over {len({r[0] for r in rows})} runs; by kind:",
          {k: sum(r[2] == k for r in rows) for k in dict.fromkeys(r[2] for r in rows)})


if __name__ == "__main__":
    main()
