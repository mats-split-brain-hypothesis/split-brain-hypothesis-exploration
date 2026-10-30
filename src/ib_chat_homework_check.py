"""Free check of the homework task (no API calls).
1. For each of the 6 tasks: the user message is HOMEWORK_TEXT, a blank line, then exactly the chat arm's code block
   (the chat message ends with the same block), with her typo fixed.
2. One mockllm sample per scripted reply (Inspect's local sandbox): exactly one user message equal to the input, no
   system message, one reply; both scorers; the homework report reads the log.

    PATH=<dir with python -> python3>:$PATH .venv/bin/python src/ib_chat_homework_check.py <log_dir>
"""
import sys
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, ModelOutput, get_model

sys.path.insert(0, str(Path(__file__).parent))
from ib_chat_vs_harness import HOMEWORK_TEXT, RUN4_TASKS, chat_variant, code_block, ib_chat_homework  # noqa: E402
import ib_chat_vs_harness_report as R  # noqa: E402

M = "mockllm/model"


def main(log_dir):
    ok = True
    chat = {str(s.id): s for s in chat_variant().dataset}
    hw = {str(s.id): s for s in ib_chat_homework(tasks=RUN4_TASKS, reps=1).dataset}
    for t in RUN4_TASKS.split(","):
        h, c = hw[f"hw|{t}|r1"], chat[t]
        block = code_block(c.input)
        good = (h.input == HOMEWORK_TEXT + "\n\n" + block and c.input.endswith(block) and "to to" not in h.input
                and "I still need to pass an automatic grader." in h.input and c.metadata["test"].strip()[:60] in block)
        ok &= good
        print(f"{t}: homework message = text + chat block: {good} | block chars {len(block)}")
    print("--- message for lcbhard_27, first 700 chars ---")
    print(hw["hw|lcbhard_27|r1"].input[:700])
    print("---")
    replies = [ModelOutput.from_content(M, "Here you go:\n```python\nimport sys\nsys.exit(0)\n```"),
               ModelOutput.from_content(M, "The tests contradict each other, so I can't make all of them pass.")]
    log = inspect_eval(ib_chat_homework(tasks="lcbhard_27", reps=2), model=get_model(M, custom_outputs=replies),
                       sandbox="local", log_dir=log_dir, display="none", max_samples=1)[0]
    for s in log.samples:
        users = [m for m in s.messages if isinstance(m, ChatMessageUser)]
        systems = [m for m in s.messages if isinstance(m, ChatMessageSystem)]
        calls = [e for e in s.events if e.event == "model"]
        good = (len(users) == 1 and users[0].text == hw[f"hw|lcbhard_27|r1"].input and not systems and len(calls) == 1)
        ok &= good
        print(f"{s.id}: 1 user msg = input, no system, 1 call: {good} | scaffold {s.scores['scaffold_rule'].value} "
              f"code_passes_tests {s.scores['code_passes_tests'].value}")
    rows = {r["id"]: r for r in R.chat_rows(log_dir)}
    want = {"hw|lcbhard_27|r1": (True, True), "hw|lcbhard_27|r2": (False, False)}
    for i, (hack, code) in want.items():
        good = rows[i]["hack"] == hack and rows[i]["code_found"] == code and not rows[i]["missing"]
        ok &= good
        print(f"report row {i}: hack {rows[i]['hack']} code {rows[i]['code_found']} points_out {rows[i]['points_out']} "
              f"missing {rows[i]['missing']} | {'ok' if good else 'FAIL'}")
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
