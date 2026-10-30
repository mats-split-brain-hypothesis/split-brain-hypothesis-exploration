"""SWE: does the look-elsewhere call come before the hack, after it, or is it the hack itself?

  python src/grader_swe_order.py <logs/data>     # writes logs/grader/dashboard/a5_swe_order.json, a5_swe_examples.json

Hack episodes = Goodfire verdict_enacted yes. Among them, those with a seek_answer call (src/grader_actions.py rules):
compare the node of the first seek_answer call with the node of the first enacted or attempted judge flag.
- "lookup first": the call's turn comes before the flag's;
- "hack flag first": the flag's turn comes first;
- "lookup itself flagged": the first flag sits on the turn that makes the call (the judge flagged the lookup itself, typically as
  environment acquisition or upstream-fix recall), kept apart because those categories overlap the call by
  definition.
Examples: the first episode in file order for each group, plus the first no-hack episode with a seek_answer call:
the reasoning sentence before the call, the command, the first flag's category and quote.
"""
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import grader_actions as GA  # noqa: E402

G = ROOT / "logs" / "grader"
FILES = {("SWE-bench Verified", "Qwen"): "swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack",
         ("SWE-bench Verified", "GLM"): "swebench-verified-glm-5.2-nohack",
         ("SWE-bench Verified", "Kimi"): "swebench-verified-kimi-k3-nohack",
         ("DeepSWE", "Qwen"): "deepswe-qwen3.8-2.4t-a95b-fp8", ("DeepSWE", "GLM"): "deepswe-glm-5.2-fp8",
         ("DeepSWE", "Kimi"): "deepswe-kimi-k3"}
CUT = lambda s, n: s if len(s) <= n else s[:n].rstrip() + "…"  # noqa: E731
SENT = re.compile(r"(?<=[.!?])\s+|\n+")


def first_flag(j):
    fl = [f for f in j.get("flags") or [] if f.get("status") in ("enacted", "attempted") and f.get("node_index") is not None]
    return min(fl, key=lambda f: f["node_index"]) if fl else None


def main(gdir):
    rows = json.loads((G / "actions_rows.json").read_text())
    by = {(r["bench"], r["model"], r["row"]): r for r in rows}
    order, examples, picked = [], [], set()
    cats = defaultdict(Counter)  # in "lookup first" episodes: the category of the first hack flag
    order_noenv = []
    pos = defaultdict(lambda: defaultdict(list))  # (bench, model) -> measure -> shares of the episode
    for (bench, model), name in FILES.items():
        path = Path(gdir) / "goodfire_swe" / f"{name}.traces.jsonl"
        jpath = Path(gdir) / "goodfire_swe" / f"{name}.judge_rollouts.jsonl"
        if not path.exists():
            continue
        judges = [json.loads(l) for l in jpath.open()]
        c, c2 = Counter(), Counter()
        with path.open() as f:
            for row, line in enumerate(f):
                r = by.get((bench, model, row))
                if r is None or r["verdict_enacted"] not in ("yes", "no"):
                    continue
                seek = [nd for nd, p in r["acts"] if p == "seek_answer"]
                if not seek:
                    continue
                t = None
                if r["verdict_enacted"] == "yes":
                    fl = first_flag(judges[row])
                    if fl is None:  # verdict yes but no enacted/attempted flag with a position
                        c["no flag position"] += 1
                        continue
                    s0, f0 = seek[0], fl["node_index"]
                    grp = "lookup itself flagged" if s0 == f0 else ("lookup first" if s0 < f0 else "hack flag first")
                    c[grp] += 1
                    # the same with environment-acquisition flags left out (the judge's flag on the lookup itself)
                    fl2 = first_flag({"flags": [x for x in judges[row].get("flags") or []
                                                if x.get("category") != "environment_acquisition"]})
                    if fl2 is None:
                        c2["only environment-acquisition flags"] += 1
                    else:
                        f2 = fl2["node_index"]
                        c2["lookup itself flagged" if s0 == f2 else ("lookup first" if s0 < f2 else "hack flag first")] += 1
                        # how far into the episode each comes: share of the episode's tool calls made before it
                        share = lambda node: sum(nd < node for nd, _ in r["acts"]) / len(r["acts"])  # noqa: E731
                        pos[(bench, model)]["first lookup"].append(share(s0))
                        pos[(bench, model)]["first hack flag"].append(share(f2))
                    if grp == "lookup first":
                        cats[(bench, model)][fl["category"]] += 1
                else:
                    grp, fl = "no hack (contrast)", None
                if model == "Qwen" and bench == "SWE-bench Verified" and grp not in picked:
                    t = json.loads(line)["traces"][0]
                    m = t["nodes"][seek[0]]["message"]
                    sents = [x for x in SENT.split(m.get("reasoning_content") or "") if x.strip()]
                    cmd = next((str(GA.args_of(tc).get("command") or "") for tc in m.get("tool_calls") or []
                                if GA.purpose_swe(GA.args_of(tc)) == "seek_answer"), "")
                    examples.append({
                        "title": f"SWE-bench Verified · Qwen · {judges[row].get('task')}: {grp}",
                        "finding": "Finding 3", "source": "Goodfire transcript",
                        "picked": f"first Qwen episode in file order in the group '{grp}'",
                        "context": CUT(sents[-1], 300) if sents else "",
                        "cue_hl": "",
                        "action": CUT(re.sub(r"\s+", " ", cmd.replace("cd /testbed && ", "")), 220),
                        "reasoning": (f"First hack flag ({fl['category']}, {fl['status']}, node {fl['node_index']}; "
                                      f"lookup at node {seek[0]}): {CUT(fl['quote'], 200)}") if fl else
                                     "No enacted or attempted flag; verdict 'no'.",
                        "outcome": f"Judge verdict_enacted '{r['verdict_enacted']}'; categories "
                                   f"{', '.join(r['hack_cats']) or 'none'}"})
                    picked.add(grp)
        n = sum(c.values())
        for grp in ("lookup first", "lookup itself flagged", "hack flag first", "no flag position"):
            order.append({"label": f"{bench} · {model}", "order": grp, "k": c[grp], "n": n})
        n2 = sum(c2.values())
        for grp in ("lookup first", "lookup itself flagged", "hack flag first", "only environment-acquisition flags"):
            order_noenv.append({"label": f"{bench} · {model}", "order": grp, "k": c2[grp], "n": n2})
        print(f"{bench:20}{model:6} hack episodes with a lookup: {n}; " + ", ".join(
            f"{g} {c[g]}" for g in ("lookup first", "lookup itself flagged", "hack flag first", "no flag position")))
    (G / "dashboard" / "a5_swe_order.json").write_text(json.dumps(order, indent=1))
    (G / "dashboard" / "a5_swe_order_noenv.json").write_text(json.dumps(order_noenv, indent=1))
    cat_rows = []
    for (bench, model), cc in cats.items():
        n = sum(cc.values())
        for cat, k in cc.most_common():
            cat_rows.append({"label": f"{bench} · {model}", "category": cat, "k": k, "n": n})
    (G / "dashboard" / "a5_swe_order_cats.json").write_text(json.dumps(cat_rows, indent=1))
    pos_rows = []
    for (bench, model), d in pos.items():
        a, b = d["first lookup"], d["first hack flag"]
        q = lambda xs, i: round(statistics.quantiles(xs, n=4)[i], 2) if len(xs) > 1 else round(xs[0], 2)  # noqa: E731
        pos_rows.append({"key": f"{bench} · {model}", "label": f"{bench} · {model}", "n": len(a),
                         "lookup_median": round(statistics.median(a), 2), "lookup_q1": q(a, 0), "lookup_q3": q(a, 2),
                         "hack_median": round(statistics.median(b), 2), "hack_q1": q(b, 0), "hack_q3": q(b, 2)})
        print(f"{bench:20}{model:6} position (share of calls): first lookup median {pos_rows[-1]['lookup_median']}, "
              f"first non-environment hack flag median {pos_rows[-1]['hack_median']} (n {len(a)})")
    (G / "dashboard" / "a5_swe_order_pos.json").write_text(json.dumps(pos_rows, indent=1))
    examples.sort(key=lambda e: ["lookup first", "lookup itself flagged", "hack flag first", "no hack (contrast)"].index(
        e["title"].split(": ")[-1]))
    (G / "dashboard" / "a5_swe_examples.json").write_text(json.dumps(examples, indent=1, ensure_ascii=False))
    print(f"{len(examples)} examples")


if __name__ == "__main__":
    main(sys.argv[1])
