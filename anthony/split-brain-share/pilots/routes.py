"""How the hiders come to leave the source out (pilots/routes/HOW.md): counts over routes/codes.tsv (hand codes, 49
thinking-carried hiders), joined with tc-reading/codes.tsv (model, design), user_codes.tsv (does the final message name
the source) and topic-events/long.tsv (expected-score arithmetic anywhere in the run).

    python3 routes.py
"""

import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def tsv(path):
    return list(csv.DictReader((l for l in open(path) if not l.startswith("#")), delimiter="\t"))


def main():
    rows = tsv(HERE / "routes/codes.tsv")
    tc = {r["run"]: r for r in tsv(HERE / "tc-reading/codes.tsv")}
    user = {r["run"]: r["user_names"] for r in tsv(HERE / "user_codes.tsv")}
    arith = {r["run"]: r["any"] for r in tsv(HERE / "topic-events/long.tsv") if r["side"] == "whole" and r["topic"] == "arith"}
    n = len(rows)
    print(f"{n} hiders")
    print("path:", dict(Counter(r["path"] for r in rows)))
    for col in ("blind", "distinct", "own", "substitute", "believes"):
        print(f"{col}: {sum(r[col] == 'y' for r in rows)}/{n}", end="  ")
        print("by path", {p: f"{sum(r[col] == 'y' for r in rows if r['path'] == p)}/{sum(r['path'] == p for r in rows)}"
                          for p in ("lost", "reversed", "never")})
    deliberate = [r for r in rows if r["path"] != "lost"]
    print(f"deliberate (reversed or never): {len(deliberate)}; of them blind {sum(r['blind'] == 'y' for r in deliberate)}, "
          f"sighted (not blind) {sum(r['blind'] != 'y' for r in deliberate)}")
    sighted = [r for r in deliberate if r["blind"] != "y"]
    print(f"  sighted deliberate: distinct {sum(r['distinct'] == 'y' for r in sighted)}, own {sum(r['own'] == 'y' for r in sighted)}, "
          f"substitute {sum(r['substitute'] == 'y' for r in sighted)}, none of the three "
          f"{sum(all(r[c] != 'y' for c in ('distinct', 'own', 'substitute')) for r in sighted)}")
    print("user told (final message names the source):", dict(Counter(user.get(r["run"], "?") for r in rows)))
    print("score arithmetic in the run:", f"{sum(arith.get(r['run']) == '1' for r in rows)}/{n}",
          {p: f"{sum(arith.get(r['run']) == '1' for r in rows if r['path'] == p)}/{sum(r['path'] == p for r in rows)}"
           for p in ("lost", "reversed", "never")})
    print("model by path:", {p: dict(Counter(tc[r["run"]]["run"].rsplit("-", 2)[-2] if False else
                                             next(m for m in ("dsv4", "q27b", "glm52") if m in r["run"]) for r in rows if r["path"] == p))
                             for p in ("lost", "reversed", "never")})
    des = Counter(d for r in rows for d in tc[r["run"]]["design"].split(";") if d)
    print("design codes:", dict(des.most_common()))


if __name__ == "__main__":
    main()
