"""Run aie (agent-interp-envs port) task variants in one process, time-matched, with agent 2's spend watchdog.

    python src/run_capped.py --task aie_norvane --log-dir logs/aie/norvane_pilot --cap 2 --epochs 5 \
        "R:framing=none" "G:framing=automated"

Each variant is <label>:<key=value,...> (the task's options). Stops with SIGINT (finished episodes kept) when this run's
own billed spend (token prices x 1.3, src/run_spend.py) passes --cap, or when the key's limit_remaining < $10.
"""
import argparse
import importlib
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval
from inspect_ai.model import get_model

sys.path.insert(0, str(Path(__file__).parent))
from run_spend import own_spend  # noqa: E402
from run_variants import ENV, log_line, parse, remaining, watchdog  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("variants", nargs="+")
    p.add_argument("--task", required=True, help="module in src/ whose same-named function is the task")
    p.add_argument("--model", default="openrouter/qwen/qwen3.8-2.4t-a95b")
    p.add_argument("--provider", default="siliconflow/fp8")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--max-sandboxes", type=int, default=4)
    p.add_argument("--cap", type=float, required=True)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--key-floor", type=float, default=None, help="stop when the key's limit_remaining is below")
    a = p.parse_args()
    if a.key_floor is not None:
        import run_variants
        run_variants.GLOBAL_STOP = a.key_floor  # the watchdog reads this module global
    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    spent_before = own_spend(a.log_dir)[1]
    log_line(log, f"start, own spend so far ~${spent_before:.2f}, key remaining ${remaining():.2f}, cap ${a.cap}, "
                  f"task {a.task}, variants {a.variants}, epochs {a.epochs}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, log, spent_before), daemon=True).start()
    factory = getattr(importlib.import_module(a.task), a.task)
    effort = None if a.effort.lower() in ("none", "default", "") else a.effort  # none: pass no reasoning effort
    tasks = [factory(effort=effort, label=label, **kw) for label, kw in map(parse, a.variants)]
    model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
    inspect_eval(tasks, model=model, epochs=a.epochs, max_tasks=len(tasks), max_sandboxes=a.max_sandboxes,
                 max_samples=a.max_sandboxes, max_connections=a.max_sandboxes, fail_on_error=False,
                 log_dir=a.log_dir, display="plain")
