"""Tokens and cost per episode from Inspect logs, at OpenRouter list prices.

  python src/costs.py logs/effort_pilot

Prices are per million tokens: (input, output, cached input). Inspect's input count includes cached
tokens, so cached tokens are priced at the cache rate and the rest at the full input rate.
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from inspect_ai.log import read_eval_log

PRICES = {  # OpenRouter, read 2026-10-20 (same on every provider listed for the 2.4T)
    "qwen/qwen3.8-2.4t-a95b": (2.00, 6.00, 0.25),
    "qwen/qwen3.8-27b": (0.15, 1.875, 0.0375),  # DeepInfra BF16
    # DeepInfra FP8 via OpenRouter, per the orchestrator 2026-10-22; cache discount unknown, so cached tokens are
    # priced at the input rate (errs high).
    "deepseek/deepseek-v4-pro": (1.30, 2.60, 1.30),
}


def episode_rows(log_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(log_dir.glob("*.eval")):
        log = read_eval_log(str(path))
        model = log.eval.model.removeprefix("openrouter/")
        p_in, p_out, p_cache = PRICES.get(model, (0.0, 0.0, 0.0))
        args = log.eval.task_args
        effort = args.get("effort")
        instr = args.get("instruction", "stop")
        if len(instr) > 10:  # logs from before the option existed stored the instruction text itself
            instr = "stop" if "STOP" in instr else "custom"
        cond = f"{instr}/{args.get('framing', 'none')}"
        for s in log.samples or []:
            calls = [e.output.usage for e in s.events if e.event == "model" and e.output and e.output.usage]
            inp = sum(u.input_tokens for u in calls)
            cache = sum(u.input_tokens_cache_read or 0 for u in calls)
            out = sum(u.output_tokens for u in calls)
            reasoning = sum(u.reasoning_tokens or 0 for u in calls)
            score = next(iter(s.scores.values())).value if s.scores else None
            rows.append(dict(
                model=model, effort=effort, cond=cond, split=args.get("split"), id=s.id,
                passed=score == "C", calls=len(calls), input=inp, cached=cache, output=out,
                reasoning=reasoning, peak_ctx=max((u.input_tokens for u in calls), default=0),
                minutes=(s.total_time or 0) / 60, error=bool(s.error),
                usd=((inp - cache) * p_in + cache * p_cache + out * p_out) / 1e6,
            ))
    return rows


def main(log_dir: str) -> None:
    rows = episode_rows(Path(log_dir))
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["effort"], r["cond"], r["split"])].append(r)
    for (model, effort, cond, split), rs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        mean = lambda k: statistics.mean(r[k] for r in rs)
        print(f"{model} effort={effort} condition={cond} split={split}: {len(rs)} episodes, "
              f"{sum(r['passed'] for r in rs)} passed, {sum(r['error'] for r in rs)} errored")
        print(f"  per episode: ${mean('usd'):.3f}, {mean('calls'):.1f} calls, {mean('output'):,.0f} output "
              f"({mean('reasoning'):,.0f} reasoning), {mean('input'):,.0f} input ({mean('cached'):,.0f} cached), "
              f"peak context {mean('peak_ctx'):,.0f}, {mean('minutes'):.1f} min")
        print(f"  total: ${sum(r['usd'] for r in rs):.2f}")
        for r in rs:
            print(f"    {r['id']:<12} passed={r['passed']!s:<5} ${r['usd']:.3f} calls={r['calls']:<3} "
                  f"out={r['output']:>7,} in={r['input']:>9,} cached={r['cached']:>9,} {r['minutes']:.1f} min")


if __name__ == "__main__":
    main(sys.argv[1])
