"""Stage-1 gate for the GLM 5.2 and Qwen 27B chat arms (pre-registered in notes/ib_chat_vs_harness.md): the first 2
replies (chat|lcbhard_101|r1, chat|lcbhard_27|r1) must each be error-free, not cut by the token limit, with visible
text, output tokens and reasoning (reasoning measured by token count or character length only; never printed).

    .venv/bin/python src/ib_chat_gate.py <chat log dir>

Prints one line per reply and GATE PASS or GATE FAIL (exit 0 or 1). On FAIL: stop and report; the other 16 don't run.
"""
import sys
from pathlib import Path

from inspect_ai.model import ChatMessageAssistant, ContentReasoning

sys.path.insert(0, str(Path(__file__).parent))
import ib_chat_vs_harness_report as R  # noqa: E402

EXPECTED = ("chat|lcbhard_101|r1", "chat|lcbhard_27|r1")


def main(d):
    rows = {r["id"]: r for r in R.chat_rows(d)}
    tokens = {}
    for s in R.samples_in(d):
        ev = [e for e in s.events if e.event == "model" and e.output and e.output.usage]
        out_t = sum(e.output.usage.output_tokens or 0 for e in ev)
        rea_t = sum(e.output.usage.reasoning_tokens or 0 for e in ev)
        rea_c = sum(len(p.reasoning or "") for m in s.messages if isinstance(m, ChatMessageAssistant)
                    for p in (m.content if isinstance(m.content, list) else []) if isinstance(p, ContentReasoning))
        tokens[str(s.id)] = (out_t, rea_t, rea_c)
    ok = set(rows) == set(EXPECTED)
    if not ok:
        print("expected exactly", EXPECTED, "found", sorted(rows))
    for i in EXPECTED:
        r = rows.get(i)
        out_t, rea_t, rea_c = tokens.get(i, (0, 0, 0))
        if r is None:
            continue
        good = (not r["error"] and not r["missing"] and out_t > 0 and (rea_t > 0 or rea_c > 0))
        ok &= good
        print(f"{i}: error {r['error']} | end {r.get('end')} | visible chars {r.get('visible_chars')} | output tokens "
              f"{out_t} | reasoning tokens {rea_t}, reasoning chars {rea_c} | code {r.get('code_found')} | "
              f"{'ok' if good else 'FAIL'}")
    print("GATE PASS" if ok else "GATE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
