"""Shared-labeller (src/cot_labels.py v3.4) rates for the stakes groups, pooled over trials.

  python src/stakes_cot.py <labels.jsonl> [<labels2.jsonl> ...]   # writes logs/stakes/cot/rates.json, prints a table
  python src/stakes_cot.py repeat <run1.jsonl> <run2.jsonl> <trial,trial>   # per-trial counts in two runs, mean
  python src/stakes_cot.py spend <raw.jsonl> [...]                 # billed cost of cot_labels runs

Groups and outcomes come from logs/stakes/trial_table.json. Rates are counts per 1,000 thinking tokens, pooled over the
trials of a group (sum of counts / sum of thinking tokens), as the verifier asked: compare groups by pooled rates, not
per-trial splits. Only reasoning-channel units are counted. Per definitions.md v2.0 the labeller's `target` and `ending`
are not used; persistence is all new candidates (`new`), not split into task and check.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["high", "low_cuefree", "low_cued", "medium_control", "low_borderline"]
MEASURES = {
    "new candidates (persistence)": lambda u: u.get("label") == "attempt" and bool(u.get("new")),
    "attempt units": lambda u: u.get("label") == "attempt",
    "correctness doubt": lambda u: u.get("label") == "doubt_correctness",
    "legitimacy doubt": lambda u: u.get("label") == "doubt_legitimacy",
    "goal: task": lambda u: u.get("goal") == "task",
    "goal: check": lambda u: u.get("goal") in ("check", "both"),
    "grader belief": lambda u: bool(u.get("belief_about")),
    "noticed obstacle": lambda u: bool(u.get("obstacle")),
    "A (alignment eval)": lambda u: "A" in (u.get("flags") or []),
    "B (capability eval)": lambda u: "B" in (u.get("flags") or []),
    "G (grading)": lambda u: "G" in (u.get("flags") or []),
    "S (score chasing)": lambda u: "S" in (u.get("flags") or []),
    "recall R1-R3": lambda u: bool(u.get("recall")),
}


def main(paths):
    trials = {t["trial"]: t for t in json.load(open(ROOT / "logs/stakes/trial_table.json"))}
    counts = defaultdict(lambda: defaultdict(int))
    units = defaultdict(int)
    seen = set()
    for p in paths:
        for l in open(p):
            u = json.loads(l)
            if u.get("channel") != "reasoning":
                continue
            key = (u["episode"], u["turn"], u["unit"])
            if key in seen:
                continue
            seen.add(key)
            ep = u["episode"]
            units[ep] += 1
            for name, f in MEASURES.items():
                if f(u):
                    counts[ep][name] += 1
    eps = [e for e in units if e in trials]
    out = []
    for g in GROUPS:
        for outcome in ("pass", "fail", "all"):
            rs = [e for e in eps if trials[e]["group"] == g and (outcome == "all" or trials[e]["outcome"] == outcome)]
            if not rs:
                continue
            tk = sum(trials[e]["thinking_k"] for e in rs)
            row = {"group": g, "outcome": outcome, "trials": len(rs), "thinking_k": round(tk),
                   "units": sum(units[e] for e in rs)}
            for name in MEASURES:
                c = sum(counts[e][name] for e in rs)
                row[name] = c
                row[f"{name} per 1k"] = round(c / tk, 3) if tk else None
            out.append(row)
    (ROOT / "logs/stakes/cot").mkdir(parents=True, exist_ok=True)
    (ROOT / "logs/stakes/cot/rates.json").write_text(json.dumps(out, indent=1))
    names = list(MEASURES)
    print(f"{'group/outcome':28s} {'n':>3s} " + " ".join(f"{n[:14]:>14s}" for n in names))
    for r in out:
        print(f"{r['group'] + '/' + r['outcome']:28s} {r['trials']:>3d} " +
              " ".join(f"{r[n + ' per 1k']:>14.3f}" for n in names))
    print(f"episodes with labels: {len(eps)}")


def per_trial(path, trial_ids):
    counts = {t: defaultdict(int) for t in trial_ids}
    seen = set()
    for l in open(path):
        u = json.loads(l)
        if u.get("channel") != "reasoning" or u["episode"] not in counts:
            continue
        key = (u["episode"], u["turn"], u["unit"])
        if key in seen:
            continue
        seen.add(key)
        counts[u["episode"]]["units"] += 1
        for name, f in MEASURES.items():
            if f(u):
                counts[u["episode"]][name] += 1
    return counts


def repeat(path1, path2, trial_ids):
    """Per-trial counts in two independent runs and their mean (single-trial examples are labelled twice)."""
    trials = {t["trial"]: t for t in json.load(open(ROOT / "logs/stakes/trial_table.json"))}
    a, b = per_trial(path1, trial_ids), per_trial(path2, trial_ids)
    out = []
    for t in trial_ids:
        tk = trials[t]["thinking_k"]
        for name in ["units"] + list(MEASURES):
            x, y = a[t][name], b[t][name]
            out.append({"trial": t, "measure": name, "run1": x, "run2": y, "mean": (x + y) / 2,
                        "mean_per_1k": round((x + y) / 2 / tk, 3) if name != "units" else None})
            print(f"{t:36s} {name:30s} {x:6d} {y:6d}  mean {(x + y) / 2:8.1f}")
    (ROOT / "logs/stakes/cot/repeat_livedb.json").write_text(json.dumps(out, indent=1))


def spend(raw_paths):
    """Billed cost summed from cot_labels' raw files (one row per call, field 'cost')."""
    total, calls = 0.0, 0
    for p in raw_paths:
        for l in open(p):
            r = json.loads(l)
            total += float(r.get("cost") or 0)
            calls += 1
    print(f"{calls} calls, ${total:.4f}")
    return calls, total


if __name__ == "__main__":
    if sys.argv[1] == "repeat":
        repeat(sys.argv[2], sys.argv[3], sys.argv[4].split(","))
    elif sys.argv[1] == "spend":
        spend(sys.argv[2:])
    else:
        main(sys.argv[1:])
