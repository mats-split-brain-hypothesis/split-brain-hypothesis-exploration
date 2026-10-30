"""Results: strict pass rate per family for every centre, judged rates on val (the numbers that count where strict
is not a proxy), pass by layer, and strict vs judge agreement. Arms are discovered on disk; names and colours
come from catalog.py, so a new centre shows up here without changes."""

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import catalog
import sources
import ui

stamp = sources.stamp()
R, A = sources.results(stamp), sources.agreement(stamp)
FAMS = [f for f in sources.EVALUATED if f in R]
NO_PROXY = [f for f in FAMS if f not in sources.STRICT_IS_PROXY]

ui.header(
    "Results so far · J-lens n1000 · Qwen3.6-27B",
    "Seven families, three centres · multi-token families below",
    "Every family is read with the plain lens and with each centre the pipeline has run: the family mean "
    "(<code>fam</code>) and the same-read-token mean (<code>tok</code>). Strict match is our free scorer and tracks the "
    f"judge on five families; on {' and '.join(NO_PROXY) or 'none'} it does not, so the judged panel below is the one "
    "to read there. None of these are WorkspaceBench scores.",
)


jpp = st.toggle("Compare with J++", value=False, key="res_jpp",
                help="Add the J++ lens (Ayonrinde & Lindsey 2026) to every panel: plain J++ and J++ read with the same centres. "
                     "A comparison map, not a centring: see notes/jpp-compare.md.")


def lens_on(a: catalog.Arm) -> bool:
    return a.lens == "jlens" or jpp


def arms_for(f: str, split: str, readout: str) -> list[catalog.Arm]:
    """zero plus every centre fitted held out from `split` (on fit itself: leave-one-out), for each lens shown."""
    ref = "self" if split == "fit" else "fit"
    arms = [catalog.parse(a) for a in R[f][split]["arms"]]
    keep = [a for a in arms if lens_on(a) and a.readout == readout and (a.centre == "zero" or a.ref == ref)]
    return sorted(keep, key=lambda a: a.sort_key)


def dot_rows(fig, rows):
    """One row per family: a faint line over the arms' range, then each arm's CI bar and dot."""
    for f, pts in rows:
        xs = [p[1] for p in pts]
        fig.add_trace(go.Scatter(x=[min(xs), max(xs)], y=[f, f], mode="lines", line=dict(color=ui.c("line-2"), width=2),
                                 hoverinfo="skip"))
        for a, v, ci, n, extra in pts:
            fig.add_trace(go.Scatter(x=ci, y=[f, f], mode="lines", line=dict(color=a.colour, width=2), opacity=0.35,
                                     hoverinfo="skip"))
            fig.add_trace(go.Scatter(
                x=[v], y=[f], mode="markers", marker=dict(size=12, color=a.colour, line=dict(color=ui.c("surface"), width=2)),
                hovertemplate=f"<b>{f}</b><br>{ui.esc(a.label)} ({a.readout}): <b>{v:.3f}</b><br>95 % CI {ci[0]:.2f}–{ci[1]:.2f}"
                              f" · n {n}{extra}<extra></extra>"))


def style_dots(fig, fams: list[str], title: str, note: dict[str, str], right: int):
    ui.plot_layout(fig, height=60 + 58 * len(fams))
    fig.update_layout(margin=dict(l=8, r=right, t=34, b=8), hovermode="closest")
    fig.update_xaxes(range=[0, 1.02], dtick=0.2, title=dict(text=title, font=dict(size=12, color=ui.c("muted"))))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickvals=fams, ticksuffix="  ",
                     ticktext=[f"{f}<br><span style='font-size:11px;color:{ui.c('muted')}'>{note.get(f, '')}</span>" for f in fams],
                     tickfont=dict(family="IBM Plex Mono", size=13, color=ui.c("ink")))


def legend(arms):
    ui.legend_arms(sorted({(a.lens, a.centre): a for a in arms}.values(), key=lambda a: a.sort_key))


# ------------------------------------------------------------------ strict
ui.section("Strict pass rate, per family and centre", eyebrow="Free scorer")
c1, c2, _ = st.columns([2, 1.4, 3])
split = c1.segmented_control("Split", sources.SPLITS, default="val", key="res_split") or "val"
read = c2.segmented_control("Readout", ["cos", "rms"], default="cos", key="res_read") or "cos"
fams = [f for f in FAMS if split in R[f]]
legend([a for f in fams for a in arms_for(f, split, read)])

fig = go.Figure()
rows, deltas = [], {}
for f in fams:
    r = R[f][split]
    pts = []
    for a in arms_for(f, split, read):
        v = r["arms"][a.name]
        pts.append((a, v["v"], v["ci"], v["n"], f"<br>median best rank {v['rank']} (0 = top)"))
        d = r["diffs"].get(f"{a.name} - zero|{read}")
        if d:
            col = ui.c("good") if d["ci"][0] > 0 else ui.c("bad") if d["ci"][1] < 0 else ui.c("muted")
            deltas.setdefault(f, []).append(f"<span style='color:{a.colour}'>●</span> <span style='color:{col}'>{d['d']:+.2f}</span>")
    rows.append((f, pts))
dot_rows(fig, rows)
for f, ds in deltas.items():
    fig.add_annotation(x=1.0, xref="paper", xanchor="left", xshift=14, y=f, showarrow=False, align="left",
                       text="  ".join(ds), font=dict(family="IBM Plex Mono", size=12.5))
fig.add_annotation(x=1.0, xref="paper", xanchor="left", xshift=14, y=1.0, yref="paper", yanchor="bottom", yshift=6,
                   showarrow=False, text="paired Δ vs plain", font=dict(size=11, color=ui.c("muted")))
style_dots(fig, fams, "strict pass rate (any layer), 95 % CI",
           {f: f"n = {R[f][split]['n_scored']}" + (" · strict ≠ judge" if f in NO_PROXY else "") for f in fams}, right=170)
ui.chart(fig, "strict")
ref_txt = "leave-one-out on fit" if split == "fit" else "fitted on the dev fit split"
st.html(f'<div class="jm-cap"><b>{split} · {read}.</b> Centres {ref_txt}. Bars are 95 % bootstrap intervals; a paired Δ is green '
        "when its interval excludes zero and red when it lies below. One family mean helps typo and association, is near "
        "ceiling on basic_readout and costs a little on multihop and multilingual. On user_modeling and directed_modulation "
        "(<i>strict ≠ judge</i>) strict undercounts what the judge credits: read those two in the judged panel.</div>")

# ------------------------------------------------------------------ judged
ui.section("Judged pass rate on val", "Claude Haiku 5.5, the development judge (unpinned, not the bench's pinned judge). "
           "The five bank-judge families are judged at every layer; user_modeling and directed_modulation at layers 24, 36, "
           "48 and 60 to keep spend down (about $1.80 and $0.80 per arm).", eyebrow="LLM judge")
jrows, jnote = [], {}
for f in FAMS:
    pts = []
    for d in sources.arm_dirs(f, "val"):
        a = catalog.parse(catalog.from_dir(d))
        if not lens_on(a) or a.readout != "cos" or (a.centre != "zero" and a.ref != "fit"):
            continue
        runs = sources.judge_runs(f, "val", d)
        if runs:
            j = sources.judged(f, "val", d, runs[0], sources.readouts_mtime(f, "val", d))
            pts.append((a, j["value"], j["ci"], j["n"], f"<br>{j['label']}"))
            jnote[f] = j["label"].split(" · ")[-1]
    if pts:
        jrows.append((f, sorted(pts, key=lambda p: p[0].sort_key)))
if jrows:
    legend([p[0] for _, pts in jrows for p in pts])
    fig = go.Figure()
    dot_rows(fig, jrows)
    style_dots(fig, [f for f, _ in jrows], "judged pass rate (Haiku 5.5), 95 % CI", jnote, right=24)
    ui.chart(fig, "judged")
    st.html('<div class="jm-cap"><b>val · cos.</b> The judge sits at or above strict on the five proxy families, and centring\'s '
            "gain is about the same under both scorers there. On directed_modulation the token-matched centre lifts the judged "
            "rate from 0.17 to 0.79 (umot's bench figure was 0.21 → 0.82). Arms not yet judged are absent, not zero.</div>")
else:
    st.info("No judge runs under out/eval yet.")

# ------------------------------------------------------------------ by layer
ui.section("Where in depth each centre pays", "Share of scored items with a target in the top 10 at that one layer (strict). "
           "The pass rate above takes the best layer per item, so it sits above every point here.", eyebrow="By layer · val · cos")
lf = [f for f in FAMS if "val" in R[f] and "zero|cos" in R[f]["val"]["by_layer"]]
lay_arms = {f: [a for a in arms_for(f, "val", "cos") if a.name in R[f]["val"]["by_layer"]] for f in lf}
legend([a for f in lf for a in lay_arms[f]])
ncol = 4
nrow = (len(lf) + ncol - 1) // ncol
fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=[f + (" *" if f in NO_PROXY else "") for f in lf],
                    horizontal_spacing=0.05, vertical_spacing=0.17, shared_yaxes=True)
for i, f in enumerate(lf):
    r, row, col = R[f]["val"], i // ncol + 1, i % ncol + 1
    for a in lay_arms[f]:
        ys = r["by_layer"][a.name]
        fig.add_trace(go.Scatter(x=r["layers"], y=ys, mode="lines", line=dict(color=a.colour, width=2),
                                 hovertemplate=f"{ui.esc(a.label)} %{{y:.2f}}<extra></extra>"), row=row, col=col)
        fig.add_trace(go.Scatter(x=[r["layers"][-1]], y=[ys[-1]], mode="markers", hoverinfo="skip",
                                 marker=dict(size=7, color=a.colour, line=dict(color=ui.c("surface"), width=1.5))), row=row, col=col)
ui.plot_layout(fig, 240 * nrow)
fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=36, b=8))
fig.update_xaxes(tickvals=[20, 40, 60], ticktext=["L20", "L40", "L60"])
fig.update_yaxes(range=[0, 1.02], dtick=0.5)
for an in fig.layout.annotations:
    an.font = dict(family="IBM Plex Mono", size=12.5, color=ui.c("ink-2"))
ui.chart(fig, "layers")
st.caption("* strict is not a proxy for the judge on this family: its curves undercount what the judge credits.")

# ------------------------------------------------------------------ agreement
ui.section("Strict match against the judge",
           "Before trusting the free scorer on a family, judge one dev arm and compare. On the five proxy families no item "
           "passes strict and fails the judge, so strict is a clean lower bound. On user_modeling and directed_modulation "
           "item kappa is 0.04–0.33: the judge credits inferred attributes and concepts that no single token spells. "
           "Kappa is undefined (–) when one scorer passes every item.", eyebrow="Scorer check · val")


def fmt(v):
    return "–" if v is None else f"{v:.2f}"


rows = []
for f in FAMS:
    name = f if f in sources.STRICT_IS_PROXY else f'{f} <span class="jm-pill part">not a proxy</span>'
    for arm in ("zero|cos", "fam@fit|cos", "tok@fit|cos", "zero|rms", "fam@fit|rms", "tok@fit|rms"):
        a = A.get(f, {}).get(arm)
        if a:
            rows.append([name, arm, a["run"], a["n"], fmt(a["strict"]), fmt(a["judge"]), f"{a['judge'] - a['strict']:+.2f}",
                         fmt(a["k_items"]), fmt(a["k_cells"]), a["strict_only"]])
ui.table(["family", "arm", "judge run", "n", "strict", "judge", "gap", "κ items", "κ cells", "strict-only"],
         rows, num={3, 4, 5, 6, 7, 8, 9}, mono={0, 1})

# ------------------------------------------------------------------ multi-token families (kept separate)
MT = [f for f in sources.MT_FAMILIES if f in R]
ui.section("Multi-token families", "Kept separate from the seven above. A J-lens token bag can never spell a multi-token "
           "form, so the bench scores bags through its LLM summarizer and then its regex (the judged rate). The free score "
           "here is the distinctive-piece proxy (<code>jlm.mtproxy</code>): an item passes when a piece of every required "
           "form that does not occur in the prompt is in a top 10 at one layer. A piece is weaker evidence than the form; "
           "trust the proxy only where the scorer check below says it tracks the judge.", eyebrow="Kept separately")
if MT:
    c1, c2, _ = st.columns([2, 1.4, 3])
    msplit = c1.segmented_control("Split", sources.SPLITS, default="bench" if all("val" not in R[f] for f in MT) else "val",
                                  key="mt_split") or "val"
    mread = c2.segmented_control("Readout", ["cos", "rms"], default="cos", key="mt_read") or "cos"
    mf = [f for f in MT if msplit in R[f]]
    if mf:
        def mt_arms(f):
            ref = "fit" if msplit != "fit" and any(catalog.parse(a).ref == "fit" for a in R[f][msplit]["arms"]) else "self"
            arms = [catalog.parse(a) for a in R[f][msplit]["arms"]]
            return sorted([a for a in arms if lens_on(a) and a.readout == mread and (a.centre == "zero" or a.ref == ref)],
                          key=lambda a: a.sort_key)

        legend([a for f in mf for a in mt_arms(f)])
        fig = go.Figure()
        mrows = []
        for f in mf:
            r = R[f][msplit]
            mrows.append((f, [(a, r["arms"][a.name]["v"], r["arms"][a.name]["ci"], r["arms"][a.name]["n"],
                               f"<br>median best piece rank {r['arms'][a.name]['rank']}") for a in mt_arms(f)]))
        dot_rows(fig, mrows)
        style_dots(fig, mf, "piece-proxy pass rate (any layer), 95 % CI",
                   {f: f"n = {R[f][msplit]['n_scored']}" for f in mf}, right=24)
        ui.chart(fig, "mt_proxy")
        excl = "; ".join(f"{f}: {sum(R[f][msplit]['excluded'].values())} unreachable" for f in mf if R[f][msplit]["excluded"])
        st.html(f'<div class="jm-cap"><b>{msplit} · {mread} · piece proxy.</b> Centres fitted on <code>fit</code> where dev banks '
                f"exist, else leave-one-out on the bank itself. {excl + '.' if excl else ''} Unreachable items have no "
                "distinctive piece (every piece of every form is in the prompt). Not WorkspaceBench scores.</div>")
    else:
        st.info(f"No multi-token results on {msplit} yet.")
    mj = []
    for f in MT:
        pts = []
        for d in sources.arm_dirs(f, "val"):
            a = catalog.parse(catalog.from_dir(d))
            runs = sources.judge_runs(f, "val", d)
            if runs and a.readout == "cos":
                j = sources.judged(f, "val", d, runs[0], sources.readouts_mtime(f, "val", d))
                pts.append((a, j["value"], j["ci"], j["n"], f"<br>{j['label']}"))
        if pts:
            mj.append((f, sorted(pts, key=lambda p: p[0].sort_key)))
    if mj:
        fig = go.Figure()
        dot_rows(fig, mj)
        style_dots(fig, [f for f, _ in mj], "judged pass rate (Haiku 5.5 summarizer + bench regex), 95 % CI", {}, right=24)
        ui.chart(fig, "mt_judged")
    rows = []
    for f in MT:
        for arm, a in A.get(f, {}).items():
            rows.append([f, arm, a["run"], a["n"], fmt(a["strict"]), fmt(a["judge"]), f"{a['judge'] - a['strict']:+.2f}",
                         fmt(a["k_items"]), fmt(a["k_cells"]), a["strict_only"]])
    if rows:
        ui.table(["family", "arm", "judge run", "n", "piece proxy", "judge", "gap", "κ items", "κ cells", "proxy-only"],
                 rows, num={3, 4, 5, 6, 7, 8, 9}, mono={0, 1})
else:
    st.info("No multi-token results under out/eval yet.")
