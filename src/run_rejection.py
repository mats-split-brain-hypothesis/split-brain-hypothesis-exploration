"""Agent 7's stage 1 runner: like src/run_variants.py (same model, watchdog, own-spend cap and global stop), but each
variant names its own tasks, so variants with different task lists share one process and one sandbox limit.

  python src/run_rejection.py --log-dir logs/rejection/stage1 --cap 18 --max-sandboxes 3 \
      "L_recorded@lcbhard_58+lcbhard_99:feedback=none" "P_base@lcbhard_7+lcbhard_10:split=original"

Each variant is <label>@<task ids joined by +>:<key=value,...> (keys are ib_variant's options; booleans as
true/false). Without "@ids" a variant runs --samples.
"""
import argparse
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval
from inspect_ai.model import get_model

sys.path.insert(0, str(Path(__file__).parent))
from ib_variants import ib_variant  # noqa: E402
from run_spend import own_spend  # noqa: E402
from run_variants import ENV, log_line, parse, remaining, watchdog  # noqa: E402


def split_spec(spec, default_ids):
    head, _, rest = spec.partition(":")
    label, _, ids = head.partition("@")
    label, kw = parse(f"{label}:{rest}")
    return label, kw, (ids.split("+") if ids else default_ids)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("variants", nargs="+")
    p.add_argument("--model", default="openrouter/qwen/qwen3.8-2.4t-a95b")
    p.add_argument("--provider", default="siliconflow/fp8")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--samples", default="lcbhard_58,lcbhard_99,lcbhard_27,lcbhard_63,lcbhard_101")
    p.add_argument("--max-sandboxes", type=int, default=3)
    p.add_argument("--cap", type=float, required=True, help="dollars, this run's own billed spend")
    p.add_argument("--log-dir", required=True)
    a = p.parse_args()

    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    spent_before = own_spend(a.log_dir)[1]
    log_line(log, f"start, own spend so far ~${spent_before:.2f}, key remaining ${remaining():.2f}, cap ${a.cap} for "
                  f"this run, variants {a.variants}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, log, spent_before), daemon=True).start()

    model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
    tasks = []
    for spec in a.variants:
        label, kw, ids = split_spec(spec, a.samples.split(","))
        t = ib_variant(effort=a.effort, label=label, **kw)
        have = {s.id for s in t.dataset}
        missing = [i for i in ids if i not in have]
        assert not missing, (label, missing)
        t.dataset = t.dataset.filter(lambda s, ids=set(ids): s.id in ids)
        log_line(log, f"{label}: {sorted(s.id for s in t.dataset)} {kw}")
        tasks.append(t)
    eval(tasks, model=model, max_tasks=len(tasks), max_sandboxes=a.max_sandboxes, max_samples=a.max_sandboxes,
         max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir, display="plain")
