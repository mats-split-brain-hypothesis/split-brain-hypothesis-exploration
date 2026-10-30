"""Per-task table for the stakes analysis: final stakes label, cues from the cheap-model labels, and trial outcomes.

  python src/stakes_tasks.py <trials.jsonl> <labels_model.jsonl> notes/stakes_hand_labels.json <out_dir>

Writes <out_dir>/task_table.json (one row per task) and prints a summary by stakes level: pass rate, errors,
output tokens, domain, requester voice, eval cues and anti-shortcut rules, to show what goes with stakes besides
stakes.
"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

LEVELS = ["low", "medium", "high"]


def load(trials_path, model_path, hand_path):
    trials = [json.loads(l) for l in open(trials_path)]
    model = {json.loads(l)["task_name"].split("/")[-1]: json.loads(l) for l in open(model_path)}
    hand = json.load(open(hand_path))["labels"]
    by_task = defaultdict(list)
    for t in trials:
        by_task[t["task_name"].split("/")[-1]].append(t)
    rows = []
    for task, ts in sorted(by_task.items()):
        m, h = model[task], hand[task]
        passed = sum((t["reward"] or 0) >= 1 for t in ts)
        rows.append({
            "task": task, "stakes": h["final"], "stakes_hand": h["hand"], "stakes_model": m["level"],
            "borderline": bool(h.get("borderline")), "why": h["why"],
            "domain": m["domain"], "voice": m["requester_voice"], "harm_target": m["harm_target"],
            "consequence_stated": m["consequence_stated"], "live_action": m["live_action"],
            "simulation_disclaimer": m["simulation_disclaimer"],
            "n_eval_cues": len(m["eval_cues"]), "n_anti_shortcut": len(m["anti_shortcut_rules"]),
            "urgency": m["urgency"],
            "trials": len(ts), "passed": passed,
            "errored": sum(t["error_type"] is not None for t in ts),
            "median_output_tokens": st.median(t["output_tokens"] or 0 for t in ts),
            "median_minutes": st.median(
                (__import__("datetime").datetime.fromisoformat(t["finished_at"]) -
                 __import__("datetime").datetime.fromisoformat(t["started_at"])).total_seconds() / 60 for t in ts),
            "trial_ids": [t["id"] for t in ts],
        })
    return rows


def summary(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["stakes"]].append(r)
    print(f"{'':28s}" + "".join(f"{l:>22s}" for l in LEVELS))

    def line(name, f):
        print(f"{name:28s}" + "".join(f"{f(by[l]):>22s}" for l in LEVELS))

    line("tasks", lambda rs: str(len(rs)))
    line("trials passed", lambda rs: f"{sum(r['passed'] for r in rs)}/{sum(r['trials'] for r in rs)}")
    line("tasks never passed", lambda rs: f"{sum(r['passed'] == 0 for r in rs)}/{len(rs)}")
    line("trials errored", lambda rs: f"{sum(r['errored'] for r in rs)}/{sum(r['trials'] for r in rs)}")
    line("median output tokens (k)", lambda rs: f"{st.median(r['median_output_tokens'] for r in rs) / 1000:.0f}")
    line("median minutes", lambda rs: f"{st.median(r['median_minutes'] for r in rs):.0f}")
    line("first-person requester", lambda rs: f"{sum(r['voice'] == 'first_person' for r in rs)}/{len(rs)}")
    line("has eval cue (beyond tail)", lambda rs: f"{sum(r['n_eval_cues'] > 0 for r in rs)}/{len(rs)}")
    line("has anti-shortcut rule", lambda rs: f"{sum(r['n_anti_shortcut'] > 0 for r in rs)}/{len(rs)}")
    line("live action", lambda rs: f"{sum(r['live_action'] for r in rs)}/{len(rs)}")
    line("borderline", lambda rs: f"{sum(r['borderline'] for r in rs)}/{len(rs)}")
    for l in LEVELS:
        print(l, "domains:", dict(Counter(r["domain"] for r in by[l]).most_common()))


if __name__ == "__main__":
    rows = load(*sys.argv[1:4])
    out = Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    (out / "task_table.json").write_text(json.dumps(rows, indent=1))
    summary(rows)
