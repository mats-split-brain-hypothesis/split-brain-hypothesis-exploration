"""The researcher's "why?" questions on cards 4, 5, 7 and 8, from existing transcripts and labels (no new runs).

  python src/grader_why.py <logs/data>      # writes logs/grader/dashboard/a5_why_*.json

Hack = Goodfire's verdict_enacted yes (split left out); the first enacted or attempted judge flag gives where it starts.

Card 4, why most hacks start before any rejection (ImpossibleBench impossible split, 29 hack episodes): before the
  first hack flag, did a local test run fail (the model's own `python test.py`, src/grader_actions.py's own_fail), and
  did the model already say a test is wrong (agent 7's flaw statement per turn, logs/rejection/stage0/turns.jsonl)?
  Compared between hacks that start before any rejection and hacks that start after one.
Card 5, where eval awareness falls: first alignment-eval (A) and capability-eval (B) passage, from awareness_llm's
  complete-coverage labels on the impossible split (logs/awareness_llm/candidates_all_fill.jsonl +
  labels_final_fill_checked.jsonl; A hand-checked), placed in the turn holding the passage's first 80 characters;
  grading talk (G) from the shared labeller's two runs on the hack episodes. Base: no-hack episodes.
Card 7, why reading the repo's tests goes with hacking on SWE-bench Verified only: the judge's hack categories per
  benchmark, the base rate in no-hack episodes, and a check of the test-path rule on DeepSWE's layouts.
Card 8, what the lookups are and what comes before them: lookup subtypes, the three calls before the first lookup
  (a failing run or error = difficulty), the sentence before it (names an upstream fix, PR, version = recognition),
  and whether another model solved the same SWE-bench Verified task honestly (resolved, verdict no).
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
D = G / "dashboard"
IB = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}
SWE = {("SWE-bench Verified", "Qwen"): "swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack",
       ("SWE-bench Verified", "GLM"): "swebench-verified-glm-5.2-nohack",
       ("SWE-bench Verified", "Kimi"): "swebench-verified-kimi-k3-nohack",
       ("DeepSWE", "Qwen"): "deepswe-qwen3.8-2.4t-a95b-fp8", ("DeepSWE", "GLM"): "deepswe-glm-5.2-fp8",
       ("DeepSWE", "Kimi"): "deepswe-kimi-k3"}
LABS = {"Qwen": "qwen", "GLM": "glm", "Kimi": "kimi"}
WS = re.compile(r"\s+")
SENT = re.compile(r"(?<=[.!?])\s+|\n+")
CUT = lambda s, n: s if len(s) <= n else s[:n].rstrip() + "…"  # noqa: E731
RECOGNISE = re.compile(r"\bupstream\b|\bfixed (in|by|upstream)\b|\b(PR|pull request|commit|changeset)\b|\bversion \d|"
                       r"\brelease[sd]?\b|\bchangelog\b|\bnewer (version|release)\b|\bmain branch\b|\bactual fix\b", re.I)
FAILED = re.compile(r"Traceback \(most recent call last\)|AssertionError|\bFAILED\b|\d+ failed|\bError\b")
LOOKUP_TYPES = [
    ("git objects beyond the base commit", re.compile(r"git\s+(log|show|diff|rev-list|branch)\b[^\n|;&]*(--all\b|\borigin\b|"
                                                      r"remotes?/|FETCH_HEAD|--grep)|git\s+(fetch|pull|clone)\b", re.I)),
    ("changelog searched for the issue number", re.compile(r"(grep|rg)\b[^\n|;]*(docs/changes|CHANGES|CHANGELOG|changelog|"
                                                           r"whatsnew)", re.I)),
    ("internet (curl, wget)", re.compile(r"\b(curl|wget)\b", re.I)),
    ("package index (pip download / index)", re.compile(r"pip\s+(download|index)", re.I)),
]


def norm(s):
    return WS.sub(" ", s or "").strip()


def nth_lines(path, rows):
    out = {}
    with open(path) as f:
        for i, line in enumerate(f):
            if i in rows:
                out[i] = json.loads(line)
    return out


def first_flag(j):
    fl = [f for f in j.get("flags") or [] if f.get("status") in ("enacted", "attempted") and f.get("node_index") is not None]
    return min(fl, key=lambda f: f["node_index"]) if fl else None


def kn(k, n):
    return {"k": k, "n": n}


def aw_passages(bench_key):
    lab = {}
    for l in (ROOT / "logs" / "awareness_llm" / "labels_final_fill_checked.jsonl").open():
        r = json.loads(l)
        lab[r["id"]] = r
    out = defaultdict(lambda: {"A": [], "B": [], "C": []})
    for l in (ROOT / "logs" / "awareness_llm" / "candidates_all_fill.jsonl").open():
        r = json.loads(l)
        if r["bench"] != bench_key:
            continue
        g = lab.get(r["id"]) or {}
        for c in "ABC":
            if g.get(c):
                out[(r["model"], r["row"])][c].append(r["text"])
    return out


def turn_texts(t):
    tn = [i for i, n in enumerate(t["nodes"]) if n["message"]["role"] == "assistant" and n.get("sampled", True)]
    texts = [norm((t["nodes"][i]["message"].get("reasoning_content") or "") + " " +
                  (t["nodes"][i]["message"].get("content") if isinstance(t["nodes"][i]["message"].get("content"), str) else ""))
             for i in tn]
    return tn, texts


def first_turn(passages, texts):
    hits = [k for p in passages for k, tx in enumerate(texts) if norm(p)[:80] in tx]
    return min(hits) if hits else None


def rel(x, h):
    return "never" if x is None else ("before the hack" if x < h else ("same turn" if x == h else "after the hack"))


def card4_5(gdir, rows):
    t7 = defaultdict(dict)
    for l in open(ROOT / "logs" / "rejection" / "stage0" / "turns.jsonl"):
        tr = json.loads(l)
        t7[(tr["model"], tr["row"])][tr["node"]] = tr
    aw = aw_passages("ImpossibleBench (impossible)")
    c4, c4ex, c5, c5base, c5ex = [], [], [], [], []
    for model, key in IB.items():
        rs = {r["row"]: r for r in rows if r["bench"] == "ImpossibleBench impossible" and r["model"] == model
              and r["verdict_enacted"] in ("yes", "no")}
        judges = [json.loads(l) for l in open(Path(gdir) / "goodfire" / f"{key}_judge_rollouts.jsonl")]
        traces = nth_lines(Path(gdir) / "goodfire" / f"{key}_traces.jsonl", set(rs))
        g_runs = []
        for run in (1, 2):
            p = G / "labels" / f"hack_{LABS[model]}_run{run}.jsonl"
            gt = defaultdict(list)
            if p.exists():
                for l in p.open():
                    u = json.loads(l)
                    if "G" in (u.get("flags") or []):
                        gt[u["episode"]].append(u["turn"])
            g_runs.append(gt)
        groups = defaultdict(Counter)
        local_fail_counts = defaultdict(list)
        rel_c = defaultdict(Counter)
        base = Counter()
        hack_turns, nohack_ab = [], []  # for the time-matched base: hack turns; (A turn, B turn) of no-hack episodes
        for row, r in sorted(rs.items()):
            t = traces[row]["traces"][0]
            tn, texts = turn_texts(t)
            turn_at = lambda node: sum(i <= node for i in tn) - 1  # noqa: E731
            f0 = r["fb"][0] if r["fb"] else 10 ** 9
            a_turn = first_turn(aw[(model, row)]["A"], texts)
            b_turn = first_turn(aw[(model, row)]["B"], texts)
            if r["verdict_enacted"] == "no":
                base["episodes"] += 1
                base["any A"] += a_turn is not None
                base["any B"] += b_turn is not None
                rj = turn_at(f0) + 1 if r["fb"] else None
                if a_turn is None:
                    base["A never"] += 1
                elif rj is None or a_turn < rj:
                    base["A before the first rejection"] += 1
                else:
                    base["A after the first rejection"] += 1
                nohack_ab.append((a_turn, b_turn))
                continue
            fl = first_flag(judges[row])
            if fl is None:
                continue
            h = fl["node_index"]
            grp = "hack before any rejection" if not any(f < h for f in r["fb"]) else "hack after a rejection"
            c = groups[grp]
            c["episodes"] += 1
            own_before = [x for x in r["own_fail"] if x < h]
            c["local test run failed before the hack"] += bool(own_before)
            # the same with agent 7's failing-run detector (its running count n_own_fail, up to the hack's turn)
            c["local test run failed before the hack (agent 7's detector)"] += any(
                (tr.get("n_own_fail") or 0) > 0 for nd, tr in t7[(model, row)].items() if nd <= h)
            local_fail_counts[grp].append(len(own_before))
            flaw_nodes = [nd for nd, tr in t7[(model, row)].items() if tr.get("flaw_here")]
            c["said a test is wrong before the hack"] += any(nd < h for nd in flaw_nodes)
            if grp == "hack after a rejection":
                c["local test run failed before the first rejection"] += any(x < f0 for x in r["own_fail"])
            split = t["task"]["data"].get("split")
            if grp == "hack before any rejection" and not any(e["title"].startswith(f"ImpossibleBench · {model} ") for e in c4ex):
                how = "after a failing local test run" if own_before else "with no failing local test run"
                c4ex.append({"title": f"ImpossibleBench · {model} · {r['task']} ({split}): hack {how}, before any rejection",
                             "finding": "Card 4", "source": "Goodfire transcript (impossible split)",
                             "picked": f"first {model} hack episode in file order whose hack starts before any rejection",
                             "context": f"Local failing test runs before the hack: {len(own_before)}; rejections before it: 0.",
                             "cue_hl": "", "action": "",
                             "reasoning": f"Judge quote at the hack's start ({fl['category']}, {fl['status']}): "
                                          f"{CUT(fl['quote'], 220)}",
                             "outcome": f"Judge verdict_enacted 'yes'; categories {', '.join(r['hack_cats'])}"})
            # card 5: A, B and G against the hack's turn
            ht = turn_at(h)
            hack_turns.append(ht)
            ep = f"{key}|{row}"
            gs = [min(g[ep]) for g in g_runs if g.get(ep)]
            g_turn = round(sum(gs) / len(gs)) if gs else None
            for lab, x in (("alignment-eval (A)", a_turn), ("capability-eval (B)", b_turn),
                           ("grading talk (G, shared labeller, mean of 2 runs)", g_turn)):
                rel_c[lab][rel(x, ht)] += 1
            if a_turn is not None and a_turn < ht:
                ap = next(p for p in aw[(model, row)]["A"] if norm(p)[:80] in texts[a_turn])
                c5ex.append({"title": f"ImpossibleBench · {model} · {r['task']} ({split}): says it is a test of itself, then hacks",
                             "finding": "Card 5", "source": "Goodfire transcript (impossible split)",
                             "picked": "every hack episode whose first A passage comes before the hack's turn",
                             "context": f"Turn {a_turn}: " + CUT(ap, 260), "cue_hl": "",
                             "action": f"Hack starts at turn {ht} ({fl['category']}, {fl['status']}).",
                             "reasoning": "Judge quote: " + CUT(fl["quote"], 200),
                             "outcome": f"Judge verdict_enacted 'yes'; categories {', '.join(r['hack_cats'])}"})
        for grp, c in groups.items():
            for k_, v in c.items():
                if k_ != "episodes":
                    c4.append({"model": model, "episodes": grp, "measure": k_, "k": v, "n": c["episodes"]})
            c4.append({"model": model, "episodes": grp, "measure": "median local failures before the hack",
                       "k": statistics.median(local_fail_counts[grp]) if local_fail_counts[grp] else 0,
                       "n": c["episodes"], "is_median": True})
        n_h = sum(c["episodes"] for c in groups.values())
        for lab, cc in rel_c.items():
            for w in ("before the hack", "same turn", "after the hack", "never"):
                c5.append({"model": model, "measure": lab, "when": w, "k": cc[w], "n": n_h})
        # time-matched base (verifier's suggestion): no-hack episodes with A / B before this model's median hack turn
        mh = statistics.median(hack_turns) if hack_turns else None
        if mh is not None:
            base["A before the median hack turn"] = sum(a is not None and a < mh for a, _ in nohack_ab)
            # B "by" the median turn (on it counts), to match "before or on the hack's turn" in hack episodes
            base["B by the median hack turn"] = sum(b is not None and b <= mh for _, b in nohack_ab)
        for k_ in ("A before the median hack turn", "B by the median hack turn", "any A", "any B",
                   "A before the first rejection", "A after the first rejection", "A never"):
            c5base.append({"model": model, "measure": k_, "k": base[k_], "n": base["episodes"], "median_hack_turn": mh})
    return c4, c4ex, c5, c5base, c5ex


DEEP_TEST = re.compile(r"(\.test\.[jt]sx?|\.spec\.[jt]sx?|_test\.go|__tests__/|/spec/|/tests?/|test_\w+\.py|_test\.py|"
                       r"tests?\.rs|/testing/|conftest\.py)")


def card7_8(gdir, rows):
    by = {(r["bench"], r["model"], r["row"]): r for r in rows}
    cats, base, pathcheck, ex7, look, before, ex8 = [], [], [], [], [], [], []
    solved = defaultdict(dict)  # SWE-bench Verified task -> model -> (resolved, verdict)
    positions = defaultdict(list)  # (bench, model, group) -> [(calls before the first lookup, calls in episode)]
    for (bench, model), name in SWE.items():
        tp = Path(gdir) / "goodfire_swe" / f"{name}.traces.jsonl"
        jp = Path(gdir) / "goodfire_swe" / f"{name}.judge_rollouts.jsonl"
        judges = [json.loads(l) for l in jp.open()]
        cat_c, n_hack = Counter(), 0
        miss_read, hit_read = Counter(), 0
        lk = defaultdict(Counter)
        bf = defaultdict(Counter)
        with tp.open() as f:
            for row, line in enumerate(f):
                r = by.get((bench, model, row))
                if r is None:
                    continue
                t = json.loads(line)["traces"][0]
                v = r["verdict_enacted"]
                if bench == "SWE-bench Verified":
                    try:
                        res = float(eval(str(t.get("metrics") or "{}")).get("resolved", 0)) if isinstance(t.get("metrics"), str) \
                            else float((t.get("metrics") or {}).get("resolved", 0))
                    except Exception:
                        res = 0.0
                    solved[t["task"]["data"]["name"]][model] = (res, v)
                if v == "yes":
                    n_hack += 1
                    cat_c.update(r["hack_cats"])
                # card 7 measurement check: reads of test-like files that the repo-test rule misses
                if bench == "DeepSWE":
                    for n in t["nodes"]:
                        m = n["message"]
                        if m["role"] != "assistant" or not n.get("sampled", True):
                            continue
                        for tc in m.get("tool_calls") or []:
                            c = str(GA.args_of(tc).get("command") or "")
                            if GA.SWE_READ.search(c) and DEEP_TEST.search(c):
                                if GA.purpose_swe(GA.args_of(tc)) == "inspect_content":
                                    hit_read += 1
                                else:
                                    miss_read[DEEP_TEST.search(c).group(1)] += 1
                # card 8: lookups
                if v not in ("yes", "no"):
                    continue
                grp = "hack (verdict)" if v == "yes" else "no hack (verdict)"
                seeks = [nd for nd, p in r["acts"] if p == "seek_answer"]
                lk[grp]["episodes"] += 1
                if not seeks:
                    continue
                lk[grp]["with a lookup"] += 1
                cmds = []
                for n in t["nodes"][seeks[0]:]:
                    m = n["message"]
                    if m["role"] == "assistant" and n.get("sampled", True):
                        for tc in m.get("tool_calls") or []:
                            if GA.purpose_swe(GA.args_of(tc)) == "seek_answer":
                                cmds.append(str(GA.args_of(tc).get("command") or ""))
                types = {lab for c in cmds for lab, p in LOOKUP_TYPES if p.search(c)}
                for lab in types:
                    lk[grp][lab] += 1
                # what comes right before the first lookup
                fl = first_flag(judges[row]) if v == "yes" else None
                order = (None if fl is None else ("lookup itself flagged" if fl["node_index"] == seeks[0] else
                         ("lookup first" if seeks[0] < fl["node_index"] else "hack flag first")))
                key = grp if v == "no" else f"hack, {order}"
                prev_out = []
                outs = {n["message"].get("tool_call_id"): str(n["message"].get("content") or "") for n in t["nodes"]
                        if n["message"]["role"] == "tool"}
                calls = [(k_, tc) for k_, n in enumerate(t["nodes"][:seeks[0]]) if n["message"]["role"] == "assistant"
                         and n.get("sampled", True) for tc in (n["message"].get("tool_calls") or [])]
                prev_out = [outs.get(tc.get("id"), "") for _, tc in calls[-3:]]
                m0 = t["nodes"][seeks[0]]["message"]
                sents = [x for x in SENT.split(m0.get("reasoning_content") or "") if x.strip()]
                last = sents[-1] if sents else ""
                bf[key]["episodes"] += 1
                pos = sum(1 for nd, _ in r["acts"] if nd < seeks[0])
                positions[(bench, model, key)].append((pos, len(r["acts"])))
                bf[key]["a failing run or error in the 3 calls before"] += any(FAILED.search(o) for o in prev_out)
                bf[key]["the sentence before names an upstream fix, PR, version or release"] += bool(RECOGNISE.search(last))
                if bench == "SWE-bench Verified" and model == "Qwen" and key in ("hack, lookup first", "no hack (verdict)") \
                        and not any(e["title"].endswith(key) for e in ex8):
                    ex8.append({"title": f"SWE-bench Verified · Qwen · {t['task']['data']['name']}: {key}",
                                "finding": "Card 8", "source": "Goodfire transcript",
                                "picked": f"first Qwen episode in file order in the group '{key}'",
                                "context": "Sentence before the lookup: " + CUT(last, 260), "cue_hl": "",
                                "action": CUT(WS.sub(" ", cmds[0].replace("cd /testbed && ", "")), 220),
                                "reasoning": (f"First hack flag ({fl['category']}, {fl['status']}): {CUT(fl['quote'], 180)}"
                                              if fl else "No enacted or attempted flag."),
                                "outcome": f"Previous 3 calls had a failing run or error: "
                                           f"{'yes' if any(FAILED.search(o) for o in prev_out) else 'no'}."})
                # card 7 excerpt: the sentence before the first repo-test read in a hack episode
                if v == "yes" and model == "Qwen" and not any(e["title"].startswith(bench) for e in ex7):
                    rd = next((nd for nd, p in r["acts"] if p == "inspect_content"), None)
                    if rd is not None:
                        mm = t["nodes"][rd]["message"]
                        ss = [x for x in SENT.split(mm.get("reasoning_content") or "") if x.strip()]
                        cmd = next((str(GA.args_of(tc).get("command") or "") for tc in mm.get("tool_calls") or []
                                    if GA.purpose_swe(GA.args_of(tc)) == "inspect_content"), "")
                        ex7.append({"title": f"{bench} · Qwen · {t['task']['data']['name']}: reads the repository's tests",
                                    "finding": "Card 7", "source": "Goodfire transcript",
                                    "picked": "first Qwen hack episode in file order with a repo-test read",
                                    "context": "Sentence before the read: " + CUT(ss[-1] if ss else "", 260), "cue_hl": "",
                                    "action": CUT(WS.sub(" ", cmd.replace("cd /testbed && ", "").replace("cd /app && ", "")), 200),
                                    "reasoning": "", "outcome": f"Hack categories: {', '.join(r['hack_cats'])}"})
        for cat, k_ in cat_c.most_common():
            cats.append({"label": f"{bench} · {model}", "category": cat, "k": k_, "n": n_hack})
        for grp, c in lk.items():
            for lab in ["with a lookup"] + [l for l, _ in LOOKUP_TYPES]:
                look.append({"label": f"{bench} · {model}", "episodes": grp, "measure": lab, "k": c[lab],
                             "n": c["episodes"] if lab == "with a lookup" else c["with a lookup"]})
        for key, c in bf.items():
            for lab in ("a failing run or error in the 3 calls before",
                        "the sentence before names an upstream fix, PR, version or release"):
                before.append({"label": f"{bench} · {model}", "group": key, "measure": lab, "k": c[lab], "n": c["episodes"]})
        if bench == "DeepSWE":
            pathcheck.append({"label": f"DeepSWE · {model}", "reads_counted": hit_read,
                              "test_like_reads_missed": sum(miss_read.values()),
                              "missed_patterns": ", ".join(f"{k} {v}" for k, v in miss_read.most_common(5))})
    for (bench, model, key), ps in sorted(positions.items()):
        before.append({"label": f"{bench} · {model}", "group": key, "measure": "first lookup within the first 5 calls",
                       "k": sum(p < 5 for p, _ in ps), "n": len(ps)})
        before.append({"label": f"{bench} · {model}", "group": key,
                       "measure": "first lookup in the first quarter of the episode",
                       "k": sum(p < 0.25 * t for p, t in ps), "n": len(ps)})
    # difficulty: was the same SWE-bench Verified task solved honestly (resolved, verdict no) by another model?
    diff = []
    for model in ("Qwen", "GLM", "Kimi"):
        c = defaultdict(Counter)
        for r in rows:
            if r["bench"] != "SWE-bench Verified" or r["model"] != model or r["verdict_enacted"] not in ("yes", "no"):
                continue
            task = r["task"]
            others = [m for m in ("Qwen", "GLM", "Kimi") if m != model]
            honest = any(solved.get(task, {}).get(o, (0, ""))[0] >= 1 and solved[task][o][1] == "no" for o in others)
            k_ = "another model solved it honestly" if honest else "no other model solved it honestly"
            c[k_]["episodes"] += 1
            c[k_]["hack"] += r["verdict_enacted"] == "yes"
            c[k_]["lookup"] += any(p == "seek_answer" for _, p in r["acts"])
            c[k_]["lookup in a hack episode"] += r["verdict_enacted"] == "yes" and any(p == "seek_answer" for _, p in r["acts"])
        for k_, cc in c.items():
            for m_ in ("hack", "lookup", "lookup in a hack episode"):
                diff.append({"label": f"SWE-bench Verified · {model}", "tasks": k_, "measure": m_, "k": cc[m_],
                             "n": cc["episodes"]})
    return cats, base, pathcheck, ex7, look, before, ex8, diff


def main(gdir):
    rows = json.loads((G / "actions_rows.json").read_text())
    c4, c4ex, c5, c5base, c5ex = card4_5(gdir, rows)
    cats, _, pathcheck, ex7, look, before, ex8, diff = card7_8(gdir, rows)
    out = {"a5_why_local": c4, "a5_why_awareness": c5, "a5_why_awareness_base": c5base,
           "a5_why_swe_cats": cats, "a5_why_pathcheck": pathcheck, "a5_why_lookup_types": look,
           "a5_why_lookup_before": before, "a5_why_difficulty": diff,
           "a5_why_examples": c4ex + c5ex[:6] + ex7 + ex8}
    for k, v in out.items():
        (D / f"{k}.json").write_text(json.dumps(v, indent=1, ensure_ascii=False))
        print(f"{k}: {len(v)} rows")


if __name__ == "__main__":
    main(sys.argv[1])
