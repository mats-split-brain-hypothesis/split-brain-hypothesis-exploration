"""Run several conditions of lcb_goodfire in one process, sharing one sandbox limit.

  python src/run.py --model openrouter/qwen/qwen3.8-27b --provider deepinfra/bf16 \
      --conditions stop/none,stop/automated,pass/automated --log-dir logs/27b_stop_vs_pass

A condition is <instruction>/<framing> (see src/lcb_goodfire.py). Tasks default to the 10 conflicting-split tasks
of the effort pilot (random.Random(20261020).sample over lcbhard_0-102).
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval
from inspect_ai.model import get_model

sys.path.insert(0, str(Path(__file__).parent))
from lcb_goodfire import lcb_goodfire  # noqa: E402

TASKS_10 = "lcbhard_99,lcbhard_58,lcbhard_95,lcbhard_83,lcbhard_40,lcbhard_27,lcbhard_61,lcbhard_7,lcbhard_101,lcbhard_63"

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--provider", help="OpenRouter provider tag to pin, e.g. deepinfra/bf16")
    p.add_argument("--conditions", required=True)
    p.add_argument("--split", default="conflicting")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--samples", default=TASKS_10)
    p.add_argument("--max-sandboxes", type=int, default=12)
    p.add_argument("--log-dir", required=True)
    a = p.parse_args()

    load_dotenv(Path(__file__).parents[1] / ".env")
    model_args = {"provider": {"order": [a.provider], "allow_fallbacks": False}} if a.provider else {}
    model = get_model(a.model, **model_args)
    tasks = []
    for cond in a.conditions.split(","):
        instruction, framing = cond.split("/")
        tasks.append(lcb_goodfire(split=a.split, effort=a.effort, instruction=instruction, framing=framing))
    eval(tasks, model=model, sample_id=a.samples.split(","), max_tasks=len(tasks), max_sandboxes=a.max_sandboxes,
         max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir, display="plain")
