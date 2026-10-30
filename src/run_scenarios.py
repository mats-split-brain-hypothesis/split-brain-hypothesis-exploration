"""Run one of our scenarios under several audience/grading arms in one process, with run_variants' spend watchdog.

  python src/run_scenarios.py --scenario e1_ledgerfx --log-dir logs/<topic>/<run> --cap 15 --global-stop 15 \
      --model openrouter/z-ai/glm-5.2 --provider siliconflow/fp8 --effort none --epochs 10 \
      "colleague:audience=colleague,graded=false" "automated:audience=automated,graded=true"

Each arm is <label>:<key=value,...> (src/scenarios.py's scenario() options; booleans as true/false). Stops (SIGINT,
finished episodes kept) when this run's own spend passes --cap or the shared key falls below --global-stop.
"""
import argparse
import threading
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval, task_with
from inspect_ai.model import get_model

from run_variants import ENV, GLOBAL_STOP, log_line, parse, remaining, watchdog
from run_spend import own_spend
from scenarios import scenario

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("arms", nargs="+")
    p.add_argument("--scenario", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--provider", required=True)
    p.add_argument("--effort", default="none")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--max-sandboxes", type=int, default=2)
    p.add_argument("--cap", type=float, required=True, help="dollars, this run's own billed spend")
    p.add_argument("--global-stop", type=float, default=GLOBAL_STOP)
    p.add_argument("--log-dir", required=True)
    a = p.parse_args()

    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    spent_before = own_spend(a.log_dir)[1]
    log_line(log, f"start, own spend so far ~${spent_before:.2f}, key remaining ${remaining():.2f}, cap ${a.cap}, "
                  f"key stop ${a.global_stop}, scenario {a.scenario}, epochs {a.epochs}, arms {a.arms}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, log, spent_before, a.global_stop), daemon=True).start()
    model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
    tasks = []
    for spec in a.arms:
        label, kw = parse(spec)
        t = scenario(scenario=a.scenario, effort=a.effort, **kw)
        tasks.append(task_with(t, name=f"{t.name}_{label}"))
    eval(tasks, model=model, epochs=a.epochs, max_tasks=len(tasks), max_sandboxes=a.max_sandboxes,
         max_samples=a.max_sandboxes, max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir,
         display="plain")
