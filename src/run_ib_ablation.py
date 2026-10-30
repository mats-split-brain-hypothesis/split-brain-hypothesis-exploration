"""Launch one stage of the IB LiveCodeBench ablation (src/ib_ablation.py) with a spend cap and the key floor.
Pre-registration: notes/ib_preregistration.md.

  .venv/bin/python src/run_ib_ablation.py --stage pilot --cells B,G --tasks lcbhard_37,lcbhard_5 --reps 1 --ref-reps 2 \
      --cap 7 --log-dir logs/ib_ablation/lcb/pilot [--dry]

Stops with SIGINT (finished episodes are kept in the .eval log) when this run's own billed spend passes --cap, or when
the shared key's limit_remaining falls below --floor. Own spend = token counts in --log-dir (finished logs + live
buffer) at src/costs.py's prices x 1.3 (src/run_spend.py), as every earlier IB run. Refuses to start if the key is
already below floor + cap. --dry prints the plan (sample ids in start order) and makes no call.
"""
import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from run_spend import own_spend  # noqa: E402
from run_variants import ENV, log_line, remaining  # noqa: E402


def completed_ids(log_dir, errored=None):
    """Sample ids completed (scored, no error) in the finished .eval files of log_dir. If `errored` is a set, it gets
    the ids present with an error and never completed (their re-run is a retry, reported apart from cut episodes)."""
    from inspect_ai.log import read_eval_log
    done, err = set(), set()
    for f in sorted(Path(log_dir).glob("*.eval")):
        if read_eval_log(str(f), header_only=True).status == "started":
            continue
        for smp in read_eval_log(str(f)).samples or []:
            (done if smp.scores and not smp.error else err).add(str(smp.id))
    if errored is not None:
        errored |= err - done
    return done


def watchdog(log_dir, cap, floor, log, spent_before):
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
        log_line(log, (f"own spend ~${billed:.2f} ({n} episodes; cap ${cap})" if billed is not None else "own spend unknown")
                 + f"; key remaining {'?' if rem is None else f'${rem:.2f}'} (floor ${floor})")
        if (billed is not None and billed > cap) or (rem is not None and rem < floor):
            log_line(log, "cap reached, stopping" if billed is not None and billed > cap else
                     f"key below the ${floor:.0f} floor: stopping; message the orchestrator")
            os.kill(os.getpid(), signal.SIGINT)
            return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True)
    p.add_argument("--bench", default="lcb", choices=["lcb", "ibswe"],
                   help="ibswe runs src/ib_swe_ablation.py; launch it with logs/ib_swe/venv/bin/python")
    p.add_argument("--cells-file", default="notes/ib_prereg/cells_lcb.jsonl")
    p.add_argument("--cells", default="", help="comma-separated; empty = every cell in the file")
    p.add_argument("--tasks", default="lcbhard_37,lcbhard_5")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--ref-reps", type=int, default=3)
    p.add_argument("--seed", default=None, help="order seed; default the registered one")
    p.add_argument("--model", default="openrouter/qwen/qwen3.8-2.4t-a95b")
    p.add_argument("--provider", default="siliconflow/fp8")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--max-sandboxes", type=int, default=3)
    p.add_argument("--cap", type=float, required=True)
    p.add_argument("--floor", type=float, default=25.0)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--dry", action="store_true")
    p.add_argument("--missing-only", action="store_true",
                   help="run only the plan's sample ids that no finished .eval in --log-dir completed (scored, no error); "
                        "for a completion run after a cap stop, which needs the orchestrator's OK")
    a = p.parse_args()

    if a.bench == "ibswe":
        from ib_swe_ablation import CELLS_FILE, ORDER_SEED, ib_swe_ablation
        if a.cells_file == "notes/ib_prereg/cells_lcb.jsonl":
            a.cells_file = CELLS_FILE   # so the watchdog logs the file the task actually uses
        task = ib_swe_ablation(cells_file=a.cells_file,
                               instances=a.tasks, cells=a.cells, reps=a.reps, ref_reps=a.ref_reps, effort=a.effort,
                               seed=a.seed or ORDER_SEED)
    else:
        from ib_ablation import ORDER_SEED, ib_ablation
        task = ib_ablation(cells_file=a.cells_file, tasks=a.tasks, cells=a.cells, reps=a.reps, ref_reps=a.ref_reps,
                           effort=a.effort, seed=a.seed or ORDER_SEED)
    ids = [str(s.id) for s in task.dataset]
    if a.missing_only:
        import json
        from collections import Counter
        errored = set()
        done = completed_ids(a.log_dir, errored)
        ids = [i for i in ids if i not in done]
        retry = [i for i in ids if i in errored]
        cut = [i for i in ids if i not in errored]
        summary = dict(completed=len(done), to_run=len(ids), cut_by_stop=cut, retried_errors=retry,
                       cut_by_cell=dict(Counter(i.split("|")[0] for i in cut)),
                       retried_by_cell=dict(Counter(i.split("|")[0] for i in retry)))
        print(f"missing-only: {len(done)} completed in {a.log_dir}; {len(ids)} to run "
              f"({len(cut)} cut by the stop, {len(retry)} errored, re-run as retries)")
        print(json.dumps({k: summary[k] for k in ("cut_by_cell", "retried_by_cell")}))
        if not a.dry:
            Path(a.log_dir, f"completion_{a.stage}.json").write_text(json.dumps(summary, indent=1))
    if a.dry:
        print(f"stage {a.stage}: {len(ids)} episodes, start order:")
        print("\n".join(ids))
        return 0

    from inspect_ai import eval as inspect_eval
    from inspect_ai.model import get_model
    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    rem = remaining()
    if rem < a.floor + a.cap:
        log_line(log, f"not started: key ${rem:.2f} < floor ${a.floor} + cap ${a.cap}")
        print(f"not started: key ${rem:.2f} < floor ${a.floor} + cap ${a.cap}")
        return 1
    spent_before = own_spend(a.log_dir)[1]
    log_line(log, f"start stage {a.stage}: {len(ids)} episodes, pid {os.getpid()}, key ${rem:.2f}, cap ${a.cap}, "
                  f"floor ${a.floor}, cells file {a.cells_file}, tasks {a.tasks}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, a.floor, log, spent_before), daemon=True).start()
    model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
    inspect_eval(task, model=model, max_sandboxes=a.max_sandboxes, max_samples=a.max_sandboxes,
                 max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir, display="plain",
                 **({"sample_id": ids} if a.missing_only else {}))
    log_line(log, "eval returned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
