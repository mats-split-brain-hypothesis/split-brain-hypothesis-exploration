"""Free check of the chat setups (no API calls): each setup's price, and that its generate settings reach the model
call. For each setup, one ib_chat sample runs on mockllm with the settings run_chat_vs_harness.py would pass
(max_tokens, effort); the logged model event's config must carry them. Then the report's missing rule on three
scripted replies: one cut by the token limit, one with no visible text, one normal.

    .venv/bin/python src/ib_chat_setups_check.py <log_dir>

Sandbox: Inspect's local sandbox (a temp folder on this machine), not Docker. The scripted replies are this file's own
text; the scorers run ImpossibleBench's test file against them.
"""
import sys
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

sys.path.insert(0, str(Path(__file__).parent))
from costs import price as price_of  # noqa: E402
from ib_chat_vs_harness import SETUPS, ib_chat  # noqa: E402
import ib_chat_vs_harness_report as R  # noqa: E402

M = "mockllm/model"


def out(content, stop="stop"):
    o = ModelOutput.from_content(M, content)
    o.choices[0].stop_reason = stop
    return o


def main(log_dir):
    ok = True
    for name, s in SETUPS.items():
        price = price_of(s["model"], s["provider"])
        gen = {"max_tokens": s["max_tokens"]} if s["max_tokens"] is not None else {}
        log = inspect_eval(ib_chat(tasks="lcbhard_101", reps=1, effort="xhigh"),
                           model=get_model(M, custom_outputs=[out("```python\nimport sys\nsys.exit(0)\n```")]),
                           sandbox="local", log_dir=f"{log_dir}/{name}", display="none", **gen)[0]
        ev = [e for e in log.samples[0].events if e.event == "model"]
        cfg = ev[0].config if ev else None
        got_mt = cfg.max_tokens if cfg else None
        got_eff = ((cfg.extra_body or {}).get("reasoning") or {}).get("effort") if cfg else None
        good = bool(price and price[1] > 0) and len(ev) == 1 and got_mt == s["max_tokens"] and got_eff == "xhigh"
        ok &= good
        print(f"{name}: model {s['model']} provider {s['provider']} price {price} | model calls {len(ev)} | "
              f"max_tokens sent {got_mt} (setup {s['max_tokens']}) | effort {got_eff} | "
              f"score {log.samples[0].scores['code_passes_tests'].value} | {'ok' if good else 'FAIL'}")
    # Missing rule, on three scripted replies (DeepSeek's settings).
    s = SETUPS["ds"]
    replies = [out("```python\nimport sys\nsys.exit(0)\n```", "max_tokens"), out("", "unknown"),
               out("The tests contradict each other.\n```python\nimport sys\nsys.exit(0)\n```")]
    log = inspect_eval(ib_chat(tasks="lcbhard_27", reps=3, effort="xhigh"),
                       model=get_model(M, custom_outputs=replies), sandbox="local", log_dir=f"{log_dir}/missing",
                       display="none", max_samples=1, max_tokens=s["max_tokens"])[0]
    rows = {r["id"]: r for r in R.chat_rows(f"{log_dir}/missing")}
    want = {"chat|lcbhard_27|r1": (True, "max_tokens"), "chat|lcbhard_27|r2": (True, "unknown"),
            "chat|lcbhard_27|r3": (False, "stop")}
    for i, (miss, end) in want.items():
        r = rows[i]
        good = r["missing"] == miss and r["end"] == end
        ok &= good
        print(f"missing rule {i}: end {r['end']} visible {r['visible_chars']} missing {r['missing']} hack {r['hack']} "
              f"points_out {r['points_out']} | {'ok' if good else 'FAIL'}")
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
