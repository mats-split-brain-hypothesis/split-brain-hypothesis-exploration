"""Run Test A's human-grader cells (src/ib_chat_grader.py; design: notes/ib_chat_grader.md). Paid.

    .venv/bin/python src/run_grader_cells.py --setup glm --ids 'ta|lcbhard_101|r1,rv|lcbhard_101|r1' --cap 8 \
        --max-sandboxes 1 --log-dir logs/ib_chat_grader/glm_s1 [--max-tokens 262144] [--dry]

The commands come from `src/ib_grader_cells.py plan`. This is run_chat_vs_harness.py's paid path unchanged (model
settings from ib_chat_vs_harness.SETUPS, provider pinned with no fallbacks, max_tokens from the setup unless given, the
price check, the key floor + cap refusal and the watchdog: SIGINT when this run's own spend on the guard scale passes
--cap, or the key falls below --floor), with the task swapped for ib_chat_grader. It is a separate file so the runner
behind the 6x3 top-up (verified at fc1141c) is untouched.
"""
import argparse
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from run_ib_ablation import watchdog  # noqa: E402
from run_spend import own_spend  # noqa: E402
from run_variants import ENV, log_line, remaining  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--setup", required=True, help="ib_chat_vs_harness.SETUPS key: qwen, dsn, glm, q27p")
    p.add_argument("--ids", required=True, help="sample ids to run (comma-separated; ta|... and rv|...)")
    p.add_argument("--max-tokens", type=int, default=None, help="default: the setup's (GLM re-draws of cuts: 262144)")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--max-sandboxes", type=int, default=2)
    p.add_argument("--cap", type=float, required=True)
    p.add_argument("--floor", type=float, default=25.0)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--dry", action="store_true")
    a = p.parse_args()

    from inspect_ai import eval as inspect_eval
    from inspect_ai import task_with
    from inspect_ai.model import get_model
    from costs import price as price_of
    from ib_chat_grader import ib_chat_grader
    from ib_chat_vs_harness import SETUPS
    setup = SETUPS[a.setup]
    model_name, provider = setup["model"], setup["provider"]
    max_tokens = a.max_tokens if a.max_tokens is not None else setup["max_tokens"]
    price = price_of(model_name, provider)
    assert price and price[1] > 0, f"no price for {model_name} in src/costs.py: the spend cap would never trip"

    task = ib_chat_grader(effort=a.effort)
    keep_ids = set(a.ids.split(","))
    task = task_with(task, dataset=task.dataset.filter(lambda s: str(s.id) in keep_ids))
    ids = [str(s.id) for s in task.dataset]
    missing_ids = keep_ids - set(ids)
    assert not missing_ids, f"--ids not in the dataset: {sorted(missing_ids)}"
    gen = {"max_tokens": max_tokens} if max_tokens is not None else {}
    if a.dry:
        print(f"model {model_name}, provider {provider}, effort {a.effort}, generate {gen or 'max_tokens not sent'}")
        print(f"{len(ids)} samples, start order:")
        print("\n".join(ids))
        return 0
    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    rem = remaining()
    if rem < a.floor + a.cap:
        log_line(log, f"not started: key ${rem:.2f} < floor ${a.floor} + cap ${a.cap}")
        print(f"not started: key ${rem:.2f} < floor ${a.floor} + cap ${a.cap}")
        return 1
    spent_before = own_spend(a.log_dir)[1]
    log_line(log, f"start grader cells: {len(ids)} samples, pid {os.getpid()}, key ${rem:.2f}, cap ${a.cap}, "
                  f"floor ${a.floor}, sandboxes {a.max_sandboxes}, model {model_name}, provider {provider}, "
                  f"max_tokens {max_tokens}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, a.floor, log, spent_before), daemon=True).start()
    model = get_model(model_name, provider={"order": [provider], "allow_fallbacks": False})
    inspect_eval(task, model=model, max_sandboxes=a.max_sandboxes, max_samples=a.max_sandboxes,
                 max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir, display="plain", **gen)
    log_line(log, "eval returned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
