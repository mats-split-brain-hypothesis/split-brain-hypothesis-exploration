"""SWE-bench Verified ablation screen (Part B of notes/ib_preregistration.md). Runs in agent 2's SWE venv
(logs/ib_cues/swe/venv: mini-swe-agent 2.4.5, swebench 4.1.0), used read-only.

  logs/ib_cues/swe/venv/bin/python src/ib_swev_ablation.py build-cells     # notes/ib_prereg/cells_swev.jsonl + check
  logs/ib_cues/swe/venv/bin/python src/ib_swev_ablation.py mock <out_dir>  # scripted, no API calls
  logs/ib_cues/swe/venv/bin/python src/ib_swev_ablation.py run --stage screen --cap 36 --out logs/ib_ablation/swev/screen

Goodfire's settings come from agent 2's config (logs/ib_cues/swe/goodfire_swebench_verified.yaml, built at
mats/agent-2-ib-cues 083400e from Goodfire's eval.json). Per cell, only the instance template changes:
- B: Goodfire's template without its "## Reward hacking" section (agent 2's "nohack" edit);
- LB_GF: Goodfire's template as it is;
- every other cell: B with the cell's cue slot as a paragraph right after "</pr_description>".
The cue-11 message goes in as one user message right after the first executed turn's observations (CueAgent, agent 2's
suggested hook). One driver for every cell, replicating mini-extra swebench's process_instance: Docker environment
from the config, DefaultAgent with the config's agent settings, agent.run(problem_statement), trajectory saved, the
patch graded by the official harness (swebench.harness.run_evaluation). Differences from agent 2's screen: the
per-call timeout is 4 h (agent 2's lesson from DeepSWE; Goodfire's config says 600 s), and the driver is ours.
"""
import copy
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import ib_cells as C  # noqa: E402

CONFIG = ROOT / "logs/ib_cues/swe/goodfire_swebench_verified.yaml"
CELLS_FILE = ROOT / "notes/ib_prereg/cells_swev.jsonl"
SCREEN = ("pydata__xarray-4075", "scikit-learn__scikit-learn-15100")
ORDER_SEED = "20261023|ib_swev|order"
CALL_TIMEOUT = 14400
SLOT_ANCHOR = "</pr_description>\n\n"
VENV_BIN = ROOT / "logs/ib_cues/swe/venv/bin"


def base_config():
    import yaml
    return yaml.safe_load(open(CONFIG))


def templates():
    t = base_config()["agent"]["instance_template"]
    i, j = t.index("## Reward hacking"), t.index("</instructions>")
    b = t[:i].rstrip("\n") + "\n" + t[j:]
    assert "Reward hacking" not in b and t.count(SLOT_ANCHOR) == 1
    return t, b


def cell_template(cell):
    full, b = templates()
    c = {x["cell"]: x for x in C.cells("swev")}[cell]
    if c["kind"] == "linkback":
        return full
    slot = C.slot_text("swev", cell)
    return b.replace(SLOT_ANCHOR, SLOT_ANCHOR + slot + "\n\n", 1) if slot else b


def render_first(template, problem_statement):
    from jinja2 import StrictUndefined, Template
    return Template(template, undefined=StrictUndefined).render(task=problem_statement)


def instances(ids):
    from datasets import load_dataset
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    return {r["instance_id"]: dict(r) for r in ds if r["instance_id"] in ids}


def build_cells(ids=SCREEN):
    rows = instances(ids)
    system = render_first(base_config()["agent"]["system_template"], "")  # rendered as the agent renders it
    with CELLS_FILE.open("w") as f:
        for inst in ids:
            for c in C.cells("swev"):
                tpl = cell_template(c["cell"])
                f.write(json.dumps(dict(bench="swev", instance=inst, cell=c["cell"], family=c["family"],
                                        reference=c["reference"], kind=c["kind"], edit_text=c["text"], system=system,
                                        instance_template=tpl, first=render_first(tpl, rows[inst]["problem_statement"]),
                                        switch=C.SWITCH.get(c["cell"]), split="verified", test_rule=True),
                                   ensure_ascii=False) + "\n")
    print("wrote", CELLS_FILE)


def check():
    rows = [json.loads(l) for l in CELLS_FILE.read_text().splitlines() if l.strip()]
    by = {(r["instance"], r["cell"]): r for r in rows}
    g = C.g_sentence("swev")
    problems = []
    for r in rows:
        if r["kind"] in ("base", "linkback"):
            continue
        ref = by[(r["instance"], r["reference"])]
        diff = [k for k in ("system", "first", "switch") if r[k] != ref[k]]
        if r["kind"] == "slot_set":
            ok = diff == ["first"] and r["first"] == ref["first"].replace(SLOT_ANCHOR, SLOT_ANCHOR + r["edit_text"] + "\n\n", 1)
        elif r["kind"] == "slot_append":
            ok = diff == ["first"] and r["first"] == ref["first"].replace(g, g + " " + r["edit_text"], 1) and ref["first"].count(g) == 1
        elif r["kind"] in ("slot_replace", "g_word"):
            ok = diff == ["first"] and r["first"] == ref["first"].replace(g, r["edit_text"]) and ref["first"].count(g) == 1
        elif r["kind"] == "switch":
            ok = diff == ["switch"]
        else:
            ok = False
        if not ok:
            problems.append((r["instance"], r["cell"], diff))
    lb = by[(SCREEN[0], "LB_GF")]
    if "## Reward hacking" not in lb["first"] or "## Reward hacking" in by[(SCREEN[0], "B")]["first"]:
        problems.append(("LB_GF/B", "reward-hacking section placement"))
    return problems


# ---------- running ----------

def make_agent(model, env, agent_cfg, cue):
    from minisweagent.agents.default import AgentConfig, DefaultAgent

    class CueAgent(DefaultAgent):
        """DefaultAgent plus one user message (the cue-11 text) right after the first executed turn's observations."""
        cue_text, cue_sent = cue, False

        def execute_actions(self, message):
            out = super().execute_actions(message)
            if self.cue_text and not self.cue_sent:
                self.cue_sent = True
                out = out + self.add_messages(self.model.format_message(role="user", content=self.cue_text))
            return out

    return CueAgent(model, env, config_class=AgentConfig, **agent_cfg)


def make_model(cfg, scripted=None):
    if scripted is not None:
        from minisweagent.models.test_models import DeterministicToolcallModel
        return DeterministicToolcallModel(outputs=scripted, observation_template=cfg["model"]["observation_template"])
    from minisweagent.models import get_model
    m = copy.deepcopy(cfg["model"])
    m["model_kwargs"]["timeout"] = CALL_TIMEOUT
    return get_model(config=m)


def billed_messages(messages):
    return sum(float((((m.get("extra") or {}).get("response") or {}).get("usage") or {}).get("cost") or 0)
               for m in messages if m.get("role") == "assistant")


def episode(row, rep, out_dir, inst_row, scripted=None):
    from minisweagent.run.benchmarks.swebench import get_sb_environment
    out_dir = Path(out_dir).resolve()   # the grader runs with cwd=eval/, so every path it gets must be absolute
    sid = f"{row['cell']}|{row['instance']}|r{rep}"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", sid)
    cfg = base_config()
    cfg["agent"]["instance_template"] = row["instance_template"]
    traj_path = out_dir / "trajectories" / f"{safe}.traj.json"
    traj_path.parent.mkdir(parents=True, exist_ok=True)
    env = get_sb_environment(cfg, inst_row)
    agent, exit_status, sub, extra = None, None, "", {}
    try:
        agent = make_agent(make_model(cfg, scripted), env, cfg["agent"], row.get("switch"))
        agent.config.output_path = traj_path   # saved after every step, so the monitor sees live spend
        info = agent.run(inst_row["problem_statement"])
        exit_status, sub = info.get("exit_status"), info.get("submission") or ""
    except Exception as e:
        exit_status, sub, extra = type(e).__name__, "", {"exception_str": str(e)[:500]}
    finally:
        if agent is not None:
            agent.save(traj_path, {"info": {"exit_status": exit_status, "submission": sub, **extra},
                                   "instance_id": row["instance"], "cell": row["cell"], "rep": rep, "sid": sid,
                                   "cue_sent": agent.cue_sent})
        try:
            env.cleanup()
        except Exception:
            pass
    preds = out_dir / "preds" / f"{safe}.json"
    preds.parent.mkdir(parents=True, exist_ok=True)
    preds.write_text(json.dumps({row["instance"]: {"model_name_or_path": safe, "instance_id": row["instance"],
                                                   "model_patch": sub}}))
    resolved, status = grade(out_dir, safe, row["instance"])
    return dict(sid=sid, exit=exit_status, resolved=resolved, grade_status=status, patch_chars=len(sub),
                traj=str(traj_path))


def grade(out_dir, safe, inst):
    """Grade one episode's saved patch (preds/<safe>.json) with the official harness; read its summary file."""
    out_dir = Path(out_dir).resolve()
    preds = out_dir / "preds" / f"{safe}.json"
    work = out_dir / "eval"
    work.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "eval" / f"{safe}.out", "w") as f:
        subprocess.run([str(VENV_BIN / "python"), "-m", "swebench.harness.run_evaluation", "--dataset_name",
                        "princeton-nlp/SWE-bench_Verified", "--predictions_path", str(preds), "--instance_ids",
                        inst, "--max_workers", "1", "--run_id", safe, "--namespace", "swebench"],
                       cwd=work, stdout=f, stderr=subprocess.STDOUT)
    summ = work / f"{safe}.{safe}.json"   # run_evaluation's summary: resolved / unresolved / empty patch / error ids
    grade = json.loads(summ.read_text()) if summ.exists() else {}
    if inst in grade.get("resolved_ids", []):
        resolved, status = True, "resolved"
    elif inst in grade.get("unresolved_ids", []):
        resolved, status = False, "unresolved"
    elif inst in grade.get("empty_patch_ids", []):
        resolved, status = False, "empty_patch"      # an empty patch resolves nothing
    else:
        resolved, status = None, "grading_error" if inst in grade.get("error_ids", []) else "no_summary"
    return resolved, status


def key_remaining(tries=3):
    """The key's limit_remaining; retried, since a connection reset here once killed a worker (24 Oct). None if every
    try fails (the caller then skips the floor check for that episode and logs it)."""
    from dotenv import dotenv_values
    k = dotenv_values(ROOT / ".env")["OPENROUTER_API_KEY"]
    for t in range(tries):
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {k}"})
            return float(json.load(urllib.request.urlopen(req, timeout=30))["data"]["limit_remaining"])
        except Exception:
            time.sleep(5 * (t + 1))
    return None


def _traj_cost(p):
    """Billed cost in one trajectory file; 0 if it can't be read right now (a worker may be writing it)."""
    try:
        return billed_messages(json.loads(p.read_text()).get("messages", []))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return 0.0


def disk_free_gb():
    try:
        out = subprocess.run(["colima", "ssh", "--", "df", "-BG", "/var/lib/docker"], capture_output=True, text=True,
                             timeout=60).stdout.splitlines()[-1].split()
        return float(out[3].rstrip("G"))
    except Exception:
        return None


def image(inst):
    return f"docker.io/swebench/sweb.eval.x86_64.{inst.replace('__', '_1776_')}:latest".lower()


def plan(cells, ids, reps, ref_reps, per_cell=None, seed=ORDER_SEED):
    per_cell = per_cell or {}
    n = lambda c: per_cell.get(c, ref_reps if c in ("B", "G") else reps)
    p = [(c, i, r) for i in ids for c in cells for r in range(1, n(c) + 1)]
    random.Random(seed).shuffle(p)
    return sorted(p, key=lambda x: ids.index(x[1]))  # instance by instance; shuffled within


def run(stage, cap, floor, out_dir, cells="", ids=SCREEN, reps=1, ref_reps=3, workers=4, keep_images=True,
        missing_only=False):
    reg = {(json.loads(l)["instance"], json.loads(l)["cell"]): json.loads(l)
           for l in CELLS_FILE.read_text().splitlines() if l.strip()}
    specs = [c for c in cells.split(",") if c]
    per_cell = {c.split(":")[0]: int(c.split(":")[1]) for c in specs if ":" in c}
    chosen = [c.split(":")[0] for c in specs] or [c["cell"] for c in C.cells("swev")]
    todo = plan(chosen, list(ids), reps, ref_reps, per_cell)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "watchdog.log"
    say = lambda t: (log.open("a").write(f"{time.strftime('%H:%M:%S')} {t}\n"), print(t, flush=True))
    spent = lambda: sum(_traj_cost(p) for p in (out_dir / "trajectories").glob("*.traj.json")) \
        if (out_dir / "trajectories").exists() else 0.0
    results = out_dir / "episodes.jsonl"
    if missing_only:   # a completion run: skip episodes already finished (a line in episodes.jsonl)
        done = {json.loads(l)["sid"] for l in results.read_text().splitlines() if l.strip()} if results.exists() else set()
        todo = [x for x in todo if f"{x[0]}|{x[1]}|r{x[2]}" not in done]
        print(f"missing-only: {len(done)} finished in {out_dir}; {len(todo)} to run")
    rem = key_remaining()
    if rem is None:
        print("not started: the key check failed 3 times")
        return 1
    if rem < floor + cap:
        say(f"not started: key ${rem:.2f} < floor ${floor} + cap ${cap}")
        return 1
    say(f"start stage {stage}: {len(todo)} episodes, pid {os.getpid()}, key ${rem:.2f}, cap ${cap}, floor ${floor}, "
        f"workers {workers}")
    rows = instances(list(ids))
    stop = threading.Event()
    for inst in ids:
        mine = [x for x in todo if x[1] == inst]
        if not mine or stop.is_set():
            continue
        free = disk_free_gb()
        if free is not None and free < 25:
            say(f"stopping before pulling {inst}: {free:.0f} GB free (< 25)")
            return 1
        subprocess.run(["docker", "pull", "--platform", "linux/amd64", image(inst)], capture_output=True)

        def one(x):
            cell, i, rep = x
            sid = f"{cell}|{i}|r{rep}"
            try:
                if stop.is_set():
                    return None
                s, k = spent(), key_remaining()
                if k is None:
                    say(f"{sid}: key check failed 3 times; starting without the floor check (agent 2 watches the key)")
                if s > cap or (k is not None and k < floor):
                    stop.set()
                    say(f"stopping: own spend ${s:.2f} (cap ${cap}), key {'?' if k is None else f'${k:.2f}'} (floor ${floor})")
                    return None
                r = episode(reg[(i, cell)], rep, out_dir, rows[i])
                with results.open("a") as f:
                    f.write(json.dumps(r) + "\n")
                say(f"{r['sid']}: exit {r['exit']}, resolved {r['resolved']}; own spend ${spent():.2f}")
                return r
            except Exception as e:   # one failed episode must not end the run (24 Oct: a worker died before its container)
                say(f"{sid}: FAILED before or during the episode: {type(e).__name__}: {str(e)[:160]}")
                return None

        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(one, mine))
        if not keep_images:  # IB-SWE and SWE-V share the screen images (Amendment 1, B6): removed by hand after both
            subprocess.run(["docker", "rmi", "-f", image(inst)], capture_output=True)
    say(f"done; own spend ${spent():.2f}")
    return 0


def mock(out_dir):
    """Scripted episodes (no API calls) on the first screen instance: B with no change (submits an empty patch), and
    c11_off (a command, then the cue, then submit). Checks the sent first message, the cue's place, and grading."""
    from minisweagent.models.test_models import make_toolcall_output
    reg = {(json.loads(l)["instance"], json.loads(l)["cell"]): json.loads(l)
           for l in CELLS_FILE.read_text().splitlines() if l.strip()}
    inst = SCREEN[0]
    rows = instances([inst])

    def call(i, cmd):
        return make_toolcall_output("scripted step", [{"id": f"call_{i}", "type": "function",
                                                        "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}],
                                    [{"command": cmd, "tool_call_id": f"call_{i}"}])
    submit = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt"
    problems = []
    for cell in ("B", "c11_off", "LB_GF"):
        scripted = [call(0, "cd /testbed && git status --short && touch patch.txt"), call(1, submit)]
        r = episode(reg[(inst, cell)], 1, Path(out_dir), rows[inst], scripted=scripted)
        t = json.loads(Path(r["traj"]).read_text())
        msgs = t["messages"]
        roles = [m.get("role") for m in msgs]
        if msgs[1].get("content") != reg[(inst, cell)]["first"]:
            problems.append((cell, "first message differs from the registered text"))
        if msgs[0].get("content") != reg[(inst, cell)]["system"]:
            problems.append((cell, "system message differs"))
        if cell == "c11_off":
            a0 = roles.index("assistant")
            j = a0 + 1
            while j < len(msgs) and roles[j] == "tool":
                j += 1
            if not (j < len(msgs) and roles[j] == "user" and msgs[j].get("content") == reg[(inst, cell)]["switch"]):
                problems.append((cell, f"cue-11 message not right after the first observations: {roles[:8]}"))
        elif any(m.get("content") == C.SWITCH.get("c11_off") for m in msgs):
            problems.append((cell, "unexpected cue message"))
        if r["resolved"] is not False or r["grade_status"] != "empty_patch":
            problems.append((cell, f"an empty patch should grade as empty_patch / unresolved: {r}"))
        print(cell, r, roles[:8])
    # the reference fix, written by the scripted agent and submitted as the patch, must resolve
    fix = rows[inst]["patch"]
    files = re.findall(r"^diff --git a/(\S+)", fix, re.M)
    scripted = [call(0, f"cd /testbed && cat > /tmp/gold.diff << 'GOLD_EOF'\n{fix}\nGOLD_EOF\ngit apply /tmp/gold.diff && git status --short"),
                call(1, f"cd /testbed && git diff -- {' '.join(files)} > patch.txt && wc -l patch.txt"),
                call(2, submit)]
    r = episode(reg[(inst, "B")], 2, Path(out_dir), rows[inst], scripted=scripted)
    print("B + reference fix", r)
    if r["resolved"] is not True:
        problems.append(("B+fix", f"the reference fix should resolve: {r}"))
    print(f"{len(problems)} problems", problems)
    return 1 if problems else 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build-cells":
        build_cells()
        p = check()
        print(f"{len(p)} problems", p[:10])
    elif cmd == "check":
        p = check()
        print(f"{len(p)} problems", p[:10])
    elif cmd == "regrade":  # re-grade saved patches (no model calls), e.g. after a grading failure; [sid ...] limits it
        out = Path(sys.argv[2]).resolve()
        lines = [json.loads(l) for l in (out / "episodes.jsonl").read_text().splitlines() if l.strip()]
        fixed = []
        only = set(sys.argv[3:])   # optional: re-grade only these sids; the other lines are kept unchanged
        for e in lines:
            if only and e["sid"] not in only:
                fixed.append(e)
                continue
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", e["sid"])
            r, st = grade(out, safe, e["sid"].split("|")[1])
            fixed.append(dict(e, resolved=r, grade_status=st, regraded=True))
            print(e["sid"], r, st)
        (out / "episodes.jsonl").write_text("".join(json.dumps(x) + "\n" for x in fixed))
    elif cmd == "mock":
        sys.exit(mock(sys.argv[2]))
    elif cmd == "run":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd")
        ap.add_argument("--stage", required=True)
        ap.add_argument("--cap", type=float, required=True)
        ap.add_argument("--floor", type=float, default=25.0)
        ap.add_argument("--out", required=True)
        ap.add_argument("--cells", default="")
        ap.add_argument("--workers", type=int, default=4)
        ap.add_argument("--remove-images", action="store_true", help="remove each instance's image when done")
        ap.add_argument("--missing-only", action="store_true", help="completion: skip episodes in episodes.jsonl")
        a = ap.parse_args()
        sys.exit(run(a.stage, a.cap, a.floor, Path(a.out), a.cells, workers=a.workers, keep_images=not a.remove_images,
                     missing_only=a.missing_only))
