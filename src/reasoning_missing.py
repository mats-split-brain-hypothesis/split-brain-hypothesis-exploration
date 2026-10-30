"""Missing reasoning text in §24's episodes (orchestrator's caveat, 27 Oct): GLM on SiliconFlow (and DeepSeek, less
often) sometimes returns "reasoning": null while usage reports reasoning_tokens > 0. Local, no calls; counts only.

    python src/reasoning_missing.py

A reply is "text missing" when its model call's usage has reasoning_tokens > 0 and the raw response's
message.reasoning is null or empty. Replies are matched to model calls in order: in a told-before episode every
assistant message has its own call; in a continuation, the replayed prefix has none, so the last N assistant messages
match its N calls. Checked: the counts must agree.
For §24: per model and arm, replies with text missing; reply 1; and, for the told episodes, whether any reply before
the first OFF_RE hit (or any reply at all, for episodes with no hit) had its text missing, i.e. whether "late" or
"never" could rest on unseen reasoning.
"""
import glob
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inspect_ai.log import read_eval_log  # noqa: E402
from late_or_never import AFTER, BEFORE, MODELS, OFF, OFF_RE, reasoning_text  # noqa: E402


def call_info(e):
    u = e.output.usage if e.output else None
    rt = (u.reasoning_tokens or 0) if u else 0
    resp = e.call.response if e.call and isinstance(e.call.response, dict) else {}
    msg = ((resp.get("choices") or [{}])[0] or {}).get("message") or {}
    raw = msg.get("reasoning")
    return dict(rt=rt, missing=rt > 0 and not (raw or "").strip(), raw_present="reasoning" in msg)


def matched(s, n_new=None):
    """(assistant message index, call info) for the assistant messages that have a model call."""
    evs = [e for e in s.events if e.event == "model"]
    a = [i for i, m in enumerate(s.messages) if m.role == "assistant"]
    if n_new is not None:
        a = a[len(a) - n_new:]
    assert len(evs) == len(a), (s.id, s.epoch, len(evs), len(a))
    return list(zip(a, (call_info(e) for e in evs)))


def told_before(model, src, told):
    out = []
    for d, lab in src:
        for fp in sorted(glob.glob(f"{d}/*.eval")):
            log = read_eval_log(fp)
            if (log.eval.task_args or {}).get("label") != lab:
                continue
            for s in log.samples or []:
                if s.error:
                    continue
                pairs = matched(s)
                if told:
                    k = next(i for i, m in enumerate(s.messages) if m.role == "user" and m.text == OFF)
                else:
                    k = pairs[1][0] - 1 if len(pairs) > 1 else len(s.messages)
                after = [(i, c) for i, c in pairs if i > k]
                hit = next((r for r, (i, _) in enumerate(after, 1)
                            if OFF_RE.search(reasoning_text(s.messages[i])) or OFF_RE.search(s.messages[i].text or "")),
                           None)
                out.append(dict(task=s.id, epoch=s.epoch, all=[c for _, c in pairs], after=[c for _, c in after],
                                hit=hit))
    return out


def continuations(dirs, prefix, keep_epoch):
    out = []
    for d in dirs:
        for fp in sorted(glob.glob(f"{d}/*.eval")):
            for s in read_eval_log(fp).samples or []:
                rec = (s.store or {}).get("ib_cont")
                if s.error or not rec or not rec["point"].startswith(prefix) or rec["arm"] not in ("L_msg", "L_none"):
                    continue
                if keep_epoch and s.epoch != keep_epoch:
                    continue
                n_new = sum(1 for m in s.messages[len(s.messages) - rec["added"]:] if m.role == "assistant")
                pairs = matched(s, n_new)
                hit = next((r for r, (i, _) in enumerate(pairs, 1)
                            if OFF_RE.search(reasoning_text(s.messages[i])) or OFF_RE.search(s.messages[i].text or "")),
                           None)
                out.append(dict(arm=rec["arm"], point=rec["point"], after=[c for _, c in pairs], hit=hit))
    return out


def frac(cs):
    return f"{sum(c['missing'] for c in cs)}/{len(cs)}"


def main():
    print("Replies with reasoning text missing (reasoning_tokens > 0, raw reasoning null or empty):")
    for model in MODELS:
        c_src, a_src = BEFORE[model]
        told, ctrl = told_before(model, a_src, True), told_before(model, c_src, False)
        print(f"\n{model}, told before:")
        for name, rows in (("told", told), ("no message", ctrl)):
            print(f"  {name}: all calls {frac([c for r in rows for c in r['all']])}; after the message's position "
                  f"{frac([c for r in rows for c in r['after']])}; reply 1 {frac([r['after'][0] for r in rows if r['after']])}"
                  f"; episodes with any {sum(any(c['missing'] for c in r['all']) for r in rows)}/{len(rows)}")
        late = [r for r in told if r["hit"] and r["hit"] > 1]
        never = [r for r in told if not r["hit"]]
        print(f"  told, first hit after reply 1 (n {len(late)}): episodes with a text-missing reply before the hit "
              f"{sum(any(c['missing'] for c in r['after'][:r['hit'] - 1]) for r in late)}; such replies "
              f"{sum(sum(c['missing'] for c in r['after'][:r['hit'] - 1]) for r in late)} of "
              f"{sum(r['hit'] - 1 for r in late)}")
        print(f"  told, first hit at reply 1 (n {sum(1 for r in told if r['hit'] == 1)})")
        if never:
            print(f"  told, no hit (n {len(never)}): episodes with any text-missing reply "
                  f"{sum(any(c['missing'] for c in r['after']) for r in never)}; replies "
                  f"{sum(sum(c['missing'] for c in r['after']) for r in never)} of {sum(len(r['after']) for r in never)}"
                  f"; per episode {[sum(c['missing'] for c in r['after']) for r in never]}")
        a3 = [c for r in told for c in r["after"][:3]]
        print(f"  told, replies 1-3 (the judge's A window): {frac(a3)}")
        # the judge's A window, by episode: text-missing replies in 1-3 and whether OFF_RE hit in 1-3
        w = [(sum(c["missing"] for c in r["after"][:3]), bool(r["hit"] and r["hit"] <= 3)) for r in told]
        print(f"  told, episodes with a text-missing reply in 1-3: {sum(1 for m, _ in w if m)} (of which no OFF_RE hit "
              f"in 1-3: {sum(1 for m, h in w if m and not h)})")
        rows = continuations(*AFTER[model])
        for arm in ("L_msg", "L_none"):
            x = [r for r in rows if r["arm"] == arm]
            print(f"  told after, {arm}: all new replies {frac([c for r in x for c in r['after']])}; reply 1 "
                  f"{frac([r['after'][0] for r in x if r['after']])}")
        x = [r for r in rows if r["arm"] == "L_msg"]
        late = [r for r in x if r["hit"] and r["hit"] > 1]
        never = [r for r in x if not r["hit"]]
        print(f"  told after, L_msg: first hit after reply 1 (n {len(late)}): text-missing reply before the hit in "
              f"{sum(any(c['missing'] for c in r['after'][:r['hit'] - 1]) for r in late)}; no hit (n {len(never)}): "
              f"replies per episode {[len(r['after']) for r in never]}, text missing {[sum(c['missing'] for c in r['after']) for r in never]}")


if __name__ == "__main__":
    main()
