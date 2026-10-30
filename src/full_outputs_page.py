"""Build a local (unpublished) HTML page: each quote card from the SoRH write-up, with the full REPLY of its record under
it, and its full REASONING, each in an open/close toggle. Her explicit request (27 Oct): "i need all reasoning copied in
the page". The page is local and unpublished, for her to read; text is copied by reference and never printed by this
script (only lengths are printed), so no agent reads it.

    python src/full_outputs_page.py <cards.json> <out.html>

cards.json: agent 9's list, [{"card", "finding", "model", "cell_label", "kind", "kn", "file_line"}], where file_line is
"<absolute path>:<1-based line>" as on the SoRH page's "Full record" pointers.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_FIELDS = [("reply", "Full reply"), ("reasoning", "Full reasoning")]


def record_at(path: Path, line: int) -> dict:
    if path.suffix == ".json":  # one record per file (SoRH raw replies)
        return json.load(open(path))
    with open(path) as f:
        for i, raw in enumerate(f, 1):
            if i == line:
                return json.loads(raw)
    raise IndexError(f"{path}:{line} not found")


def full_prompt(path: Path, rec: dict) -> str:
    """What the model was sent for this reply. SoRH runs use no system prompt (agent 1's sorh_ablate, agent 3's sorh_mt).
    Single-turn: the one user message. Multi-turn (agent 3's sorh_mt): each record's `prompt` is the message sent that
    turn and earlier replies go back as visible text only, so the conversation is rebuilt from the same episode's
    earlier rows (same stage, prompt_id, arm, sample)."""
    turn = rec.get("turn") or 1
    if turn == 1 or path.suffix == ".json":
        return f"[User]\n{rec.get('prompt', '')}"
    key = (rec.get("stage"), rec.get("prompt_id"), rec.get("arm"), rec.get("sample"))
    earlier = {}
    with open(path) as f:
        for raw in f:
            r = json.loads(raw)
            if (r.get("stage"), r.get("prompt_id"), r.get("arm"), r.get("sample")) == key and (r.get("turn") or 1) < turn:
                earlier.setdefault(r["turn"], r)
    if sorted(earlier) != list(range(1, turn)):
        raise ValueError(f"{path}: turns {sorted(earlier)} found for {key}, expected 1..{turn - 1}")
    parts = []
    for t in range(1, turn):
        parts += [f"[User, turn {t}]\n{earlier[t].get('prompt', '')}", f"[Assistant, turn {t}: visible reply]\n{earlier[t].get('reply', '')}"]
    parts.append(f"[User, turn {turn}]\n{rec.get('prompt', '')}")
    return "\n\n".join(parts)


def card_html(c: dict) -> str:
    path, line = c["file_line"].rsplit(":", 1)
    c = dict(c, file=path, line=int(line), label=c.get("cell_label", ""))
    rec = record_at(Path(path), int(line))
    prompt = full_prompt(Path(path), rec)
    blocks = [f'<details{" open" if len(prompt) <= 2000 else ""}><summary>Full prompt '
              f'<span class="n">(no system prompt; {len(prompt):,} characters)</span></summary>'
              f'<pre>{html.escape(prompt)}</pre></details>']
    lengths = [f"prompt {len(prompt):,}"]
    for key, title in TEXT_FIELDS:
        val = rec.get(key)
        if isinstance(val, str) and val:
            lengths.append(f"{key} {len(val):,}")
            blocks.append(f'<details><summary>{title} <span class="n">({len(val):,} characters)</span></summary>'
                          f'<pre>{html.escape(val)}</pre></details>')
        else:
            blocks.append(f'<p class="none">{title}: not recorded</p>')
    print(f"card {c['card']}: {c['file']}:{c['line']} -> " + (", ".join(lengths) or "no text fields"))
    pad = c.get("padded")
    stripe = "pad" if pad else "nopad"
    excerpt = c.get("excerpt") or ""
    facts = [str(c[k]) for k in ("reply_type", "counts", "density") if c.get(k)]
    if pad is not None:
        facts.insert(0, "padded" if pad else "not padded")
    return (f'<article class="card {stripe}"><header><span class="m">#{c["card"]} {html.escape(str(c.get("model", "")))}</span> · '
            f'{html.escape(str(c.get("label", "")))} <span class="kn">{html.escape(str(c.get("kn", "")))}</span>'
            f'<span class="src">{html.escape(c["file"])}:{c["line"]}</span></header>'
            + (f'<p class="facts">{html.escape(" · ".join(facts))}</p>' if facts else "")
            + (f'<blockquote>{html.escape(excerpt)}</blockquote>' if excerpt else "") + "".join(blocks) + "</article>")


STYLE = """
:root{--bg:#fff;--fg:#1d2126;--muted:#5f6670;--line:#e3e5e8;--soft:#f4f5f7;--pad:#c4672f;--nopad:#9aa1aa}
@media (prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#e7e9ec;--muted:#a0a7b0;--line:#2c3036;--soft:#1d2024;--pad:#e08a55;--nopad:#6b7280}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0}
.wrap{max-width:1000px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.15rem;margin:32px 0 10px}
.sub{color:var(--muted);margin:0 0 16px}
.card{border:1px solid var(--line);border-left:4px solid var(--nopad);border-radius:8px;padding:12px 14px;margin:0 0 14px}
.card.pad{border-left-color:var(--pad)}
header{font-size:.9rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline}
header .m{color:var(--fg);font-weight:600}.kn{font-variant-numeric:tabular-nums}.src{margin-left:auto;font:12px ui-monospace,Menlo,monospace}
blockquote{margin:8px 0;padding:8px 12px;background:var(--soft);border-radius:6px;white-space:pre-wrap}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}.n{color:var(--muted);font-weight:400}
pre{white-space:pre-wrap;word-break:break-word;background:var(--soft);border-radius:6px;padding:10px 12px;font:13px/1.45 ui-monospace,Menlo,monospace;max-height:70vh;overflow:auto}
.none{color:var(--muted);font-size:.9rem;margin:4px 0}
.facts{margin:6px 0 0;font-size:.9rem;color:var(--muted);font-variant-numeric:tabular-nums}
"""


def main():
    cards = json.load(open(sys.argv[1]))
    out = Path(sys.argv[2])
    by_finding = {}
    for c in cards:
        by_finding.setdefault(c.get("finding", "other"), []).append(c)
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>SoRH Full Outputs</title><style>{STYLE}</style></head><body><div class='wrap'>",
             "<h1>SoRH full outputs</h1><p class='sub'>Each quote card from the four-model SoRH page (same numbers), "
             "including the \"Nobody will score\" cards and every Mean requests table row, with the padded flag and "
             "density line from the page, the full prompt the model was sent (multi-turn: the whole conversation), and "
             "the model's full reply and full reasoning under it: click to open or "
             "close. Local file, not published; copied from the run records without being read.</p>"]
    for finding, cs in by_finding.items():
        parts.append(f"<h2>{html.escape(str(finding))}</h2>")
        parts += [card_html(c) for c in cs]
    parts.append("</div></body></html>")
    out.write_text("".join(parts))
    print(f"wrote {out} ({len(cards)} cards)")


if __name__ == "__main__":
    main()
