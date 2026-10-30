"""Pull each Dark Mode (puppeteer) seed's own decision turn into the labeller's row format.

    python src/aie_decision_extract.py <out.jsonl> <log_dir_or_eval> [...]

Row: {"arm", "i", "ok", "reasoning", "content", "tool_calls": [{"name", "arguments"}], "log", "sample", "epoch",
"decision": {after_step, trigger, trigger_kind, trigger_rc}}. The decision turn is the assistant message at the
scorer's `decision.decision_turn_index` (stop_at_decision runs). Episodes with no decision point get ok=false and
their end state (steps, completed, PNG) so they are reported, not dropped. arm = the task label after "aie_puppeteer_"
(e.g. R, G); i counts episodes within an arm in log order.
"""
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentReasoning


def turn_fields(m):
    reasoning = "".join(c.reasoning for c in m.content if isinstance(c, ContentReasoning)) \
        if isinstance(m.content, list) else ""
    calls = [{"name": tc.function, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}
             for tc in (m.tool_calls or [])]
    return {"reasoning": reasoning, "content": m.text or "", "tool_calls": calls}


def rows_for(paths):
    count = defaultdict(int)
    for p in paths:
        log = read_eval_log(p)
        arm = log.eval.task.split("aie_puppeteer_")[-1]
        for s in log.samples or []:
            md = s.scores["puppeteer_scorer"].metadata if s.scores else (s.store.get("aie_puppeteer") or {})
            d = md.get("decision")
            row = {"arm": arm, "i": count[arm], "log": str(p), "sample": s.id, "epoch": s.epoch}
            count[arm] += 1
            if d:
                m = s.messages[d["decision_turn_index"]]
                assert m.role == "assistant", (p, s.epoch)
                row.update(ok=True, decision={k: d.get(k) for k in ("after_step", "trigger", "trigger_kind", "trigger_rc")},
                           **turn_fields(m))
            else:
                row.update(ok=False, steps=md.get("steps"), completed=md.get("completed"), png=md.get("png"),
                           final_reply=(md.get("final_reply") or "")[-1500:], error=str(s.error)[:300] if s.error else None)
            yield row


if __name__ == "__main__":
    out, srcs = sys.argv[1], sys.argv[2:]
    paths = []
    for src in srcs:
        paths += sorted(glob.glob(f"{src}/*.eval")) if Path(src).is_dir() else [src]
    rows = list(rows_for(paths))
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for r in rows:
        print(r["arm"], r["i"], "ok" if r["ok"] else "NO DECISION", r.get("decision", {}).get("after_step"),
              r.get("decision", {}).get("trigger_kind"), len(r.get("reasoning", "")), r.get("steps"))
