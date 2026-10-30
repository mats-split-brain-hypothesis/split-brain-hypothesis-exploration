"""Free mock check of src/ib_swe_continue.py (no API calls): scripted tool calls through Inspect's mockllm, one
sandbox at a time. Runs in logs/ib_swe/venv.

    logs/ib_swe/venv/bin/python src/ib_swe_continue_mock.py [--only ABC]

  A. c_stop: init's commit is re-dated to the logged hash; the replay reproduces the logged tool outputs; the model
     gets the logged messages up to turn 6's tool result, then STOP_SWE; the tools sent are the base's; a bash call,
     then submitting at once passes (the code fix and the test edit are in place), with the tests changed.
  B. c_stop: restoring the committed test file, then submitting, fails, with the tests unchanged (the scorer keeps or
     drops test edits as the screen's did).
  C. d_stop: the message comes after turn 13's tool result; submitting at once passes.
  D, E. c_nomod, d_nomod: the c13_nomodify text after turn 6 / turn 13; submitting at once passes.
  F, G. c_abort, d_abort: the abort clause after turn 6 / turn 13; submitting at once passes.
  H, I, J. c_approve_nomod: APPROVE after turn 6; NOMODIFY after the 7th new turn (H), in place of an early submit,
     which is dropped (I), or in place of the continue message after a reply with no tool call (J); then submit passes.
"""
import argparse
import sys
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.log import ModelEvent
from inspect_ai.model import ModelOutput, get_model

sys.path.insert(0, str(Path(__file__).parent))
from ib_swe_continue import APPROVE, ARMS, NOMODIFY, TWO_STEP, cut_index, ib_swe_continue, load_base  # noqa: E402

M = "mockllm/model"
OUT = "logs/forensics_no_person/mock_ibswe"
TESTS = "sklearn/feature_extraction/tests/test_text.py"


def call(name, **args):
    return ModelOutput.for_tool_call(model=M, tool_name=name, tool_arguments=args)


SUBMIT = call("submit", answer="done")
SCENARIOS = {
    "A": ("c_stop", [call("bash", cmd="cd /testbed && git log --oneline -2 && git status --short"), SUBMIT], 1.0, True),
    "B": ("c_stop", [call("bash", cmd=f"cd /testbed && git checkout HEAD -- {TESTS} && git status --short"), SUBMIT],
          0.0, False),
    "C": ("d_stop", [SUBMIT], 1.0, True),
    "D": ("c_nomod", [SUBMIT], 1.0, True),
    "E": ("d_nomod", [SUBMIT], 1.0, True),
    "F": ("c_abort", [SUBMIT], 1.0, True),
    "G": ("d_abort", [SUBMIT], 1.0, True),
}
BASH = call("bash", cmd="cd /testbed && git status --short")
TWO = {  # two-step arm: (outputs, expected: second message's index, after which new turn, intercepted at, in place of continue)
    "H": ([BASH] * 7 + [SUBMIT], 34, 7, None, False),
    "I": ([BASH, BASH, SUBMIT, SUBMIT], 24, 2, 3, False),
    "J": ([BASH] * 6 + [ModelOutput.from_content(model=M, content="Thinking."), SUBMIT], 33, 7, None, True),
}


def tools_of(sample):
    ev = next(e for e in sample.events if isinstance(e, ModelEvent))
    return [(t.name, t.description, t.parameters.model_dump()) for t in ev.tools]


def check(name, sample, base):
    arm, _, want_score, want_changed = SCENARIOS[name]
    rec = sample.store["ib_mom"]
    k = cut_index(base.messages, ARMS[arm][0])
    msgs = sample.messages
    score = list(sample.scores.values())[0].value
    fails = []

    def expect(cond, what):
        if not cond:
            fails.append(what)
    expect(rec["redate"].get("matched"), f"HEAD re-dated to the logged hash: {rec['redate']}")
    expect(sample.store.get("ib_tests_head") == base.store["ib_tests_head"], "ib_tests_head equals the base's")
    expect(rec["prefix_messages"] == k, f"prefix length {rec['prefix_messages']} vs {k}")
    expect([m.model_dump() for m in msgs[:k]] == [m.model_dump() for m in base.messages[:k]],
           "the messages up to the cut are the logged ones")
    expect(msgs[k - 1].role == "tool" and msgs[k].role == "user" and msgs[k].text == ARMS[arm][1],
           f"the arm's text right after the cut's tool results: {msgs[k-1].role} {msgs[k].role}")
    expect(tools_of(sample) == tools_of(base), "tools sent to the model equal the base's")
    expect(score == want_score, f"score {score}, expected {want_score}")
    expect(sample.store.get("ib_test_changed_at_submit") == want_changed,
           f"test_changed_at_submit {sample.store.get('ib_test_changed_at_submit')}, expected {want_changed}")
    expect(sample.store.get("ib_end") == "submit", f"end {sample.store.get('ib_end')}")
    return fails, rec, score


def check_two(name, sample, base):
    """c_approve_nomod: APPROVE right after turn 6's tool results; NOMODIFY after the 7th new turn's tool results, or
    in place of an early submit (that reply dropped), or in place of the continue message; then the loop runs on."""
    outputs, want_at, want_after, want_icpt, want_cont = TWO[name]
    rec = sample.store["ib_mom"]
    sec = rec["second"]
    k = cut_index(base.messages, TWO_STEP["c_approve_nomod"][0])
    msgs = sample.messages
    score = list(sample.scores.values())[0].value
    fails = []

    def expect(cond, what):
        if not cond:
            fails.append(what)
    expect(rec["redate"].get("matched") and not rec["replay_mismatches"], "replay as before")
    expect([m.model_dump() for m in msgs[:k]] == [m.model_dump() for m in base.messages[:k]], "logged prefix")
    expect(msgs[k].role == "user" and msgs[k].text == APPROVE, "APPROVE right after the cut")
    expect(sec["sent_at_message"] == want_at and msgs[want_at].role == "user" and msgs[want_at].text == NOMODIFY,
           f"NOMODIFY at message {sec['sent_at_message']}, expected {want_at}")
    expect(sec["sent_after_new_turn"] == want_after, f"after new turn {sec['sent_after_new_turn']}, expected {want_after}")
    expect((sec["intercepted"] or {}).get("at_new_turn") == want_icpt, f"intercepted {sec['intercepted']}")
    expect(sec["in_place_of_continue"] == want_cont, f"in place of continue {sec['in_place_of_continue']}")
    expect(sec["test_changed_when_sent"] is True, "the test edit is there when NOMODIFY is sent")
    expect(sum(1 for m in msgs if m.role == "user" and m.text == NOMODIFY) == 1, "NOMODIFY sent once")
    expect(want_cont or all(m.text != "Please proceed to the next step using your best judgement."
                            for m in msgs[k:] if m.role == "user"), "no continue message")
    n_submits = sum(1 for m in msgs if m.role == "assistant" for tc in (m.tool_calls or []) if tc.function == "submit")
    expect(n_submits == 1, f"one executed submit in the messages, got {n_submits}")
    expect(score == 1.0 and sample.store.get("ib_end") == "submit", f"score {score}, end {sample.store.get('ib_end')}")
    return fails, rec, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="ABCDEFGHIJ")
    a = ap.parse_args()
    base = load_base()
    bad = False
    for name in a.only:
        arm, outputs = ("c_approve_nomod", TWO[name][0]) if name in TWO else SCENARIOS[name][:2]
        log = inspect_eval(ib_swe_continue(arm=arm, label=f"mock{name}"), model=get_model(M, custom_outputs=outputs),
                           log_dir=OUT, display="none", max_sandboxes=1, max_samples=1)[0]
        if log.status != "success" or not log.samples or log.samples[0].error:
            print(f"scenario {name}: eval {log.status}: {log.error or (log.samples[0].error if log.samples else '')}")
            bad = True
            continue
        fails, rec, score = (check_two if name in TWO else check)(name, log.samples[0], base)
        bad |= bool(fails)
        print(f"scenario {name}: {'OK' if not fails else 'FAIL'}  arm={arm} score={score} "
              f"replayed={rec['replayed_calls']} mismatches={len(rec['replay_mismatches'])} redate={rec['redate']}")
        for mm in rec["replay_mismatches"]:
            print(f"   mismatch {mm['fn']} {mm['args'][:120]!r}\n      replayed {mm['replayed'][:200]!r}\n"
                  f"      logged   {mm['logged'][:200]!r}")
        for f in fails:
            print("   -", f)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
