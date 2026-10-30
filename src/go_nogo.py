"""Go/no-go for a model's short check episode (notes/ib_persistence.md §21, §23), read once before any batch.

    python src/go_nogo.py <log dir> [--max-text-calls K] [--max-odd-stops K] [--expect N]

GO only if every episode in the dir has: no error; no model call that stopped at the length limit (stop_reason
model_length); no model call that ended any other way than "tool_calls" or "stop" (e.g. DeepInfra's raw
finish_reason "error", seen by agent 11 on 27B; Inspect maps unknown reasons to "unknown"), and no model event
carrying an error; no empty reply (an assistant turn with no text, no tool call and no reasoning); no tool call
returned as text (an assistant turn with no parsed tool call whose text matches TEXT_CALL); and a reasoning block
on at least half of its assistant turns. Prints the counts and the verdict.

§23 (registered before any top-up call): --max-text-calls and --max-odd-stops allow up to K tool calls returned as
text, and up to K calls with another stop reason (not model_length), per episode. They are set per model to the
most seen in one episode of that model's epoch-1 batch (DeepSeek 2 and 1; Qwen 3.8 Max 0 and 1). Defaults are 0,
which is §21's rule unchanged.

Also NO-GO when the dir holds no samples (a mistyped path, or a check run that crashed before writing its log), and,
with --expect N, unless it holds exactly N samples (§23 uses --expect 1 for each check dir). Added at the verifier's
check of §23.
"""
import glob
import re
import sys
from collections import Counter

from inspect_ai.log import read_eval_log

TEXT_CALL = re.compile(r"</?invoke|</?parameter|function_calls|<tool_call")
args = sys.argv[1:]
opt = lambda f: int(args[args.index(f) + 1]) if f in args else 0  # noqa: E731
max_text, max_odd = opt("--max-text-calls"), opt("--max-odd-stops")
expect = int(args[args.index("--expect") + 1]) if "--expect" in args else None
ok, n_samples = True, 0
for fp in sorted(glob.glob(f"{args[0]}/*.eval")):
    log = read_eval_log(fp)
    for s in log.samples or []:
        n_samples += 1
        models = [e for e in s.events if e.event == "model"]
        stops = Counter(e.output.stop_reason for e in models if e.output)
        odd_stops = sum(v for k, v in stops.items() if k not in ("tool_calls", "stop"))
        length_stops = stops.get("model_length", 0)
        event_errors = sum(1 for e in models if getattr(e, "error", None))
        turns = [m for m in s.messages if m.role == "assistant"]
        has_reasoning = lambda m: any(getattr(c, "type", "") == "reasoning"  # noqa: E731
                                      for c in (m.content if isinstance(m.content, list) else []))
        empty = sum(1 for m in turns if not (m.text or "").strip() and not m.tool_calls and not has_reasoning(m))
        text_calls = sum(1 for m in turns if not m.tool_calls and TEXT_CALL.search(m.text or ""))
        reasoned = sum(1 for m in turns if has_reasoning(m))
        good = (not s.error and length_stops == 0 and odd_stops <= max_odd and event_errors == 0 and empty == 0
                and text_calls <= max_text and reasoned * 2 >= len(turns))
        ok &= good
        print(f"{log.eval.model} {s.id} ep{s.epoch}: error {bool(s.error)} | stop reasons {dict(stops)} (other than "
              f"tool_calls/stop: {odd_stops}, allowed {max_odd}; model_length {length_stops}) | model-event errors "
              f"{event_errors} | empty replies {empty} | tool calls returned as text {text_calls} (allowed {max_text}) "
              f"| turns with reasoning {reasoned}/{len(turns)} | {'ok' if good else 'FAIL'}")
if n_samples == 0 or (expect is not None and n_samples != expect):
    ok = False
    print(f"samples found: {n_samples}" + (f", expected {expect}" if expect is not None else ", expected at least 1"))
print("GO" if ok else "NO-GO: stop and report before any batch")
