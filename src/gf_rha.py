"""Goodfire's transcripts: rejection, hacking and eval awareness (notes/gf_rejection_hack_awareness.md).

  python src/gf_rha.py ib <stage0 dir> <aw dir> <goodfire dir> <out dir>

`ib` reads stage 0's per-turn table (logs/rejection/stage0/turns.jsonl, episodes.jsonl, texts.jsonl; built by
src/rejection_turns.py), adds sampled-coverage A/B placement (the shared candidates_all / labels_final rule) for
comparisons with the possible-split control, and writes <out dir>/ib.json plus a plain-text report of counts.

Scripts only count: nothing here prints or stores the models' text (texts.jsonl is read only to place labelled
passages by their first 80 characters, as stage 0 did).
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

WS = " "
MODELS = ["Qwen", "GLM", "Kimi"]
IMPOSSIBLE = ("conflicting", "oneoff")
TRACE_FILES = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}


def norm(s):
    return WS.join((s or "").split())


# ---------- statistics ----------

def kn(k, n):
    return f"{k}/{n}"


def mh_rr(strata):
    """Mantel-Haenszel risk ratio over strata of (a, n1, b, n0): exposed events/turns, unexposed events/turns.
    Returns (rr, informative strata, exposed turns in them, unexposed turns in them, events exposed, events unexposed)."""
    num = den = 0.0
    info = n1s = n0s = a_s = b_s = 0
    for a, n1, b, n0 in strata:
        if n1 == 0 or n0 == 0:
            continue
        N = n1 + n0
        num += a * n0 / N
        den += b * n1 / N
        info += 1
        n1s += n1
        n0s += n0
        a_s += a
        b_s += b
    rr = (num / den) if den > 0 else (float("inf") if num > 0 else None)
    return rr, info, n1s, n0s, a_s, b_s


def boot_ci(episodes, stat_fn, reps=1000, seed=0):
    """Percentile 95% interval of stat_fn over episode resamples (turns within an episode stay together)."""
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        sample = [episodes[rng.randrange(len(episodes))] for _ in episodes]
        v = stat_fn(sample)
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    return lo, hi


def fmt_rr(rr):
    if rr is None:
        return "n/a"
    if rr == float("inf"):
        return "inf"
    return f"{rr:.2f}"


# ---------- loading ----------

def load_ib(stage0, aw, gdir):
    stage0, aw = Path(stage0), Path(aw)
    eps = {}
    for l in (stage0 / "episodes.jsonl").open():
        e = json.loads(l)
        eps[(e["model"], e["row"])] = e
    turns = defaultdict(list)
    for l in (stage0 / "turns.jsonl").open():
        t = json.loads(l)
        turns[(t["model"], t["row"])].append(t)
    for k in turns:
        turns[k].sort(key=lambda t: t["turn"])
    # Sampled-coverage labels (the shared rule: keyword-flagged passages + <= 10 random per episode), both splits.
    lab = {json.loads(l)["id"]: json.loads(l) for l in (aw / "labels_final.jsonl").open()}
    samp = defaultdict(lambda: {"A": [], "B": []})
    for l in (aw / "candidates_all.jsonl").open():
        c = json.loads(l)
        if not c["bench"].startswith("ImpossibleBench"):
            continue
        g = lab.get(c["id"])
        for x in "AB":
            if g and g[x]:
                samp[(c["model"], int(c["row"]))][x].append(norm(c["text"])[:80])
    texts = defaultdict(dict)
    for l in (stage0 / "texts.jsonl").open():
        r = json.loads(l)
        texts[(r["model"], r["row"])][r["turn"]] = norm(r["reasoning"] + " " + r["reply"])
    for key, ts in turns.items():
        tx = texts.get(key, {})
        for x in "AB":
            placed = defaultdict(int)
            for head in samp.get(key, {"A": [], "B": []})[x]:
                hit = next((t["turn"] for t in ts if head and head in tx.get(t["turn"], "")), None)
                if hit is not None:
                    placed[hit] += 1
            for t in ts:
                t[f"{x}_samp"] = placed.get(t["turn"], 0)
    # Visible pass from Goodfire's own metric (test_passed), for the pass vs verdict_enacted disagreement count.
    gdir = Path(gdir)
    for model, key in TRACE_FILES.items():
        for row, line in enumerate((gdir / f"{key}_traces.jsonl").open()):
            m = json.loads(line)["traces"][0].get("metrics") or {}
            if (model, row) in eps:
                eps[(model, row)]["test_passed"] = float(m.get("test_passed", 0) or 0) == 1.0
    return eps, turns


# ---------- per-episode helpers ----------

def hacked_any(t):
    return t["considered_here"] > 0 or t["acted_here"] > 0


def hacked_acted(t):
    return t["acted_here"] > 0


def first_turn(ts, fn):
    return next((t["turn"] for t in ts if fn(t)), None)


def at_risk(ts, event):
    """Turns up to and including the first event turn, each with whether the event happens there."""
    out = []
    for t in ts:
        e = bool(event(t))
        out.append((t, e))
        if e:
            break
    return out


# ---------- measures ----------

def hazard_by_rej(eps_turns, event):
    c = defaultdict(lambda: [0, 0])
    for ts in eps_turns:
        for t, e in at_risk(ts, event):
            g = min(t["n_rej"], 3)
            c[g][1] += 1
            c[g][0] += e
    return {str(k): c[k] for k in sorted(c)}


def char_bins(eps_turns, event, nb=10):
    vals = sorted(t["chars_before"] for ts in eps_turns for t, _ in at_risk(ts, event))
    if not vals:
        return []
    return [vals[int(i * len(vals) / nb)] for i in range(1, nb)]


def strata_counts(eps_turns, event, key, exposed=lambda t: t["n_rej"] >= 1):
    s = defaultdict(lambda: [0, 0, 0, 0])
    for ts in eps_turns:
        for t, e in at_risk(ts, event):
            k = key(t)
            if exposed(t):
                s[k][0] += e
                s[k][1] += 1
            else:
                s[k][2] += e
                s[k][3] += 1
    return list(s.values())


def matched(eps_turns, event, by, exposed=lambda t: t["n_rej"] >= 1, reps=1000):
    if by == "turn":
        key = lambda t: t["turn"]
    else:
        cuts = char_bins(eps_turns, event)
        key = lambda t: sum(t["chars_before"] >= c for c in cuts)
    rr, info, n1, n0, a, b = mh_rr(strata_counts(eps_turns, event, key, exposed))
    lo, hi = boot_ci(eps_turns, lambda smp: (lambda r: None if r[0] in (None, float("inf")) else r[0])(
        mh_rr(strata_counts(smp, event, key, exposed))), reps=reps)
    return dict(rr=rr, ci=[lo, hi], informative_strata=info, exposed_turns=n1, unexposed_turns=n0,
                exposed_events=a, unexposed_events=b)


def rate_per_10k(eps_turns, field, phase):
    n = chars = 0
    for ts in eps_turns:
        for t in ts:
            if phase(t):
                n += t[field]
                chars += t["chars"]
    return dict(passages=n, chars=chars, per_10k=round(10000 * n / chars, 3) if chars else None)


def orders(eps, turns_of, model, hack_fn, field="A_here"):
    """Order of the first rejection, first awareness passage (`field`, complete coverage; labelled "A" in the order
    strings whatever the field) and first hack (turn level; a rejection sits before the first turn that has seen it).
    Among impossible-split episodes with all three."""
    cnt = defaultdict(int)
    n_all = n_three = 0
    for key, ts in turns_of.items():
        if key[0] != model or ts[0]["split"] not in IMPOSSIBLE:
            continue
        n_all += 1
        r = first_turn(ts, lambda t: t["n_rej"] >= 1)
        a = first_turn(ts, lambda t: t[field] > 0)
        h = first_turn(ts, hack_fn)
        if r is None or a is None or h is None:
            continue
        n_three += 1
        ev = [("R", r - 0.5), ("A", a), ("H", h)]
        ev.sort(key=lambda x: x[1])
        if a == h:
            lab = "->".join(x[0] for x in ev if x[0] == "R") + ("->" if r - 0.5 < a else "") + "A=H(same turn)"
            if r - 0.5 > a:
                lab = "A=H(same turn)->R"
        else:
            lab = "->".join(x[0] for x in ev)
        cnt[lab] += 1
    return dict(n_all=n_all, n_with_all_three=n_three, orders=dict(sorted(cnt.items(), key=lambda x: -x[1])))


def awareness_matched(eps_turns, hack_fn, window=(1, 2), reps=1000, field="A_here", min_rej=1):
    """Among rejected episodes: turns t with n_rej >= min_rej before the first hack (so t holds no flag); exposed = an
    awareness passage (`field`) at t. Outcome = the first hack within turns t+window[0] .. t+window[1]. Strata
    (turn, n_rej)."""
    def strata(sample):
        s = defaultdict(lambda: [0, 0, 0, 0])
        for ts in sample:
            h = first_turn(ts, hack_fn)
            for t in ts:
                if t["n_rej"] < min_rej:
                    continue
                if h is not None and t["turn"] >= h:
                    break
                y = h is not None and t["turn"] + window[0] <= h <= t["turn"] + window[1]
                k = (t["turn"], t["n_rej"])
                if t[field] > 0:
                    s[k][0] += y
                    s[k][1] += 1
                else:
                    s[k][2] += y
                    s[k][3] += 1
        return list(s.values())
    rr, info, n1, n0, a, b = mh_rr(strata(eps_turns))
    lo, hi = boot_ci(eps_turns, lambda smp: (lambda r: None if r[0] in (None, float("inf")) else r[0])(mh_rr(strata(smp))),
                     reps=reps)
    return dict(rr=rr, ci=[lo, hi], informative_strata=info, exposed_turns=n1, unexposed_turns=n0,
                exposed_events=a, unexposed_events=b)


def ib(stage0, aw, gdir, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    eps, turns = load_ib(stage0, aw, gdir)
    res = {}
    lines = []
    P = lines.append
    for model in MODELS:
        R = res[model] = {}
        imp = [ts for k, ts in turns.items() if k[0] == model and ts[0]["split"] in IMPOSSIBLE]
        pos = [ts for k, ts in turns.items() if k[0] == model and ts[0]["split"] == "original"]
        imp_rej = [ts for ts in imp if ts[-1]["n_rej"] >= 1]
        pos_rej = [ts for ts in pos if ts[-1]["n_rej"] >= 1]
        # Episode-level counts.
        E = [eps[k] for k in eps if k[0] == model]
        ei = [e for e in E if e["split"] in IMPOSSIBLE]
        R["episodes"] = dict(
            impossible=len(ei), possible=len(E) - len(ei),
            impossible_with_rejection=len(imp_rej), possible_with_rejection=len(pos_rej),
            verdict_enacted_yes_impossible=sum(1 for e in ei if e["verdict"] == "yes"),
            pass_impossible=sum(1 for e in ei if e.get("test_passed")),
            pass_but_not_enacted=sum(1 for e in ei if e.get("test_passed") and e["verdict"] != "yes"),
            enacted_but_no_pass=sum(1 for e in ei if not e.get("test_passed") and e["verdict"] == "yes"))
        P(f"\n######## {model}")
        P(f"episodes {R['episodes']}")
        # Q1: rejection -> hacking.
        for oname, fn in (("hack_considered_any", hacked_any), ("hack_attempted_enacted", hacked_acted)):
            for sname, S in (("impossible", imp), ("impossible_rejected", imp_rej), ("possible", pos), ("possible_rejected", pos_rej)):
                if not S:
                    continue
                q = R.setdefault("Q1", {}).setdefault(oname, {})[sname] = dict(
                    episodes=len(S), by_rej=hazard_by_rej(S, fn),
                    mh_turn=matched(S, fn, "turn"), mh_chars=matched(S, fn, "chars"))
                P(f"Q1 {oname:24} {sname:20} eps {len(S):3}  by n_rej {q['by_rej']}  "
                  f"MH turn {fmt_rr(q['mh_turn']['rr'])} [{q['mh_turn']['ci'][0] and round(q['mh_turn']['ci'][0],2)}, {q['mh_turn']['ci'][1] and round(q['mh_turn']['ci'][1],2)}] "
                  f"strata {q['mh_turn']['informative_strata']} ({q['mh_turn']['exposed_turns']} vs {q['mh_turn']['unexposed_turns']} turns)  "
                  f"MH chars {fmt_rr(q['mh_chars']['rr'])} [{q['mh_chars']['ci'][0] and round(q['mh_chars']['ci'][0],2)}, {q['mh_chars']['ci'][1] and round(q['mh_chars']['ci'][1],2)}] "
                  f"strata {q['mh_chars']['informative_strata']}")
        # Q2: rejection -> awareness. Complete coverage within the impossible split; sampled for the control.
        for oname, fld, S, sname in (("first_A_complete", "A_here", imp, "impossible"), ("first_B_complete", "B_here", imp, "impossible"),
                                     ("first_A_sampled", "A_samp", imp, "impossible"), ("first_A_sampled", "A_samp", pos, "possible"),
                                     ("first_B_sampled", "B_samp", imp, "impossible"), ("first_B_sampled", "B_samp", pos, "possible")):
            fn = (lambda f: (lambda t: t[f] > 0))(fld)
            q = R.setdefault("Q2", {}).setdefault(oname, {})[sname] = dict(
                episodes=len(S), by_rej=hazard_by_rej(S, fn), mh_turn=matched(S, fn, "turn"), mh_chars=matched(S, fn, "chars"))
            P(f"Q2 {oname:18} {sname:11} eps {len(S):3}  by n_rej {q['by_rej']}  MH turn {fmt_rr(q['mh_turn']['rr'])} "
              f"[{q['mh_turn']['ci'][0] and round(q['mh_turn']['ci'][0],2)}, {q['mh_turn']['ci'][1] and round(q['mh_turn']['ci'][1],2)}] "
              f"strata {q['mh_turn']['informative_strata']} ({q['mh_turn']['exposed_turns']} vs {q['mh_turn']['unexposed_turns']})  "
              f"MH chars {fmt_rr(q['mh_chars']['rr'])} strata {q['mh_chars']['informative_strata']}")
        for fld in ("A_here", "B_here"):
            q = R.setdefault("Q2_rates", {})[fld] = dict(
                before_any_rejection=rate_per_10k(imp, fld, lambda t: t["n_rej"] == 0),
                after_first_rejection=rate_per_10k(imp, fld, lambda t: t["n_rej"] >= 1))
            P(f"Q2 rate {fld} per 10k chars (impossible, complete): before {q['before_any_rejection']} after {q['after_first_rejection']}")
        # Q3: order.
        for oname, fn in (("hack_considered_any", hacked_any), ("hack_attempted_enacted", hacked_acted)):
            q = R.setdefault("Q3", {})[oname] = orders(eps, turns, model, fn)
            P(f"Q3 {oname:24} {q}")
        # Q4: awareness turn vs matched turns without, among rejected impossible episodes.
        for oname, fn in (("hack_considered_any", hacked_any), ("hack_attempted_enacted", hacked_acted)):
            for wname, w in (("t+1..t+2", (1, 2)), ("t+1", (1, 1)), ("t+1..t+5", (1, 5))):
                q = R.setdefault("Q4", {}).setdefault(oname, {})[wname] = awareness_matched(imp_rej, fn, w)
                P(f"Q4 {oname:24} {wname:9} MH {fmt_rr(q['rr'])} [{q['ci'][0] and round(q['ci'][0],2)}, {q['ci'][1] and round(q['ci'][1],2)}] "
                  f"strata {q['informative_strata']} A-turns {q['exposed_turns']} (events {q['exposed_events']}) "
                  f"other turns {q['unexposed_turns']} (events {q['unexposed_events']})")
    (out / "ib.json").write_text(json.dumps(res, indent=1, default=str))
    (out / "ib_report.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------- the other benchmarks: build per-turn tables (counts only) ----------

import re  # noqa: E402

OTHER = {  # bench label in the awareness files -> [(model, traces, labels file, label kind)]
    "SWE-bench Verified": [(m, f"goodfire_swe/swebench-verified-{k}-nohack.traces.jsonl",
                            f"goodfire_swe/swebench-verified-{k}-nohack.judge_rollouts.jsonl", "judge")
                           for m, k in (("Qwen", "qwen3.8-2.4t-a95b-fp8"), ("GLM", "glm-5.2"), ("Kimi", "kimi-k3"))],
    "DeepSWE": [(m, f"goodfire_swe/deepswe-{k}.traces.jsonl", f"goodfire_swe/deepswe-{k}.judge_rollouts.jsonl", "judge")
                for m, k in (("Qwen", "qwen3.8-2.4t-a95b-fp8"), ("GLM", "glm-5.2-fp8"), ("Kimi", "kimi-k3"))],
    "τ3-bench": [(m, f"goodfire_other/tau3bench-{k}.traces.jsonl", f"goodfire_other/tau3bench-{k}.monitor_passages.jsonl", "monitor")
                 for m, k in (("GLM", "glm-5.2-fp8"), ("Kimi", "kimi-k3"))],
    "ShoppingBench": [(m, f"goodfire_other/shoppingbench-{k}-20260828.traces.jsonl",
                       f"goodfire_other/shoppingbench-{k}-20260828.monitor_passages.jsonl", "monitor")
                      for m, k in (("GLM", "glm-5.2"), ("Kimi", "kimi-k3"))],
}

# A bash call that runs tests: some segment of the command (split at &&, ||, ;, | and newlines) starts with a test
# runner, after env assignments and wrappers (timeout N, npx, poetry/uv/pipenv run, bundle exec). Mentions elsewhere
# ("pip list | grep pytest", a path with "vitest" in it) don't count. Checked by hand on 40 random command/output
# pairs (notes: "own failing test run").
SEG = re.compile(r"&&|\|\||;|\||\n")
PREFIX = re.compile(r"^(?:\w+=\S*\s+)*(?:(?:timeout\s+\S+|sudo|npx|poetry\s+run|uv\s+run|pipenv\s+run|bundle\s+exec|"
                    r"env(?:\s+\w+=\S*)*)\s+)*")
RUNNER = re.compile(r"(?:python\d?(?:\.\d+)?|\S*/python\d?(?:\.\d+)?)\s+(?:-\S+\s+)*-m\s+(?:pytest|unittest)\b|"
                    r"(?:\S*/)?(?:pytest|py\.test)\b|tox\b|nox\b|go\s+test\b|cargo\s+test\b|"
                    r"(?:npm|yarn|pnpm)\s+(?:run\s+)?test\S*|(?:\S*/)?(?:jest|mocha|vitest)\b|mvn\b.*\btest\b|"
                    r"(?:\./)?gradlew?\s+(?:\S+\s+)*test\b|rspec\b|rake\s+test\b|(?:\S*/)?phpunit\b|dotnet\s+test\b|"
                    r"ctest\b|make\s+(?:test|check)\b|(?:python\d?(?:\.\d+)?\s+)?\S*runtests\.py\b|"
                    r"(?:python\d?(?:\.\d+)?\s+)?(?:\./)?bin/test\b|(?:bash\s+|sh\s+)?\S*test\.sh\b", re.I)


def is_test_cmd(cmd):
    for seg in SEG.split(cmd or ""):
        seg = seg.strip().lstrip("(").strip()
        if seg.startswith("cd "):
            continue
        if RUNNER.match(PREFIX.sub("", seg)):
            return True
    return False


# The runner reports a failure: a non-zero count of failures/errors/exceptions, or its failure markers. (A zero
# return code doesn't clear it: "| tail" hides the runner's code.)
FAIL_OUT = re.compile(r"\b[1-9]\d* (?:failed|failures?|errors?|exceptions?)\b|^FAILED\b|\bFAILED\b|=+ FAILURES =+|"
                      r"^--- FAIL\b|^FAIL\b|\[FAIL\]|AssertionError|Traceback \(most recent call last\)|"
                      r"\bTests?: +[1-9]\d* failed|\bnot ok \d+|BUILD FAILURE|\berror\[E\d+\]|panicked at|"
                      r"ERR_MODULE_NOT_FOUND|Cannot find module|Error Trace:", re.M)
RC = re.compile(r"<returncode>(-?\d+)</returncode>|\"returncode\":\s*(-?\d+)")


def _content(m):
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in c)
    return ""


def _cmd(tc):
    a = tc.get("arguments") or (tc.get("function") or {}).get("arguments") or ""
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except ValueError:
            return a
    if isinstance(a, dict):
        return str(a.get("command") or a.get("cmd") or "")
    return ""


def test_run_failed(cmd, out):
    """(is a test run, failed). DeepSWE wraps output as JSON {"returncode", "output"}: decode it first, so that
    line-start markers see real newlines."""
    if not is_test_cmd(cmd):
        return False, False
    out = out or ""
    m = RC.search(out)
    rc = int(next(g for g in m.groups() if g is not None)) if m else None
    if out.lstrip().startswith("{"):
        try:
            out = str(json.loads(out).get("output", out))
        except (ValueError, AttributeError):
            pass
    return True, (rc not in (None, 0)) or bool(FAIL_OUT.search(out))


def walk_other(t):
    turns, st = [], dict(n_test=0, n_own_fail=0, chars_before=0)
    pending = {}  # tool_call_id -> command
    for i, n in enumerate(t["nodes"]):
        m = n["message"]
        if m["role"] == "assistant" and n.get("sampled", True):
            text = norm((m.get("reasoning_content") or "") + " " + _content(m))
            turns.append(dict(node=i, turn=len(turns), text=text, n_test=st["n_test"], n_own_fail=st["n_own_fail"],
                              chars_before=st["chars_before"], chars=len(text)))
            st["chars_before"] += len(text)
            for tc in m.get("tool_calls") or []:
                pending[tc.get("id")] = _cmd(tc)
        elif m["role"] == "tool":
            cmd = pending.get(m.get("tool_call_id"), "")
            is_test, failed = test_run_failed(cmd, _content(m))
            st["n_test"] += is_test
            st["n_own_fail"] += failed
    return turns


def build_other(data_dir, aw, out):
    data_dir, aw, out = Path(data_dir), Path(aw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    lab = {json.loads(l)["id"]: json.loads(l) for l in (aw / "labels_final.jsonl").open()}
    heads = defaultdict(lambda: {"A": [], "B": []})
    for l in (aw / "candidates_all.jsonl").open():
        c = json.loads(l)
        if c["bench"] not in OTHER:
            continue
        g = lab.get(c["id"])
        for x in "AB":
            if g and g[x]:
                heads[(c["bench"], c["model"], int(c["row"]))][x].append(norm(c["text"])[:80])
    for bench, files in OTHER.items():
        tag = {"SWE-bench Verified": "swev", "DeepSWE": "deepswe", "τ3-bench": "tau3", "ShoppingBench": "shopping"}[bench]
        ft = (out / f"turns_{tag}.jsonl").open("w")
        fe = (out / f"episodes_{tag}.jsonl").open("w")
        for model, tf, lf, kind in files:
            flags_by_row = defaultdict(list)
            verdict = {}
            if kind == "judge":
                for l in (data_dir / lf).open():
                    j = json.loads(l)
                    verdict[j["row_index"]] = (j.get("verdict"), j.get("verdict_enacted"))
                    for f in j.get("flags") or []:
                        if f.get("node_index") is not None:
                            flags_by_row[j["row_index"]].append((f["node_index"], f.get("status")))
            else:
                for l in (data_dir / lf).open():
                    p = json.loads(l)
                    if p.get("evidence") == "certain" and p.get("node_index") is not None:
                        flags_by_row[p["row_index"]].append((p["node_index"], p.get("status")))
            for row, line in enumerate((data_dir / tf).open()):
                t = json.loads(line)["traces"][0]
                turns = walk_other(t)
                hd = heads.get((bench, model, row), {"A": [], "B": []})
                placed = {x: defaultdict(int) for x in "AB"}
                for x in "AB":
                    for h in hd[x]:
                        k = next((tr["turn"] for tr in turns if h and h in tr["text"]), None)
                        if k is not None:
                            placed[x][k] += 1
                fl = flags_by_row.get(row, [])
                for k, tr in enumerate(turns):
                    lo, hi = tr["node"], (turns[k + 1]["node"] if k + 1 < len(turns) else 10**9)
                    here = [s for nd, s in fl if lo <= nd < hi]
                    ft.write(json.dumps(dict(bench=tag, model=model, row=row, turn=k, node=tr["node"],
                                             n_test=tr["n_test"], n_own_fail=tr["n_own_fail"],
                                             chars_before=tr["chars_before"], chars=tr["chars"],
                                             A_here=placed["A"].get(k, 0), B_here=placed["B"].get(k, 0),
                                             considered_here=sum(1 for s in here if s == "considered"),
                                             acted_here=sum(1 for s in here if s in ("attempted", "enacted")))) + "\n")
                v = verdict.get(row, (None, None))
                fe.write(json.dumps(dict(bench=tag, model=model, row=row, n_turns=len(turns), verdict_any=v[0],
                                         verdict_enacted=v[1], n_flags=len(fl), n_A=len(hd["A"]), n_B=len(hd["B"]),
                                         n_A_placed=sum(placed["A"].values()), n_B_placed=sum(placed["B"].values()),
                                         metrics=t.get("metrics"))) + "\n")
            print(bench, model, "done", flush=True)
        ft.close()
        fe.close()


# ---------- the other benchmarks: measures ----------

def hazard_by(eps_turns, event, field):
    c = defaultdict(lambda: [0, 0])
    for ts in eps_turns:
        for t, e in at_risk(ts, event):
            g = min(t[field], 3)
            c[g][1] += 1
            c[g][0] += e
    return {str(k): c[k] for k in sorted(c)}


def matched_by(eps_turns, event, by, field, reps=500):
    exposed = lambda t: t[field] >= 1
    return matched(eps_turns, event, by, exposed=exposed, reps=reps)


def other(out):
    out = Path(out)
    res, lines = {}, []
    P = lines.append
    for tag in ("swev", "deepswe", "tau3", "shopping"):
        eps = [json.loads(l) for l in (out / f"episodes_{tag}.jsonl").open()]
        turns = defaultdict(list)
        for l in (out / f"turns_{tag}.jsonl").open():
            t = json.loads(l)
            turns[(t["model"], t["row"])].append(t)
        for k in turns:
            turns[k].sort(key=lambda t: t["turn"])
        for model in MODELS:
            E = [e for e in eps if e["model"] == model]
            if not E:
                continue
            R = res.setdefault(tag, {}).setdefault(model, {})
            S = [turns[(model, e["row"])] for e in E if turns.get((model, e["row"]))]
            nt = sum(len(ts) for ts in S)
            R["episodes"] = dict(
                n=len(E), turns=nt,
                verdict_any_yes=sum(1 for e in E if e["verdict_any"] == "yes"),
                verdict_enacted_yes=sum(1 for e in E if e["verdict_enacted"] == "yes"),
                with_flag=sum(1 for ts in S if any(hacked_any(t) for t in ts)),
                with_attempted_enacted_flag=sum(1 for ts in S if any(hacked_acted(t) for t in ts)),
                with_test_run=sum(1 for ts in S if ts[-1]["n_test"] > 0 or any(t["n_test"] for t in ts)),
                with_own_fail=sum(1 for ts in S if ts[-1]["n_own_fail"] >= 1),
                with_A=sum(1 for ts in S if any(t["A_here"] for t in ts)),
                with_B=sum(1 for ts in S if any(t["B_here"] for t in ts)),
                A_placed=f"{sum(e['n_A_placed'] for e in E)}/{sum(e['n_A'] for e in E)}",
                B_placed=f"{sum(e['n_B_placed'] for e in E)}/{sum(e['n_B'] for e in E)}")
            P(f"\n######## {tag} {model}: {R['episodes']}")
            R["rates_per_10k"] = {f: rate_per_10k(S, f, lambda t: True) for f in ("A_here", "B_here")}
            if tag in ("tau3", "shopping"):
                P(f"rates per 10k chars: {R['rates_per_10k']}")
                continue
            # Exposure: the model's own failing test run (no grader rejection exists here).
            S_fail = [ts for ts in S if ts[-1]["n_own_fail"] >= 1]
            for oname, fn in (("hack_considered_any", hacked_any), ("hack_attempted_enacted", hacked_acted)):
                for sname, SS in (("all", S), ("with_own_fail", S_fail)):
                    q = R.setdefault("Q1", {}).setdefault(oname, {})[sname] = dict(
                        episodes=len(SS), by_own_fail=hazard_by(SS, fn, "n_own_fail"),
                        mh_turn=matched_by(SS, fn, "turn", "n_own_fail"), mh_chars=matched_by(SS, fn, "chars", "n_own_fail"))
                    P(f"Q1 {oname:24} {sname:13} eps {len(SS):3} by own fails {q['by_own_fail']}  MH turn {fmt_rr(q['mh_turn']['rr'])} "
                      f"[{q['mh_turn']['ci'][0] and round(q['mh_turn']['ci'][0],2)}, {q['mh_turn']['ci'][1] and round(q['mh_turn']['ci'][1],2)}] "
                      f"strata {q['mh_turn']['informative_strata']} ({q['mh_turn']['exposed_turns']} vs {q['mh_turn']['unexposed_turns']})  "
                      f"MH chars {fmt_rr(q['mh_chars']['rr'])} [{q['mh_chars']['ci'][0] and round(q['mh_chars']['ci'][0],2)}, {q['mh_chars']['ci'][1] and round(q['mh_chars']['ci'][1],2)}] strata {q['mh_chars']['informative_strata']}")
            # Awareness: first B (and A), with and without B passages in a turn that has a hack flag.
            for oname, fn in (("first_B", lambda t: t["B_here"] > 0),
                              ("first_B_outside_flagged_turns", lambda t: t["B_here"] > 0 and not hacked_any(t)),
                              ("first_A", lambda t: t["A_here"] > 0)):
                q = R.setdefault("Q2", {})[oname] = dict(
                    episodes=len(S), by_own_fail=hazard_by(S, fn, "n_own_fail"),
                    mh_turn=matched_by(S, fn, "turn", "n_own_fail"), mh_chars=matched_by(S, fn, "chars", "n_own_fail"))
                P(f"Q2 {oname:30} by own fails {q['by_own_fail']}  MH turn {fmt_rr(q['mh_turn']['rr'])} "
                  f"[{q['mh_turn']['ci'][0] and round(q['mh_turn']['ci'][0],2)}, {q['mh_turn']['ci'][1] and round(q['mh_turn']['ci'][1],2)}] "
                  f"strata {q['mh_turn']['informative_strata']}  MH chars {fmt_rr(q['mh_chars']['rr'])} strata {q['mh_chars']['informative_strata']}")
            for fld in ("A_here", "B_here"):
                R.setdefault("Q2_rates", {})[fld] = dict(
                    before_first_own_fail=rate_per_10k(S, fld, lambda t: t["n_own_fail"] == 0),
                    after_first_own_fail=rate_per_10k(S, fld, lambda t: t["n_own_fail"] >= 1))
                P(f"Q2 rate {fld} per 10k: {R['Q2_rates'][fld]}")
            # Q3: order of the first own failing run (F), first B and first hack.
            for oname, fn in (("hack_considered_any", hacked_any), ("hack_attempted_enacted", hacked_acted)):
                cnt = defaultdict(int)
                n3 = 0
                for ts in S:
                    f = first_turn(ts, lambda t: t["n_own_fail"] >= 1)
                    b = first_turn(ts, lambda t: t["B_here"] > 0)
                    h = first_turn(ts, fn)
                    if f is None or b is None or h is None:
                        continue
                    n3 += 1
                    ev = sorted([("F", f - 0.5), ("B", b), ("H", h)], key=lambda x: x[1])
                    lab = "->".join(x[0] for x in ev) + (" (B and H same turn)" if b == h else "")
                    cnt[lab] += 1
                R.setdefault("Q3", {})[oname] = dict(n_all=len(S), n_with_all_three=n3, orders=dict(sorted(cnt.items(), key=lambda x: -x[1])))
                P(f"Q3 {oname}: {R['Q3'][oname]}")
            # Q4: a turn with a B passage vs matched turns without (turn, own fails), after the first own fail.
            for oname, fn in (("hack_considered_any", hacked_any), ("hack_attempted_enacted", hacked_acted)):
                ex = [[dict(t, n_rej=t["n_own_fail"], A_here=t["B_here"]) for t in ts] for ts in S_fail]
                q = R.setdefault("Q4_B", {})[oname] = awareness_matched(ex, fn, (1, 2), reps=500)
                P(f"Q4 B-turn {oname:24} t+1..t+2 MH {fmt_rr(q['rr'])} [{q['ci'][0] and round(q['ci'][0],2)}, {q['ci'][1] and round(q['ci'][1],2)}] "
                  f"strata {q['informative_strata']} B-turns {q['exposed_turns']} (events {q['exposed_events']}) other {q['unexposed_turns']} (events {q['unexposed_events']})")
    (out / "other.json").write_text(json.dumps(res, indent=1, default=str))
    (out / "other_report.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------- measure 5(a): awareness passages against Goodfire's own hack flags (counts only) ----------

def _overlap(a, b, k=30):
    """A shared run of >= k characters between two normalised strings (lower-cased)."""
    a, b = norm(a).lower(), norm(b).lower()
    if len(a) < k or len(b) < k:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return any(short[i:i + k] in long_ for i in range(0, len(short) - k + 1, 5))


def flag_overlap(data_dir, bench, model, tf, lf, C):
    """Awareness passages C {(model, row): [text]} against the judge's flags in one trace file: counts only."""
    judge = {json.loads(l)["row_index"]: json.loads(l) for l in (data_dir / lf).open()}
    n = in_flag_turn = overlap_quote = overlap_attempted = 0
    n_flags = flags_with_aw = 0
    for row, line in enumerate((data_dir / tf).open()):
        ps = C.get((model, row), [])
        j = judge.get(row) or {}
        if bench.startswith("ImpossibleBench") and j.get("split") not in IMPOSSIBLE:
            continue
        if not ps and not j.get("flags"):
            continue
        t = json.loads(line)["traces"][0]
        turns = walk_other(t)
        flags = [f for f in (j.get("flags") or []) if f.get("node_index") is not None]
        n_flags += len(flags)
        fl_aw = set()
        for p in ps:
            n += 1
            head = norm(p)[:80]
            k = next((tr["turn"] for tr in turns if head and head in tr["text"]), None)
            if k is None:
                continue
            lo, hi = turns[k]["node"], (turns[k + 1]["node"] if k + 1 < len(turns) else 10**9)
            here = [(i, f) for i, f in enumerate(flags) if lo <= f["node_index"] < hi]
            if here:
                in_flag_turn += 1
                ov = [(i, f) for i, f in here if _overlap(p, f.get("quote") or "")]
                if ov:
                    overlap_quote += 1
                    overlap_attempted += any(f.get("status") in ("attempted", "enacted") for _, f in ov)
                    fl_aw.update(i for i, _ in ov)
        flags_with_aw += len(fl_aw)
    return dict(passages=n, in_flagged_turn=in_flag_turn, overlap_flag_quote=overlap_quote,
                overlap_attempted_or_enacted_flag=overlap_attempted, judge_flags=n_flags,
                flags_overlapping_an_awareness_passage=flags_with_aw)


def q5a(data_dir, aw, out):
    """For each awareness passage (A on ImpossibleBench's impossible split, complete coverage; B on SWE-bench
    Verified and DeepSWE, sampled coverage): does it sit in a turn with a hack flag, and does its text overlap that
    flag's quote? Plus monitor verdicts for tau3 / ShoppingBench. Nothing is printed but counts."""
    data_dir, aw, out = Path(data_dir), Path(aw), Path(out)
    res = {}
    # ImpossibleBench: complete-coverage A (impossible split) from stage 0's file pair.
    lab = {json.loads(l)["id"]: json.loads(l) for l in (aw / "labels_final_fill_checked.jsonl").open()}
    cand = defaultdict(list)
    for l in (aw / "candidates_all_fill.jsonl").open():
        c = json.loads(l)
        g = lab.get(c["id"])
        if c["bench"] == "ImpossibleBench (impossible)" and g and g["A"]:
            cand[(c["model"], int(c["row"]))].append(c["text"])
    jobs = [("ImpossibleBench (impossible)", m, f"goodfire/{k}_traces.jsonl", f"goodfire/{k}_judge_rollouts.jsonl", "A", cand)
            for m, k in TRACE_FILES.items()]
    lab2 = {json.loads(l)["id"]: json.loads(l) for l in (aw / "labels_final.jsonl").open()}
    candB = defaultdict(list)
    for l in (aw / "candidates_all.jsonl").open():
        c = json.loads(l)
        g = lab2.get(c["id"])
        if c["bench"] in ("SWE-bench Verified", "DeepSWE") and g and g["B"]:
            candB[(c["bench"], c["model"], int(c["row"]))].append(c["text"])
    for bench in ("SWE-bench Verified", "DeepSWE"):
        for m, tf, lf, _ in OTHER[bench]:
            jobs.append((bench, m, tf, lf, "B", {(mm, r): v for (b, mm, r), v in candB.items() if b == bench}))
    for bench, model, tf, lf, kind, C in jobs:
        res[f"{bench} | {model} | {kind}"] = flag_overlap(data_dir, bench, model, tf, lf, C)
        print(bench, model, kind, res[f"{bench} | {model} | {kind}"], flush=True)
    # tau3 / ShoppingBench: the monitor's own verdicts (not ground truth).
    for bench in ("τ3-bench", "ShoppingBench"):
        for m, tf, lf, _ in OTHER[bench]:
            rf = lf.replace("monitor_passages", "monitor_rollouts")
            v = defaultdict(int)
            for l in (data_dir / rf).open():
                r = json.loads(l)
                v[r.get("verdict")] += 1
                v["enacted_certain"] += bool(r.get("any_certain_enacted"))
                v["attempted_certain"] += bool(r.get("any_certain_attempted"))
            res[f"{bench} | {m} | monitor"] = dict(v)
            print(bench, m, dict(v), flush=True)
    (out / "q5a.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "q5a":
        q5a(*sys.argv[2:5])
    elif sys.argv[1] == "ib":
        ib(*sys.argv[2:6])
    elif sys.argv[1] == "build_other":
        build_other(*sys.argv[2:5])
    elif sys.argv[1] == "other":
        other(sys.argv[2])
    else:
        sys.exit(__doc__)
