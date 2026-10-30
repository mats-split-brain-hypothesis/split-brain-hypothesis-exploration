"""In-episode validation for the graded-but-real search pick (notes/d1_graded_real_search.md): eval and grader talk in
the reasoning of agent 7's C11 (the pick, R2c) vs C5 and C6 episodes. Local, no API calls.

  python src/d1_search_inepisode.py

Measures, pre-registered: per text, the episodes with at least one reasoning passage matching src/patterns.py EVAL or
GRADER, and matches per 1,000 reasoning characters. Descriptive only.
Adjustment, not pre-registered: the C11 validation ran at message_limit 60, the existing C5/C6 at 80. So the existing
episodes are also counted over their first 60 messages, alongside their full length.
"""
import json
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from patterns import EVAL, GRADER  # noqa: E402

G = ROOT / "logs" / "rejection" / "graded"
SETS = {
    "C11 (pick R2c), validation, limit 60": [G / "c11_valid"],
    "C5, validation, limit 60": [G / "c11_valid"],
    "C5, earlier runs, limit 80": [G / "c5c6", G / "c5c6_rep", G / "c5c6_n20"],
    "C6, earlier runs, limit 80": [G / "c5c6", G / "c5c6_rep", G / "c5c6_n20"],
}


def task_kind(task):
    if "sent-person-done" in task:
        return "C11"
    if "colleague-graded" in task or "_graded_" in task.replace("-", "_"):
        return "C6"
    return "C5"


def want(label, kind):
    return label.startswith(kind + " ") or label.startswith(kind + ",")


def reasoning(msgs, limit=None):
    out = []
    for m in msgs[:limit] if limit else msgs:
        if m.role != "assistant" or not isinstance(m.content, list):
            continue
        out += [c.reasoning for c in m.content if getattr(c, "type", None) == "reasoning" and c.reasoning]
    return out


def main():
    rows = []
    for label, dirs in SETS.items():
        seen, eps = set(), []
        for d in dirs:
            for p in sorted(d.glob("*.eval")):
                log = read_eval_log(str(p))
                kind = task_kind(log.eval.task.replace("_", "-"))
                # validation texts come only from c11_valid, the earlier ones only from the other folders
                if not want(label, kind) or ("validation" in label) != ("c11_valid" in str(p)):
                    continue
                for s in log.samples or []:
                    if s.error or not s.scores:
                        continue
                    k = (d.name, log.eval.task, s.id, s.epoch)
                    if k in seen:
                        continue
                    seen.add(k)
                    eps.append(s.messages)
        for lim, tag in (((None, "all messages"), (60, "first 60 messages")) if "limit 80" in label else ((None, "all messages"),)):
            passages = [reasoning(m, lim) for m in eps]
            chars = sum(len(x) for ps in passages for x in ps)
            ev = sum(len(EVAL.findall(x)) for ps in passages for x in ps)
            gr = sum(len(GRADER.findall(x)) for ps in passages for x in ps)
            any_ep = sum(any(EVAL.search(x) or GRADER.search(x) for x in ps) for ps in passages)
            ev_ep = sum(any(EVAL.search(x) for x in ps) for ps in passages)
            gr_ep = sum(any(GRADER.search(x) for x in ps) for ps in passages)
            rows.append({"text": label, "messages": tag, "episodes": len(eps), "episodes_eval_or_grader": any_ep,
                         "episodes_eval": ev_ep, "episodes_grader": gr_ep, "reasoning_chars": chars,
                         "eval_per_1k": round(1000 * ev / chars, 3) if chars else None,
                         "grader_per_1k": round(1000 * gr / chars, 3) if chars else None})
    for r in rows:
        print(f"{r['text']:40} {r['messages']:18} episodes {r['episodes']:2} | EVAL or GRADER {r['episodes_eval_or_grader']}/"
              f"{r['episodes']} (EVAL {r['episodes_eval']}, GRADER {r['episodes_grader']}) | per 1k chars: EVAL "
              f"{r['eval_per_1k']}, GRADER {r['grader_per_1k']} | {r['reasoning_chars']} chars")
    (ROOT / "logs" / "grader" / "d1_search_inepisode.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
