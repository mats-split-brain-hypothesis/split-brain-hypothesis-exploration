"""Free mock check of src/ib_continue.py (no API calls): scripted tool calls through Inspect's mockllm.

    python src/ib_continue_mock.py [--only ABCDEFG]

  A. exp9 arm E on r3_lcbhard_101_ep1: the replay reproduces the logged tool outputs; the E sentence is the end of the
     latest assistant turn's reasoning and renders inside its <think> block; no message is inserted; a submit ends.
  B. exp9 arm U on the same point: the prefix is exactly the logged one (no edit).
  C. exp10 L_msg on r4_lcbhard_27_ep2 (no func.py write between its hack turn and its passing submission): the
     message comes right after the cut; submitting at once scores C, as the original's passing submission did.
  D. exp10 L_none on the same point: no message; submitting at once scores C.
  E. exp10 E_msg on the same point: the message comes right after reply 1's tool results; func.py is still the stub,
     so submitting at once scores I.
  F. the message cap: endless think calls stop at max_new_messages ("message_cap", no submit).
  G. a reply without a tool call gets basic_agent's continue message; then a submit ends.
"""
import argparse
import json
import sys
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

sys.path.insert(0, str(Path(__file__).parent))
from ib_continue import CONTINUE_MESSAGE, OFF_BARE, ROOT, SENTENCES, ib_continue  # noqa: E402

M = "mockllm/model"
OUT = "logs/forensics_no_person/mock_cont"


def call(name, **args):
    return ModelOutput.for_tool_call(model=M, tool_name=name, tool_arguments=args)


def subset(exp, ids):
    spec = json.loads((ROOT / f"logs/forensics_no_person/{exp}/points.json").read_text())
    spec["points"] = [p for p in spec["points"] if p["id"] in ids]
    path = f"{OUT}/{exp}_{'_'.join(sorted(ids))}.json"
    (ROOT / OUT).mkdir(parents=True, exist_ok=True)
    (ROOT / path).write_text(json.dumps(spec))
    return path, spec["points"][0]


P9, P10 = "r3_lcbhard_101_ep1", "r4_lcbhard_27_ep2"
SUBMIT = call("submit", answer="done")
SCENARIOS = {
    "A": ("exp9", P9, "E", [call("bash", cmd="cd /workspace && python test.py 2>&1 | tail -2"), SUBMIT], 30),
    "B": ("exp9", P9, "U", [SUBMIT], 30),
    "C": ("exp10", P10, "L_msg", [SUBMIT], 30),
    "D": ("exp10", P10, "L_none", [SUBMIT], 30),
    "E": ("exp10", P10, "E_msg", [SUBMIT], 30),
    "F": ("exp9", P9, "N", [call("think", thought="hmm")] * 10, 6),
    "G": ("exp9", P9, "N", [ModelOutput.from_content(model=M, content="Let me think."), SUBMIT], 30),
}


async def rendered(msg):
    from inspect_ai.model._openai import openai_chat_message
    return (await openai_chat_message(msg))["content"]


def check(name, sample, point):
    import asyncio
    from inspect_ai.model import ContentReasoning
    rec = sample.store["ib_cont"]
    score = list(sample.scores.values())[0].value
    msgs = sample.messages
    prefix_logged = json.loads((ROOT / point["prefix"][rec["cut"]]).read_text())
    n0 = len(prefix_logged) + (1 if rec["arm"] in ("L_msg", "E_msg") else 0)
    fails = []

    def expect(cond, what):
        if not cond:
            fails.append(what)
    expect(len(rec["replay_mismatches"]) <= 1, f"replay mismatches {len(rec['replay_mismatches'])} of {rec['replayed_calls']}")
    last_a = max(i for i in range(len(prefix_logged)) if prefix_logged[i]["role"] == "assistant")
    reason = "".join(c.reasoning for c in msgs[last_a].content if isinstance(c, ContentReasoning)) \
        if isinstance(msgs[last_a].content, list) else ""
    if name == "A":
        expect(reason.endswith("\n\n" + SENTENCES["E"]), f"sentence at the end of the reasoning: {reason[-90:]!r}")
        r = asyncio.run(rendered(msgs[last_a]))
        expect(SENTENCES["E"] + "\n</think>" in r, f"rendered inside <think>: {r[-120:]!r}")
        expect(all(m.role != "user" or m.text != OFF_BARE for m in msgs), "no message inserted")
        expect(rec["stop"] == "submit" and rec["added"] == 4, f"bash + submit, then end: {rec['stop']} {rec['added']}")
    if name == "B":
        logged_last = prefix_logged[last_a]
        logged_reason = "".join(c.get("reasoning", "") for c in logged_last["content"] if c.get("type") == "reasoning") \
            if isinstance(logged_last["content"], list) else ""
        expect(reason == logged_reason, "reasoning unchanged")
    if name in ("C", "E"):
        expect(msgs[n0 - 1].role == "user" and msgs[n0 - 1].text == OFF_BARE, f"message right after the cut: {msgs[n0-1].role}")
        expect(msgs[n0 - 2].role == "tool", "the cut ends on tool results")
    if name == "C":
        expect(score == "C", f"late cut + immediate submit passes: {score}")
    if name == "D":
        expect(score == "C" and all(m.text != OFF_BARE for m in msgs if m.role == "user"), f"no message, passes: {score}")
    if name == "E":
        expect(sum(1 for m in msgs[:n0] if m.role == "assistant") == 1, "early cut is after reply 1")
        expect(score == "I", f"stub at reply 1 fails: {score}")
    if name == "F":
        expect(rec["stop"] == "message_cap" and not rec["submitted"] and rec["added"] >= 6, f"cap: {rec}")
    if name == "G":
        expect(any(m.role == "user" and m.text == CONTINUE_MESSAGE for m in msgs[n0:]), "continue message after a reply")
        expect(rec["stop"] == "submit", "then submit ends")
    return fails, rec, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="ABCDEFG")
    a = ap.parse_args()
    bad = False
    for name in a.only:
        exp, pid, arm, outputs, cap = SCENARIOS[name]
        path, point = subset(exp, {pid})
        log = inspect_eval(ib_continue(points=path, arm=arm, max_new_messages=cap, label=f"mock{name}"),
                           model=get_model(M, custom_outputs=outputs), log_dir=OUT, display="none")[0]
        if log.status != "success":
            print(f"scenario {name}: eval {log.status}: {log.error}")
            bad = True
            continue
        fails, rec, score = check(name, log.samples[0], point)
        bad |= bool(fails)
        print(f"scenario {name}: {'OK' if not fails else 'FAIL'}  arm={arm} score={score} stop={rec['stop']} "
              f"added={rec['added']} replayed={rec['replayed_calls']} mismatches={len(rec['replay_mismatches'])}")
        for f in fails:
            print("   -", f)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
