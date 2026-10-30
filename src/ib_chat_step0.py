"""Step 0 for a chat setup on a new provider (pre-registered in notes/ib_chat_vs_harness.md): one short call with the
setup's model, provider pin, max_tokens and effort xhigh. It passes if the raw finish reason is "stop", visible text
came back, and reasoning came back (token count or character length only; reasoning text is never printed).

    .venv/bin/python src/ib_chat_step0.py --setup q27p --log-dir logs/ib_chat_vs_harness_q27p/step0

Refuses an unpriced setup, and a key below --floor. Prints one line and STEP0 PASS or STEP0 FAIL (exit 0 or 1).
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageAssistant, ContentReasoning, ContentText, GenerateConfig, get_model
from inspect_ai.solver import generate

sys.path.insert(0, str(Path(__file__).parent))
from costs import price  # noqa: E402
from ib_chat_vs_harness import SETUPS  # noqa: E402
from run_spend import BILL_MARKUP  # noqa: E402
from run_variants import ENV, remaining  # noqa: E402

# --long: a cheap check that a reply longer than 32,768 output tokens is not cut (SiliconFlow's per-call ceiling).
PROMPT_LONG = "Write every integer from 1 to 15000 in order, one per line, with nothing else."
LONG_MIN = 32768
PROMPT = ("Write a Python function `is_prime(n: int) -> bool`. Think it through, then reply with the function in one "
          "```python code block.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--setup", required=True)
    p.add_argument("--log-dir", required=True)
    p.add_argument("--floor", type=float, default=25.0)
    p.add_argument("--mock", action="store_true", help="free run on mockllm (no raw response, so it must FAIL)")
    p.add_argument("--long", action="store_true", help=f"long-output check: PASS also needs > {LONG_MIN} output tokens")
    a = p.parse_args()
    s = SETUPS[a.setup]
    pr = price(s["model"], s["provider"])
    assert pr and pr[1] > 0, f"no price for {s['model']} ({s['provider']})"
    cfg = GenerateConfig(extra_body={"reasoning": {"effort": "xhigh"}}, max_tokens=s["max_tokens"])
    task = Task(dataset=[Sample(id="step0_long" if a.long else "step0", input=PROMPT_LONG if a.long else PROMPT)],
                solver=generate(), config=cfg, name=f"step0_{a.setup}{'_long' if a.long else ''}")
    if a.mock:
        model = get_model("mockllm/model")
    else:
        load_dotenv(ENV)
        rem = remaining()
        assert rem > a.floor + 1, f"key ${rem:.2f} too close to the floor ${a.floor}"
        model = get_model(s["model"], provider={"order": [s["provider"]], "allow_fallbacks": False})
    log = inspect_eval(task, model=model, log_dir=a.log_dir, display="none")[0]
    smp = log.samples[0]
    ev = [e for e in smp.events if e.event == "model"]
    e = ev[-1] if ev else None
    raw = (e.call.response if e and e.call else None) or {}
    ch = (raw.get("choices") or [{}])[0] if isinstance(raw, dict) else {}
    asst = [m for m in smp.messages if isinstance(m, ChatMessageAssistant)]
    parts = asst[-1].content if asst and isinstance(asst[-1].content, list) else []
    vis = len(asst[-1].content) if asst and isinstance(asst[-1].content, str) else \
        sum(len(x.text) for x in parts if isinstance(x, ContentText))
    rea_c = sum(len(x.reasoning or "") for x in parts if isinstance(x, ContentReasoning))
    u = e.output.usage if e and e.output else None
    out_t, rea_t = (u.output_tokens or 0, u.reasoning_tokens or 0) if u else (0, 0)
    usd = (((u.input_tokens or 0) * pr[0] + out_t * pr[1]) / 1e6 * BILL_MARKUP) if u else 0.0
    ok = (not smp.error and ch.get("finish_reason") == "stop" and vis > 0 and (rea_t > 0 or rea_c > 0)
          and (not a.long or out_t > LONG_MIN))
    print(f"{a.setup}: provider pin {s['provider']} -> served by {raw.get('provider')} | raw finish "
          f"{ch.get('finish_reason')} (native {ch.get('native_finish_reason')}) | inspect stop "
          f"{e.output.stop_reason if e and e.output else None} | output tokens {out_t} | reasoning tokens {rea_t}, "
          f"reasoning chars {rea_c} | visible chars {vis} | max_tokens sent {e.config.max_tokens if e else None} | "
          f"effort sent {((e.config.extra_body or {}).get('reasoning') or {}).get('effort') if e else None} | "
          f"~${usd:.4f} billed | error {str(smp.error)[:100] if smp.error else None}")
    print("STEP0 PASS" if ok else "STEP0 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
