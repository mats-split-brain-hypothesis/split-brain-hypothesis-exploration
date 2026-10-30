"""Complete an ib_continue run that its spend guard stopped: list the unfinished samples and print the command.

    python src/ib_continue_complete.py <stopped log dir> <variant spec as launched> <out ids.json> [--dry]

Definitions (the verifier's, pinned before use):
- finished = a sample with a score and no error in any log of the stopped run. That includes continuations that ended
  by submit and those that ended at their message window ("message_cap"), which are outcomes, not unfinished.
- unfinished = a planned id with no such sample (never started, or in flight when the guard stopped the run).
- errored = a sample with an error; listed apart as a retry.
The ids written to <out ids.json> are unfinished + errored, in the planned (interleaved) order. The completion runs the same variant with
`only=<out ids.json>` added, so the settings are identical and only the unfinished samples run, in the same order.
--dry prints the plan and the command without writing anything else.
"""
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ib_continue import ROOT, ib_continue  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402
from run_variants import parse  # noqa: E402

if __name__ == "__main__":
    log_dir, spec, out = sys.argv[1], sys.argv[2], sys.argv[3]
    dry = "--dry" in sys.argv
    label, kw = parse(spec)
    planned = [s.id for s in ib_continue(**kw).dataset]
    logs = sorted(glob.glob(f"{log_dir}/*.eval"))
    done, errored = set(), set()
    for p in logs:
        log = read_eval_log(p)
        print(f"{Path(p).name}: status {log.status}, {len(log.samples or [])} samples in the log")
        errored |= {s.id for s in log.samples or [] if s.error}
        done |= {s.id for s in log.samples or [] if s.scores and not s.error}
    done &= set(planned)  # ids outside this variant's plan don't count
    errored = (errored & set(planned)) - done
    unfinished = [i for i in planned if i not in done and i not in errored]
    print(f"errored (retry): {sorted(errored)}")
    rest = [i for i in planned if i not in done]  # unfinished + errored, planned order
    by_arm = {}
    for i in rest:
        by_arm[i.split("|")[1]] = by_arm.get(i.split("|")[1], 0) + 1
    print(f"planned {len(planned)}, finished {len(done)}, unfinished {len(unfinished)}, errored {len(errored)}; "
          f"to run {len(rest)} by arm {by_arm}")
    print("unfinished:", rest)
    cmd = (f'.venv/bin/python src/run_capped.py --task ib_continue --log-dir {log_dir}_completion --cap 6 '
           f'--key-floor 25 --max-sandboxes 3 "{spec},only={out}"')
    print("command:", cmd)
    if not dry:
        (ROOT / out).write_text(json.dumps(rest, indent=1))
        print("wrote", out)
