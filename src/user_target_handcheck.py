"""Amendment 1 hand check of the judge's 'recommends' on screen A (notes, "Pre-registration A").

  python src/user_target_handcheck.py sample   # writes logs/user_target/handcheck_A.csv (blind: no voice, no feedback)
  python src/user_target_handcheck.py show     # prints the blinded replies in sheet order, for hand coding
  python src/user_target_handcheck.py compare  # after the 'hand' column is filled and the stripped judge has run

Pick rule: per voice, tasks in A_TASKS order, for each the lowest sample in 1-4 that has a reply 2; if fewer than 6
tasks qualify, the remaining picks go to the next samples of the earliest tasks. 6 per voice, 18 in all, shuffled
with a fixed seed so the voice can't be read off the order.
"""
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import user_target as T  # noqa: E402

SHEET = T.OUT / "handcheck_A.csv"
KEY = T.OUT / "handcheck_A_key.json"


def pick():
    eps = {(e["arm"], e["task"], e["sample"]): e for e in T.a_episodes() if e["sample"] in (1, 2, 3, 4)}
    out = []
    for v in T.A_SOURCES:
        has2 = {(t, s) for (a, t, s), e in eps.items() if a == v and len(e["turns"]) > 1}
        chosen = []
        for t in T.A_TASKS:
            s = next((s for s in (1, 2, 3, 4) if (t, s) in has2), None)
            if s is not None:
                chosen.append((t, s))
        extra = [(t, s) for t in T.A_TASKS for s in (1, 2, 3, 4) if (t, s) in has2 and (t, s) not in chosen]
        chosen = (chosen + extra)[:6]
        out += [(v, t, s) for t, s in chosen]
    return out, eps


def sample():
    picks, eps = pick()
    rng = random.Random(20261021)
    rng.shuffle(picks)
    key = {}
    with SHEET.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "task", "hand", "hand_note"])
        for i, (v, t, s) in enumerate(picks, 1):
            key[str(i)] = [v, t, s]
            w.writerow([i, t, "", ""])
    KEY.write_text(json.dumps(key))
    print(f"{len(picks)} items -> {SHEET}")


def show():
    key = json.loads(KEY.read_text())
    eps = {(e["arm"], e["task"], e["sample"]): e for e in T.a_episodes()}
    for i, (v, t, s) in key.items():
        e = eps[(v, t, s)]
        print(f"\n################ item {i} ({t}; request: {e['turns'][0]['user'].splitlines()[0][:90]})")
        print(e["turns"][1]["reply"][:3000])


def compare():
    key = json.loads(KEY.read_text())
    J2 = T._load("stripped")
    rows = list(csv.DictReader(SHEET.open()))
    agree, n = 0, 0
    for r in rows:
        v, t, s = key[r["item"]]
        j = J2.get(f"{v}/{t}/{s}/2", {}).get("recommends")
        ok = j == r["hand"]
        agree += ok
        n += 1
        print(f"item {r['item']:>2} {v:8} {t:9} s{s}: hand {r['hand']:13} judge {j}{'' if ok else '   <-- differs'}")
    print(f"\nagreement {agree}/{n}; pre-registered threshold 15/18 -> "
          f"{'judge measure stays primary' if agree >= 15 else 'decision moves to the code measure (first version special)'}")


if __name__ == "__main__":
    {"sample": sample, "show": show, "compare": compare}[sys.argv[1]]()
