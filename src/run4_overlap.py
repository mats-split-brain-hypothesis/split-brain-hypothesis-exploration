"""Run 4 concurrency from its logs, two ways: episodes overlapping by [first event, last event] (the verifier's
measure) and by [first sandbox/model activity, last event]; also each episode's wait between its first event and its
first model call."""
import glob

from inspect_ai.log import read_eval_log

spans = []
for fp in sorted(glob.glob("logs/ib_persistence/grading_off_r4/*.eval")):
    for s in read_eval_log(fp).samples:
        evs = [e for e in s.events if getattr(e, "timestamp", None)]
        first = min(e.timestamp for e in evs)
        last = max(e.timestamp for e in evs)
        model = min((e.timestamp for e in evs if e.event == "model"), default=last)
        sbx = min((e.timestamp for e in evs if e.event == "sandbox"), default=model)
        spans.append((first, sbx, model, last, s.id, s.epoch, fp.split("_ib-")[1][:4]))


def peak(pairs):
    pts = sorted([(a, 1) for a, b in pairs] + [(b, -1) for a, b in pairs])
    cur = best = 0
    for _, d in pts:
        cur += d
        best = max(best, cur)
    return best


print("peak by [first event, last event]:", peak([(f, l) for f, s, m, l, *_ in spans]))
print("peak by [first sandbox event, last event]:", peak([(s, l) for f, s, m, l, *_ in spans]))
print("peak by [first model call, last event]:", peak([(m, l) for f, s, m, l, *_ in spans]))
waits = sorted(((m - f).total_seconds() / 60, sid, ep, arm) for f, s, m, l, sid, ep, arm in spans)
print("minutes from first event to first model call, largest 6:", [(round(w, 1), f"{a}:{i}/{e}") for w, i, e, a in waits[-6:]])
