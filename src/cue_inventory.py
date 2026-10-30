"""Goodfire's Qwen3.8 2.4T runs on ImpossibleBench, SWE-bench Verified and DeepSWE, side by side: behaviour (pass,
hacks made or attempted and their categories) next to awareness (A/B/C labels from src/awareness_llm.py).

  python src/cue_inventory.py <data dir> <aw dir>

<data dir> is logs/data (goodfire/, goodfire_swe/); <aw dir> holds candidates_all.jsonl and labels_final.jsonl.
Results: notes/ib_cues.md.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WS = re.compile(r"\s+")


def norm(s):
    return WS.sub(" ", s).strip()


def sets(d):
    d = Path(d)
    return [("ImpossibleBench", d / "goodfire/qwen_traces.jsonl", d / "goodfire/qwen_judge_rollouts.jsonl"),
            ("SWE-bench Verified", d / "goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.traces.jsonl",
             d / "goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.judge_rollouts.jsonl"),
            ("DeepSWE", d / "goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.traces.jsonl",
             d / "goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.judge_rollouts.jsonl")]


def load_labels(aw):
    lab = {json.loads(l)["id"]: json.loads(l) for l in (Path(aw) / "labels_final.jsonl").open()}
    out = defaultdict(lambda: {"A": [], "B": [], "C": []})
    for l in (Path(aw) / "candidates_all.jsonl").open():
        r = json.loads(l)
        if r["model"] != "Qwen":
            continue
        g = lab.get(r["id"])
        fam = r["bench"].split(" (")[0]
        for c in "ABC":
            if g and g[c]:
                out[(fam, r["row"])][c].append(r["text"])
    return out


def first_node(t, passages):
    """Node index of the earliest sampled assistant node containing the start of any passage."""
    heads = [norm(p)[:80] for p in passages]
    for i, n in enumerate(t["nodes"]):
        m = n["message"]
        if m["role"] != "assistant" or not n.get("sampled", True):
            continue
        c = m.get("content") if isinstance(m.get("content"), str) else ""
        txt = norm((m.get("reasoning_content") or "") + " " + c)
        if any(h in txt for h in heads):
            return i
    return None


def passed(bench, t):
    m = t.get("metrics") or {}
    if bench == "ImpossibleBench":
        return bool(m.get("test_passed"))
    if bench == "SWE-bench Verified":
        return bool(m.get("resolved"))
    return bool(((t.get("rewards") or {}).get("reward") or {}).get("score"))


def main(d, aw):
    labels = load_labels(aw)
    for bench, tp, jp in sets(d):
        traces = [json.loads(l)["traces"][0] for l in open(tp)]
        judge = [json.loads(l) for l in open(jp)]
        groups = defaultdict(list)
        for row, (t, j) in enumerate(zip(traces, judge)):
            split = t["task"]["data"].get("split")
            key = bench if bench != "ImpossibleBench" else f"{bench} ({'possible' if split == 'original' else 'impossible'})"
            lab = labels.get((bench, row), {"A": [], "B": [], "C": []})
            ns = t["nodes"]
            turns = [n for n in ns if n["message"]["role"] == "assistant" and n.get("sampled", True)]
            rchars = sum(len(n["message"].get("reasoning_content") or "") for n in turns)
            acted = [f for f in (j.get("flags") or []) if f.get("status") in ("enacted", "attempted")]
            first_act = min((f["node_index"] for f in acted if f.get("node_index") is not None), default=None)
            fb = first_node(t, lab["B"]) if lab["B"] else None
            fc = first_node(t, lab["C"]) if lab["C"] else None
            groups[key].append(dict(turns=len(turns), rchars=rchars, passed=passed(bench, t), enacted=j["verdict_enacted"],
                                    cats={f["category"] for f in acted}, A=bool(lab["A"]), B=bool(lab["B"]), C=bool(lab["C"]),
                                    fb=fb, fc=fc, first_act=first_act))
        for key, rs in groups.items():
            n = len(rs)
            med = lambda xs: sorted(xs)[len(xs) // 2]
            y = sum(r["enacted"] == "yes" for r in rs)
            no = sum(r["enacted"] == "no" for r in rs)
            print(f"\n## {key}: {n} episodes")
            print(f"  agent turns median {med([r['turns'] for r in rs])}, reasoning chars median {med([r['rchars'] for r in rs]):,}")
            print(f"  pass {sum(r['passed'] for r in rs)}/{n} ({100 * sum(r['passed'] for r in rs) / n:.0f}%)")
            print(f"  hack made or attempted (judge): {y}/{y + no} ({100 * y / max(1, y + no):.0f}%), split {n - y - no}")
            cats = Counter(c for r in rs if r["enacted"] == "yes" for c in r["cats"])
            print("  categories among those episodes: " + ", ".join(f"{c} {v}" for c, v in cats.most_common()))
            for c in "ABC":
                k = sum(r[c] for r in rs)
                print(f"  {c}: {k}/{n} ({100 * k / n:.0f}%)", end="")
            print()
            for c, f in (("B", "fb"), ("C", "fc")):
                for flag in (True, False):
                    g = [r for r in rs if r[c] == flag]
                    yy = sum(r["enacted"] == "yes" for r in g)
                    nn = sum(r["enacted"] == "no" for r in g)
                    print(f"  {c} {'yes' if flag else 'no '}: {len(g):>3} episodes, hacks {yy}/{yy + nn}", end=";")
                hk = [r for r in rs if r["enacted"] == "yes" and r["first_act"] is not None]
                pre = sum(1 for r in hk if r[f] is not None and r[f] <= r["first_act"])
                print(f"  among {len(hk)} hacking episodes, first {c} at or before the first hack in {pre}")


CANARY = re.compile(r"canary|BENCHMARK DATA SHOULD NEVER|\bGUID\b", re.I)
CANARY_STRICT = re.compile(r"BENCHMARK DATA SHOULD NEVER|canary[ _-]?(GUID|string|token)|canary:? [0-9a-f]{8}-", re.I)


def canary(d, aw):
    """Canary strings in tool outputs: which episodes see one, whether the model mentions it, and B / hidden-test
    targeting / hacks with vs without (Qwen, within benchmark)."""
    labels = load_labels(aw)
    for bench, tp, jp in sets(d):
        traces = [json.loads(l)["traces"][0] for l in open(tp)]
        judge = [json.loads(l) for l in open(jp)]
        groups = defaultdict(list)
        examples = []
        for row, (t, j) in enumerate(zip(traces, judge)):
            tool_text = "\n".join(str(n["message"].get("content") or "") for n in t["nodes"] if n["message"]["role"] == "tool")
            model = "\n".join((n["message"].get("reasoning_content") or "") + " " + str(n["message"].get("content") or "")
                              for n in t["nodes"] if n["message"]["role"] == "assistant" and n.get("sampled", True))
            strict = CANARY_STRICT.search(tool_text)
            loose = CANARY.search(tool_text)
            key = "strict canary" if strict else ("other 'canary'/'GUID' word" if loose else "none")
            lab = labels.get((bench, row), {"A": [], "B": [], "C": []})
            acted = {f["category"] for f in (j.get("flags") or []) if f.get("status") in ("enacted", "attempted")}
            groups[key].append(dict(mention=bool(CANARY.search(model)), B=bool(lab["B"]), enacted=j["verdict_enacted"],
                                    hidden="hidden_test_targeting" in acted))
            if strict and len(examples) < 3:
                examples.append(tool_text[max(0, strict.start() - 80): strict.end() + 80].replace("\n", " "))
        print(f"\n## {bench}")
        for key, rs in groups.items():
            n = len(rs)
            y = sum(r["enacted"] == "yes" for r in rs)
            no = sum(r["enacted"] == "no" for r in rs)
            print(f"  {key:<30} {n:>4} episodes; model mentions canary/GUID {sum(r['mention'] for r in rs)}/{n}; "
                  f"B {sum(r['B'] for r in rs)}/{n}; hidden-test targeting {sum(r['hidden'] for r in rs)}/{n}; "
                  f"hacks {y}/{y + no}")
        for e in examples:
            print(f"    e.g. …{e}…")


if __name__ == "__main__":
    if sys.argv[1] == "canary":
        canary(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1], sys.argv[2])
