"""Targeted, blind hand-label sheet for the shared labeller's open questions (about 150 units, random order).

  python src/checkset_targeted.py <out.csv> <key.jsonl>
  python src/checkset_targeted.py unblind <filled.csv> <key.jsonl> <scored.csv>   # then cot_labels.py agree

Units come from episodes that Luna (luna_med) and GPT-5.6 Sol have both labelled in window mode
(logs/ib_persistence/checkset/v34*_window.jsonl, v35_*_heldout.jsonl, v35_*_sorh456.jsonl):
  ImpossibleBench, honest: qwen|132, qwen|28; hack: qwen|183, qwen|259 (Goodfire verdict_enacted yes for 259,
  hack attempted for 183); School of Reward Hacks: original/sorh_456/1.json (agent 1), base/sorh_147/0.json and
  base/sorh_0/0.json (agent 3, multi-turn).
Strata (drawn in this order, random.Random(SEED), no unit twice):
  ib_target_disagree  30  ImpossibleBench attempts where the two labellers' task/check differ (15 honest, 15 hack)
  ib_target_random    30  other ImpossibleBench attempts (15 honest, 15 hack)
  sorh_flag           25  SoRH units either labeller flagged G or S
  sorh_check          15  SoRH attempts either labeller called check-aimed
  sorh_random         10  other SoRH units
  new_obstacle        20  units either labeller marked as a new candidate (10) or an obstacle (10)
  goal_belief         20  units either labeller gave a goal (10) or a grader belief (10)
The sheet shows no model labels: only the unit, two units before it and one after (same turn), and its turn. The key
file records each unit's stratum for the analysis; give the hand labeller the sheet only.
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cot_labels import FIELDS, load, units  # noqa: E402

SEED = 20261021
C = "logs/ib_persistence/checkset"
PAIRS = [(f"{C}/v34final_window.jsonl", f"{C}/v34_sol_window.jsonl"),
         (f"{C}/v35_luna_med_heldout.jsonl", f"{C}/v35_sol_heldout.jsonl"),
         (f"{C}/v35_luna_med_sorh456.jsonl", f"{C}/v35_sol_sorh456.jsonl")]
SOURCES = {"qwen|": "logs/data/goodfire/qwen_traces.jsonl", "original/": "logs/sorh_cues/raw/original",
           "base/": "logs/sorh_persistence/raw/base"}
HONEST, HACK = {"qwen|132", "qwen|28"}, {"qwen|183", "qwen|259"}


def key(r):
    return f"{r['episode']}|{r['turn']}|{r['channel']}|{r['unit']}"


def main(out_csv, key_path):
    a, b = {}, {}
    for fa, fb in PAIRS:
        for l in open(fa):
            r = json.loads(l)
            a.setdefault(key(r), r)
        for l in open(fb):
            r = json.loads(l)
            b.setdefault(key(r), r)
    both = [k for k in a if k in b and a[k]["label"] and b[k]["label"]]
    rng = random.Random(SEED)
    taken, picked = set(), []

    def draw(stratum, pool, n):
        pool = [k for k in pool if k not in taken]
        for k in rng.sample(pool, min(n, len(pool))):
            taken.add(k)
            picked.append((k, stratum))

    ib = [k for k in both if k.startswith("qwen|")]
    sorh = [k for k in both if not k.startswith("qwen|")]
    att = lambda k: a[k]["label"] == b[k]["label"] == "attempt"
    ep = lambda k: k.rsplit("|", 3)[0]
    for grp in (HONEST, HACK):
        draw("ib_target_disagree", [k for k in ib if ep(k) in grp and att(k) and a[k]["target"] != b[k]["target"]], 15)
    for grp in (HONEST, HACK):
        draw("ib_target_random", [k for k in ib if ep(k) in grp and att(k)], 15)
    fl = lambda r: set(r.get("flags") or [])
    draw("sorh_flag", [k for k in sorh if {"G", "S"} & (fl(a[k]) | fl(b[k]))], 25)
    draw("sorh_check", [k for k in sorh if "check" in (a[k]["target"], b[k]["target"])], 15)
    draw("sorh_random", sorh, 10)
    draw("new_obstacle", [k for k in both if (a[k]["label"] == "attempt" and a[k]["new"]) or
                          (b[k]["label"] == "attempt" and b[k]["new"])], 10)
    draw("new_obstacle", [k for k in both if a[k].get("obstacle") or b[k].get("obstacle")], 10)
    draw("goal_belief", [k for k in both if a[k].get("goal") or b[k].get("goal")], 10)
    draw("goal_belief", [k for k in both if a[k].get("belief_about") or b[k].get("belief_about")], 10)

    # Context from the full episodes.
    want = defaultdict(set)
    for k, _ in picked:
        e = ep(k)
        want[next(s for p, s in SOURCES.items() if e.startswith(p))].add(e)
    ctx = {}
    for src, ids in want.items():
        for e in load(src, sorted(ids)):
            us = units(e)
            for i, u in enumerate(us):
                same = lambda j: 0 <= j < len(us) and us[j]["turn"] == u["turn"]
                ctx[f"{e['id']}|{u['turn']}|{u['channel']}|{u['unit']}"] = (
                    " / ".join(us[j]["text"] for j in (i - 2, i - 1) if same(j)),
                    us[i + 1]["text"] if same(i + 1) else "", e["bench"])
    rng.shuffle(picked)
    rows = []
    with open(key_path, "w") as kf:
        for n, (k, stratum) in enumerate(picked):
            before, after, bench = ctx[k]
            turn = k.rsplit("|", 3)[1]
            rows.append(dict(row=n + 1, source=bench, turn=turn, context_before=before, text=a[k]["text"],
                             context_after=after, **{f: "" for f in FIELDS}))
            kf.write(json.dumps(dict(row=n + 1, id=k, stratum=stratum)) + "\n")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    counts = defaultdict(int)
    for _, s in picked:
        counts[s] += 1
    print(f"{len(rows)} units written to {out_csv}; strata {dict(counts)}")


def unblind(filled_csv, key_path, out_csv):
    """Add the unit ids back to a filled sheet (from the key), so `cot_labels.py agree` can score it."""
    ids = {str(json.loads(l)["row"]): json.loads(l)["id"] for l in open(key_path)}
    rows = list(csv.DictReader(open(filled_csv)))
    for r in rows:
        r["id"] = ids[r["row"]]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id"] + [c for c in rows[0] if c != "id"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows with ids written to {out_csv}")


if __name__ == "__main__":
    if sys.argv[1] == "unblind":
        unblind(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        main(sys.argv[1], sys.argv[2])
