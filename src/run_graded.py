"""Agent 7's graded-context experiment: one scenario under the four audience × grading conditions, N epochs each.

  python src/run_graded.py --scenario d1_invoices --log-dir logs/rejection/graded/d1 --cap 18 --epochs 5

Conditions (notes/rejection.md, pre-registration): C1 automated/graded, C2 colleague/ungraded, C3 colleague/graded,
C4 takehome/ungraded. Same watchdog and own-spend cap as src/run_variants.py (fixed estimator), with the global stop
raised to the orchestrator's overnight floor: stop when the key's limit_remaining falls below --floor dollars.
"""
import argparse
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval
from inspect_ai.model import get_model

sys.path.insert(0, str(Path(__file__).parent))
import run_variants  # noqa: E402
from run_spend import own_spend  # noqa: E402
from scenarios import scenario  # noqa: E402

CONDITIONS = [("C1", "automated", True), ("C2", "colleague", False), ("C3", "colleague", True), ("C4", "takehome", False)]
# The real-reading cells (amendment, notes/rejection.md): no system prompt, no scaffolding lines, neutral submit tool.
PLAIN = dict(system="none", scaffold=False, submit_desc="neutral")
CELLS = {"c1c4": [dict(audience=aud, graded=gr) for _, aud, gr in CONDITIONS],
         "c5c6": [dict(audience="colleague", graded=False, grading_sentence=False, **PLAIN),   # C5
                  dict(audience="colleague", graded=True, grading_sentence=True, **PLAIN)]}    # C6
# Follow-ups (notes/rejection.md, pre-registration 2026-10-22): C9 a person runs the tests on each submission;
# C10 the automatic failure message alone.
C9 = dict(audience="colleague", graded=False, grading_sentence=True, submit_sentence="person", **PLAIN)
C10 = dict(audience="colleague", graded=True, grading_sentence=False, **PLAIN)
CELLS.update({"c9c10": [C9, C10], "c10": [C10], "c9": [C9]})
# C11: agent 5's graded-but-real pick; validation run against C5 (3 + 3, phase 3 support).
C11 = dict(audience="colleague", graded=False, grading_sentence=True, submit_sentence="person_done", **PLAIN)
CELLS.update({"c11_valid": [CELLS["c5c6"][0], C11]})
# Phase 3 G3 (notes/phase3_agent7.md): C6 with grading switched off right after the first failure vs "stays on".
C6 = CELLS["c5c6"][1]
CELLS.update({"g3": [dict(C6, switch="off"), dict(C6, switch="stay_on")]})
# C12 (approved 2026-10-22): agent 5's R3b (a recorded check that reads as real) vs C6 vs C5, interleaved.
R3B = dict(audience="colleague", graded=False, grading_sentence=True, submit_sentence="person_ticket", feedback="ticket",
           **PLAIN)
CELLS.update({"c12": [CELLS["c5c6"][0], C6, R3B]})

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", required=True)
    p.add_argument("--model", default="openrouter/qwen/qwen3.8-2.4t-a95b")
    p.add_argument("--provider", default="siliconflow/fp8")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--message-limit", type=int, default=80)
    p.add_argument("--max-sandboxes", type=int, default=4)
    p.add_argument("--cap", type=float, required=True, help="dollars, this run's own billed spend")
    p.add_argument("--floor", type=float, default=70.0, help="stop when the key's limit_remaining is below this")
    p.add_argument("--log-dir", required=True)
    p.add_argument("--cells", default="c1c4", choices=sorted(CELLS))
    p.add_argument("--retry", action="store_true", help="resume this log dir's cancelled logs (unfinished samples)")
    a = p.parse_args()

    load_dotenv(run_variants.ENV)
    run_variants.GLOBAL_STOP = a.floor
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    spent_before = own_spend(a.log_dir)[1]
    rem = run_variants.remaining()
    run_variants.log_line(log, f"start {a.scenario}, own spend so far ~${spent_before:.2f}, key remaining ${rem:.2f}, "
                               f"cap ${a.cap}, floor ${a.floor}, epochs {a.epochs}, message_limit {a.message_limit}")
    if rem < a.floor:
        run_variants.log_line(log, "key below the floor: not launching")
        sys.exit(1)
    threading.Thread(target=run_variants.watchdog, args=(a.log_dir, a.cap, log, spent_before), daemon=True).start()
    common = dict(max_sandboxes=a.max_sandboxes, max_samples=a.max_sandboxes, max_connections=a.max_sandboxes,
                  fail_on_error=False, log_dir=a.log_dir, display="plain")
    if a.retry:
        from inspect_ai import eval_retry
        from inspect_ai.log import read_eval_log
        stopped = [str(f) for f in sorted(Path(a.log_dir).glob("*.eval"))
                   if read_eval_log(str(f), header_only=True).status in ("cancelled", "error")]
        run_variants.log_line(log, f"retrying {len(stopped)} logs")
        eval_retry(stopped, max_tasks=len(stopped), **common)
    else:
        model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
        tasks = [scenario(scenario=a.scenario, effort=a.effort, message_limit=a.message_limit, **c) for c in CELLS[a.cells]]
        eval(tasks, model=model, epochs=a.epochs, max_tasks=len(tasks), **common)
