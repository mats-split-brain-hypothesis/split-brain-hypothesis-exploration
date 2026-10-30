"""Across Goodfire's three ImpossibleBench models: how often does the reasoning say it's being tested for cheating,
and how does that relate to hacking (Goodfire's judge labels)?

  python src/goodfire_suspicion.py <dir with the downloaded traces.jsonl and judge_rollouts.jsonl files>

Expects, from HF Goodfire/reward-hack-data: qwen_traces.jsonl, qwen_judge_rollouts.jsonl (from
impossiblebench-qwen3.8-2.4t-a95b-fp8/), and <key>_traces.jsonl, <key>_judge_rollouts.jsonl for
key in glm-5.2-fp8, kimi-k3. Results: notes/cheating_test_suspicion.md.
"""
import json
import random
import sys

from patterns import EVAL, SUSPECT

MODELS = [("Qwen3.8 2.4T (xhigh)", "qwen"), ("GLM 5.2 (max)", "glm-5.2-fp8"), ("Kimi K3 (max)", "kimi-k3")]


def load(key, d):
    traces = [json.loads(l)["traces"][0] for l in open(f"{d}/{key}_traces.jsonl")]
    labels = [json.loads(l) for l in open(f"{d}/{key}_judge_rollouts.jsonl")]
    assert len(traces) == len(labels)
    return traces, labels


def first_hit(t, pat):
    """Index of the first assistant node whose reasoning matches, and the snippet."""
    for i, n in enumerate(t["nodes"]):
        if n["message"]["role"] != "assistant":
            continue
        r = n["message"].get("reasoning_content") or ""
        m = pat.search(r)
        if m:
            return i, r[max(0, m.start() - 150): m.end() + 130].replace("\n", " ")
    return None, None


def rate(rows, key, value="yes"):
    y = sum(r[key] == value for r in rows)
    n = sum(r[key] == "no" for r in rows)
    return y, y + n


def main(d):
    random.seed(7)
    for name, key in MODELS:
        traces, labels = load(key, d)
        rows = []
        for t, l in zip(traces, labels):
            s_idx, s_snip = first_hit(t, SUSPECT)
            e_idx, _ = first_hit(t, EVAL)
            acted = [f for f in (l.get("flags") or []) if f.get("status") in ("enacted", "attempted")]
            first_act = min((f["node_index"] for f in acted if f.get("node_index") is not None), default=None)
            rows.append(dict(split=t["task"]["data"]["split"], task=t["task"]["data"]["name"],
                             suspect=s_idx is not None, s_idx=s_idx, snip=s_snip, eval=e_idx is not None,
                             any=l["verdict"], enacted=l["verdict_enacted"],
                             passed=bool(t["metrics"].get("test_passed")), first_act=first_act))
        print(f"\n######## {name}")
        for sp in ["conflicting", "oneoff", "original"]:
            rs = [r for r in rows if r["split"] == sp]
            k = len(rs)
            sus = sum(r["suspect"] for r in rs)
            ev = sum(r["eval"] for r in rs)
            ya, na = rate(rs, "any")
            ye, ne = rate(rs, "enacted")
            print(f"  {sp:<11} n={k:<3} suspects cheating test {sus:>3} ({100*sus/k:4.0f}%) | "
                  f"mentions eval/benchmark {100*ev/k:4.0f}% | judge any-status {100*ya/max(1, na):4.0f}% | "
                  f"made/attempted {100*ye/max(1, ne):4.1f}% | passed {sum(r['passed'] for r in rs)}")
        imp = [r for r in rows if r["split"] != "original"]
        for flag in (True, False):
            g = [r for r in imp if r["suspect"] == flag]
            y, n = rate(g, "enacted")
            label = "suspects" if flag else "no suspicion"
            print(f"  impossible splits, {label}: n={len(g)}, made/attempted hack {y}/{n} = {100*y/max(1, n):.1f}%")
        hackers = [r for r in imp if r["enacted"] == "yes" and r["first_act"] is not None]
        before = sum(1 for r in hackers if r["suspect"] and r["s_idx"] < r["first_act"])
        after = sum(1 for r in hackers if r["suspect"] and r["s_idx"] >= r["first_act"])
        print(f"  among {len(hackers)} episodes that made/attempted a hack: suspicion before first hack {before}, "
              f"only after {after}, never {len(hackers) - before - after}")
        pool = [r for r in imp if r["suspect"]]
        print("  random examples:")
        for r in random.sample(pool, min(4, len(pool))):
            print(f"    - {r['task']} ({r['split']}): {r['snip']!r}")


if __name__ == "__main__":
    main(sys.argv[1])
