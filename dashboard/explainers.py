"""Live panels for a study card's "In depth" blocks (CARDS.md, ``explainer``): each block may name a ``panel`` here,
drawn beside (or under) its text from a study's precomputed numbers. A panel reads only small JSON files under
out/analysis/ (written by the study's own script), never captures or readouts, so the page stays fast.

- ``s14_tokens``, ``s14_norms``, ``s14_examples``: out/analysis/S14-explainer/explainer.json
  (``experiments/s14_explainer.py``).
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import sources
import ui

S14 = sources.ANALYSIS / "S14-explainer" / "explainer.json"


@st.cache_data(show_spinner=False)
def _load(path: str, _mtime: float) -> dict | None:
    p = sources._get(Path(path))
    return json.loads(p.read_text()) if p.exists() else None


def _s14() -> dict | None:
    d = _load(str(S14), S14.stat().st_mtime if S14.exists() else 0.0)
    if d is None:
        st.caption("No out/analysis/S14-explainer/explainer.json: run `python experiments/s14_explainer.py`.")
    return d


def _source_group(sources_: list[str]) -> str:
    s = " ".join(sources_)
    if "special" in s:
        return "chat template specials"
    if "decoded means" in s:
        return "strings the decoded reference means share"
    if "unigram" in s:
        return "chat corpus's most frequent tokens"
    return "hand list"


def _chip(text: str, cls: str = "") -> str:
    vis = text.replace("\n", "\\n") if text.strip() else (text.replace(" ", "␣") or "∅")
    return f'<span class="jm-chip{(" " + cls) if cls else ""}">{ui.esc(vis)}</span>'


def s14_tokens(key: str) -> None:
    """The first 64 template tokens (T), grouped by where they came from, in list order."""
    d = _s14()
    if not d:
        return
    groups: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for i, t in enumerate(d["tokens"]):
        groups[_source_group(t["sources"])].append((i + 1, t["text"]))
    order = ["chat template specials", "strings the decoded reference means share", "chat corpus's most frequent tokens",
             "hand list"]
    html = ""
    for g in order:
        if g in groups:
            html += (f'<div style="font-size:12px;color:var(--muted);margin:8px 0 4px">{ui.esc(g)} · {len(groups[g])}</div>'
                     '<div class="jm-chips" style="display:flex;flex-wrap:wrap;gap:4px">'
                     + "".join(f'<span title="#{i} in T">{_chip(t)}</span>' for i, t in groups[g]) + "</div>")
    st.html(html)
    st.caption(f"T₁..₆₄ (data/template_tokens/template.json; a token with several sources is listed under the first). "
               "␣ is a space; \\n a newline.")


def s14_norms(key: str) -> None:
    """Per layer, mean over families: the share of h's norm in B and in a random 64-dim subspace, the share of the family
    mean's norm in B, and how closely h's and the mean's template parts agree."""
    d = _s14()
    if not d:
        return
    fams = d["families"]
    pick = st.selectbox("Family", ["mean over families", *fams], key=f"{key}_fam", label_visibility="collapsed")
    use = list(fams) if pick == "mean over families" else [pick]
    Ls = sorted({int(L) for f in use for L in fams[f]})

    def curve(field: str) -> list[float]:
        return [float(np.mean([fams[f][str(L)][field] for f in use if str(L) in fams[f]])) for L in Ls]

    fig = go.Figure()
    for field, name, tok, dash in [("h_in_B", "h in B (what s14t64 removes)", "h", "solid"),
                                   ("mu_in_B", "family mean μ in B", "mu", "solid"),
                                   ("h_in_rand", "h in a random 64-dim subspace", "muted", "dot")]:
        fig.add_trace(go.Scatter(x=Ls, y=curve(field), name=name, mode="lines+markers", line=dict(color=ui.c(tok), dash=dash, width=2),
                                 marker=dict(size=5), hovertemplate=f"L%{{x}} · {name}: %{{y:.2f}}<extra></extra>"))
    ui.plot_layout(fig, 270)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)), margin=dict(t=40))
    fig.update_yaxes(title=dict(text="‖Bᵀv‖ / ‖v‖", font=dict(size=11.5)), rangemode="tozero")
    fig.update_xaxes(title=dict(text="layer", font=dict(size=11.5)), tickvals=Ls)
    ui.chart(fig, f"{key}_share_{pick}")
    fig = go.Figure(go.Scatter(x=Ls, y=curve("cos_h_mu_in_B"), mode="lines+markers", line=dict(color=ui.c("delta"), width=2),
                               marker=dict(size=5), hovertemplate="L%{x}: cos %{y:.2f}<extra></extra>"))
    ui.plot_layout(fig, 190)
    fig.update_yaxes(title=dict(text="cos(Bᵀh, Bᵀμ)", font=dict(size=11.5)), range=[0, 1])
    fig.update_xaxes(tickvals=Ls)
    ui.label("Inside B, does the cell's template part point where the family mean's does?", "mean cosine over read cells")
    ui.chart(fig, f"{key}_cos_{pick}")
    st.caption(f"val read cells, fam fitted on fit; {sum(next(iter(fams[f].values()))['n'] for f in use)} cells per layer. "
               "A random 64-dim subspace of 5120 holds about √(64/5120) ≈ 0.11 of any vector's norm.")


def s14_examples(key: str) -> None:
    """Worked examples: one val cell each where the plain lens misses the target behind template tokens and s14t64 reads
    it; the three arms' top 10 side by side, template tokens struck through, the target highlighted."""
    d = _s14()
    if not d or not d.get("examples"):
        return
    template = {t["display"] for t in d["tokens"]}
    ex = d["examples"]
    i = st.selectbox("Example", range(len(ex)), key=f"{key}_ex",
                     format_func=lambda k: f"{ex[k]['family']} · {ex[k]['item']} · target “{ex[k]['targets'][0]}” · L{ex[k]['layer']} "
                                           f"({ex[k]['n_template_zero']}/10 template tokens in the plain lens's top 10)")
    e = ex[i]
    st.html(f'<div style="font-size:13.5px;color:var(--ink-2);margin:2px 0 8px"><b>Prompt</b> ({ui.esc(e["family"])}, read at '
            f'L{e["layer"]}): {ui.esc(e["prompt"])}<br><b>Accepted target</b>: '
            + ", ".join(f'<span class="jm-chip hit">{ui.esc(t)}</span>' for t in e["targets"]) + "</div>")
    targets = {t.lower() for t in e["targets"]}
    cols = st.columns(3, gap="medium")
    for col, (arm, title) in zip(cols, [("zero", "Plain J-lens (no centring)"), ("fam", "Family mean"),
                                        ("s14t64", "s14t64: template directions removed")], strict=True):
        rows = []
        for r, tok in enumerate(e["top"][arm]):
            txt = sources.decode_token(tok)
            if txt.strip().lower() in targets:
                c = _chip(txt, "hit")
            elif tok in template:
                c = f'<span style="opacity:.55;text-decoration:line-through">{_chip(txt)}</span>'
            else:
                c = _chip(txt)
            rows.append(f'<div style="display:flex;gap:8px;align-items:center;margin:2px 0">'
                        f'<span style="width:18px;text-align:right;color:var(--muted);font-size:11px">{r + 1}</span>{c}</div>')
        with col:
            ui.label(title)
            st.html("".join(rows))
    st.caption("Struck through: a token in T (it scores exactly 0 once B is removed, so it cannot appear in s14t64's top 10). "
               "Highlighted: an accepted target. Chosen automatically: val cells where the plain lens misses, s14t64 hits, and "
               "the plain top 10 holds the most template tokens (experiments/s14_explainer.py).")


PANELS = {"s14_tokens": s14_tokens, "s14_norms": s14_norms, "s14_examples": s14_examples}


def render(name: str, key: str) -> None:
    fn = PANELS.get(name)
    if fn is None:
        st.caption(f"Unknown panel {name!r} (dashboard/explainers.py).")
        return
    fn(key)
