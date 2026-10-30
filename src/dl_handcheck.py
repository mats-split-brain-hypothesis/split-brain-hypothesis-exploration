"""Amendment 1 of the 2x2: a random sample of legitimacy-doubt units per cell, for a hand check against definitions
v2.4 ("weighing a shortcut": a named, specific shortcut judged allowed or not; a bare restatement of a rule or decision
with no named shortcut doesn't count). Prints each unit with the one before and after it, and writes
logs/sorh_persistence/dl_handcheck.csv with an empty `genuine` column to fill in (y / n).

  python src/dl_handcheck.py sample [--n 20]
"""
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_persist as P  # noqa: E402
import sorh_persist_dash as D  # noqa: E402

if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 20
    L = D.labels()
    rng = random.Random(2026)
    rows = []
    for v in D.CELLS.values():
        units = []
        for key, us in L.items():
            vv, t, s = key.split("/")
            if vv != v or P.GROUP.get(t) != "main":
                continue
            rs = [u for u in us if u["channel"] == "reasoning" and u["turn"] >= 1]
            for i, u in enumerate(rs):
                if u.get("label") == "doubt_legitimacy":
                    units.append((key, rs, i))
        pick = units if len(units) <= n else rng.sample(units, n)
        print(f"\n######## {v}: {len(units)} legitimacy-doubt units, {len(pick)} sampled")
        for key, rs, i in pick:
            u = rs[i]
            before = rs[i - 1]["text"] if i else ""
            after = rs[i + 1]["text"] if i + 1 < len(rs) else ""
            print(f"\n[{v} {key} turn {u['turn']} unit {u['unit']} stance {u.get('stance')}]\n  before: {before[:200]}\n"
                  f"  >> {u['text'][:300]}\n  after: {after[:200]}")
            rows.append({"variant": v, "episode": key, "turn": u["turn"], "unit": u["unit"], "stance": u.get("stance"),
                         "text": u["text"][:400], "genuine": "", "note": ""})
    out = D.HANDCHECK
    if out.exists():
        sys.exit(f"{out} exists; not overwriting the hand labels")
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows to {out}")
