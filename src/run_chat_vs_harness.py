"""Run the chat arm (paid) or the harness re-check (free) of src/ib_chat_vs_harness.py.
Pre-registration: notes/ib_chat_vs_harness.md.

  .venv/bin/python src/run_chat_vs_harness.py --cap 4 --log-dir logs/ib_chat_vs_harness/chat --max-sandboxes 2 [--dry]
  .venv/bin/python src/run_chat_vs_harness.py --recheck --log-dir logs/ib_chat_vs_harness/recheck
  .venv/bin/python src/run_chat_vs_harness.py --missing-only --cap 3 --log-dir logs/ib_chat_vs_harness/chat [--dry]

--missing-only (completion run, her pick 26 Oct): runs only the chat ids with no scored, error-free sample in the
finished .eval files already in --log-dir (never run, or errored). Replies that were scored stay as they are, the empty
ones included. The cap counts only this run's spend (own spend in --log-dir minus what was there at start).

Chat: same stop rules as src/run_ib_ablation.py (its watchdog): SIGINT when this run's own billed spend (token counts
at src/costs.py's prices x 1.3, src/run_spend.py) passes --cap, or when the key's limit_remaining falls below --floor.
Refuses to start if the key is below floor + cap. --recheck runs on mockllm (no model calls), 1 sandbox.

--setup (ib_chat_vs_harness.SETUPS; default qwen) sets the model, provider and max_tokens defaults, and which harness
episodes --recheck reads. DeepSeek (notes/ib_chat_vs_harness.md, "DeepSeek"):
  .venv/bin/python src/run_chat_vs_harness.py --setup ds --cap 6 --log-dir logs/ib_chat_vs_harness_ds/chat --max-sandboxes N
  .venv/bin/python src/run_chat_vs_harness.py --setup ds --recheck --log-dir logs/ib_chat_vs_harness_ds/recheck
The chat run refuses a model with no price in src/costs.py (its spend would read $0 and the cap would never trip).

--task homework runs her homework wording (ib_chat_vs_harness.ib_chat_homework), e.g. one reply per task:
  .venv/bin/python src/run_chat_vs_harness.py --task homework --setup glm --reps 1 --cap 1 --log-dir logs/ib_chat_homework/glm
--task rejection runs rounds 2-3 (src/ib_chat_rejection.py) on the failing round-1 replies of a homework log dir:
  .venv/bin/python src/run_chat_vs_harness.py --task rejection --setup glm --source logs/ib_chat_homework/glm --cap 3.5 \
      --log-dir logs/ib_chat_rejection/glm
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


def scored_ids(log_dir):
    """Chat ids with a scored, error-free sample in the finished .eval files in log_dir."""
    from ib_chat_vs_harness_report import samples_in
    return {str(s.id) for s in samples_in(log_dir) if not s.error and s.scores}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--recheck", action="store_true", help="re-check runs 3-4 C episodes (no model calls)")
    p.add_argument("--tasks", default=None, help="default: ib_chat_vs_harness.RUN4_TASKS")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--setup", default="qwen", help="ib_chat_vs_harness.SETUPS key (model defaults, harness logs)")
    p.add_argument("--model", default=None, help="default: the setup's")
    p.add_argument("--provider", default=None, help="default: the setup's")
    p.add_argument("--max-tokens", type=int, default=None, help="default: the setup's (None = not sent)")
    p.add_argument("--effort", default="xhigh")
    p.add_argument("--max-sandboxes", type=int, default=2)
    p.add_argument("--cap", type=float, default=None)
    p.add_argument("--floor", type=float, default=25.0)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--dry", action="store_true")
    p.add_argument("--missing-only", action="store_true", help="run only the chat ids not yet scored in --log-dir")
    p.add_argument("--task", default="chat", choices=["chat", "homework", "rejection"],
                   help="homework: ib_chat_homework, her student wording (27 Oct); rejection: rounds 2-3 on --source")
    p.add_argument("--source", default=None, help="rejection: the finished homework log dir whose failing replies go on "
                                                  "(comma-separated dirs: later dirs' replies replace earlier ones by id)")
    p.add_argument("--resume", default=None, help="rejection: resume the conversations lost to a missing reply at the "
                                                  "lost round, from these rejection dirs (comma-separated, layered; "
                                                  "amendment 9); use with --ids")
    p.add_argument("--ids", default=None, help="run only these sample ids (comma-separated; the 6x3 top-up, "
                                               "src/ib_topup.py plan)")
    p.add_argument("--extraction", default="both", choices=["both", "find_code"],
                   help="rejection: 'both' (amendment 8, runs from then on) or 'find_code' (the runs before it)")
    a = p.parse_args()

    from inspect_ai import eval as inspect_eval
    from inspect_ai import task_with
    from inspect_ai.model import get_model
    from costs import price as price_of
    from ib_chat_vs_harness import RUN4_TASKS, SETUPS, ib_chat, ib_chat_homework, ib_harness_recheck
    setup = SETUPS[a.setup]
    a.model = a.model or setup["model"]
    a.provider = a.provider or setup["provider"]
    a.max_tokens = a.max_tokens if a.max_tokens is not None else setup["max_tokens"]
    if a.recheck:
        task = ib_harness_recheck(setup=a.setup)
        if a.dry:
            print("\n".join(str(s.id) for s in task.dataset))
            return 0
        inspect_eval(task, model=get_model("mockllm/model"), max_sandboxes=1, max_samples=1, log_dir=a.log_dir,
                     display="plain")
        return 0

    assert a.cap is not None, "--cap is required for the chat run"
    price = price_of(a.model, a.provider)
    assert price and price[1] > 0, f"no price for {a.model} in src/costs.py: the spend cap would never trip"
    tasks = a.tasks or RUN4_TASKS
    if a.task == "rejection":
        from ib_chat_rejection import ib_chat_rejection
        assert a.source or a.resume, "--source (the homework log dir) or --resume is required for --task rejection"
        task = ib_chat_rejection(source=a.source, effort=a.effort, extraction=a.extraction, resume=a.resume)
        if a.tasks:   # e.g. a re-draw of one conversation's rounds 2-3 (her "Yes, re-draw at 262k", 27 Oct)
            keep = set(a.tasks.split(","))
            task = task_with(task, dataset=task.dataset.filter(lambda s: str(s.id).split("|")[1] in keep))
    else:
        task = (ib_chat_homework if a.task == "homework" else ib_chat)(tasks=tasks, reps=a.reps, effort=a.effort)
    if a.ids:
        keep_ids = set(a.ids.split(","))
        task = task_with(task, dataset=task.dataset.filter(lambda s: str(s.id) in keep_ids))
        missing_ids = keep_ids - {str(s.id) for s in task.dataset}
        assert not missing_ids, f"--ids not in the dataset: {sorted(missing_ids)}"
    if a.missing_only:
        done = scored_ids(a.log_dir)
        print(f"already scored in {a.log_dir}: {len(done)}")
        task = task_with(task, dataset=task.dataset.filter(lambda s: str(s.id) not in done))
    ids = [str(s.id) for s in task.dataset]
    if not ids:
        print("nothing to run")
        return 0
    gen = {"max_tokens": a.max_tokens} if a.max_tokens is not None else {}
    if a.dry:
        print(f"model {a.model}, provider {a.provider}, effort {a.effort}, generate {gen or 'max_tokens not sent'}")
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
    log_line(log, f"start chat arm: {len(ids)} samples, pid {os.getpid()}, key ${rem:.2f}, cap ${a.cap}, "
                  f"floor ${a.floor}, tasks {tasks}, sandboxes {a.max_sandboxes}, model {a.model}, provider {a.provider}, "
                  f"max_tokens {a.max_tokens}")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, a.floor, log, spent_before), daemon=True).start()
    model = get_model(a.model, provider={"order": [a.provider], "allow_fallbacks": False})
    inspect_eval(task, model=model, max_sandboxes=a.max_sandboxes, max_samples=a.max_sandboxes,
                 max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir, display="plain", **gen)
    log_line(log, "eval returned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
