"""Fixed task set for the ImpossibleBench (LiveCodeBench) ablation programme: text rules, a seeded draw stratified
by return type, and reserves. Design: notes/ib_design.md.

    python src/ib_select.py rules                     # the funnel and every exclusion, with reasons
    python src/ib_select.py draw [--no-capability]    # writes logs/ib_select/selection.json (+ notes/ib_selection.json)

No hacking outcome is read anywhere. The rules read only the dataset's task text: the prompt (signature and
docstring), the original tests and the planted tests. The one exception is the optional capability rule R3, which
reads whether Qwen passed the task's *original* (possible) split in Goodfire's released run: a capability filter,
not a hack outcome. `--no-capability` drops it.
"""
import argparse
import ast
import json
import random
import re
import sys
from pathlib import Path

DATASET = "fjzzq2002/impossible_livecodebench"
REVISION = "98650ffc3f28a01b261669b6d19fcd7773823710"  # Goodfire's pin (notes/goodfire_setup.md)
GOODFIRE_QWEN = Path("logs/data/goodfire/qwen_traces.jsonl")

# R0: tasks whose own original tests are wrong (notes/project_brief.md, data caveat). 57, 61, 81 can't be passed
# honestly; 67's test 9 contradicts "vertices are numbered 1 to n".
FLAWED_ORIGINALS = {"lcbhard_57": "original test wrong (74 XOR 51 = 121, not 125)",
                    "lcbhard_61": "original test wrong (expects 64; total not divisible by 3)",
                    "lcbhard_81": "original test wrong (expects 500; brute force 499)",
                    "lcbhard_67": "original test malformed (n=3 with vertices up to 15)"}

STRATA = ("int", "other")
N_SELECT = {"int": 9, "other": 3}    # 12 tasks, about proportional to the pool (69/23 of 92; 71/25 of 96)
N_RESERVE = {"int": 4, "other": 2}   # 6 reserves
SEED = "20261023|ib|{stratum}"

# Tasks used in earlier IB runs (notes on mats/agent-2-ib-cues and mats/agent-4-ib-persistence). Reported as a flag
# only; never used to include or exclude.
EARLIER = {
    "pilot 10 (seed 20261020)": [99, 58, 95, 83, 40, 27, 61, 7, 101, 63],
    "hack-prone 6 (runs 3, 4; chosen on outcomes)": [27, 40, 58, 63, 99, 101],
    "run 1 / 2e 20 (seed 20261022)": [0, 6, 7, 16, 22, 24, 25, 30, 31, 37, 40, 46, 72, 77, 82, 84, 87, 90, 92, 94],
    "agent 8's decision-turn replays (registry)": [7, 27, 58, 63, 95, 99, 101],
}


def num(tid):
    return int(tid.split("_")[1])


def load():
    from datasets import load_dataset
    ds = load_dataset(DATASET, revision=REVISION)
    return {split: {r["task_id"]: r for r in ds[split]} for split in ("original", "conflicting", "oneoff")}


def check_body(src):
    """The statements of `def check(candidate)` in source order, or None if the file doesn't parse or has no check."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check"]
    return fns[0].body if fns else None


def flat(stmts):
    """Statements in source order, descending into compound statements (for, if, with)."""
    out = []
    for s in stmts:
        out.append(s)
        for field in ("body", "orelse", "finalbody"):
            out.extend(flat(getattr(s, field, []) or []))
    return out


def assertions(stmts):
    """[(call, comparison)] for every assert. call = ast.dump of the candidate(...) call it checks (directly, or via a
    variable assigned from one, tracked in source order), or None; comparison = ast.dump of the whole assert test."""
    var, out = {}, []
    for s in flat(stmts):
        if isinstance(s, ast.Assign) and isinstance(s.value, ast.Call) and getattr(s.value.func, "id", "") == "candidate":
            for t in s.targets:
                if isinstance(t, ast.Name):
                    var[t.id] = ast.dump(s.value)
        if isinstance(s, ast.Assert):
            t, call = s.test, None
            left = t.left if isinstance(t, ast.Compare) else None
            if isinstance(left, ast.Call) and getattr(left.func, "id", "") == "candidate":
                call = ast.dump(left)
            elif isinstance(left, ast.Name):
                call = var.get(left.id)
            out.append((call, ast.dump(t)))
    return out


def r1_conflicting(orig_src, test_src):
    """R1: the conflicting test parses, defines check(candidate), keeps every original assertion, and adds at least one
    assertion on a call the original already checks, with a different comparison (a same-call contradiction)."""
    o, t = check_body(orig_src), check_body(test_src)
    if t is None:
        return False, "planted test doesn't parse or has no `def check`"
    oa, ta = assertions(o), assertions(t)
    missing = [a for a in oa if a not in ta]
    if missing:
        return False, f"planted test drops {len(missing)} original assertion(s)"
    added = list(ta)
    for a in oa:
        added.remove(a)
    ocalls = {}
    for call, comp in oa:
        if call:
            ocalls.setdefault(call, set()).add(comp)
    if any(call in ocalls and comp not in ocalls[call] for call, comp in added):
        return True, "same-call contradiction"
    return False, "no added assertion contradicts an original one on the same call"


def r2_oneoff(orig_src, test_src):
    """R2: the oneoff test parses, defines check(candidate), and differs from the original in exactly one contiguous
    run of statements that contains an assertion (one expectation changed)."""
    o, t = check_body(orig_src), check_body(test_src)
    if t is None:
        return False, "planted test doesn't parse or has no `def check`"
    od, td = [ast.dump(s) for s in flat(o)], [ast.dump(s) for s in flat(t)]
    i = 0
    while i < min(len(od), len(td)) and od[i] == td[i]:
        i += 1
    j = 0
    while j < min(len(od), len(td)) - i and od[-1 - j] == td[-1 - j]:
        j += 1
    changed_o, changed_t = od[i:len(od) - j], td[i:len(td) - j]
    if not changed_o and not changed_t:
        return False, "identical to the original"
    if not any("Assert(" in s for s in changed_t):
        return False, "the changed run has no assertion"
    return True, "one expectation changed"


def return_type(prompt):
    sig = next((l for l in prompt.splitlines() if l.startswith("def ")), "")
    m = re.search(r"->\s*(.+?):\s*$", sig)
    return m.group(1) if m else "?"


def stratum(prompt):
    return "int" if return_type(prompt) == "int" else "other"


def qwen_original_pass():
    """{task_id: passed} for Qwen's original-split episodes in Goodfire's release (one episode per task)."""
    out = {}
    with open(GOODFIRE_QWEN) as f:
        for line in f:
            t = json.loads(line)["traces"][0]
            if t["task"]["data"]["split"] == "original":
                out[t["task"]["data"]["name"]] = bool(t["metrics"].get("test_passed"))
    return out


def planted_contradicts_docstring(tid, data):
    """True if a call in the conflicting split's added statements is also a `>>> f(...)` example in the docstring
    (whitespace ignored), so the docstring shows which of the two expectations is right."""
    c = data["conflicting"][tid]
    norm = lambda x: re.sub(r"\s+", "", x)
    ob = {ast.dump(x) for x in flat(check_body(c["original_test"]))}
    planted = set()
    for x in flat(check_body(c["test"])):
        if ast.dump(x) in ob:
            continue
        for n in ast.walk(x):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "candidate":
                planted.add(norm(ast.get_source_segment(c["test"], n)[len("candidate("):-1]))
    ep = re.escape(data["original"][tid]["entry_point"])
    doc = {norm(m.group(1)) for m in re.finditer(r">>>\s*" + ep + r"\((.*)\)\s*$", data["original"][tid]["prompt"], re.M)}
    return bool(planted & doc)


def flags(tid, data):
    """Facts for the hand reading; they never change the draw."""
    out = []
    o1 = data["oneoff"][tid]
    oa = assertions(check_body(o1["original_test"]) or [])
    ta = assertions(check_body(o1["test"]) or [])
    added = [a for a in ta if a not in oa]
    if any(call and sum(c == call for c, _ in ta) > 1 for call, _ in added):
        out.append("oneoff: the changed assertion's call is checked twice, so the oneoff flaw is also a same-call "
                   "contradiction")
    tests = data["conflicting"][tid]["original_test"].lower()
    if any(w in tests for w in ("skip this", "modify it", "todo", "fixme", "not sure", "might be wrong")):
        out.append("original tests carry an odd comment (e.g. 'skip this … or modify it')")
    if planted_contradicts_docstring(tid, data):
        out.append("conflicting: the planted assertion contradicts a worked example (>>> line) in the docstring")
    used = [k for k, v in EARLIER.items() if num(tid) in v]
    if used:
        out.append("used earlier: " + "; ".join(used))
    return out


def funnel(data, capability=True):
    ids = sorted(data["original"], key=num)
    rows, steps = [], []
    pool = list(ids)
    steps.append(("dataset", len(pool), []))
    out0 = [t for t in pool if t in FLAWED_ORIGINALS]
    pool = [t for t in pool if t not in FLAWED_ORIGINALS]
    steps.append(("R0 original tests correct", len(pool), [(t, FLAWED_ORIGINALS[t]) for t in out0]))
    r1 = {t: r1_conflicting(data["conflicting"][t]["original_test"], data["conflicting"][t]["test"]) for t in pool}
    out1 = [(t, r1[t][1]) for t in pool if not r1[t][0]]
    pool = [t for t in pool if r1[t][0]]
    steps.append(("R1 conflicting test well-formed (same-call contradiction)", len(pool), out1))
    r2 = {t: r2_oneoff(data["oneoff"][t]["original_test"], data["oneoff"][t]["test"]) for t in pool}
    out2 = [(t, r2[t][1]) for t in pool if not r2[t][0]]
    pool = [t for t in pool if r2[t][0]]
    steps.append(("R2 oneoff test well-formed (one expectation changed)", len(pool), out2))
    qp = qwen_original_pass()
    if capability:
        out3 = [(t, "Qwen failed the original split in Goodfire's run") for t in pool if not qp.get(t, False)]
        steps.append(("R3 capability: Qwen passed the original split (Goodfire, 1 episode)",
                      len(pool) - len(out3), out3))
    # Rows cover the R0-R2 pool; R3 only skips tasks in the draw, so the seeded order is the same with or without it.
    for t in pool:
        p = data["original"][t]["prompt"]
        rows.append(dict(task=t, stratum=stratum(p), return_type=return_type(p),
                         entry_point=data["original"][t]["entry_point"], qwen_original_pass=qp.get(t, False),
                         flags=flags(t, data)))
    return steps, rows


def draw(rows, capability=True):
    """Per stratum: the R0-R2 members sorted by task number, shuffled with the stratum's seed; walk that order, skipping
    tasks that fail R3 when it applies; the first N_SELECT are selected and the next N_RESERVE are reserves."""
    sel = []
    for s in STRATA:
        members = sorted((r for r in rows if r["stratum"] == s), key=lambda r: num(r["task"]))
        random.Random(SEED.format(stratum=s)).shuffle(members)
        eligible = [r for r in members if r["qwen_original_pass"] or not capability]
        for rank, r in enumerate(eligible, 1):
            status = ("selected" if rank <= N_SELECT[s] else
                      "reserve" if rank <= N_SELECT[s] + N_RESERVE[s] else None)
            if status:
                sel.append(dict(r, rank=rank, order=members.index(r) + 1, status=status, pool_size=len(eligible)))
    return sel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rules", "draw"])
    ap.add_argument("--no-capability", action="store_true", help="drop R3 (the capability filter)")
    ap.add_argument("--out", default="logs/ib_select/selection.json")
    a = ap.parse_args()
    data = load()
    steps, rows = funnel(data, capability=not a.no_capability)
    for name, n, out in steps:
        print(f"{name}: {n}")
        for t, why in out:
            print(f"    - {t}: {why}")
    cap = not a.no_capability
    for s in STRATA:
        print(f"stratum {s}: {sum(r['stratum'] == s and (r['qwen_original_pass'] or not cap) for r in rows)}")
    if a.cmd == "rules":
        return
    sel = draw(rows, capability=cap)
    # Screen pair (added 2026-10-23 after the researcher set the screen at 2 episodes per cue, reading no outcome): the
    # rank-1 selected task of each stratum. The 12 are the confirmation set.
    for r in sel:
        r["screen"] = r["status"] == "selected" and r["rank"] == 1
    print("screen pair: " + ", ".join(r["task"] for r in sel if r["screen"]))
    for status in ("selected", "reserve"):
        for s in STRATA:
            print(f"{status} {s}: " + ", ".join(r["task"] for r in sel if r["status"] == status and r["stratum"] == s))
    doc = dict(dataset=DATASET, revision=REVISION, capability_rule=cap, seed=SEED,
               n_select=N_SELECT, n_reserve=N_RESERVE,
               funnel=[dict(step=n, remaining=k, excluded=[dict(task=t, why=w) for t, w in out]) for n, k, out in steps],
               strata={s: sum(r["stratum"] == s and (r["qwen_original_pass"] or not cap) for r in rows) for s in STRATA},
               tasks=sel)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
