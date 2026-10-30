"""How often would held-back correct tests give a genuine rejection? A free estimate for the 2a harder version
(notes/phase3_agent7.md), from Goodfire's possible-split ("original") runs, where test.py holds the full, correct
assert list.

  python src/heldback_sim.py extract <goodfire dir> <out dir>    # func.py versions from each episode's tool calls
  python src/heldback_sim.py eval <out dir>                       # run every version on every assert, in the sandbox image
  python src/heldback_sim.py sim <out dir>                        # counterfactual yield under each design

extract: replays each episode's writes to func.py (text_editor create / str_replace / insert, bash heredocs) and
records the version at each `python test.py` run and at the first submit, plus what that run printed. Episodes with a
write it can't replay (e.g. a python script that rewrites func.py) are kept but marked.
sim: under a design that shows only some asserts (V), the counterfactual submission is the first tested version that
passes V (or the version at the real first submit); it is a genuine rejection if it fails the full list, leaving out
asserts that no replayed version of any model passes (wrong or unpassable tests). Only the
model's code and the tool outputs are read, never its reasoning.
"""
import ast
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

MODELS = {"qwen": "qwen_traces.jsonl", "glm": "glm-5.2-fp8_traces.jsonl", "kimi": "kimi-k3_traces.jsonl"}


def task_data(t):
    d = t["task"]["data"]
    d = ast.literal_eval(d) if isinstance(d, str) else d
    out = {}
    for k, v in d.items():
        try:
            out[k] = ast.literal_eval(v) if isinstance(v, str) else v
        except Exception:
            out[k] = v
    return out


def test_units(test_code):
    """The test file split for running assert by assert: module-level statements other than check() (the prelude),
    then check()'s top-level statements in order. A statement holding an assert is a test unit; any other (an
    assignment, an import, a helper) is setup that the later asserts may need. Each test unit records whether it sits
    in the '# Example test cases' block (before the '# Additional test cases' comment)."""
    lines = test_code.splitlines()
    tree = ast.parse(test_code)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check")
    prelude = "\n".join(ast.unparse(n) for n in tree.body if n is not fn)
    add_line = next((i + 1 for i, l in enumerate(lines) if "Additional test" in l), None)
    units = []
    for n in fn.body:
        is_test = any(isinstance(x, ast.Assert) for x in ast.walk(n))
        units.append(dict(src=ast.unparse(n), kind="test" if is_test else "setup", line=n.lineno,
                          example=add_line is None or n.lineno < add_line))
    return prelude, units


def canonical_path(nodes):
    """The messages on the path from the root to the last node (the transcript drops duplicate sampled copies)."""
    i = len(nodes) - 1
    path = []
    while i is not None:
        path.append(nodes[i]["message"])
        i = nodes[i].get("parent")
    return path[::-1]


HEREDOC = re.compile(r"cat\s*>\s*['\"]?(?:/workspace/)?func\.py['\"]?\s*<<-?\s*['\"]?(\w+)['\"]?\n(.*?)\n\1\s*(?:\n|$)", re.S)


def replay(msgs, stub):
    content, unknown, events = stub, [], []
    results = {}
    for m in msgs:
        if m["role"] == "tool":
            results[m.get("tool_call_id")] = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
    for m in msgs:
        if m["role"] != "assistant":
            continue
        for tc in m.get("tool_calls") or []:
            try:
                a = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
            except Exception:
                a = {}
            name, out = tc["name"], results.get(tc["id"], "")
            if name == "text_editor" and str(a.get("path", "")).rstrip("/").endswith("func.py"):
                cmd = a.get("command")
                if cmd != "view" and (out.startswith("Error") or out in ("", "null")):
                    if out in ("", "null"):
                        unknown.append("edit without a result")
                    continue  # the edit failed in the run (e.g. create on an existing file), so func.py didn't change
                if cmd == "create":
                    content = a.get("file_text") or ""
                elif cmd == "str_replace" and content is not None:
                    old, new = a.get("old_str") or "", a.get("new_str") or ""
                    if content.count(old) == 1:
                        content = content.replace(old, new, 1)
                    else:
                        unknown.append("str_replace mismatch")
                elif cmd == "insert" and content is not None:
                    ls = content.split("\n")
                    k = int(a.get("insert_line") or 0)
                    content = "\n".join(ls[:k] + (a.get("new_str") or "").split("\n") + ls[k:])
                elif cmd == "undo_edit":
                    unknown.append("undo_edit")
            elif name == "bash":
                cmd = a.get("cmd", "")
                h = HEREDOC.search(cmd)
                if h:
                    content = h.group(2) + "\n"
                elif re.search(r"(>|tee|cp|mv|sed -i)[^|;&\n]*func\.py", cmd):
                    unknown.append("bash write: " + cmd[:80])
                if re.search(r"python3?\s+(?:/workspace/)?test\.py", cmd):
                    events.append(dict(kind="test", code=content, out=out[-1500:], unknown=len(unknown)))
            elif name == "python":
                code = a.get("code", "")
                if re.search(r"open\([^)]*func\.py['\"]\s*,\s*['\"][wa]", code):
                    unknown.append("python write")
                if "test.py" in code and ("exec" in code or "subprocess" in code or "runpy" in code):
                    events.append(dict(kind="test", code=content, out=out[-1500:], unknown=len(unknown)))
            elif name == "submit":
                events.append(dict(kind="submit", code=content, out="", unknown=len(unknown)))
    return events, unknown


def extract(gdir, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    eps, versions, tasks = [], {}, {}
    for model, fname in MODELS.items():
        for line in open(Path(gdir) / fname):
            t = json.loads(line)["traces"][0]
            if ":original:" not in t["task"]["key"]:
                continue
            d = task_data(t)
            events, unknown = replay(canonical_path(t["nodes"]), d["function_prompt"] + "\n    raise NotImplementedError\n")
            first_sub = next((i for i, e in enumerate(events) if e["kind"] == "submit"), None)
            pre = events if first_sub is None else events[:first_sub + 1]
            vids = []
            for e in pre:
                if e["code"] is None:
                    vids.append(None)
                    continue
                vid = "v" + hashlib.sha1((d["name"] + "\0" + e["code"]).encode()).hexdigest()[:12]
                versions[vid] = dict(vid=vid, task=d["name"], entry_point=d["entry_point"], code=e["code"])
                vids.append(vid)
            eps.append(dict(model=model, task=d["name"], passed=float(t["metrics"].get("test_passed", 0)) == 1.0,
                            submitted=first_sub is not None, unknown=unknown,
                            events=[dict(kind=e["kind"], vid=v, out=e["out"], unknown_before=e["unknown"])
                                    for e, v in zip(pre, vids)]))
            if d["name"] not in tasks:
                prelude, units = test_units(d["test_code"])
                tasks[d["name"]] = dict(entry_point=d["entry_point"], prompt=d["function_prompt"], prelude=prelude,
                                        units=units, asserts=[u for u in units if u["kind"] == "test"])
    (outdir / "tasks.json").write_text(json.dumps(tasks))
    (outdir / "episodes.jsonl").write_text("".join(json.dumps(e) + "\n" for e in eps))
    (outdir / "versions.jsonl").write_text("".join(json.dumps(v) + "\n" for v in versions.values()))
    n_unk = sum(1 for e in eps if e["unknown"])
    print(f"{len(eps)} episodes, {len(versions)} distinct versions, {n_unk} episodes with a write not replayed")


IMG = "python:3.10-slim@sha256:98afeb797842e08a6321fb5bb09fcc710ff8bb7a4b6ccd3308ff18d1ae84ca3e"


def evaluate(outdir):
    """Runs every version on every assert in one sandbox container (src/heldback_sim_runner.py); resumable."""
    import subprocess
    import threading
    outdir = Path(outdir)
    tasks = json.loads((outdir / "tasks.json").read_text())
    done_path = outdir / "results.jsonl"
    done = {json.loads(l)["vid"] for l in done_path.open()} if done_path.exists() else set()
    jobs = []
    for l in (outdir / "versions.jsonl").open():
        v = json.loads(l)
        if v["vid"] not in done:
            t = tasks[v["task"]]
            jobs.append(json.dumps(dict(vid=v["vid"], code=v["code"], entry_point=v["entry_point"], prelude=t["prelude"],
                                        units=[[u["kind"], u["src"]] for u in t["units"]])))
    print(f"{len(jobs)} versions to run ({len(done)} already done)", flush=True)
    src = Path(__file__).resolve().parent
    proc = subprocess.Popen(["docker", "run", "--rm", "-i", "--platform", "linux/amd64", "--network", "none",
                             "--cpus", "1", "-m", "2g", "-v", f"{src}:/s:ro", IMG, "python", "/s/heldback_sim_runner.py"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def feed():
        for j in jobs:
            proc.stdin.write(j + "\n")
        proc.stdin.close()

    threading.Thread(target=feed, daemon=True).start()
    with done_path.open("a") as f:
        for k, line in enumerate(proc.stdout, 1):
            f.write(line)
            f.flush()
            if k % 25 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    print("exit", proc.wait())


def sim(outdir, draws=400, seed=0):
    outdir = Path(outdir)
    tasks = json.loads((outdir / "tasks.json").read_text())
    res = {json.loads(l)["vid"]: json.loads(l) for l in (outdir / "results.jsonl").open()}
    eps = [json.loads(l) for l in (outdir / "episodes.jsonl").open()]
    rng = random.Random(seed)

    def fails(vid):
        r = res.get(vid)
        if r is None:
            return None
        return set(r["fail"])

    # Check the replay per episode: every test.py run's printed result must match the replayed code's, and the
    # version at the first submit must match the run's recorded outcome. Only consistent episodes give the estimate.
    agree = disagree = 0
    for e in eps:
        ok = not e["unknown"]
        for ev in e["events"]:
            if ev["vid"] is None or ev["vid"] not in res:
                ok = ok and ev["kind"] != "submit"
                continue
            if ev["kind"] == "test":
                same = ("All tests passed" in ev["out"]) == (not fails(ev["vid"]))
                agree, disagree = agree + same, disagree + (not same)
                ok = ok and same
            elif ev["kind"] == "submit":
                ok = ok and (not fails(ev["vid"])) == e["passed"]
        e["consistent"] = ok
    print(f"replay check: {agree} test runs agree with the replayed code, {disagree} don't; "
          f"consistent episodes {sum(e['consistent'] for e in eps)}/{len(eps)}")

    # Asserts that no replayed version of the task (any model) passes: the possible split's wrong or unpassable
    # tests. A rejection on one of them is a flawed-test rejection, not a genuine one, so they are dropped.
    vtask = {json.loads(l)["vid"]: json.loads(l)["task"] for l in (outdir / "versions.jsonl").open()}
    passed_by_some = defaultdict(set)
    for vid, r in res.items():
        if not r["load_error"]:
            passed_by_some[vtask[vid]] |= {i for i, k in enumerate(r["kinds"]) if k == "pass"}
    wrong = {t: {i for i in range(len(v["asserts"])) if i not in passed_by_some[t]} for t, v in tasks.items()}
    wrong = {t: w for t, w in wrong.items() if w}
    print("asserts no replayed version passes (excluded):", {t: sorted(w) for t, w in wrong.items()})

    def outcome(e, visible):
        """Counterfactual: the first tested version passing the visible asserts is submitted; else the real first
        submission. True = a genuine rejection (it fails a passable assert of the full list)."""
        drop = wrong.get(e["task"], set())
        for ev in e["events"]:
            if ev["vid"] is None:
                continue
            f = fails(ev["vid"])
            if f is None:
                return None
            f = f - drop
            if ev["kind"] == "submit" or not (f & visible):
                return bool(f)
        return None  # never submitted and never passed V in a test run

    def has_hidden(a, vis):
        return len(vis) < len(a)

    designs = {
        "examples only": lambda a: {i for i, x in enumerate(a) if x["example"]},
        "half (random)": None,
        "half, first in file order": lambda a: set(range((len(a) + 1) // 2)),
    }
    rows = defaultdict(list)  # (design, model) -> (task, value, consistent)
    for e in eps:
        a = tasks[e["task"]]["asserts"]
        for dname, fn in designs.items():
            if fn is None:
                vals = []
                for _ in range(draws):
                    vis = set(rng.sample(range(len(a)), (len(a) + 1) // 2))
                    o = outcome(e, vis)
                    if o is not None:
                        vals.append(o)
                v = sum(vals) / len(vals) if vals else None
            else:
                vis = fn(a)
                o = outcome(e, vis) if has_hidden(a, vis) else None  # nothing held back: not part of this design
                v = None if o is None else float(o)
            rows[(dname, e["model"])].append((e["task"], v, e["consistent"]))
    summary = {}
    for (dname, model), rs in rows.items():
        good = [(t, v) for t, v, c in rs if v is not None and c]
        allv = [v for _, v, _ in rs if v is not None]
        summary[f"{dname} | {model}"] = dict(
            n_consistent=len(good), rate_consistent=round(sum(v for _, v in good) / len(good), 3) if good else None,
            n_all=len(allv), rate_all=round(sum(allv) / len(allv), 3) if allv else None,
            tasks_consistent={t: round(v, 2) for t, v in good if v})
        print(f"{dname:26} {model:5} consistent n={len(good):3} rate {summary[f'{dname} | {model}']['rate_consistent']}"
              f"   | all n={len(allv):3} rate {summary[f'{dname} | {model}']['rate_all']}")
    # Out-of-sample task choice: tasks where GLM or Kimi would have been rejected; Qwen's rate there and elsewhere.
    for dname in designs:
        other = {t for m in ("glm", "kimi") for t, v, c in rows[(dname, m)] if v and c}
        q = [(t, v) for t, v, c in rows[(dname, "qwen")] if v is not None and c]
        inside = [v for t, v in q if t in other]
        outside = [v for t, v in q if t not in other]
        summary[f"{dname} | selection"] = dict(tasks=sorted(other, key=lambda x: int(x.split("_")[1])),
                                              qwen_in=[round(sum(inside), 2), len(inside)],
                                              qwen_out=[round(sum(outside), 2), len(outside)])
        print(f"{dname:26} tasks picked by GLM/Kimi: {len(other)}; Qwen there {sum(inside):.1f}/{len(inside)}"
              f" = {sum(inside) / max(len(inside), 1):.2f}; elsewhere {sum(outside):.1f}/{len(outside)}"
              f" = {sum(outside) / max(len(outside), 1):.2f}")
    (outdir / "sim.json").write_text(json.dumps(summary, indent=1))

if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "eval":
        evaluate(sys.argv[2])
    elif sys.argv[1] == "sim":
        sim(sys.argv[2])
    else:
        sys.exit(__doc__)
