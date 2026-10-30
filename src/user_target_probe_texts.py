"""Render the exact conversation each screen-A / E4 voice sees up to its first feedback, for agent 5's
eval-awareness probe. No API calls: reply 1 is the cached shared reply, and the feedback is computed from it.

  python src/user_target_probe_texts.py      # writes logs/user_target/probe_texts_E4.jsonl

One row per (voice, task, sample): messages = [user: request + examples, assistant: reply 1, user: first feedback].
No system prompt. Units whose reply 1 already passed all examples (no feedback) are skipped.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import user_target as T  # noqa: E402

VOICES = ("person", "relayed", "harness", "ci", "downstream", "colleague", "manager", "own_ci", "colleague_tests")


def main(samples=(0,)):
    out = T.OUT / "probe_texts_E4.jsonl"
    n = 0
    with out.open("w") as fh:
        for tid in T.A_TASKS:
            for s in samples:
                p = T.RAW / "turn1" / tid / f"{s}.json"
                if not p.exists():
                    continue
                t1 = json.loads(p.read_text())
                res = T.run_examples(tid, t1["reply"])
                fails = [(i + 1, r) for i, r in enumerate(res or []) if r[2] != r[1]] if res else None
                if res is not None and not fails:
                    continue  # ended before any feedback
                if res is None:
                    k = next(i + 1 for i in range(3) if not T._holds(tid, i))
                    c, e = T.A_TASKS[tid]["examples"][k - 1]
                    fails = [(k, (c, e, "no output"))]
                for v in VOICES:
                    msgs = [{"role": "user", "content": t1["user"]}, {"role": "assistant", "content": t1["reply"]},
                            {"role": "user", "content": T.a_feedback(v, 1, fails[0])}]
                    fh.write(json.dumps({"voice": v, "task": tid, "sample": s, "system_prompt": None,
                                         "messages": msgs}) + "\n")
                    n += 1
    # The control arm: its first message only (no contradiction, so normally no feedback).
    with out.open("a") as fh:
        for tid in T.A_TASKS:
            for s in samples:
                fh.write(json.dumps({"voice": "control", "task": tid, "sample": s, "system_prompt": None,
                                     "messages": [{"role": "user", "content": T.a_first(tid, control=True)}]}) + "\n")
                n += 1
    print(f"{n} rows -> {out}")


if __name__ == "__main__":
    main(tuple(int(x) for x in sys.argv[1].split(",")) if len(sys.argv) > 1 else (0,))
