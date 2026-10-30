"""Semantic-only readouts: every arm scored twice, over the full vocabulary and over the semantic vocabulary only
(J++'s Readout Filtering; jlm.controls.non_semantic_ids, evaluate.py's <arm>/sem/), side by side. Read straight
from summary.json in both views, whatever the sidebar's vocabulary switches say: the pass per family, whether
centring's gain survives the filter (the summaries' paired diffs), what the filter removes, every arm in a table,
and the arms whose semantic readouts come from a refit that does not reproduce the stored one."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import catalog
import sources
import ui

ui.header(
    "Pipeline",
    "Semantic-only readouts",
    "The J++ authors (Ayonrinde &amp; Lindsey 2026) score their lens after <b>Readout Filtering</b>: every token whose "
    "text has no letter or digit (punctuation, whitespace, runs of underscores, padding rows) is removed from the "
    "vocabulary before the top 10 is taken. Our default readouts keep the full vocabulary. Every arm is now read both "
    "ways, so the two can be set side by side; this page always shows both, whatever the sidebar's vocabulary switches "
    "say.",
)

stamp = sources.stamp()
VC = sources.vocab_compare(stamp)
splits = [s for s in sources.SPLITS if any(s in VC[f] for f in VC)]
if not splits:
    st.info("No summary.json under out/eval yet: run experiments/evaluate.py first.")
    st.stop()

# ------------------------------------------------------------------ how the filter is applied
left, right = st.columns([1.35, 1], gap="large")
with left:
    ui.prose(
        "The rule is J++'s own (<code>non_semantic_token_ids</code> in their <code>lens_evals</code>): an id is "
        "removed when its decoded string has no letter or digit, <i>unless</i> it is one of the ids the bank scores, "
        "so no target becomes unrankable. Special ids stay (they decode word-like). On Qwen3.6-27B that removes about "
        "6,100 of the 248k ids.",
        "Both views come from the same scores in one pass (<code>jlm.read</code>): the semantic top 10, target rank "
        "and prompt-masked top 10 are the full ones with those ids set to −∞. Strict pass, the piece proxy, echo and "
        "next-token overlap are then computed the same way on each. The full vocabulary stays the default everywhere "
        "else; the sidebar's <b>semantic tokens only</b> switches move the other pages to this view (all arms, or "
        "the J++ arms alone).",
    )
with right:
    info = next((VC[f][s]["semantic"] for f in VC for s in VC[f] if VC[f][s].get("semantic")), None) or {}
    n_arms = sum(len(VC[f][s]["arms"]) for f in VC for s in VC[f])
    n_sem = sum(1 for f in VC for s in VC[f] for v in VC[f][s]["arms"].values() if v["sem"])
    st.html('<div class="jm-stats">'
            f'<div class="jm-stat"><span class="v">{info.get("excluded_ids", 0):,}</span><span class="l">ids removed (typo; '
            'varies a little with the spared targets)</span></div>'
            f'<div class="jm-stat"><span class="v">{n_sem:,} / {n_arms:,}</span><span class="l">arms read both ways</span></div>'
            '</div>')

c1, c2, c3 = st.columns([1, 1, 3], vertical_alignment="bottom")
split = c1.segmented_control("Split", splits, default="val" if "val" in splits else splits[0], key="sv_split") or splits[0]
readout = c2.segmented_control("Readout", ["cos", "rms"], default="rms", key="sv_readout",
                               help="rms is where the filter matters most: the plain J-lens's rms top 10 is the one most "
                                    "crowded by punctuation and blanks.") or "rms"
fams = [f for f in sources.ALL_FAMILIES if split in VC.get(f, {})]
names = {a for f in fams for a in VC[f][split]["arms"]}
arms = sorted((catalog.parse(n) for n in names if catalog.parse(n).readout == readout), key=lambda a: a.sort_key)
if not arms:
    st.info(f"No {readout} arms on {split}.")
    st.stop()
by_name = {a.name: a for a in arms}
held_ref = "self" if split == "fit" else "fit"
default = [a.name for a in arms if not a.control and (
    (a.centre == "zero") or (a.lens == "jlens" and a.centre in ("fam", "knnx8", "pco16") and a.ref == held_ref))]
picked = c3.multiselect("Arms", [a.name for a in arms], default=default, format_func=lambda n: by_name[n].label,
                        key=f"sv_arms_{split}_{readout}")
chosen = [by_name[n] for n in sorted(picked, key=lambda n: by_name[n].sort_key)]
if not chosen:
    st.info("Pick at least one arm.")
    st.stop()


def val(f: str, a: str, view: str):
    v = VC[f][split]["arms"].get(a)
    return None if v is None or v[view] is None else v[view]["v"]


def fam_label(f: str) -> str:
    return f.replace("_", " ")


# ------------------------------------------------------------------ pass per family, full -> semantic
ui.section("Pass per family, full → semantic", "Hollow marker: full vocabulary. Filled: semantic tokens only. A long "
           "segment is an arm whose top 10 was being crowded by tokens with no letter or digit.")
g1, g2 = st.columns([1.6, 1], gap="large")
with g1:
    fig = go.Figure()
    n = len(chosen)
    offs = np.linspace(-0.28, 0.28, n) if n > 1 else [0.0]
    ypos = {f: i for i, f in enumerate(reversed(fams))}
    for k, a in enumerate(chosen):
        xs, ys, xf, xs_, hov = [], [], [], [], []
        for f in fams:
            full, sem = val(f, a.name, "full"), val(f, a.name, "sem")
            if full is None or sem is None:
                continue
            y = ypos[f] + offs[k]
            xs += [full, sem, None]
            ys += [y, y, None]
            xf.append((full, y))
            xs_.append((sem, y))
            hov.append(f"{a.label}<br>{fam_label(f)}: {full:.2f} → {sem:.2f} ({sem - full:+.2f})")
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=a.colour, width=2.2), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[p[0] for p in xf], y=[p[1] for p in xf], mode="markers", hoverinfo="skip",
                                 marker=dict(symbol="circle-open", size=8, color=a.colour, line=dict(width=1.6))))
        fig.add_trace(go.Scatter(x=[p[0] for p in xs_], y=[p[1] for p in xs_], mode="markers", name=a.label,
                                 marker=dict(size=8, color=a.colour), text=hov, hovertemplate="%{text}<extra></extra>"))
    ui.plot_layout(fig, 60 + 46 * len(fams))
    fig.update_yaxes(tickvals=list(ypos.values()), ticktext=[fam_label(f) for f in ypos], showgrid=False)
    fig.update_xaxes(range=[-0.02, 1.02], title_text="pass", tickformat=".1f")
    ui.chart(fig, f"sv_dumb_{split}_{readout}")
    ui.legend_arms(chosen)
with g2:
    rows = []
    for a in chosen:
        both = [(val(f, a.name, "full"), val(f, a.name, "sem")) for f in fams]
        both = [(x, y) for x, y in both if x is not None and y is not None]
        if not both:
            continue
        mf, ms = np.mean([x for x, _ in both]), np.mean([y for _, y in both])
        up = sum(y - x > 0.005 for x, y in both)
        best = max(zip(fams, both), key=lambda t: t[1][1] - t[1][0])
        rows.append([f'<span style="color:{a.colour}">●</span> {ui.esc(a.label)}', f"{mf:.3f}", f"{ms:.3f}",
                     f"{ms - mf:+.3f}", f"{up} / {len(both)}",
                     f"{fam_label(best[0])} ({best[1][1] - best[1][0]:+.2f})"])
    ui.label("Macro average over families", f"{split} · {readout}")
    ui.table(["arm", "full", "semantic", "Δ", "families up", "largest gain"], rows, num={1, 2, 3, 4})
    ns = [VC[f][split]["next"] for f in fams if VC[f][split].get("next") is not None]
    nss = [VC[f][split]["next_sem"] for f in fams if VC[f][split].get("next_sem") is not None]
    if ns and nss and len(ns) == len(nss):
        st.caption(f"The model's own next token at the read cells, for scale: {np.mean(ns):.3f} → {np.mean(nss):.3f}.")
    st.caption("Macro: unweighted mean over the families each arm was read on (strict pass; the piece proxy on the "
               "multi-token families). Ours, not WorkspaceBench scores.")

# ------------------------------------------------------------------ does centring still help?
ui.section("Does centring's gain survive the filter?",
           "Each centred arm against the plain lens of the same map and readout, paired item by item (the summaries' "
           "diffs, 95 % bootstrap intervals), in each view. If centring mostly removed junk directions, its gain "
           "shrinks once the junk is filtered out anyway.")
centred = [a for a in chosen if a.centre != "zero"]
if not centred:
    st.caption("Pick a centred arm above to compare its gain in the two views.")
else:
    h1, h2 = st.columns([1.6, 1], gap="large")
    with h1:
        which = st.segmented_control("Centred arm", [a.name for a in centred], default=centred[0].name,
                                     format_func=lambda n: by_name[n].label, key=f"sv_gain_{split}_{readout}") or centred[0].name
        a = by_name[which]
        base = catalog.Arm(f"{'' if a.lens == 'jlens' else a.lens + ':'}zero|{a.readout}", "zero", "", a.readout, a.lens).name
        key = f"{a.name} - {base}"
        fig = go.Figure()
        for view, col, nm in (("diffs", ui.c("h"), "full vocabulary"), ("diffs_sem", ui.c("delta"), "semantic only")):
            ds = [VC[f][split][view].get(key) for f in fams]
            fig.add_trace(go.Bar(
                y=[fam_label(f) for f in fams], x=[d["d"] if d else None for d in ds], orientation="h", name=nm,
                marker_color=col, error_x=dict(type="data", symmetric=False, color=ui.c("muted"), thickness=1.2,
                                               array=[d["ci"][1] - d["d"] if d else 0 for d in ds],
                                               arrayminus=[d["d"] - d["ci"][0] if d else 0 for d in ds]),
                hovertemplate="%{y}: %{x:+.3f}<extra>" + nm + "</extra>"))
        ui.plot_layout(fig, 60 + 46 * len(fams))
        fig.update_layout(barmode="group", showlegend=True, legend=dict(orientation="h", y=1.08, x=0))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title_text=f"paired change in pass vs {by_name.get(base, catalog.parse(base)).label}",
                         zeroline=True, zerolinecolor=ui.c("line-2"), tickformat="+.2f")
        ui.chart(fig, f"sv_gain_chart_{split}_{readout}_{which}")
    with h2:
        rows = []
        for a in centred:
            base = f"{'' if a.lens == 'jlens' else a.lens + ':'}zero|{a.readout}"
            k = f"{a.name} - {base}"
            df = [VC[f][split]["diffs"][k]["d"] for f in fams if k in VC[f][split]["diffs"]]
            ds = [VC[f][split]["diffs_sem"][k]["d"] for f in fams if k in VC[f][split]["diffs_sem"]]
            if df and ds:
                rows.append([f'<span style="color:{a.colour}">●</span> {ui.esc(a.label)}', f"{np.mean(df):+.3f}",
                             f"{np.mean(ds):+.3f}", f"{np.mean(ds) - np.mean(df):+.3f}"])
        ui.label("Mean gain over the plain lens", "macro over families")
        if rows:
            ui.table(["centred arm", "full", "semantic", "change"], rows, num={1, 2, 3})
        else:
            st.caption("No paired diffs for these arms on this split.")
        jl, jp = f"zero|{readout}", f"jpp:zero|{readout}"
        both = [f for f in fams if all(val(f, x, v) is not None for x in (jl, jp) for v in ("full", "sem"))]
        if both:
            gf = np.mean([val(f, jp, "full") - val(f, jl, "full") for f in both])
            gs = np.mean([val(f, jp, "sem") - val(f, jl, "sem") for f in both])
            st.caption(f"Plain J++ minus plain J-lens ({readout}), macro over {len(both)} families: {gf:+.3f} on the "
                       f"full vocabulary, {gs:+.3f} on semantic tokens only (difference of rates, unpaired).")

# ------------------------------------------------------------------ what the filter removes
ui.section("What the filter removes", "Share of each arm's full-vocabulary top 10 that has no letter or digit, by layer "
           "(the slots the semantic view hands to the next tokens down).")
fam_j = st.segmented_control("Family", fams, default="typo" if "typo" in fams else fams[0], format_func=fam_label,
                             key=f"sv_junk_fam_{split}") or fams[0]
k1, k2 = st.columns([1.6, 1], gap="large")
J = {}
for a in chosen:
    d = sources.arm_dir(a.name)
    if sources._have(sources.EVAL / fam_j / split / d / "readouts.jsonl"):
        J[a.name] = sources.junk_by_layer(fam_j, split, d, sources._mt(sources.EVAL / fam_j / split / d / "readouts.jsonl"))
with k1:
    fig = go.Figure()
    for a in chosen:
        if a.name in J:
            fig.add_trace(go.Scatter(x=J[a.name]["layers"], y=J[a.name]["share"], mode="lines+markers", name=a.label,
                                     line=dict(color=a.colour, width=2.2, dash=a.dash), marker=dict(size=6),
                                     hovertemplate=f"{a.label}<br>layer %{{x}}: %{{y:.0%}}<extra></extra>"))
    ui.plot_layout(fig, 320)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero", title_text="non-semantic share of top 10")
    fig.update_xaxes(title_text="layer")
    ui.chart(fig, f"sv_junk_{fam_j}_{split}_{readout}")
with k2:
    ui.label("Commonest removed tokens", f"{fam_label(fam_j)} · {split}")
    for a in chosen[:4]:
        if a.name in J and J[a.name]["top"]:
            st.html(f'<div style="font-size:13px;color:var(--muted);margin-top:6px">{ui.esc(a.label)}</div>'
                    + ui.chips([t for t, _ in J[a.name]["top"][:10]], ""))

# ------------------------------------------------------------------ every arm
ui.section("Every arm", f"Strict pass on {split} ({readout}), full vs semantic, macro over families, with the median "
           "best target rank (lower is better) in each view. Sorted by the change.")
f1, f2 = st.columns([2, 1], vertical_alignment="bottom")
flt = f1.text_input("Filter", placeholder="e.g. knn, jpp, kmw", key="sv_filter").strip().lower()
fam_t = f2.selectbox("Families", ["macro (all)", *fams], format_func=lambda x: x if x.startswith("macro") else fam_label(x),
                     key=f"sv_tfam_{split}")
rows = []
for a in arms:
    if flt and flt not in a.name.lower() and flt not in a.label.lower():
        continue
    fs = fams if fam_t.startswith("macro") else [fam_t]
    vals = [(VC[f][split]["arms"][a.name]["full"], VC[f][split]["arms"][a.name]["sem"]) for f in fs
            if a.name in VC[f][split]["arms"] and VC[f][split]["arms"][a.name]["sem"]]
    if not vals:
        continue
    mf, ms = np.mean([x["v"] for x, _ in vals]), np.mean([y["v"] for _, y in vals])
    rf = np.median([x["rank"] for x, _ in vals if x["rank"] is not None])
    rs = np.median([y["rank"] for _, y in vals if y["rank"] is not None])
    rows.append({"arm": a.label, "name": a.name, "families": len(vals), "full": mf, "semantic": ms, "Δ": ms - mf,
                 "rank full": rf, "rank semantic": rs})
if rows:
    st.dataframe(sorted(rows, key=lambda r: -r["Δ"]), hide_index=True, width="stretch", height=min(560, 38 + 35 * len(rows)),
                 column_config={k: st.column_config.NumberColumn(format="%.3f") for k in ("full", "semantic")}
                 | {"Δ": st.column_config.NumberColumn(format="%+.3f"),
                    "rank full": st.column_config.NumberColumn(format="%.1f"),
                    "rank semantic": st.column_config.NumberColumn(format="%.1f")})
else:
    st.caption("No arm matches.")

# ------------------------------------------------------------------ caveat: refits
refits = [r for r in sources.sem_refits(stamp) if r["split"] == split]
loud = [r for r in refits if r["share"] >= 0.01]
ui.section("Caveat: arms re-read from a refit", "Arms evaluated before the semantic view existed were re-read for it "
           "(pod, 2026-10-11): the centre was fitted again and the stored full-vocabulary files kept. Where the refit "
           "does not reproduce the stored top 10 exactly, that arm's two views come from slightly different fits.")
if loud:
    st.caption(f"{len(loud)} arms on {split} differ on at least 1 % of cells, all non-deterministic k-means fits:")
    ui.table(["family", "arm", "cells differing"],
             [[fam_label(r["family"]), ui.esc(catalog.from_dir(r["adir"])), f"{r['share']:.1%}"] for r in loud[:40]],
             num={2}, mono={1})
else:
    st.caption(f"Every arm on {split} reproduces its stored readouts to within 1 % of cells.")
