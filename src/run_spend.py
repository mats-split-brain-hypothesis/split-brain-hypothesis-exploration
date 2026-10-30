"""A run's own spend from its token counts: finished Inspect logs plus the live sample buffer, at src/costs.py's
OpenRouter list prices, times BILL_MARKUP (the bill has run about 30% above the token estimate).

  python src/run_spend.py logs/ib_cues/round1a      # prints the estimate (one poll: a lower bound mid-run)

While a task runs, its samples sit in Inspect's live buffer and leave it when they finish; their usage only comes back
when the task's .eval is written at the end. So own_spend() keeps a module-level cache of the last-seen cost per
(log file, sample id, epoch), never dropped while that file is still "started"; a started file's total is the sum of
its cached samples. Once the file is finished, the .eval is used and the cache entries are cleared. Called repeatedly
from one process (the run_variants.py watchdog), the estimate therefore never falls. It still misses the tail between
the last poll and a sample's end, and a single call from a fresh process sees only the samples still in the buffer.
"""
import os
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log
from inspect_ai.log._recorders.buffer.database import SampleBufferDatabase

sys.path.insert(0, str(Path(__file__).parent))
from costs import PRICES  # noqa: E402

BILL_MARKUP = 1.3
_finished = {}  # log file -> (usd, samples), from the finished .eval
_live = {}      # (log file, sample id, epoch) -> last-seen usd while the file is "started"


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
        key = str(f)
        if key in _finished:
            total += _finished[key][0]
            n += _finished[key][1]
            continue
        h = read_eval_log(key, header_only=True)
        if h.status != "started":
            log = read_eval_log(key)
            usd = sum(_usd(log.eval.model, [e.output.usage.model_dump() for e in s.events
                                            if e.event == "model" and e.output and e.output.usage])
                      for s in log.samples or [])
            _finished[key] = (usd, len(log.samples or []))
            for k in [k for k in _live if k[0] == key]:
                del _live[k]
            total += usd
            n += len(log.samples or [])
            continue
        try:
            buf = SampleBufferDatabase(os.path.realpath(f), create=False)
            got = buf.get_samples()
            for s in (got.samples if got else []):
                data = buf.get_sample_data(s.id, s.epoch)
                usages = [e.event["output"]["usage"] for e in (data.events if data else [])
                          if e.event.get("event") == "model" and (e.event.get("output") or {}).get("usage")]
                k = (key, str(s.id), s.epoch)
                _live[k] = max(_live.get(k, 0.0), _usd(h.eval.model, usages))
        except FileNotFoundError:
            pass
        mine = [v for k, v in _live.items() if k[0] == key]
        total += sum(mine)
        n += len(mine)
    return total, total * BILL_MARKUP, n


if __name__ == "__main__":
    est, billed, n = own_spend(sys.argv[1])
    print(f"{n} episodes: ${est:.2f} by token count, ~${billed:.2f} billed (one poll: a lower bound while running)")
