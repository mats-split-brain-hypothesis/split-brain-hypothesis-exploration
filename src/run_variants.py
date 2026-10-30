"""Run several ib_variant settings in one process, at most --max-sandboxes episodes at once, with a spend cap.

  python src/run_variants.py --log-dir logs/ib_cues/round1 --cap 10 \
      "L_attempts1:attempts=1" "H_base:instruction=pass,framing=automated" ...
  python src/run_variants.py --log-dir logs/ib_cues/round1 --cap 10 --retry   # finish a stopped run's episodes

Each variant is <label>:<key=value,...> (keys are ib_variant's options; booleans as true/false). The model is Qwen3.8
2.4T on SiliconFlow FP8 at xhigh unless --model/--provider/--effort say otherwise.

Stops (SIGINT, so finished episodes are kept; --retry resumes) when this run's own spend passes --cap dollars, or when
the shared key's limit_remaining falls below $10 (the orchestrator's global stop). Own spend = token counts in this
log dir (finished logs + live buffer) at src/costs.py's prices x 1.3 billing markup (src/run_spend.py).
"""
import argparse
import json
import os
import signal
import sys
import threading
import time
import urllib.request
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from inspect_ai import eval, eval_retry
from inspect_ai.log import read_eval_log
from inspect_ai.model import get_model

sys.path.insert(0, str(Path(__file__).parent))
from ib_variants import ib_variant  # noqa: E402
from run_spend import own_spend  # noqa: E402

ENV = Path(__file__).parents[1] / ".env"
GLOBAL_STOP = 10.0


def key_info():
    k = dotenv_values(ENV)["OPENROUTER_API_KEY"]
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {k}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["data"]


def remaining():
    return float(key_info()["limit_remaining"])


def parse(spec):
    label, _, rest = spec.partition(":")
    kw = {}
    for part in filter(None, rest.split(",")):
        k, v = part.split("=")
        kw[k] = {"true": True, "false": False}.get(v, int(v) if v.isdigit() else v)
    return label, kw


def log_line(log, text):
    with open(log, "a") as f:
        f.write(f"{time.strftime('%H:%M')} {text}\n")


def watchdog(log_dir, cap, log, spent_before):
    while True:
        time.sleep(60)
        try:
            _, billed, n = own_spend(log_dir)
            billed -= spent_before
        except Exception as e:
            log_line(log, f"own-spend check failed: {str(e)[:120]}")
            billed, n = None, None
        try:
            rem = remaining()
        except Exception as e:
            log_line(log, f"key check failed: {str(e)[:120]}")
            rem = None
        log_line(log, f"own spend ~${billed:.2f} billed this run ({n} episodes; cap ${cap}); key remaining "
                      f"{'?' if rem is None else f'${rem:.2f}'}" if billed is not None else
                 f"own spend unknown; key remaining {'?' if rem is None else f'${rem:.2f}'}")
        if (billed is not None and billed > cap) or (rem is not None and rem < GLOBAL_STOP):
            log_line(log, "cap reached, stopping" if billed is not None and billed > cap else
                     f"key below ${GLOBAL_STOP:.0f}: global stop, message the orchestrator")
            os.kill(os.getpid(), signal.SIGINT)
            return


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("variants", nargs="*")
    p.add_argument("--model", default="openrouter/qwen/qwen3.8-2.4t-a95b")
    p.add_argument("--provider", default="siliconflow/fp8")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--samples", default="lcbhard_58,lcbhard_99")
    p.add_argument("--max-sandboxes", type=int, default=3)
    p.add_argument("--cap", type=float, required=True, help="dollars, this run's own billed spend")
    p.add_argument("--log-dir", required=True)
    p.add_argument("--retry", action="store_true", help="re-run the unfinished episodes of this log dir's stopped logs")
    a = p.parse_args()

    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    spent_before = own_spend(a.log_dir)[1]
    log_line(log, f"start{' (retry)' if a.retry else ''}, own spend so far ~${spent_before:.2f}, key remaining "
                  f"${remaining():.2f}, cap ${a.cap} for this run, variants {a.variants}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, log, spent_before), daemon=True).start()

    common = dict(max_sandboxes=a.max_sandboxes, max_samples=a.max_sandboxes, max_connections=a.max_sandboxes,
                  fail_on_error=False, log_dir=a.log_dir, display="plain")
    if a.retry:
        stopped = [str(f) for f in sorted(Path(a.log_dir).glob("*.eval"))
                   if read_eval_log(str(f), header_only=True).status in ("cancelled", "error")]
        log_line(log, f"retrying {len(stopped)} logs")
        eval_retry(stopped, max_tasks=len(stopped), **common)
    else:
        model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
        tasks = []
        for spec in a.variants:
            label, kw = parse(spec)
            tasks.append(ib_variant(effort=a.effort, label=label, **kw))
        eval(tasks, model=model, sample_id=a.samples.split(","), max_tasks=len(tasks), **common)
