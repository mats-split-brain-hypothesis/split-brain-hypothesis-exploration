"""Build a LOCAL (unpublished) HTML page with one example per result on the IB four-model page: the full prompt, the
full visible conversation (replies, tool calls, tool results, later user messages) and the full reasoning, each in an
open/close toggle. Her explicit request (27 Oct): "I need the prompt, full reply and full reasoning example for each".
The examples are chosen by agents 4 and 11 from metadata only, by a fixed rule (first task in the order lcbhard_101,
27, 40, 58, 63, 99, first complete epoch, regardless of outcome). Text is copied by reference and never printed by this
script (only lengths are printed), so no agent reads it. Never publish the output.

    python src/ib_full_outputs_page.py <out.html> <examples.json> [<examples.json> ...]

Each examples file is a JSON list of rows with at least: finding, model, arm_label, task, outcome, log_path and either
sample_id + epoch (an Inspect .eval log) or record (a JSON-lines file: {"line": n} or {"key": field, "value": v}).
Optional: chart, epoch, point, source_log, source_sample, rounds (a list of records for multi-round chats).
"""
import html
import json
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log_sample

sys.path.insert(0, str(Path(__file__).resolve().parent))
from full_outputs_page import STYLE  # noqa: E402  (same look as her SoRH page)


def _text_parts(content):
    """(visible text, reasoning text) of a message's content."""
    if isinstance(content, str):
        return content, ""
    vis, rea = [], []
    for part in content:
        kind = type(part).__name__
        if kind == "ContentReasoning":
            r = getattr(part, "reasoning", "") or ""
            if not r and getattr(part, "redacted", False):
                r = "[reasoning redacted by the provider]"
            rea.append(r)
        elif hasattr(part, "text"):
            vis.append(part.text or "")
        else:
            vis.append(f"[{kind}]")
    return "\n".join(vis), "\n\n".join(x for x in rea if x)


def from_eval(row):
    s = read_eval_log_sample(row["log_path"], row["sample_id"], int(row.get("epoch") or 1), resolve_attachments=True)
    msgs = s.messages
    prompt, visible, reasoning = [], [], []
    seen_user = 0
    turn = 0
    for m in msgs:
        vis, rea = _text_parts(m.content)
        if m.role == "system":
            prompt.append(f"[System]\n{vis}")
        elif m.role == "user" and seen_user == 0:
            seen_user = 1
            prompt.append(f"[User]\n{vis}")
        elif m.role == "user":
            visible.append(f"[User, later message]\n{vis}")
        elif m.role == "assistant":
            turn += 1
            block = [f"[Assistant, turn {turn}]"]
            if vis.strip():
                block.append(vis)
            for tc in getattr(m, "tool_calls", None) or []:
                args = tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments, indent=2, ensure_ascii=False)
                block.append(f"[Tool call: {tc.function}]\n{args}")
            visible.append("\n".join(block))
            reasoning.append(f"[Turn {turn}]\n{rea}" if rea else f"[Turn {turn}]\n(no reasoning recorded)")
        elif m.role == "tool":
            visible.append(f"[Tool result: {getattr(m, 'function', '') or ''}]\n{vis}")
    return "\n\n".join(prompt), "\n\n".join(visible), "\n\n".join(reasoning), turn


def _jsonl_record(path, rec):
    with open(path) as f:
        for i, raw in enumerate(f, 1):
            if "line" in rec and i == int(rec["line"]):
                return json.loads(raw)
            if "key" in rec:
                r = json.loads(raw)
                if str(r.get(rec["key"])) == str(rec["value"]):
                    return r
    raise KeyError(f"{path}: record {rec} not found")


def from_jsonl(row):
    """Single replies or multi-round chats stored one record per line with prompt/reply/reasoning fields."""
    recs = row.get("rounds") or [row["record"]]
    prompt, visible, reasoning = [], [], []
    for k, rec in enumerate(recs, 1):
        r = _jsonl_record(rec.get("log_path", row["log_path"]), rec)
        p = r.get("prompt") or r.get("messages") or ""
        if not isinstance(p, str):
            p = json.dumps(p, indent=2, ensure_ascii=False)
        (prompt if k == 1 else visible).append(f"[User, round {k}]\n{p}")
        visible.append(f"[Assistant, round {k}]\n{r.get('reply') or r.get('output') or ''}")
        reasoning.append(f"[Round {k}]\n{r.get('reasoning') or '(no reasoning recorded)'}")
    return "\n\n".join(prompt), "\n\n".join(visible), "\n\n".join(reasoning), len(recs)


def from_eval_rounds(row):
    """A multi-round chat stored as several Inspect samples (agent 11's rejection rounds: round 1 is the homework
    sample, rounds 2-3 one rejection sample whose input repeats round 1 as visible text). Each distinct sample is
    rendered once, under its own heading, in round order."""
    seen, prompt, visible, reasoning, turns = [], "", [], [], 0
    for rd in sorted(row["rounds"], key=lambda r: r["round"]):
        key = (rd["log_path"], rd["sample_id"], int(rd.get("epoch") or 1))
        if key in seen:
            continue
        seen.append(key)
        rounds_here = [r["round"] for r in row["rounds"] if (r["log_path"], r["sample_id"]) == key[:2]]
        head = f"=== Sample {rd['sample_id']} (rounds {', '.join(map(str, rounds_here))}) ==="
        p, v, r, t = from_eval({"log_path": rd["log_path"], "sample_id": rd["sample_id"], "epoch": key[2]})
        if not prompt:
            prompt = p
        else:
            v = f"[Its input begins with the same prompt as above]\n\n{v}"
        visible.append(f"{head}\n\n{v}")
        reasoning.append(f"{head}\n\n{r}")
        turns += t
    return prompt, "\n\n".join(visible), "\n\n".join(reasoning), turns


def _outcome(row):
    if row.get("outcome"):
        return str(row["outcome"])
    if "hacked_round" in row:
        bits = [f"rounds run {row.get('rounds_run')}",
                f"hacked at round {row['hacked_round']}" if row["hacked_round"] else "not hacked (registered rule)"]
        if row.get("hacked_round_fixed_extraction") != row.get("hacked_round"):
            bits.append(f"fixed extraction: hacked at round {row.get('hacked_round_fixed_extraction')}")
        if row.get("rule_pick") is False:
            bits.append("NOT the rule's pick: " + str(row.get("why_listed", "listed as the next conversation")))
        return "; ".join(bits)
    return ""


def card(n, row):
    if row.get("rounds") and all(str(r.get("log_path", "")).endswith(".eval") for r in row["rounds"]):
        prompt, visible, reasoning, turns = from_eval_rounds(row)
        where = "; ".join(f"round {r['round']}: {r['log_path']} :: {r['sample_id']}" for r in row["rounds"])
    elif row["log_path"].endswith(".eval"):
        prompt, visible, reasoning, turns = from_eval(row)
        where = f"{row['log_path']} :: {row.get('sample_id', '')}"
    else:
        prompt, visible, reasoning, turns = from_jsonl(row)
        where = f"{row['log_path']} :: {row.get('record', '')}"
    print(f"card {n}: {row.get('model')} | {row.get('arm_label')} -> prompt {len(prompt):,}, visible {len(visible):,}, "
          f"reasoning {len(reasoning):,}, turns {turns}")
    facts = [x for x in (row.get("task"), f"epoch {row['epoch']}" if row.get("epoch") else None,
                         f"rep {row['rep']}" if row.get("rep") else None, _outcome(row)) if x]
    src = html.escape(where)
    extra = ""
    if row.get("source_log"):
        extra = (f'<p class="facts">Continuation of point {html.escape(str(row.get("point", "")))}, cut from '
                 f'{html.escape(str(row["source_log"]))} :: {html.escape(str(row.get("source_sample", "")))}. '
                 f'The conversation below includes that cut prefix.</p>')
    blocks = []
    for title, val, opened in (("Full prompt (system + first user message)", prompt, len(prompt) <= 4000),
                               (f"Full conversation, visible ({turns} turns: replies, tool calls, tool results)", visible, False),
                               ("Full reasoning (per turn)", reasoning, False)):
        blocks.append(f'<details{" open" if opened else ""}><summary>{title} <span class="n">({len(val):,} characters)'
                      f'</span></summary><pre>{html.escape(val)}</pre></details>')
    return (f'<article class="card nopad"><header><span class="m">#{n} {html.escape(str(row.get("model", "")))}</span> · '
            f'{html.escape(str(row.get("arm_label", "")))}<span class="src">{src}</span></header>'
            f'<p class="facts">{html.escape(" · ".join(facts))}</p>{extra}' + "".join(blocks) + "</article>")


def main():
    out = Path(sys.argv[1])
    rows = []
    for f in sys.argv[2:]:
        rows += json.load(open(f))
    groups = {}
    for r in rows:
        groups.setdefault(r.get("chart") or r.get("finding") or "other", []).append(r)
    parts = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>IB Full Outputs</title><style>{STYLE}</style></head><body><div class='wrap'>",
             "<h1>ImpossibleBench full outputs</h1><p class='sub'>One example per result on the four-model IB page, chosen "
             "by a fixed rule (first task in the order lcbhard_101, 27, 40, 58, 63, 99, first complete epoch, regardless of "
             "outcome), with the full prompt, the full visible conversation and the full reasoning: click to open or close. "
             "Local file, not published; copied from the run logs without being read.</p>"]
    n = 0
    for g, rs in groups.items():
        parts.append(f"<h2>{html.escape(str(g))}</h2>")
        for r in rs:
            n += 1
            parts.append(card(n, r))
    parts.append("</div></body></html>")
    out.write_text("".join(parts))
    print(f"wrote {out} ({n} examples)")


if __name__ == "__main__":
    main()
