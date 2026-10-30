"""SWE-bench Verified feasibility: one instance on Goodfire's mini-swe-agent setup, Qwen 3.8 Max at xhigh.

  python src/swe_feasibility.py config                       # write the config from Goodfire's eval.json
  python src/swe_feasibility.py probe                        # one tiny API call with the same model settings
  python src/swe_feasibility.py run <instance_id> <run dir>  # mini-extra swebench (batch mode, DefaultAgent), 1 worker
  python src/swe_feasibility.py report <run dir>             # calls, tokens, cost, reasoning kept?, time

mini-swe-agent 2.4.5 and swebench live in their own venv (logs/ib_cues/swe/venv) so they can't disturb the pinned
inspect_ai / openai of the ImpossibleBench harness. Goodfire's config: logs/ib_cues/hf_swe_config/…/eval.json (from HF
Goodfire/reward-hack-data). Differences from theirs are listed in DIFFERENCES and in notes/ib_cues.md.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWE = ROOT / "logs/ib_cues/swe"
VENV = SWE / "venv/bin"
EVAL_JSON = ROOT / "logs/ib_cues/hf_swe_config/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack/eval.json"
CONFIG = SWE / "goodfire_swebench_verified.yaml"
MODEL = "openrouter/qwen/qwen3.8-2.4t-a95b"
PROVIDER = "siliconflow/fp8"
DIFFERENCES = [
    "Docker on macOS (amd64 image under Rosetta) instead of Modal; no CPU/memory reservation (theirs 8 CPU / 32 GB)",
    "network off with docker --network none (theirs: Modal network blocked)",
    "OpenRouter (SiliconFlow FP8, no fallbacks) instead of their own server; reasoning effort sent as "
    "reasoning.effort=xhigh (theirs: reasoning_effort=xhigh to SGLang)",
    "cost_limit 0 (off): theirs was 3.0 but their local server reported no cost, so it never applied",
    "image tag :latest from Docker Hub (theirs pinned by digest for each instance)",
]


def env():
    from dotenv import dotenv_values
    e = dict(os.environ)
    e["OPENROUTER_API_KEY"] = dotenv_values(ROOT / ".env")["OPENROUTER_API_KEY"]
    return e


def config():
    import yaml
    gf = json.load(open(EVAL_JSON))["config"]
    stock = yaml.safe_load(open(next((SWE / "venv/lib").glob("python3.*/site-packages/minisweagent/config/benchmarks"
                                                         "/swebench.yaml"))))
    cfg = {
        "agent": {k: gf["agent"][k] for k in ("system_template", "instance_template", "step_limit",
                                              "wall_time_limit_seconds", "max_consecutive_format_errors")},
        "environment": {**stock["environment"], "cwd": gf["environment"]["cwd"], "timeout": gf["environment"]["timeout"],
                        "interpreter": gf["environment"]["interpreter"],
                        "run_args": ["--rm", "--network", "none", "--platform", "linux/amd64"],
                        "pull_timeout": 1800},
        "model": {
            "model_name": MODEL,
            "model_kwargs": {"drop_params": True, "parallel_tool_calls": True, "timeout": 600,
                             "temperature": gf["model"]["model_kwargs"]["temperature"],
                             "top_p": gf["model"]["model_kwargs"]["top_p"],
                             "extra_body": {"top_k": gf["model"]["model_kwargs"]["extra_body"]["top_k"],
                                            "min_p": gf["model"]["model_kwargs"]["extra_body"]["min_p"],
                                            "reasoning": {"effort": gf["model"]["model_kwargs"]["extra_body"]["reasoning_effort"]},
                                            "provider": {"order": [PROVIDER], "allow_fallbacks": False},
                                            "usage": {"include": True}}},
            "cost_tracking": "ignore_errors",
            "observation_template": gf["model"]["observation_template"],
            "format_error_template": gf["model"]["format_error_template"],
        },
    }
    cfg["agent"]["cost_limit"] = 0
    assert set(cfg["environment"]["env"]) == set(gf["environment"]["env_names"]), "env vars differ from Goodfire's"
    CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, width=10000))
    print(f"wrote {CONFIG}")
    print("Differences from Goodfire's run:\n- " + "\n- ".join(DIFFERENCES))


def probe():
    import yaml
    cfg = yaml.safe_load(open(CONFIG))
    code = ("import litellm, json, sys; kw=json.loads(sys.argv[1]); "
            "r=litellm.completion(model=sys.argv[2], messages=[{'role':'user','content':'Reply with the word ok.'}], "
            "max_tokens=2000, **kw); m=r.choices[0].message; "
            "print(json.dumps({'content': m.content, 'has_reasoning': bool(getattr(m,'reasoning_content',None)), "
            "'provider': getattr(r,'provider',None), 'usage': r.usage.model_dump() if r.usage else None}, default=str))")
    kw = {k: v for k, v in cfg["model"]["model_kwargs"].items() if k not in ("parallel_tool_calls",)}
    out = subprocess.run([str(VENV / "python"), "-c", code, json.dumps(kw), MODEL], env=env(), capture_output=True,
                         text=True, timeout=600)
    print(out.stdout[-2000:], out.stderr[-2000:])


def run(instance, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(VENV / "mini-extra"), "swebench", "--subset", "verified", "--split", "test", "--filter", f"^{instance}$",
           "-c", str(CONFIG), "-o", str(out_dir), "-w", "1"]
    t0 = time.time()
    with open(out_dir / "run.out", "w") as f:
        p = subprocess.run(cmd, env=env(), stdout=f, stderr=subprocess.STDOUT)
    (out_dir / "wall_time.json").write_text(json.dumps({"seconds": time.time() - t0, "returncode": p.returncode}))
    print(f"done in {time.time() - t0:.0f}s, return code {p.returncode}")


def evaluate(out_dir, instance):
    """Grade the run's preds.json with the official SWE-bench harness (prebuilt images from the swebench namespace)."""
    out_dir = Path(out_dir).resolve()
    work = out_dir / "eval"
    work.mkdir(exist_ok=True)
    cmd = [str(VENV / "python"), "-m", "swebench.harness.run_evaluation", "--dataset_name", "princeton-nlp/SWE-bench_Verified",
           "--predictions_path", str(out_dir / "preds.json"), "--instance_ids", instance, "--max_workers", "1",
           "--run_id", out_dir.name, "--namespace", "swebench"]  # swebench 4.1.0: the prebuilt swebench/ images
    t0 = time.time()
    with open(work / "eval.out", "w") as f:
        p = subprocess.run(cmd, cwd=work, stdout=f, stderr=subprocess.STDOUT)
    print(f"evaluation done in {time.time() - t0:.0f}s, return code {p.returncode}")
    for rep in work.rglob("report.json"):
        print(rep, json.dumps(json.load(open(rep)))[:1500])
    print((work / "eval.out").read_text()[-1500:])


def report(out_dir):
    out_dir = Path(out_dir)
    trajs = list(out_dir.rglob("*.traj.json"))
    for tp in trajs:
        t = json.load(open(tp))
        msgs = t.get("messages", [])
        asst = [m for m in msgs if m.get("role") == "assistant"]
        usages = [m.get("extra", {}).get("response", {}).get("usage") for m in asst]
        usages = [u for u in usages if u]
        cost = sum(float(u.get("cost") or 0) for u in usages)
        tok_in = sum(u.get("prompt_tokens") or 0 for u in usages)
        tok_out = sum(u.get("completion_tokens") or 0 for u in usages)
        reasoning = sum(1 for m in asst if m.get("reasoning_content") or (m.get("extra", {}).get("response", {})
                                                                         .get("choices", [{}])[0].get("message", {})
                                                                         .get("reasoning_content")))
        info = t.get("info", {})
        print(f"{tp.name}: {len(asst)} agent turns, exit {info.get('exit_status')}, usage records {len(usages)}, "
              f"input {tok_in:,} output {tok_out:,} tokens, OpenRouter cost ${cost:.3f}, turns with reasoning {reasoning}")
        sub = info.get("submission") or ""
        print(f"  submission: {len(sub)} chars; first lines: {sub[:300]!r}")
    wt = out_dir / "wall_time.json"
    if wt.exists():
        print("wall time:", json.loads(wt.read_text()))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "config":
        config()
    elif cmd == "probe":
        probe()
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3])
    elif cmd == "evaluate":
        evaluate(sys.argv[2], sys.argv[3])
    elif cmd == "report":
        report(sys.argv[2])
