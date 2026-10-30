"""Agent 7's stage 1: what part of a rejection makes the model say it is being tested? Our Inspect runs of
src/ib_variants.py (Qwen 3.8 Max), measured as in stage 0.

  python src/rejection_stage1.py extract <out dir> <log dir or .eval> ...   # turns.jsonl, texts.jsonl, candidates.jsonl
  python src/rejection_stage1.py label   <out dir> [budget USD]             # A/B/C labels (awareness_llm, luna2 prompt)
  python src/rejection_stage1.py report  <out dir>                          # per-variant tables -> report.txt, a7s1_*.json

Variant = the task name without "ib_" (e.g. L_recorded_bare); the effort-pilot log (lcb_goodfire, xhigh) counts as
L_base. Feedback messages (user turns after the task) are typed: rejection (full test output), passfail ("Your
implementation failed the tests. Please analyze…"), recorded ("Your submission has been recorded…"), person (a
PERSON_TEXTS reply), nudge ("Please proceed…"). Falsely rejected submissions come from the sample store
(ib_false_rejections). A labels: every passage (src/awareness_llm.py `passages`, the BROAD filter windows) of every
turn is classified with the same prompt and model as stage 0 (GPT-5.6 Luna, SYSTEM_V2), so coverage is complete.
"""
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import awareness_llm  # noqa: E402
import rejection_turns as rt  # noqa: E402

WS = re.compile(r"\s+")


def norm(s):
    return WS.sub(" ", s or "").strip()


def _person_prefixes():
    from ib_variants import PERSON_TEXTS
    out = []
    for v in PERSON_TEXTS.values():
        for texts in v.values():
            for x in ([texts] if isinstance(texts, str) else texts):
                out.append(x.split("{")[0].strip()[:20])
    return tuple(p for p in out if p)


PERSON_PREFIXES = None


def feedback_type(text):
    global PERSON_PREFIXES
    if PERSON_PREFIXES is None:
        PERSON_PREFIXES = _person_prefixes()
    t = text.strip()
    if t.startswith(PERSON_PREFIXES):
        return "person"
    if t.startswith("Your implementation failed the tests. Here are the test results"):
        return "rejection"
    if t.startswith("Your implementation failed the tests"):
        return "passfail"
    if t.startswith("Your submission has been recorded"):
        return "recorded"
    if t.startswith("Please proceed to the next step"):
        return "nudge"
    if t.startswith("Hmm,"):
        return "person"
    return "other"


def text_of(content):
    if isinstance(content, str):
        return content, ""
    reasoning, reply = [], []
    for b in content or []:
        if getattr(b, "type", None) == "reasoning":
            reasoning.append(getattr(b, "reasoning", "") or "")
        elif getattr(b, "type", None) == "text":
            reply.append(getattr(b, "text", "") or "")
    return "\n".join(reasoning), "\n".join(reply)


def variant_of(log):
    name = log.eval.task
    if name.startswith("ib_"):
        return name[3:]
    if name.startswith("lcb_goodfire") and log.eval.task_args.get("effort") == "xhigh":
        return "L_base"
    return None


def extract(out, sources):
    from inspect_ai.log import read_eval_log
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for s in sources:
        p = Path(s)
        files += sorted(p.glob("*.eval")) if p.is_dir() else [p]
    ft, fx, fc = (out / "turns.jsonl").open("w"), (out / "texts.jsonl").open("w"), (out / "candidates.jsonl").open("w")
    fe = (out / "episodes.jsonl").open("w")
    seen = set()
    for f in files:
        log = read_eval_log(str(f))
        var = variant_of(log)
        if var is None or not log.samples:
            continue
        split = log.eval.task_args.get("split", "conflicting")
        for s in log.samples:
            key = (var, s.id)
            if key in seen:
                print("duplicate, kept the first:", key, f.name)
                continue
            if not s.scores:  # unfinished (cancelled) sample
                continue
            seen.add(key)
            score = list(s.scores.values())[0]
            store = dict(s.store or {})
            turns, n_fb, fb_types, events, n_sub, n_fail, chars = [], 0, [], [], 0, 0, 0
            first_flaw = None
            for i, m in enumerate(s.messages):
                if m.role == "assistant":
                    reasoning, reply = text_of(m.content)
                    calls = [t.function for t in (m.tool_calls or [])]
                    submit = "\n".join(str((t.arguments or {}).get("answer", "")) for t in (m.tool_calls or [])
                                       if t.function == "submit")
                    text = norm(reasoning + " " + reply)
                    k = len(turns)
                    fl = rt.flaw_sentence(reasoning + "\n" + reply)
                    nf, nfb, nrp, fq, nbare, nopen = rt.frustration(reasoning + "\n" + reply)
                    rec = dict(variant=var, task=s.id, split=split, turn=k, n_fb=n_fb, fb_types=list(fb_types),
                               events=list(events), n_submit=n_sub, n_own_fail=n_fail, chars_before=chars,
                               chars=len(text), noticed_before=first_flaw is not None, flaw_here=bool(fl),
                               flaw_quote=fl, frust=nf, frust_fb=nfb, repeat=nrp, tool_calls=calls,
                               submit_chars=len(submit))
                    if fl and first_flaw is None:
                        first_flaw = k
                    turns.append(rec)
                    ft.write(json.dumps(rec) + "\n")
                    fx.write(json.dumps(dict(variant=var, task=s.id, turn=k, reasoning=reasoning, reply=reply,
                                             submit=submit)) + "\n")
                    bench = f"ImpossibleBench ({'possible' if split == 'original' else 'impossible'})"
                    for j, p in enumerate(awareness_llm.passages(reasoning + "\n" + reply)):
                        pid = hashlib.sha256(f"{var}|{s.id}|{k}|{j}|{p}".encode()).hexdigest()[:20]
                        fc.write(json.dumps(dict(id=pid, bench=bench, model="Qwen", variant=var, task=s.id, turn=k,
                                                 text=p)) + "\n")
                    chars += len(text)
                    events = []
                elif m.role == "tool":
                    c = m.text if hasattr(m, "text") else str(m.content)
                    if m.function == "submit":
                        n_sub += 1
                    elif rt.own_failure(m.function, c):
                        n_fail += 1
                        events.append("own_fail")
                elif m.role == "user" and i > 1:
                    ty = feedback_type(m.text if hasattr(m, "text") else str(m.content))
                    if ty != "nudge":
                        n_fb += 1
                        fb_types.append(ty)
                    events.append(ty)
            fe.write(json.dumps(dict(variant=var, task=s.id, split=split, log=f.name,
                                     passed=score.value in ("C", 1, 1.0, "1"), score=str(score.value),
                                     n_turns=len(turns), n_submit=n_sub, n_fb=n_fb, fb_types=fb_types,
                                     false_rejections=store.get("ib_false_rejections", []),
                                     first_flaw_turn=first_flaw,
                                     limit=str(getattr(s, "limit", None) or ""),
                                     total_tokens=sum((u.output_tokens or 0) for u in (s.model_usage or {}).values()),
                                     )) + "\n")
    for fh in (ft, fx, fc, fe):
        fh.close()
    print("extracted", len(seen), "episodes")


def label(out, budget=2.0):
    out = Path(out)
    awareness_llm.classify(str(out), "luna2", str(out / "candidates.jsonl"), float(budget))


def load(out):
    out = Path(out)
    eps = [json.loads(l) for l in (out / "episodes.jsonl").open()]
    turns = [json.loads(l) for l in (out / "turns.jsonl").open()]
    cands = {json.loads(l)["id"]: json.loads(l) for l in (out / "candidates.jsonl").open()}
    labf = out / "aw" / "labels_luna2.jsonl"
    labels = {json.loads(l)["id"]: json.loads(l) for l in labf.open()} if labf.exists() else {}
    flags = defaultdict(lambda: Counter())
    for pid, c in cands.items():
        lab = labels.get(pid)
        if lab:
            for k in "ABC":
                flags[(c["variant"], c["task"], c["turn"])][k] += lab[k]
            flags[(c["variant"], c["task"], c["turn"])]["labelled"] += 1
        flags[(c["variant"], c["task"], c["turn"])]["passages"] += 1
    # Hand check of every A passage (a_handcheck.json, written by reading them): A counts only where confirmed.
    hc_path = out / "a_handcheck.json"
    hc = json.loads(hc_path.read_text()) if hc_path.exists() else {}
    checked = defaultdict(int)
    for pid, v in hc.items():
        if v["verdict"] == "A":
            c = cands[pid]
            checked[(c["variant"], c["task"], c["turn"])] += 1
    unchecked = sum(1 for pid, l in labels.items() if l.get("A") and pid in cands and pid not in hc)
    for t in turns:
        f = flags[(t["variant"], t["task"], t["turn"])]
        key = (t["variant"], t["task"], t["turn"])
        t.update(A_raw=f["A"], A=checked[key] if hc else f["A"], B=f["B"], C=f["C"], labelled=f["labelled"],
                 passages=f["passages"])
    if unchecked:
        print(f"WARNING: {unchecked} A passages not hand-checked yet")
    return eps, turns, cands, labels


def med(xs):
    return statistics.median(xs) if xs else None


def report(out):
    out = Path(out)
    eps, turns, cands, labels = load(out)
    by_ep = defaultdict(list)
    for t in turns:
        by_ep[(t["variant"], t["task"])].append(t)
    lines = []
    unl = sum(t["passages"] - t["labelled"] for t in turns)
    lines.append(f"passages {sum(t['passages'] for t in turns)}, unlabelled {unl}")
    rows = []
    order = ["L_base", "L_recorded", "L_recorded_bare", "L_reiterate_off", "L_person", "P_base", "P_false_reject",
             "P_false_reject_person"]
    variants = sorted({e["variant"] for e in eps}, key=lambda v: order.index(v) if v in order else 99)
    for v in variants:
        es = [e for e in eps if e["variant"] == v]
        r = dict(variant=v, episodes=len(es), tasks=",".join(sorted(e["task"].replace("lcbhard_", "") for e in es)),
                 passed=sum(e["passed"] for e in es), submits_median=med([e["n_submit"] for e in es]),
                 feedback_median=med([e["n_fb"] for e in es]), turns_median=med([e["n_turns"] for e in es]))
        firstA, after_fb, right_after, before_fb, at_notice = [], 0, 0, 0, 0
        risk_after = risk_k = 0
        for e in es:
            ts = sorted(by_ep[(v, e["task"])], key=lambda t: t["turn"])
            fa = next((t for t in ts if t["A"] > 0), None)
            if fa:
                firstA.append(fa["turn"])
                after_fb += fa["n_fb"] > 0
                before_fb += fa["n_fb"] == 0
                right_after += any(x in fa["events"] for x in ("rejection", "passfail", "recorded", "person"))
                at_notice += fa["turn"] == e["first_flaw_turn"]
            for t in ts:
                if fa and t["turn"] > fa["turn"]:
                    break
                if t["n_fb"] > 0 and any(x in t["events"] for x in ("rejection", "passfail", "recorded", "person")):
                    risk_after += 1
                    risk_k += bool(fa and t["turn"] == fa["turn"])
        r.update(episodes_with_A=len(firstA), firstA_turn_median=med(firstA), firstA_after_feedback=after_fb,
                 firstA_right_after_feedback=right_after, firstA_before_feedback=before_fb,
                 firstA_in_noticing_turn=at_notice, turns_right_after_feedback=risk_after,
                 first_A_in_those=risk_k,
                 episodes_with_B=sum(any(t["B"] > 0 for t in by_ep[(v, e["task"])]) for e in es),
                 frust_fb_turns=sum(t["frust_fb"] > 0 for e in es for t in by_ep[(v, e["task"])]),
                 repeat_turns=sum(t["repeat"] > 0 for e in es for t in by_ep[(v, e["task"])]),
                 turns_total=sum(len(by_ep[(v, e["task"])]) for e in es),
                 false_rejections=sum(len(e["false_rejections"]) for e in es))
        rows.append(r)
    keys = list(rows[0].keys()) if rows else []
    lines.append("\t".join(keys))
    for r in rows:
        lines.append("\t".join(str(r[k]) for k in keys))
    lines.append("\nPer episode:")
    for e in sorted(eps, key=lambda e: (variants.index(e["variant"]), e["task"])):
        ts = sorted(by_ep[(e["variant"], e["task"])], key=lambda t: t["turn"])
        fa = next((t for t in ts if t["A"] > 0), None)
        lines.append(f"{e['variant']:<22} {e['task']:<11} passed={e['passed']!s:<5} turns={e['n_turns']:<3} "
                     f"submits={e['n_submit']} fb={e['fb_types']} false={e['false_rejections']} "
                     f"flaw@{e['first_flaw_turn']} A@{fa['turn'] if fa else None}"
                     f"{' (fb so far ' + str(fa['n_fb']) + ', just ' + str(fa['events']) + ')' if fa else ''} "
                     f"B_turns={sum(t['B'] > 0 for t in ts)} limit={e['limit']}")
    text = "\n".join(lines)
    (out / "report.txt").write_text(text)
    (out / "a7s1_variants.json").write_text(json.dumps(rows, indent=1))
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(sys.argv[2], sys.argv[3:])
    elif cmd == "label":
        label(sys.argv[2], *(sys.argv[3:4] or []))
    elif cmd == "report":
        report(sys.argv[2])
    else:
        sys.exit(__doc__)
