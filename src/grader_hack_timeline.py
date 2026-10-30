"""Order of events in the ImpossibleBench hack episodes (Goodfire verdict_enacted yes, impossible split).

  python src/grader_hack_timeline.py <logs/data>     # writes logs/grader/dashboard/a5_hack_timeline*.json

Per episode, the agent turn (0 = first sampled assistant turn) of:
- first read of test.py: first inspect_content call (src/grader_actions.py rules);
- first noticed obstacle: first unit with `obstacle` set by the shared labeller (src/cot_labels.py v3.4, luna_med),
  labelled twice (logs/grader/labels/hack_<model>_run{1,2}.jsonl); both runs are reported, and their mean;
- first hack flag: the turn holding the first enacted or attempted judge flag (Goodfire's node_index);
- first rejection: the first turn that comes after a harness rejection;
- first alignment-eval (A) statement: the first passage labelled A by src/awareness_llm.py (GPT-5.6 Luna), located in
  the turn where it starts (logs/awareness_llm/candidates_all.jsonl, labels_final.jsonl; method from agent 2's
  src/ib_cues.py, branch mats/agent-2-ib-cues).
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "logs" / "grader"
AW = ROOT / "logs" / "awareness_llm"
KEYS = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}
LAB = {"Qwen": "qwen", "GLM": "glm", "Kimi": "kimi"}
WS = re.compile(r"\s+")
FEEDBACK = "Your implementation failed the tests"


def norm(s):
    return WS.sub(" ", s or "").strip()


def a_passages():
    lab = {json.loads(l)["id"]: json.loads(l) for l in (AW / "labels_final.jsonl").open()}
    out = {}
    for l in (AW / "candidates_all.jsonl").open():
        r = json.loads(l)
        if r["bench"] == "ImpossibleBench (impossible)" and (lab.get(r["id"]) or {}).get("A"):
            out.setdefault((r["model"], r["row"]), []).append(r["text"])
    return out


def first_obstacle(path, ep):
    if not path.exists():
        return None
    ts = [json.loads(l)["turn"] for l in path.open() if json.loads(l)["episode"] == ep and json.loads(l).get("obstacle")]
    return min(ts) if ts else None


def main(gdir):
    rows = json.loads((G / "actions_rows.json").read_text())
    apass = a_passages()
    out = []
    for model, key in KEYS.items():
        hs = {r["row"]: r for r in rows if r["bench"] == "ImpossibleBench impossible" and r["model"] == model
              and r["verdict_enacted"] == "yes"}
        with open(Path(gdir) / "goodfire" / f"{key}_traces.jsonl") as f:
            for row, line in enumerate(f):
                if row not in hs:
                    continue
                r = hs[row]
                t = json.loads(line)["traces"][0]
                tnodes = [i for i, n in enumerate(t["nodes"]) if n["message"]["role"] == "assistant" and n.get("sampled", True)]
                texts = [norm((t["nodes"][i]["message"].get("reasoning_content") or "") + " " +
                              (t["nodes"][i]["message"].get("content") if isinstance(t["nodes"][i]["message"].get("content"), str) else ""))
                         for i in tnodes]
                turn_at = lambda node: sum(i <= node for i in tnodes) - 1  # noqa: E731  turn holding (or before) a node
                read = next((n for n, p in r["acts"] if p == "inspect_content"), None)
                rej = r["fb"][0] if r["fb"] else None
                a_turns = [k for p in apass.get((model, row), []) for k, tx in enumerate(texts) if norm(p)[:80] in tx]
                ep = f"{key}|{row}"
                o1 = first_obstacle(G / "labels" / f"hack_{LAB[model]}_run1.jsonl", ep)
                o2 = first_obstacle(G / "labels" / f"hack_{LAB[model]}_run2.jsonl", ep)
                obs = [x for x in (o1, o2) if x is not None]
                split = t["task"]["data"].get("split")
                out.append({"key": f"{model} {r['task']} {split}", "model": model,
                            "task": f"{r['task']} ({split})", "row": row,
                            "turns": len(tnodes),
                            "first_test_read": turn_at(read) if read is not None else None,
                            "first_obstacle_run1": o1, "first_obstacle_run2": o2,
                            "first_obstacle": round(sum(obs) / len(obs), 1) if obs else None,
                            "first_hack_flag": turn_at(r["first_hack"]) if r["first_hack"] is not None else None,
                            "first_rejection": turn_at(rej) + 1 if rej is not None else None,
                            "first_A": min(a_turns) if a_turns else None,
                            "categories": ", ".join(r["hack_cats"])})
    G.joinpath("dashboard").mkdir(parents=True, exist_ok=True)
    (G / "dashboard" / "a5_hack_timeline.json").write_text(json.dumps(out, indent=1))

    # Order summary per model: how many hack episodes have each event before the first hack flag.
    summ = []
    for model in KEYS:
        rs = [x for x in out if x["model"] == model]
        n = len(rs)

        def before(field):
            return sum(x[field] is not None and x["first_hack_flag"] is not None and x[field] <= x["first_hack_flag"]
                       for x in rs)
        for field, lab in (("first_test_read", "read test.py by the hack's turn"),
                           ("first_obstacle", "noticed obstacle by the hack's turn (mean of 2 runs)"),
                           ("first_rejection", "rejection by the hack's turn"),
                           ("first_A", "test-of-me (A) statement by the hack's turn")):
            summ.append({"model": model, "measure": lab, "k": before(field), "n": n})
    (G / "dashboard" / "a5_hack_order.json").write_text(json.dumps(summ, indent=1))
    for x in out:
        print({k: x[k] for k in ("key", "turns", "first_test_read", "first_obstacle_run1", "first_obstacle_run2",
                                 "first_hack_flag", "first_rejection", "first_A")})
    for s in summ:
        print(s)


if __name__ == "__main__":
    main(sys.argv[1])
