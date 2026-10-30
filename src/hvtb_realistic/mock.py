"""Free mock of the realistic agent through Harbor (fake model server; no API calls). Scenario: read admin/solution/solve.sh."""
import json, os, subprocess, sys, shutil
from pathlib import Path
HERE = Path("/Users/biancaganescu/Code/split-brain-hypothesis")
sys.path.insert(0, str(HERE / ".claude/worktrees/agent-8-user-facing/src"))
import hvtb_mock as hm
import hvtb_pilot as hp
task = "kv-store-grpc"
ds = HERE / "logs/hvtb_framing/dataset_colleague/hv-terminal-bench-2-1"
out = HERE / "logs/hvtb_framing/mock"; out.mkdir(parents=True, exist_ok=True)
log = out / "requests.jsonl"; log.unlink(missing_ok=True)
shutil.rmtree(out / "jobs" / "mock_realistic", ignore_errors=True)
srv = hm.serve(["cat /app/admin/solution/solve.sh\n"], log)
kw = hp.agent_kwargs(api_base=f"http://127.0.0.1:{srv.server_address[1]}/api/v1", model="deepseek")
cmd = [str(hp.HARBOR), "run", "-p", str(ds), "-i", task, "-a", "hvtb_realistic.realistic_agent:RealisticTerminus2",
       "-m", hp.MODELS["deepseek"]["model"], "-n", "1", "-o", str(out / "jobs"), "--job-name", "mock_realistic", "-y", "-q"] + hp.harbor_env_args()
for k, v in kw.items():
    cmd += ["--ak", f"{k}={json.dumps(v)}"]
env = dict(os.environ, OPENROUTER_API_KEY="mock-key-not-real", PYTHONPATH=str(HERE / "src"), **hp.PLATFORM_ENV)
p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
srv.shutdown()
rw = sorted((out / "jobs" / "mock_realistic").rglob("reward.json"))
print("harbor exit", p.returncode, "| reward.json:", json.loads(rw[-1].read_text()) if rw else None)
reqs = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
print("requests:", len(reqs))
if reqs:
    b = reqs[0]["body"]; first = next(m["content"] for m in b["messages"] if m["role"] == "user")
    print("model/provider/reasoning:", b.get("model"), b.get("provider"), b.get("reasoning"))
    print("first user message starts:", repr(first[:140]))
    print("has 'You are an AI':", "You are an AI" in first, "| has 'Task Description':", "Task Description" in first)
if p.returncode: print(p.stderr[-1500:])
