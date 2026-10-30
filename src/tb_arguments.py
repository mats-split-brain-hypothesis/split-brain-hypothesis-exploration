"""How the rule gets argued away on Terminal-Bench: blind hand coding of "weighing a shortcut" units. Agent 6,
2026-10-21; codebook in notes/tb_shortcuts.md (written before coding).

  python src/tb_arguments.py pool <out_dir> [--n 60]
      -> <out_dir>/blind.json (index + text only, both groups shuffled together), <out_dir>/key.json (index -> group,
         trial, turn, unit, stance)
  python src/tb_arguments.py show <out_dir> <from> <to>      # print blind units for coding
  python src/tb_arguments.py summary <out_dir> notes/tb_argument_codes.json <out.json>

Groups:
- took: weighing units in the window before the first shortcut of the confirmed shortcut trials (phase 2, v3.5)
- none: weighing units in trials without a confirmed shortcut: the 54 stakes trials (v3.4 main pass, the same as
  v3.5's on Terminal-Bench) minus confirmed shortcut trials, and the phase 2 control windows (v3.5)
Reasoning channel only; distinct units; up to --n per group at random (seed 6).
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODES = ["a", "b", "c", "d", "other", "not_weighing"]
NAMES = {"a": "Literal reading of the rule", "b": "Real-world practice", "c": "General reference",
         "d": "Rule against it", "other": "Other genuine weighing", "not_weighing": "Not weighing"}


def load(p):
    return [json.loads(l) for l in open(ROOT / p)]


def pool(out_dir, n=60):
    checks = json.load(open(ROOT / "notes/tb_shortcut_checks.json"))
    shortcut_trials = {t for typ in ("answer_lookup", "upstream_diff", "risky_live")
                       for t in checks["shortcuts"][typ]["trials"]}
    A = json.load(open(ROOT / "logs/stakes/tb/phase2/antecedents.json"))
    p2 = defaultdict(list)
    for u in load("logs/stakes/tb/phase2/labels_v35.jsonl"):
        p2[u["episode"]].append(u)
    groups = {"took": {}, "none": {}}
    for r in A:
        traj = json.load(open(ROOT / "logs/stakes/tb/phase2/traj" / f"{r['trial']}.json"))
        agent = [s for s in traj["steps"] if s["source"] == "agent"]
        turns = {i for i, s in enumerate(agent) if s["step_id"] <= r["anchor"]}
        g = "took" if r["role"] == "shortcut" else "none"
        for u in p2[r["trial"]]:
            if u["turn"] in turns and u["channel"] == "reasoning" and u.get("label") == "doubt_legitimacy":
                groups[g][(u["episode"], u["turn"], u["unit"])] = u
    for f in ("logs/stakes/cot/v34_main.jsonl", "logs/stakes/cot/v34_rest.jsonl"):
        for u in load(f):
            if u["episode"] in shortcut_trials or u["channel"] != "reasoning" or u.get("label") != "doubt_legitimacy":
                continue
            groups["none"].setdefault((u["episode"], u["turn"], u["unit"]), u)
    rng = random.Random(6)
    picked = []
    for g, units in groups.items():
        keys = sorted(units)
        sel = rng.sample(keys, min(n, len(keys)))
        print(f"{g}: {len(keys)} units in {len({k[0] for k in keys})} trials; {len(sel)} drawn")
        picked += [(g, k, units[k]) for k in sel]
    rng.shuffle(picked)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "blind.json").write_text(json.dumps([{"idx": i, "text": u["text"]} for i, (_, _, u) in enumerate(picked)],
                                               indent=1, ensure_ascii=False))
    (out / "key.json").write_text(json.dumps([{"idx": i, "group": g, "trial": k[0], "turn": k[1], "unit": k[2],
                                               "stance": u.get("stance")} for i, (g, k, u) in enumerate(picked)],
                                             indent=1))
    print(len(picked), "units ->", out)


def show(out_dir, a, b):
    for r in json.load(open(Path(out_dir) / "blind.json"))[int(a):int(b)]:
        print(f"[{r['idx']}] {r['text'][:260]}")


def summary(out_dir, codes_path, out_path):
    key = {r["idx"]: r for r in json.load(open(Path(out_dir) / "key.json"))}
    blind = {r["idx"]: r["text"] for r in json.load(open(Path(out_dir) / "blind.json"))}
    codes = json.load(open(ROOT / codes_path))["codes"]
    rows, quotes = [], defaultdict(list)
    by = defaultdict(Counter)
    for c in codes:
        g = key[c["idx"]]["group"]
        by[g][c["code"]] += 1
        if c["code"] not in ("not_weighing",) and c.get("quote"):
            quotes[(c["code"], g)].append(blind[c["idx"]][:180])
    for g in ("took", "none"):
        genuine = sum(v for k, v in by[g].items() if k != "not_weighing")
        for code in CODES[:-1]:
            rows.append({"code": NAMES[code], "group": {"took": "Took the shortcut", "none": "No shortcut taken"}[g],
                         "k": by[g][code], "n": genuine})
        print(g, dict(by[g]), "genuine", genuine)
    Path(out_path).write_text(json.dumps({"rows": rows, "quotes": {f"{k[0]}|{k[1]}": v for k, v in quotes.items()},
                                          "counts": {g: dict(c) for g, c in by.items()}}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pool":
        pool(sys.argv[2], int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 60)
    elif cmd == "show":
        show(*sys.argv[2:5])
    elif cmd == "summary":
        summary(*sys.argv[2:5])
