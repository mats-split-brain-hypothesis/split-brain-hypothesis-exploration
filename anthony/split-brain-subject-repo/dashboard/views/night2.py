"""Night 2 overview: what the three instances (A, B, C) found on 11-12 Oct 2026, laid out from the steward's digest
(notes/iteration-anthony/overnight/night-2-digest.md) and the night's study cards, with the headline numbers rebuilt
from out/eval: the finalists' change against fam on val and on the fresh splits (val2, val3, pooled as
experiments/s24_pool.py pools them). LL ran in its own pot and has its own page. Arms -> studies: dashboard/nights.py."""

import re

import plotly.graph_objects as go
import streamlit as st

import catalog
import nights
import sources
import ui

NIGHT = "night-2"
N = nights.NIGHTS[NIGHT]
stamp = sources.stamp()
R = sources.results(stamp)
SS = nights.studies(NIGHT, stamp)
DIGEST = nights.digest_sections(NIGHT)

ui.header(
    "Overnight",
    f"{N.title}: {N.dates}",
    "Three instances ran the mu loop overnight: A on priors and template subspaces (S13-S15, S22), B on neighbours, "
    "depth and outliers (S16-S18, S20x, S21, S23, S25), C on learned centres, ceilings and fresh data (S19, S20, S24). "
    "The headline numbers below are rebuilt from out/eval; the text is the steward's digest. Every method's scores "
    "are on the next page. LL ran separately and has its own page.",
)

st.html("""<style>
.n2-tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:1px; background:var(--line);
  border:1px solid var(--line); border-radius:12px; overflow:hidden; margin:4px 0 8px; }
.n2-tiles > div { background:var(--surface); padding:14px 16px; display:grid; gap:3px; align-content:start; }
.n2-tiles .l { font-size:12px; color:var(--muted); line-height:1.35; }
.n2-tiles .v { font-size:25px; font-weight:600; color:var(--ink); line-height:1.2; font-variant-numeric:tabular-nums; }
.n2-tiles .s { font-size:12px; color:var(--ink-2); line-height:1.4; }
.n2-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:12px; margin-bottom:6px; }
.n2-card { display:grid; gap:6px; align-content:start; background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:13px 16px; text-decoration:none !important; color:var(--ink) !important; }
.n2-card:hover { border-color:var(--h); }
.n2-card .top { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.n2-card .id { font:600 12.5px var(--f-mono, monospace); color:var(--muted); }
.n2-card h4 { margin:0; padding:0; font-size:15.5px; line-height:1.3; color:var(--ink); }
.n2-card p { margin:0; font-size:13px; line-height:1.5; color:var(--ink-2); }
.n2-card .links { font-size:12px; color:var(--muted); }
.n2-inst { font-size:11.5px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:14px 0 6px; }
div[class*="st-key-n2md_"] { max-width: 980px; }
</style>""")

# ------------------------------------------------------------------ headline numbers, rebuilt
FRESH_FAMS = ["typo", "association", "multihop"]
FAM = "fam@fit|cos"
FINALISTS = {  # the digest's finalists, by their out/eval names
    "S14bL": "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5@fit|cos",
    "S14b-x": "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos",
    "S14b": "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos",
    "S14k": "sched:40:kmx64+s14t64@fit|cos",
    "S20x (sup.)": "s20xt:1@fit|cos",
    "s20xon (sup.)": "s20xon:1:kmx64@fit|cos",
    "S21b (sup.)": "sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos",
    "matched null · S14bL": "famr:*:sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5@fit|cos",
    "matched null · S20x": "famr:*:s20xt:1@fit|cos",
}
SPLITS = ["val", *N.fresh, nights.POOLED]


@st.cache_data(show_spinner="Rebuilding the night's headline numbers…")
def headline(_stamp: float) -> dict:
    """(finalist, split) -> {d, ci, per, n} against fam, macro over typo / association / multihop; plus item counts."""
    out, n_items = {}, {}
    for s in SPLITS:
        ref = {f: nights.passes(R, f, s, FAM, False) for f in FRESH_FAMS}
        n_items[s] = sum(len(v) for v in ref.values() if v)
        for k, arm in FINALISTS.items():
            P = {f: nights.passes(R, f, s, arm, False) for f in FRESH_FAMS}
            if all(P.values()):
                out[k, s] = nights.macro_change(P, ref, FRESH_FAMS)
    pool = lambda arm: {f: nights.passes(R, f, nights.POOLED, arm, False) for f in FRESH_FAMS}  # noqa: E731
    out["S20x - S14bL"] = nights.macro_change(pool(FINALISTS["S20x (sup.)"]), pool(FINALISTS["S14bL"]), FRESH_FAMS)
    return {"d": out, "n": n_items}


H = headline(stamp)
D = H["d"]


def fmt(c: dict | None) -> tuple[str, str]:
    return ("–", "") if not c else (f"{c['d']:+.3f}", f"[{c['ci'][0]:+.3f}, {c['ci'][1]:+.3f}]")


tiles = [
    ("S14bL, label-free · fresh val2 + val3, Δ vs fam", D.get(("S14bL", nights.POOLED)),
     f"{H['n'].get(nights.POOLED, 0)} fresh items, strict, cos"),
    ("S20x, supervised · fresh val2 + val3, Δ vs fam", D.get(("S20x (sup.)", nights.POOLED)), "other families' fit targets inside g"),
    ("S20x − S14bL · fresh val2 + val3", D.get("S20x - S14bL"), "not separated"),
    ("Matched null (fam + random g, S14bL's norm)", D.get(("matched null · S14bL", nights.POOLED)), "3 seeds averaged: norm alone does nothing"),
]
st.html('<div class="n2-tiles">' + "".join(
    f'<div><span class="l">{ui.esc(lab)}</span><span class="v">{fmt(c)[0]}</span>'
    f'<span class="s">{fmt(c)[1]} · {ui.esc(sub)}</span></div>' for lab, c, sub in tiles) + "</div>")
st.caption("Rebuilt live from out/eval (macro over typo / association / multihop, items pooled within family, 2,000 "
           "within-family bootstrap draws), as experiments/s24_pool.py computes them; the digest quotes S14bL +0.039 "
           "[+0.018, +0.059] and S20x +0.051 [+0.030, +0.073].")

left, right = st.columns([1.05, 1], gap="large")
with left:
    ui.section("The night in five lines", "The steward's summary, 09:01 BST.")
    with st.container(key="n2md_five"):
        st.markdown(DIGEST.get("The night in five lines", "_No digest found._"))
with right:
    ui.section("Did it hold on fresh data?", "Each finalist's change against fam on val (where the forms were chosen), "
               "then on the fresh splits read once each. Same three families on every split; whiskers 95 %.")
    COL = {"val": ui.c("muted"), "val2": "#3b63c9", "val3": "#0f8a77", nights.POOLED: "#c2417a"}
    names = [k for k in FINALISTS if any((k, s) in D for s in SPLITS)]
    fig = go.Figure()
    for j, s in enumerate(SPLITS):
        pts = [(i, D[k, s]) for i, k in enumerate(names) if (k, s) in D]
        if not pts:
            continue
        off = (j - (len(SPLITS) - 1) / 2) * 0.18
        fig.add_trace(go.Scatter(
            x=[c["d"] for _, c in pts], y=[i + off for i, _ in pts], mode="markers", name=s,
            marker=dict(color=COL[s], size=9 if s == nights.POOLED else 7, symbol="diamond" if s == nights.POOLED else "circle"),
            error_x=dict(type="data", symmetric=False, array=[c["ci"][1] - c["d"] for _, c in pts],
                         arrayminus=[c["d"] - c["ci"][0] for _, c in pts], thickness=1.2, width=0, color=COL[s]),
            customdata=[[names[i], s] for i, _ in pts],
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}: %{x:+.3f}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=ui.c("line-2"), width=1))
    ui.plot_layout(fig, 90 + 46 * len(names))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.04, x=0, yanchor="bottom", font=dict(size=11.5)))
    fig.update_yaxes(tickvals=list(range(len(names))), ticktext=names, autorange="reversed", automargin=True,
                     tickfont=dict(size=11.5, color=ui.c("ink-2")))
    fig.update_xaxes(title=dict(text="Δ strict pass vs fam (typo, association, multihop)", font=dict(size=11.5)),
                     tickformat="+.2f")
    ui.chart(fig, "n2_fresh")
    st.caption("S14k (+0.032 on val) fell to +0.003 on val2 and was not read on val3; the val-selected S14b-x / "
               "S14bL held. val's numbers here are over the same three families, so they differ from the 11-family "
               "val macros in the study notes.")

# ------------------------------------------------------------------ studies
ui.section("The night's studies", "One card per study, by the instance that ran it: its status and verdict from the "
           "card. Click a card for the study page; “scores” opens the next page on that study.", eyebrow="Studies")
STATUS = {"finalist": "good", "negative": "bad", "diagnostic": "h", "closed": "muted", "open": "mu"}
INST = {"A": "A · priors and template subspaces (j-lens-mean-2e)", "B": "B · neighbours, depth, outliers (j-lens-mean-e1)",
        "C": "C · learned centres, ceilings, fresh data (j-lens-mean-19c)"}
fit_arms = {}
for f in sources.ALL_FAMILIES:
    for s in ("fit", "val"):
        for a in R.get(f, {}).get(s, {}).get("arms", {}):
            fit_arms.setdefault(s, set()).add(a)


@st.cache_data(show_spinner=False)
def counts(_stamp: float) -> dict:
    """study -> split -> number of non-reference arms."""
    out = {}
    for s, names in fit_arms.items():
        for n in names:
            m = nights.member(catalog.parse(n), NIGHT, _stamp)
            if m and m.kind != "reference":
                for sid in m.studies:
                    out.setdefault(sid, {}).setdefault(s, 0)
                    out[sid][s] += 1
    return out


CNT = counts(stamp)


def plain(s: str) -> str:
    s = re.sub(r"\$([^$]*)\$", r"\1", s or "")
    s = re.sub(r"`([^`]*)`", r"\1", s).replace("->", "→")
    s = ui.esc(s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


for inst in ("A", "B", "C"):
    sids = [s for s, v in SS.items() if v["instance"] == inst]
    if not sids:
        continue
    st.html(f'<div class="n2-inst">{ui.esc(INST[inst])}</div>')
    cards = []
    for sid in sids:
        v = SS[sid]
        tok = STATUS.get(v["status"] or "", "muted")
        chip = (f'<span style="padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;color:var(--{tok});'
                f'border:1px solid var(--{tok})">{ui.esc(v["status"] or "in S20x notes")}</span>')
        verdict = plain(v["verdict"]) or "Written up inside S20x.md (no card)."
        if len(verdict) > 330:
            verdict = verdict[:330].rsplit(" ", 1)[0] + " …"
        c = CNT.get(sid, {})
        target = sid if v["card"] else "S20x"
        cards.append(
            f'<a class="n2-card" href="/study?study={target}" target="_self"><div class="top"><span class="id">{sid}</span>{chip}</div>'
            f'<h4>{ui.esc(v["title"])}</h4><p>{verdict}</p>'
            f'<span class="links">{c.get("fit", 0)} arms on fit · {c.get("val", 0)} on val</span></a>')
    st.html(f'<div class="n2-grid">{"".join(cards)}</div>')
st.html(f'<p style="margin:2px 0 0"><a href="/night2_scores" target="_self">→ Every method\'s scores: {N.title} scores</a></p>')

# ------------------------------------------------------------------ the digest
ui.section("From the digest", "The steward's digest and the night's briefs, as written.", eyebrow="Notes")
TABS = ["Decisions for the user", "Per instance", "What is next", "Spend", "What broke, and the fix"]
tabs = st.tabs([t if t != "What broke, and the fix" else "What broke" for t in TABS] + ["Briefs", "Full digest"])
for t, tab in zip(TABS, tabs, strict=False):
    with tab, st.container(key=f"n2md_{re.sub(r'[^a-z]', '', t.lower())}"):
        st.markdown(DIGEST.get(t, "_Not in the digest._"))
with tabs[-2], st.container(key="n2md_briefs"):
    for name in ("preamble.md", "A.md", "B.md", "C.md", "steward.md"):
        p = nights.OVERNIGHT / name
        if p.exists():
            with st.expander(name):
                st.markdown(p.read_text())
with tabs[-1], st.container(key="n2md_full"):
    p = nights.OVERNIGHT / N.digest
    st.markdown(re.sub(r"\]\(\.\./studies/([A-Za-z0-9-]+)\.md\)", r"](/study?study=\1)", p.read_text()) if p.exists() else "–")
