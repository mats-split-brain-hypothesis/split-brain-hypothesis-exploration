"""Build a LOCAL (never published) static site for reading every result by hand: one page per statement and prompt/task,
with each version as a row and each model as a column, side by side. Every card holds the full prompt, the full reply or
conversation, and the full reasoning, in open/close toggles. Her request (27 Oct): "a dashboard where I can see each
prompt side by side for each investigation/statement, fully response dumped, don't need any agent to read it, so I can
analyse everything by hand". Text is copied unread: this script prints only counts and lengths.

    python src/handview_site.py <out_dir> <manifest.json> [<manifest.json> ...]

Manifest rows (metadata only, written by the data owners): benchmark, statement, statement_title, unit, unit_label,
version, version_label, model, rep (or epoch), labels (dict or str), and source:
  {"kind": "jsonl", "path", "line"}  |  {"kind": "json", "path"}  |  {"kind": "eval", "path", "sample_id", "epoch"}
  |  {"kind": "turns", "turns": [{"path", "line", "turn"}, ...]}   (multi-turn SoRH conversations)
  |  {"kind": "rounds", "rounds": [{"round", "path", "sample_id", "epoch"}, ...]}   (IB rejection conversations)
Older example rows (log_path / sample_id / epoch / rounds, chart / arm_label / task) are accepted too.
"""
import html
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from full_outputs_page import STYLE as BASE_STYLE, record_at  # noqa: E402
from ib_full_outputs_page import _text_parts, from_eval, from_eval_rounds  # noqa: E402
from inspect_ai.log import read_eval_log_sample  # noqa: E402

MODEL_ORDER = ["qwen 3.8 2.4t", "qwen 3.8 max", "deepseek", "glm", "qwen 3.8 27b"]

STYLE = BASE_STYLE + """
.wrap{max-width:none;padding:20px 16px 60px}
.grid{display:grid;gap:10px;align-items:start}
.vrow{margin:18px 0 6px;font-weight:700;font-size:1rem;border-top:2px solid var(--line);padding-top:10px}
.cell{min-width:0}
.colhead{font-weight:700;font-size:.9rem;color:var(--muted);position:sticky;top:0;background:var(--bg);padding:4px 0;z-index:1}
.card{margin:0 0 8px;padding:8px 10px}
.reply{white-space:pre-wrap;word-break:break-word;background:var(--soft);border-radius:6px;padding:8px 10px;
  font:13px/1.45 ui-monospace,Menlo,monospace;max-height:55vh;overflow:auto;margin:6px 0}
.nav{display:flex;gap:12px;flex-wrap:wrap;font-size:.9rem;margin:6px 0 10px}
a{color:inherit}
table.idx{border-collapse:collapse;font-size:.9rem}table.idx td,table.idx th{border:1px solid var(--line);padding:4px 8px;text-align:left}
.episode{max-height:85vh;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:6px 8px;margin:6px 0}
.blk{border-left:4px solid var(--line);background:var(--soft);border-radius:6px;padding:6px 9px;margin:7px 0}
.blk .bh{font-weight:700;font-size:.85rem;margin-bottom:4px}
.blk pre{margin:4px 0;max-height:60vh}
.blk.asst{border-left-color:#5b7cfa}
.blk.res{border-left-color:#9aa1aa;background:transparent;border:1px dashed var(--line);border-left:4px solid #9aa1aa}
.blk.rej{border-left-color:#d9534f;background:rgba(217,83,79,.12)}
.blk.rej .bh{color:#c0392b}
.blk.msg{border-left-color:#e0a030;background:rgba(224,160,48,.12)}
.blk.usr,.blk.sys{border-left-color:#7a7a7a}
.blk.off{border-left-color:#8e44ad;background:rgba(142,68,173,.16)}
.blk.off .bh{color:#8e44ad}
.blk.nudge{border-left-color:#c8c8c8;background:transparent;opacity:.75}
.blk.end{border-left-color:#333;background:rgba(120,120,120,.14)}
.sibling{border:1px solid var(--line);border-left:4px solid #e0a030;border-radius:6px;padding:8px 10px;margin:8px 0;font-size:.92rem}
.badge{background:#2e7d32;color:#fff;border-radius:4px;padding:1px 7px;font-size:.75rem;margin-left:6px}
.said{white-space:pre-wrap;word-break:break-word;margin:6px 0;font-size:.92rem}
.tc{margin:6px 0}.tch{font:600 12px ui-monospace,Menlo,monospace;color:var(--muted)}
.divider{margin:12px 0 4px;font-weight:700;font-size:.85rem;color:var(--muted);border-top:1px solid var(--line);padding-top:6px}
.toggle{font:inherit;font-size:.85rem;padding:3px 10px;border:1px solid var(--line);border-radius:6px;background:var(--soft);color:var(--fg);cursor:pointer}
body.stacked .grid{grid-template-columns:1fr !important}
body.stacked .colhead{display:none}
"""


def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-")[:60] or "x"


def _model_key(m):
    ml = str(m).lower()
    for i, k in enumerate(MODEL_ORDER):
        if ml.startswith(k) or k in ml:
            return (min(i, 3) if i > 0 else 0, ml)
    return (9, ml)


def _norm(row):
    """Fill the standard fields from older example rows."""
    r = dict(row)
    if isinstance(r.get("statement"), dict):  # agent 1's rows: {"id", "title"}
        st = r["statement"]
        r["statement"], r["statement_title"] = st.get("id"), st.get("title")
    r.setdefault("benchmark", "IB" if (str(r.get("log_path", "")).endswith(".eval") or r.get("rounds")) else "SoRH")
    r["statement"] = r.get("statement") or r.get("chart") or r.get("finding") or "other"
    r["statement_title"] = r.get("statement_title") or r["statement"]
    if r.get("section"):  # agent 4's #1 rows: keep "told before" and "told after" apart
        r["statement"] = f"{r['statement']} | {r['section']}"
        r["statement_title"] = f"{r['statement_title']} | {r['section']}"
    if isinstance(r.get("chart"), dict):  # agent 11's rows: one statement per chart within a page section
        ch = r["chart"]
        r["statement"] = f"{r['statement']} | {ch.get('id')}"
        r["statement_title"] = f"{r['statement_title']} | {ch.get('title')}"
    if r.get("rounds") and not r.get("source"):  # agent 11's rounds: each round carries its own source
        rounds = []
        for rd in r["rounds"]:
            s = rd.get("source") or {}
            rounds.append({"round": rd.get("round"), "log_path": rd.get("log_path") or s.get("path"),
                           "sample_id": rd.get("sample_id") or s.get("sample_id"), "epoch": rd.get("epoch") or s.get("epoch", 1)})
        r["source"] = {"kind": "rounds", "rounds": rounds}
    unit = r.get("unit")
    if unit in (None, "", "task", "prompt") and (r.get("task") or r.get("prompt_id")):  # agent 4: unit names the kind
        unit = r.get("task") or r.get("prompt_id")
    r["unit"] = unit or "?"
    r["unit_label"] = r.get("unit_label") or r["unit"]
    r["version_label"] = r.get("version_label") or r.get("arm_label") or r.get("version") or "?"
    r["rep"] = r.get("rep") if r.get("rep") is not None else r.get("epoch", 1)
    src = r.get("source")
    if isinstance(src, list):  # agent 3's multi-turn rows: [{path, line, turn}, ...]
        src = {"kind": "turns", "turns": src}
    if not src:
        if r.get("rounds"):
            src = {"kind": "rounds", "rounds": r["rounds"]}
        elif str(r.get("log_path", "")).endswith(".eval"):
            src = {"kind": "eval", "path": r["log_path"], "sample_id": r.get("sample_id"), "epoch": r.get("epoch", 1)}
        elif r.get("file_line"):
            p, ln = r["file_line"].rsplit(":", 1)
            src = {"kind": "json" if p.endswith(".json") else "jsonl", "path": p, "line": int(ln)}
    r["source"] = src
    return r


def load(src):
    """(prompt, visible conversation or reply, reasoning, is_single_reply)."""
    k = src.get("kind")
    if k in ("jsonl", "json"):
        rec = record_at(Path(src["path"]), int(src.get("line") or 1))
        return f"[User]\n{rec.get('prompt', '')}", rec.get("reply") or "", rec.get("reasoning") or "", True
    if k == "eval":
        p, v, r, _ = from_eval({"log_path": src["path"], "sample_id": src["sample_id"], "epoch": src.get("epoch", 1)})
        return p, v, r, False
    if k == "rounds":
        p, v, r, _ = from_eval_rounds({"rounds": src["rounds"]})
        return p, v, r, False
    if k == "turns":
        conv, rea, prompt = [], [], ""
        for t in sorted(src["turns"], key=lambda t: t.get("turn", 0)):
            rec = record_at(Path(t["path"]), int(t["line"]))
            n = t.get("turn", len(conv) // 2 + 1)
            if not prompt:
                prompt = f"[User, turn {n}]\n{rec.get('prompt', '')}"
            else:
                conv.append(f"[User, turn {n}]\n{rec.get('prompt', '')}")
            conv.append(f"[Assistant, turn {n}]\n{rec.get('reply') or ''}")
            rea.append(f"[Turn {n}]\n{rec.get('reasoning') or '(no reasoning recorded)'}")
        return prompt, "\n\n".join(conv), "\n\n".join(rea), False
    raise ValueError(f"unknown source kind: {src}")


REJECT = re.compile(r"^(Your implementation failed the tests|I submitted it and the autograder says it failed)", re.I)
SCORE = re.compile(r"Score:\s*\d+\s*/\s*10")
GRADING_OFF = re.compile(r"grading is (switched|turned) off|grading (has been )?(switched|turned) off", re.I)
NUDGE = re.compile(r"^Please proceed to the next step", re.I)


def _esc(s):
    return html.escape(s or "")


def _pre(text, fold_over=4000):
    t = text or ""
    if len(t) > fold_over:
        return f'<details><summary>show all ({len(t):,} characters)</summary><pre>{_esc(t)}</pre></details>'
    return f"<pre>{_esc(t)}</pre>"


def _blk(cls, title, inner):
    return f'<div class="blk {cls}"><div class="bh">{title}</div>{inner}</div>'


def _tool_args(tc):
    a = tc.arguments
    if isinstance(a, str):
        return a
    if isinstance(a, dict) and len(a) == 1:
        (only,) = a.values()
        if isinstance(only, str):
            return only
    parts = []
    for k, v in (a or {}).items():
        v = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        parts.append(f"{k}:\n{v}" if ("\n" in v or len(v) > 80) else f"{k}: {v}")
    return "\n".join(parts)


def eval_blocks(path, sample_id, epoch, skip_first_exchange=False, counters=None):
    """One Inspect sample as turn blocks: reasoning (toggle), visible text, tool calls, results, rejections."""
    c = counters if counters is not None else {"turn": 0, "sub": 0, "rej": 0, "chars": 0}
    s = read_eval_log_sample(path, sample_id, int(epoch or 1), resolve_attachments=True)
    msgs = list(s.messages)
    if skip_first_exchange:  # later samples of a multi-round chat repeat the round-1 prompt and reply as input
        first_a = next((i for i, m in enumerate(msgs) if m.role == "assistant"), -1)
        msgs = msgs[first_a + 1:]
    blocks, users = [], 0
    # Some multi-round runs (agent 11's rejection rounds) stored later replies as plain text, so the reasoning is only
    # in the model-call events; match those by the reply's visible text.
    def _sig(msg, vis):  # visible text plus tool calls: an empty-text tool turn must not match another turn
        return (vis.strip(), tuple((tc.function, json.dumps(tc.arguments, sort_keys=True, default=str))
                                   for tc in (getattr(msg, "tool_calls", None) or [])))
    ev_out = []
    for e in s.events or []:
        if type(e).__name__ == "ModelEvent" and getattr(e, "output", None) and e.output.choices:
            em = e.output.choices[0].message
            ev_vis, ev_rea = _text_parts(em.content)
            u = getattr(e.output, "usage", None)
            ev_out.append((_sig(em, ev_vis), ev_rea, getattr(u, "reasoning_tokens", None) if u else None))
    for m in msgs:
        vis, rea = _text_parts(m.content)
        from_events, billed = False, None
        if m.role == "assistant" and not rea:
            sig = _sig(m, vis)
            j = next((j for j, ev in enumerate(ev_out) if ev[1] and ev[0] == sig), None)
            if j is not None:
                rea, from_events = ev_out.pop(j)[1], True
            else:  # the call itself returned no reasoning text: say so, with the reasoning tokens it billed
                j = next((j for j, ev in enumerate(ev_out) if ev[0] == sig), None)
                if j is not None:
                    billed = ev_out.pop(j)[2]
        c["chars"] += len(vis) + len(rea)
        if m.role == "system":
            blocks.append(f'<details class="blk sys"><summary>System prompt ({len(vis):,})</summary><pre>{_esc(vis)}</pre></details>')
        elif m.role == "user":
            users += 1
            if users == 1 and not skip_first_exchange:
                blocks.append(f'<details class="blk usr"><summary>Task prompt ({len(vis):,})</summary><pre>{_esc(vis)}</pre></details>')
            elif REJECT.search(vis.strip()):
                c["rej"] += 1
                blocks.append(_blk("rej", f"✗ REJECTED · feedback #{c['rej']}", _pre(vis, 2500)))
            elif GRADING_OFF.search(vis):
                c["off"] = c.get("off", 0) + 1
                c.setdefault("off_before_turn", c["turn"] + 1)
                blocks.append(_blk("off", "⚑ GRADING-OFF MESSAGE (the intervention)", _pre(vis)))
            elif NUDGE.search(vis):
                blocks.append(_blk("nudge", "Harness nudge (sent because the model replied without a tool call)", _pre(vis)))
            else:
                blocks.append(_blk("msg", "Other message to the model (user / harness)", _pre(vis)))
        elif m.role == "assistant":
            c["turn"] += 1
            tcs = getattr(m, "tool_calls", None) or []
            badge = ""
            if any(tc.function == "submit" for tc in tcs):
                c["sub"] += 1
                badge = f' <span class="badge">SUBMISSION #{c["sub"]}</span>'
            src_note = " · from the run's model-call log" if from_events else ""
            if rea:
                inner = [f'<details><summary>Reasoning ({len(rea):,}{src_note})</summary><pre>{_esc(rea)}</pre></details>']
            elif billed:
                inner = [f'<p class="none">(the provider returned no reasoning text for this call, though it billed '
                         f'{billed:,} reasoning tokens; the API response has "reasoning": null)</p>']
            elif (s.metadata or {}).get("prefix_path"):
                inner = ['<p class="none">(no reasoning recorded: this turn is in the replayed start of the episode, copied '
                         'from the original run, where the call returned no reasoning text)</p>']
            else:
                inner = ['<p class="none">(no reasoning recorded for this message)</p>']
            if vis.strip():
                inner.append(f'<div class="said">{_esc(vis)}</div>')
            for tc in tcs:
                inner.append(f'<div class="tc"><div class="tch">▶ {_esc(tc.function)}</div>{_pre(_tool_args(tc), 6000)}</div>')
            blocks.append(_blk("asst", f"Turn {c['turn']}{badge}", "".join(inner)))
        elif m.role == "tool":
            blocks.append(_blk("res", f"Result · {_esc(getattr(m, 'function', '') or '')}", _pre(vis, 2500)))
    end = _end_note(s, msgs, c)
    if end:
        blocks.append(_blk("end", "■ EPISODE ENDED", f"<p>{_esc(end)}</p>"))
    return blocks, c


def _end_note(s, msgs, c):
    """Why the episode stops where it does, so a missing 'failed' message isn't mistaken for a gap."""
    score = next((str(v.value) for v in (s.scores or {}).values()), None)
    sc = f" Score: {score}." if score else ""
    lim = getattr(s, "limit", None)
    if lim:
        return f"Stopped by the {getattr(lim, 'type', 'run')} limit ({getattr(lim, 'limit', '')}); no further reply.{sc}"
    last = msgs[-1] if msgs else None
    if last is not None and last.role == "user":
        return f"The episode stopped here, before the model's next reply; no further submission. The final files were scored.{sc}"
    if not (last is not None and last.role == "tool" and getattr(last, "function", "") == "submit"):
        return ""
    if c.get("off"):
        return ("Grading was off after the purple message, so this submission ended the episode with no reply to the "
                f"model; the final files were scored silently.{sc}")
    if score == "C":
        return ("This submission passed the tests, which ends the episode with no reply to the model. The tests are "
                "impossible, so a pass means a hack. Score: C (passed).")
    cap = (s.metadata or {}).get("max_attempts") or 10
    if c["sub"] >= int(cap):
        return f"This was submission {c['sub']}, the limit, so the episode ended with no reply to the model.{sc}"
    return f"The episode ended after this submission with no reply to the model.{sc}"


def rounds_blocks(rounds):
    c = {"turn": 0, "sub": 0, "rej": 0, "chars": 0}
    seen, blocks = [], []
    for rd in sorted(rounds, key=lambda r: r.get("round") or 0):
        key = (rd["log_path"], rd["sample_id"], int(rd.get("epoch") or 1))
        if key in seen:
            continue
        here = [str(r.get("round")) for r in rounds if (r["log_path"], r["sample_id"]) == key[:2]]
        blocks.append(f'<div class="divider">Sample {_esc(rd["sample_id"])} · round(s) {", ".join(here)}</div>')
        b, c = eval_blocks(*key, skip_first_exchange=bool(seen), counters=c)
        blocks += b
        seen.append(key)
    return blocks, c


def turns_blocks(turns):
    c = {"turn": 0, "sub": 0, "rej": 0, "chars": 0}
    blocks = []
    for t in sorted(turns, key=lambda t: t.get("turn", 0)):
        rec = record_at(Path(t["path"]), int(t["line"]))
        msg, reply, rea = rec.get("prompt") or "", rec.get("reply") or "", rec.get("reasoning") or ""
        c["chars"] += len(msg) + len(reply) + len(rea)
        n = t.get("turn")
        if c["turn"] == 0:
            blocks.append(f'<details class="blk usr"><summary>Request ({len(msg):,})</summary><pre>{_esc(msg)}</pre></details>')
        elif SCORE.search(msg):
            c["rej"] += 1
            blocks.append(_blk("rej", f"Score feedback before turn {n}", _pre(msg)))
        else:
            blocks.append(_blk("msg", f"Message before turn {n}", _pre(msg)))
        c["turn"] += 1
        inner = [f'<details><summary>Reasoning ({len(rea):,})</summary><pre>{_esc(rea)}</pre></details>' if rea
                 else '<p class="none">(no reasoning recorded)</p>', f'<div class="said">{_esc(reply) or "<i>(no reply)</i>"}</div>']
        blocks.append(_blk("asst", f"Turn {n}", "".join(inner)))
    return blocks, c


def _labels(row):
    lab = row.get("labels")
    if isinstance(lab, dict):
        return " · ".join(f"{k} {v}" for k, v in lab.items() if v not in (None, ""))
    return str(lab or row.get("outcome") or "")


def card(row, stats):
    if not row.get("source"):  # a gap the owner recorded (e.g. no record exists): show it, don't hide it
        stats["cards"] += 1
        return (f'<article class="card"><p class="facts">rep {html.escape(str(row["rep"]))} · {html.escape(_labels(row))}</p>'
                f'<p class="none">No record: missing (see labels).</p></article>')
    src_d = row["source"]
    head = (f'<b>{html.escape(str(row.get("model", "")))}</b> · rep {html.escape(str(row["rep"]))}'
            + (f' · {html.escape(_labels(row))}' if _labels(row) else ""))
    if src_d.get("kind") in ("eval", "rounds", "turns"):
        try:
            if src_d["kind"] == "eval":
                blocks, c = eval_blocks(src_d["path"], src_d["sample_id"], src_d.get("epoch", 1))
            elif src_d["kind"] == "rounds":
                blocks, c = rounds_blocks(src_d["rounds"])
            else:
                blocks, c = turns_blocks(src_d["turns"])
        except Exception as e:
            stats["cards"] += 1
            return (f'<article class="card"><p class="facts">{head}</p>'
                    f'<p class="none">record not loaded: {type(e).__name__}</p></article>')
        stats["cards"] += 1
        stats["chars"] += c["chars"]
        summ = (f'{c["turn"]} turns' + (f' · {c["sub"]} submissions' if c["sub"] else "")
                + (f' · {c["rej"]} {"rejections" if src_d["kind"] != "turns" else "score messages"}' if c["rej"] else "")
                + (f' · ⚑ grading-off message before turn {c["off_before_turn"]}' if c.get("off_before_turn") else ""))
        return (f'<article class="card"><p class="facts">{head}</p><p class="facts"><b>{summ}</b></p>'
                f'<div class="episode">{"".join(blocks)}</div>'
                f'<p class="facts" title="source">{html.escape(json.dumps(src_d)[:300])}</p></article>')
    try:
        prompt, visible, reasoning, single = load(row["source"])
        err = ""
    except Exception as e:  # missing record: show the gap, don't hide it
        prompt = visible = reasoning = ""
        single, err = True, f"record not loaded: {type(e).__name__}"
    stats["cards"] += 1
    stats["chars"] += len(prompt) + len(visible) + len(reasoning)
    src = html.escape(json.dumps(row["source"])[:300])
    head = (f'<b>{html.escape(str(row.get("model", "")))}</b> · rep {html.escape(str(row["rep"]))}'
            + (f' · {html.escape(_labels(row))}' if _labels(row) else ""))
    body = [f'<details><summary>Full prompt <span class="n">({len(prompt):,})</span></summary><pre>{html.escape(prompt)}</pre></details>']
    if single:
        body.append(f'<div class="reply">{html.escape(visible) or "<i>(no reply)</i>"}</div>')
    else:
        body.append(f'<details><summary>Full conversation <span class="n">({len(visible):,})</span></summary>'
                    f'<pre>{html.escape(visible)}</pre></details>')
    body.append(f'<details><summary>Full reasoning <span class="n">({len(reasoning):,})</span></summary>'
                f'<pre>{html.escape(reasoning)}</pre></details>')
    if err:
        body.append(f'<p class="none">{err}</p>')
    return f'<article class="card"><p class="facts">{head}</p>{"".join(body)}<p class="facts" title="source">{src}</p></article>'


def page(title, inner, back):
    return (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body><div class='wrap'>"
            f"<div class='nav'>{back} <button class='toggle' onclick=\"document.body.classList.toggle('stacked')\">"
            f"Switch: side by side / one under another</button></div>{inner}</div></body></html>")


def main():
    out = Path(sys.argv[1])
    rows = []
    for f in sys.argv[2:]:
        data = json.load(open(f))
        if isinstance(data, dict):  # {"about": ..., "rows": [...]}
            data = data.get("rows", [])
        rows += [_norm(r) for r in data]
    tree = OrderedDict()  # (benchmark, statement) -> unit -> version -> model -> [rows]
    for r in rows:
        tree.setdefault((r["benchmark"], r["statement"]), {"title": r["statement_title"], "units": OrderedDict()})
        u = tree[(r["benchmark"], r["statement"])]["units"].setdefault(r["unit"], {"label": r["unit_label"], "v": OrderedDict()})
        u["v"].setdefault(r["version_label"], {}).setdefault(r["model"], []).append(r)
    out.mkdir(parents=True, exist_ok=True)
    stats = {"cards": 0, "chars": 0, "pages": 0}
    idx = ["<h1>Hand-analysis viewer</h1><p class='sub'>Every prompt or task, side by side per statement: versions as rows, "
           "models as columns, with the full prompt, reply or conversation, and reasoning in toggles. Local only, never "
           "published; copied from the run records without being read.</p>"]
    # statements that share a title before " | " (e.g. homework first reply / the same chats after rejections) link
    # to each other's page for the same task
    family = {}
    for (bench, st), node in tree.items():
        family.setdefault((bench, str(node["title"]).split(" | ")[0]), []).append((st, node))
    for (bench, st), node in tree.items():
        sdir = out / _slug(bench) / _slug(st)
        sibs = [(s2, n2) for s2, n2 in family[(bench, str(node["title"]).split(" | ")[0])] if s2 != st]
        sdir.mkdir(parents=True, exist_ok=True)
        units = list(node["units"].items())
        idx.append(f"<h2>{html.escape(bench)} · {html.escape(node['title'])}</h2><p class='nav'>" + " ".join(
            f"<a href='{_slug(bench)}/{_slug(st)}/{_slug(u)}.html'>{html.escape(str(d['label']))}</a>" for u, d in units) + "</p>")
        for i, (u, d) in enumerate(units):
            models = sorted({m for v in d["v"].values() for m in v}, key=_model_key)
            cols = f"grid-template-columns:repeat({len(models)},minmax(260px,1fr))"
            sib_links = [f"<a href='../{_slug(s2)}/{_slug(u)}.html'>{html.escape(str(n2['title']).split(' | ')[-1])} →</a>"
                         for s2, n2 in sibs if u in n2["units"]]
            sib_html = (f"<div class='sibling'><b>Same {html.escape(str(d['label']))} on the related page:</b> "
                        + " · ".join(sib_links) + "</div>") if sib_links else ""
            inner = [f"<h1>{html.escape(bench)} · {html.escape(node['title'])}</h1><p class='sub'>{html.escape(str(d['label']))}</p>",
                     sib_html,
                     f"<div class='grid' style='{cols}'>" + "".join(f"<div class='colhead'>{html.escape(str(m))}</div>" for m in models) + "</div>"]
            for vlabel, bym in d["v"].items():
                inner.append(f"<div class='vrow'>{html.escape(str(vlabel))}</div><div class='grid' style='{cols}'>")
                for m in models:
                    cards = "".join(card(r, stats) for r in sorted(bym.get(m, []), key=lambda r: str(r["rep"])))
                    inner.append(f"<div class='cell'>{cards or '<p class=none>(none)</p>'}</div>")
                inner.append("</div>")
            nav = ["<a href='../../index.html'>All statements</a>"]
            if i > 0:
                nav.append(f"<a href='{_slug(units[i-1][0])}.html'>← {html.escape(str(units[i-1][1]['label']))}</a>")
            if i + 1 < len(units):
                nav.append(f"<a href='{_slug(units[i+1][0])}.html'>{html.escape(str(units[i+1][1]['label']))} →</a>")
            (sdir / f"{_slug(u)}.html").write_text(page(f"{st} · {d['label']}", "".join(inner), " · ".join(nav)))
            stats["pages"] += 1
    (out / "index.html").write_text(page("Hand-analysis viewer", "".join(idx), ""))
    print(f"wrote {out}/index.html: {len(tree)} statements, {stats['pages']} pages, {stats['cards']} cards, "
          f"{stats['chars']:,} characters copied (unread)")


if __name__ == "__main__":
    main()
