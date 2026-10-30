"""Stage 1, persistence and doubt by arm: shared labeller (src/cot_labels.py) units per 1,000 characters, before any
feedback (turn 5+), in the turn right after a feedback message, and in later turns after one.

  python src/rejection_stage1_cot.py logs/rejection/stage1_an

Reads <an>/cot/*.jsonl (one labels file per Inspect log, episode id "<log stem>|<task>|<epoch>") and <an>/turns.jsonl
from src/rejection_stage1.py (same turn numbering: one turn per assistant message). Writes <an>/a7s1_cot.json.
Labels are provisional (prompt v3.5, luna_med; task/check unreliable on honest episodes until hand labels exist).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from inspect_ai.log import read_eval_log

MEASURES = {
    "new task-aimed candidates": lambda u: u["label"] == "attempt" and u["target"] == "task" and u["new"],
    "check-aimed attempt units": lambda u: u["label"] == "attempt" and u["target"] == "check",
    "weighing a shortcut (as labelled)": lambda u: u["label"] == "doubt_legitimacy",
    "correctness doubt": lambda u: u["label"] == "doubt_correctness",
}
FEEDBACK = ("rejection", "passfail", "recorded", "person")


def variant_of_stem(stem, logs_root=Path("logs")):
    hits = list(logs_root.glob(f"**/{stem}.eval"))
    name = read_eval_log(str(hits[0]), header_only=True).eval.task
    return name[3:] if name.startswith("ib_") else "L_base"  # the effort-pilot log (lcb_goodfire, xhigh)


def main(an):
    an = Path(an)
    counts = defaultdict(lambda: defaultdict(int))
    variants = {}
    for f in sorted((an / "cot").glob("*.jsonl")):
        for l in f.open():
            u = json.loads(l)
            if u.get("label") is None:
                continue
            stem, task, _ = u["episode"].split("|")
            if stem not in variants:
                variants[stem] = variant_of_stem(stem)
            k = (variants[stem], task, u["turn"])
            counts[k]["units"] += 1
            for m, fn in MEASURES.items():
                counts[k][m] += bool(fn(u))
    turns = [json.loads(l) for l in (an / "turns.jsonl").open()]
    groups = defaultdict(lambda: defaultdict(float))
    per_ep = defaultdict(lambda: defaultdict(int))   # (variant, when, measure) -> {task: units}
    eps_in = defaultdict(set)                         # (variant, when) -> tasks with a turn in the cell
    for t in turns:
        key = (t["variant"], t["task"], t["turn"])
        if key not in counts:
            continue
        just = any(e in FEEDBACK for e in t["events"])
        if t["n_fb"] == 0:
            if t["turn"] < 5:
                continue
            when = "no feedback yet (turn 5+)"
        elif just:
            when = "turn right after feedback"
        else:
            when = "later turns after feedback"
        g = groups[(t["variant"], when)]
        g["turns"] += 1
        g["kchars"] += t["chars"] / 1000
        eps_in[(t["variant"], when)].add(t["task"])
        for m in MEASURES:
            g[m] += counts[key][m]
            per_ep[(t["variant"], when, m)][t["task"]] += counts[key][m]
    rows = []
    for (v, when), g in sorted(groups.items()):
        for m in MEASURES:
            pe = per_ep[(v, when, m)]
            top = max(pe.items(), key=lambda kv: kv[1]) if pe else (None, 0)
            rows.append(dict(variant=v, when=when, measure=m, units=int(g[m]), turns=int(g["turns"]),
                             kchars=round(g["kchars"], 1), per_1k=round(g[m] / g["kchars"], 3) if g["kchars"] else None,
                             episodes=len(eps_in[(v, when)]), episodes_with=sum(1 for x in pe.values() if x > 0),
                             top_episode=top[0] if top[1] else "", top_units=int(top[1])))
    (an / "a7s1_cot.json").write_text(json.dumps(rows, indent=1))
    order = ["L_base", "L_reiterate_off", "L_person", "L_recorded", "L_recorded_bare"]
    for m in MEASURES:
        print(f"\n## {m} (per 1,000 characters; turns in brackets)")
        print(f"{'arm':<18}" + "".join(f"{w:>30}" for w in ["no feedback yet (turn 5+)", "turn right after feedback",
                                                          "later turns after feedback"]))
        for v in order:
            cells = []
            for w in ["no feedback yet (turn 5+)", "turn right after feedback", "later turns after feedback"]:
                r = next((r for r in rows if r["variant"] == v and r["when"] == w and r["measure"] == m), None)
                cells.append(f"{r['per_1k']:.2f} [{r['episodes_with']}/{r['episodes']} ep, {r['units']}u]" if r else "-")
            print(f"{v:<18}" + "".join(f"{c:>30}" for c in cells))


if __name__ == "__main__":
    main(sys.argv[1])
