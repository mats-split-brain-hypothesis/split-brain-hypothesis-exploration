"""Launch agent 8's run_capped.py (unmodified, imported read-only from its worktree) for the dashboard_perf seeds, with
two additions (agent 6):
- the orchestrator's DeepSeek V4 Pro price fix for the spend watchdog (as src/darkmode_ds_run.py on
  mats-reward-hacking): SiliconFlow FP8 (1.5016, 3.135, 0.135) $/M instead of cached input at the full price;
- a host-load logger: every 30 s, the running Docker containers and their CPU shares go to <log-dir>/hostload.jsonl
  (the bench is wall-clock, so load during the run is part of the record).

    PYTHONPATH=src python src/dashboard_run.py --task aie_dashboard --log-dir logs/stakes/dashboard/seed_qwen \
        --cap 22 --model openrouter/qwen/qwen3.8-2.4t-a95b --provider siliconflow/fp8 --effort xhigh \
        --max-sandboxes 1 "qwen:episode_cap_usd=20"
"""
import json
import runpy
import subprocess
import sys
import threading
import time
from pathlib import Path

A8_SRC = Path(__file__).resolve().parents[2] / "agent-8-user-facing" / "src"  # worktrees sit side by side
assert (A8_SRC / "run_capped.py").exists(), A8_SRC
sys.path.insert(0, str(A8_SRC))
sys.path.insert(1, str(Path(__file__).resolve().parent))
import costs  # noqa: E402  (agent 8's module; run_spend does `from costs import PRICES`, the same dict)

DEEPSEEK = "deepseek/deepseek-v4-pro"
costs.PRICES[DEEPSEEK] = (1.5016, 3.135, 0.135)


def host_logger(path: Path, every: float = 30.0, pid: int | None = None) -> None:
    """Container count and each container's CPU share (docker stats; a busy container matters more than an idle one
    waiting on an API call). The path must be absolute: Inspect changes the working directory to the task's folder
    during a run (a relative path here killed the DeepSeek seed's logger thread). With pid, stops when it exits."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    while pid is None or _alive(pid):
        try:
            r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.CPUPerc}}"],
                               capture_output=True, text=True, timeout=60)
            rows = [l.split("\t") for l in r.stdout.splitlines() if "\t" in l]
            cpu = {n: float(c.rstrip("%") or 0) for n, c in rows}
            with open(path, "a") as f:
                f.write(json.dumps({"time": time.time(), "n": len(cpu), "cpu_total_pct": round(sum(cpu.values()), 1),
                                    "cpu": cpu}) + "\n")
        except Exception as e:  # never let the logger stop the run
            try:
                with open(path, "a") as f:
                    f.write(json.dumps({"time": time.time(), "error": str(e)[:200]}) + "\n")
            except OSError:
                pass
        time.sleep(every)


def _alive(pid: int) -> bool:
    import os
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    if sys.argv[1:2] == ["--hostlog-only"]:  # standalone logger: --hostlog-only <path> <pid>
        host_logger(Path(sys.argv[2]), pid=int(sys.argv[3]))
        raise SystemExit(0)
    import run_spend  # noqa: E402
    assert run_spend.PRICES[DEEPSEEK] == (1.5016, 3.135, 0.135), run_spend.PRICES[DEEPSEEK]
    log_dir = Path(sys.argv[sys.argv.index("--log-dir") + 1]).resolve()
    threading.Thread(target=host_logger, args=(log_dir / "hostload.jsonl",), daemon=True).start()
    sys.argv = [str(A8_SRC / "run_capped.py")] + sys.argv[1:]
    runpy.run_path(str(A8_SRC / "run_capped.py"), run_name="__main__")
