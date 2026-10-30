"""Cost of the four probe views per set, from logged token counts (no API calls).

Views: whole / cut, each without reasoning (the current renderer) and with reasoning ("[reasoning] ..." at the start of
each assistant turn, each block clipped head+tail to BLOCK chars). Total cap CAP chars (head and tail kept) for every
view, so the two views at a cut differ only by the reasoning.

  reasoning_view_cost.py <worktree> <rv_sizes.jsonl>
"""
import glob
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "src"))
import eval_probe as EP  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402
from inspect_ai.model import ContentReasoning  # noqa: E402

# price fit on long inputs only (whole-transcript probes), from usage.cost
X, y = [], []
for f in glob.glob(str(root / "logs/eval_probe/a[12]_*.jsonl")):
    for l in open(f):
        r = json.loads(l)
        if r.get("family") == "qwen" and r.get("prompt_tokens") and r.get("usd") and r.get("completion_tokens") is not None:
            X.append([r["prompt_tokens"], r["completion_tokens"]])
            y.append(r["usd"])
coef = np.linalg.lstsq(np.array(X, float), np.array(y), rcond=None)[0]
P_IN, P_OUT = coef * 1.15  # the all-call fit is ~10% low on 12k-token inputs (a2_e1: $0.0176 billed vs $0.0158)
print(f"price fit on {len(y)} calls, x1.15: ${P_IN * 1e6:.3f}/M in, ${P_OUT * 1e6:.3f}/M out")
OUT = {"purpose_mc": 990, "eval_binary": 800, "who_checks": 600}  # mean completion tokens on long inputs (a2_e1*)
TOK_PER_CHAR, OVERHEAD = 0.31, 350


def call_cost(chars, probe):
    return (chars * TOK_PER_CHAR + OVERHEAD) * P_IN + OUT[probe] * P_OUT


def clip_ht(s, n):
    return s if len(s) <= n else s[: n // 2] + f" [... {len(s) - n} characters clipped] " + s[-n // 2:]


def render(ms, cut, with_reasoning, block, cap):
    sub = ms[:cut] if cut is not None else ms
    gen = []
    for m, r in sub:
        g = dict(m)
        if with_reasoning and m["role"] == "assistant" and r:
            g["content"] = "[reasoning] " + clip_ht(r, block) + ("\n\n" + m["content"] if m["content"] else "")
        gen.append(g)
    EP.CLIP_TOTAL = cap
    return sum(len(x["content"]) for x in EP.to_chat(gen))


rows = [json.loads(l) for l in open(sys.argv[2])]
logs = {}
for r in rows:
    hits = glob.glob(str(root) + "/logs/**/" + r["log"], recursive=True)
    logs.setdefault(hits[0], []).append(r)
out = []
for path, rs in logs.items():
    log = read_eval_log(path)
    by = {(s.id, s.epoch): s for s in log.samples}
    for r in rs:
        s = by[(r["sample"], r["epoch"])]
        ms = []
        for m in s.messages:
            g = {"role": m.role, "content": m.text or "", "calls": []}
            rr = ""
            if m.role == "assistant":
                g["calls"] = [(t.function, json.dumps(t.arguments)) for t in (m.tool_calls or [])]
                rr = "".join(c.reasoning or "" for c in m.content if isinstance(c, ContentReasoning)) \
                    if isinstance(m.content, list) else ""
            ms.append((g, rr))
        cut = r["cut_index"]
        if r["set"].startswith("IB"):  # IB: the first failed test run after the switch (control: after turn 1)
            cut = r.get("ib_cut", cut)
        v = {}
        for block, cap in ((6000, 80000), (4000, 40000)):
            v[(block, cap)] = {
                "whole_plain": render(ms, None, False, block, cap), "whole_reason": render(ms, None, True, block, cap),
                "cut_plain": render(ms, cut, False, block, cap) if cut else None,
                "cut_reason": render(ms, cut, True, block, cap) if cut else None}
        out.append({**{k: r[k] for k in ("set", "arm", "hack", "epoch", "sample", "cut_rule")}, "views": {str(k): x for k, x in v.items()}})

Path(sys.argv[2].replace(".jsonl", "_rendered.jsonl")).write_text("".join(json.dumps(o) + "\n" for o in out))
EP.CLIP_TOTAL = 40000
qs = {"base": {"purpose_mc": 3, "eval_binary": 1}, "who": {"purpose_mc": 3, "eval_binary": 1, "who_checks": 3}}
WHO_SETS = ("G3", "G3 ext", "IB run 3", "IB run 4")
for key in ("(6000, 80000)", "(4000, 40000)"):
    print(f"\n== reasoning blocks clipped to {key.split(',')[0][1:]} chars, total cap {key.split(',')[1][:-1].strip()} chars")
    print(f"{'set':15} {'arm':11} n  | median chars: whole plain / +reasoning ; cut plain / +reasoning | $ per episode (all questions): whole plain, whole+R, cut plain, cut+R")
    tot = defaultdict(float)
    grp = defaultdict(list)
    for o in out:
        if o["hack"] is None and o["set"] in ("E1 (D1 C5/C6)",):
            continue  # unlabelled retry episodes
        grp[(o["set"], str(o["arm"]))].append(o)
    for (sname, arm), os_ in grp.items():
        q = qs["who" if sname in WHO_SETS else "base"]
        meds, costs = [], []
        for view in ("whole_plain", "whole_reason", "cut_plain", "cut_reason"):
            ch = [o["views"][key][view] for o in os_ if o["views"][key][view]]
            meds.append(int(st.median(ch)) if ch else 0)
            c = sum(sum(k * call_cost(o["views"][key][view] or 0, p) for p, k in q.items()) for o in os_)
            costs.append(c)
            tot[view] += c
        print(f"{sname:15} {arm[:11]:11} {len(os_):2} | {meds[0]:6} / {meds[1]:6} ; {meds[2]:6} / {meds[3]:6} | "
              + ", ".join(f"{c / len(os_):.3f}" for c in costs) + "   (set: " + ", ".join(f"${c:.2f}" for c in costs) + ")")
    print("TOTAL over the finished episodes:", ", ".join(f"{v}: ${c:.2f}" for v, c in tot.items()))
