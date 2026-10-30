"""A run's own spend from its token counts: finished Inspect logs plus the live sample buffer, at src/costs.py's
OpenRouter list prices, times BILL_MARKUP (the bill has run about 30% above the token estimate).

  python src/run_spend.py logs/ib_cues/round1a      # prints the estimate
"""
import os
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log
from inspect_ai.log._recorders.buffer.database import SampleBufferDatabase

sys.path.insert(0, str(Path(__file__).parent))
from costs import PRICES  # noqa: E402

BILL_MARKUP = 1.3
_finished = {}


def _usd(model, usages):
    p_in, p_out, p_cache = PRICES.get(model.removeprefix("openrouter/"), (0.0, 0.0, 0.0))
    inp = sum(u.get("input_tokens") or 0 for u in usages)
    cache = sum(u.get("input_tokens_cache_read") or 0 for u in usages)
    out = sum(u.get("output_tokens") or 0 for u in usages)
    return ((inp - cache) * p_in + cache * p_cache + out * p_out) / 1e6


def own_spend(log_dir):
    """(token estimate in dollars, the same times BILL_MARKUP, episodes counted)."""
    total, n = 0.0, 0
    for f in sorted(Path(log_dir).glob("*.eval")):
        if f in _finished:
            total += _finished[f][0]
            n += _finished[f][1]
            continue
        h = read_eval_log(str(f), header_only=True)
        if h.status != "started":
            log = read_eval_log(str(f))
            usd = sum(_usd(log.eval.model, [e.output.usage.model_dump() for e in s.events
                                            if e.event == "model" and e.output and e.output.usage])
                      for s in log.samples or [])
            _finished[f] = (usd, len(log.samples or []))
            total += usd
            n += len(log.samples or [])
            continue
        try:
            buf = SampleBufferDatabase(os.path.realpath(f), create=False)
        except FileNotFoundError:
            continue
        got = buf.get_samples()
        for s in (got.samples if got else []):
            data = buf.get_sample_data(s.id, s.epoch)
            usages = [e.event["output"]["usage"] for e in (data.events if data else [])
                      if e.event.get("event") == "model" and (e.event.get("output") or {}).get("usage")]
            total += _usd(h.eval.model, usages)
            n += 1
    return total, total * BILL_MARKUP, n


if __name__ == "__main__":
    est, billed, n = own_spend(sys.argv[1])
    print(f"{n} episodes: ${est:.2f} by token count, ~${billed:.2f} billed")
