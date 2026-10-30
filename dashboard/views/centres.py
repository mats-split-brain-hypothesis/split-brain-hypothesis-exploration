"""Centres in detail: for one bank, or every family pooled, what each centre's mu is and does. Its scores, how much
of ||h|| it leaves (||h - mu|| / ||h||) by layer and by category, and the clouds of states, centres and read vectors
h - mu in their top principal directions. mu is rebuilt from the captures with jlm.centres (jlm.geometry), exactly as
the evaluated arm built it; arms are discovered from out/eval and named in catalog.py."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import torch

import catalog
import sources
import ui

ui.header(
    "Explore",
    "Centres in detail",
    "What each μ is and what it does to h: its scores, the share of ‖h‖ the centred read keeps, and the clouds of "
    "states, centres and read vectors h − μ. μ is rebuilt from the captured states exactly as the evaluated arm "
    "built it (no lens needed), so these are the vectors the readouts came from.",
)

POOLED = "all families (pooled)"
stamp = sources.stamp()
R, A = sources.results(stamp), sources.agreement(stamp)
fams = sources.families_with_readouts()
if not fams:
    st.info("No readouts under out/eval yet: run experiments/evaluate.py first.")
    st.stop()

# ------------------------------------------------------------------ scope and arms
c1, c2, c3, _ = st.columns([1.5, 1.2, 1, 3.3], vertical_alignment="bottom")
family = c1.selectbox("Family", [*fams, POOLED], key="ce_family",
                      help="Pooled: every family with readouts on this split, each centred by its own μ.")
splits = [s for s in sources.SPLITS if any(s in sources.splits_with_readouts(f) for f in (fams if family == POOLED else [family]))]
split = c2.segmented_control("Split", splits, default="val" if "val" in splits else splits[0], key=f"ce_split_{family}") or splits[0]
readout = c3.segmented_control("Readout", ["cos", "rms"], default="cos", key="ce_readout",
                               help="Only the scores and the pass categories depend on it: μ and h − μ are the same.") or "cos"
scope = [f for f in fams if split in sources.splits_with_readouts(f)] if family == POOLED else [family]


def arm_names(f: str) -> set[str]:
    return {catalog.from_dir(d) for d in sources.arm_dirs(f, split)}


names = set.intersection(*(arm_names(f) for f in scope))
arms = sorted((catalog.parse(n) for n in names if catalog.parse(n).readout == readout), key=lambda a: a.sort_key)
if not arms:
    st.info(f"No {readout} arms common to {', '.join(scope)} on {split}.")
    st.stop()
by_name = {a.name: a for a in arms}
held_ref = "self" if split == "fit" else "fit"
chosen_names = ui.grouped_pills(
    "Centres", [a.name for a in arms], lambda n: catalog.group(by_name[n]), order=catalog.group_order, fold=catalog.folded, beside=catalog.beside,
    default=catalog.defaults(arms, held_ref),
    format_func=lambda n: by_name[n].label, key=f"ce_arms_{family}_{split}_{readout}",
    help="LOO: leave-one-out mean on the read bank itself. fit: fitted on the dev fit split, so held out from val and bench.",
)
chosen = [by_name[n] for n in sorted(chosen_names or [], key=lambda n: by_name[n].sort_key)]
if not chosen:
    st.info("Select at least one centre above.")
    st.stop()
ui.legend_arms(chosen)
centred = [a for a in chosen if a.centre != "zero"]


def mtime(f: str, a=None) -> float:
    return sources.captures_mtime(f, split, a.ref if a else "")


# Families whose captures are on disk (archived ones drop out of the geometry, not the scores).
geo_scope = []
for f in scope:
    try:
        sources.geometry(f, split, "zero", "", mtime(f))
        geo_scope.append(f)
    except FileNotFoundError:
        pass
missing = [f for f in scope if f not in geo_scope]
G = {(f, a.name): sources.geometry(f, split, a.centre, a.ref, mtime(f, a)) for f in geo_scope for a in centred}
layers = sorted(set.intersection(*({L for (_, L, _) in sources.geometry(f, split, "zero", "", mtime(f))} for f in geo_scope))) \
    if geo_scope else sorted(set.intersection(*(set(R[f][split]["layers"]) for f in scope if split in R.get(f, {}))))

# ------------------------------------------------------------------ scores
ui.section("Scores per centre", "Strict pass rate (an item passes if any read cell, any layer, has an accepted target in its "
           "top 10), its change from the plain lens with the same readout (paired, 95 % CI), the judged rate on val where a "
           "judge run exists, and the median of each item's best target place (0 = top).", eyebrow="Scores")


def fmt_ci(v, ci, sign=False) -> str:
    if v is None:
        return "–"
    s = "+" if sign else ""
    return f"{v:{s}.3f} <span style='color:var(--muted)'>[{ci[0]:{s}.2f}, {ci[1]:{s}.2f}]</span>"


def tag(a) -> str:
    return f'<span class="jm-armtag"><i style="background:{a.colour}"></i>{ui.esc(a.label)}</span>'


def vs_plain(name: str, family: str = family) -> dict | None:
    """Paired change against the plain lens rebuilt from the readouts, for arms whose summary has no such diff
    (study arms are paired against their own references when evaluated)."""
    plain = f"zero|{readout}"
    r = R.get(family, {}).get(split)
    if r is None or name == plain or plain not in r["arms"]:
        return None
    passes = [sources.item_passes(family, split, sources.arm_dir(x), sources.readouts_mtime(family, split, sources.arm_dir(x)))
              for x in (name, plain)]
    if None in passes:
        return None
    p = sources.paired(*passes, tuple(r["scored_ids"]))
    return None if p["diff"] is None else {"d": p["diff"], "ci": p["ci95"]}


def judged(f: str, name: str) -> float | None:
    """The newest full judge run of this arm on f (val), as on the Leaderboard."""
    adir = sources.arm_dir(name)
    runs = sources.judge_runs(f, split, adir)
    return sources.judged(f, split, adir, runs[0], sources.readouts_mtime(f, split, adir))["value"] if runs else None


if family != POOLED:
    r = R.get(family, {}).get(split)
    if r is None:
        st.caption("No summary.json for this bank.")
    else:
        rows = []
        for a in chosen:
            v = r["arms"].get(a.name)
            d = r["diffs"].get(f"{a.name} - zero|{readout}") or vs_plain(a.name)
            j = judged(family, a.name) if split == "val" else None
            rows.append([tag(a), fmt_ci(v["v"], v["ci"]) if v else "–", fmt_ci(d["d"], d["ci"], True) if d else "–",
                         f"{j:.3f}" if j is not None else "<span style='color:var(--muted)'>not judged</span>", f"{v['rank']:g}" if v and v["rank"] is not None else "–"])
        ui.table(["centre", "strict pass", "Δ vs plain", "judged (val)", "median best place"], rows, num={1, 2, 3, 4})
        st.caption(f"{r['scorer']} · n scored {r['n_scored']} of {r['n_items']}.")
        BL = r["by_layer"]
        fig = go.Figure()
        for a in chosen:
            if a.name in BL:
                fig.add_trace(go.Scatter(x=r["layers"], y=BL[a.name], mode="lines+markers", name=a.label,
                                         line=dict(color=a.colour, width=2, dash=a.dash),
                                         marker=dict(size=6, color=a.colour),
                                         hovertemplate=f"<b>{ui.esc(a.label)}</b> L%{{x}}: %{{y:.2f}}<extra></extra>"))
        if fig.data:
            ui.plot_layout(fig, 240)
            fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=12, b=8))
            fig.update_xaxes(tickvals=r["layers"], ticktext=[f"L{L}" for L in r["layers"]])
            fig.update_yaxes(range=[0, 1.02], title=dict(text="pass at this layer", font=dict(size=12, color=ui.c("muted"))))
            ui.chart(fig, f"ce_bylayer_{family}_{split}_{readout}")
            st.caption("Share of scored items with a target in the top 10 at each layer (any read position).")
else:
    head = ["family", *[tag(a) for a in chosen]]
    rows = []
    for f in scope:
        r = R.get(f, {}).get(split)
        if r is None:
            continue
        cells = []
        for a in chosen:
            v, d = r["arms"].get(a.name), r["diffs"].get(f"{a.name} - zero|{readout}") or vs_plain(a.name, f)
            cells.append("–" if not v else f"{v['v']:.2f}" + (
                f" <span style='color:var({'--good' if d['d'] > 0 else '--bad'})'>{d['d']:+.2f}</span>" if d else ""))
        rows.append([f"<span class='mono'>{f}</span>", *cells])
    ui.table(head, rows, num=set(range(1, len(head))))
    st.caption("Strict pass rate per family (piece proxy on the multi-token families), with the paired change from the "
               "plain lens. Per-family CIs and the judged rates are on the Results page.")

if not geo_scope:
    st.info("No captures on disk for this bank, so μ cannot be rebuilt (fetch them, see CLAUDE.md).")
    st.stop()
if missing:
    st.caption(f"No captures on disk for {', '.join(missing)}: left out of the geometry below.")
if not centred:
    st.info("Select a centred arm to see its geometry (the plain lens has μ = 0).")
    st.stop()

# ------------------------------------------------------------------ categories
ITEMS = {f: sources.bank(f, split)["items"] for f in geo_scope}
FIELDS = {"subfamily": "subfamily", "attr_class": "attribute", "concept": "concept", "polarity": "instruction"}
cat_opts = (["family"] if family == POOLED else []) + [
    lab for k, lab in FIELDS.items() if len({str(it.get(k)) for f in geo_scope for it in ITEMS[f].values() if it.get(k)}) > 1
] + ["read token", "target in top 10 here", "none"]


def vis(tok: str) -> str:
    t = sources.decode_token(tok)
    return t.replace("\n", "↵") if t.strip() else (t.replace(" ", "␣").replace("\n", "↵") or "∅")


HITS, FORM_HITS = {}, {}  # (family, arm) -> {(item, layer, pos)} whose top 10 holds a target / another form of it
for f in geo_scope:
    for a in chosen:
        adir = sources.arm_dir(a.name)
        hc = sources.hit_cells(f, split, adir, sources.readouts_mtime(f, split, adir))
        HITS[f, a.name] = {(i, L, p) for i, cs in hc.items() for L, p in cs}
        hf = sources.hit_cells(f, split, adir, sources.readouts_mtime(f, split, adir), with_forms=True)
        FORM_HITS[f, a.name] = {(i, L, p) for i, cs in hf.items() for L, p in cs} - HITS[f, a.name]

k1, k2, k3, _ = st.columns([1.3, 1.6, 2.2, 2], vertical_alignment="bottom")
cat = k1.selectbox("Category", cat_opts, key=f"ce_cat_{family}", help="Groups the boxes and colours the clouds. "
                   "Target in top 10 here: whether this centre's readout at the cell holds an accepted target, or only "
                   "another form of it (swims for swimming: a pass under strict + forms only).")
measure = k2.segmented_control("Measure", ["‖h−μ‖/‖h‖", "‖μ‖/‖h‖", "cos(h, μ)"], default="‖h−μ‖/‖h‖", key="ce_measure") or "‖h−μ‖/‖h‖"
layer = k3.select_slider("Layer", layers, value=44 if 44 in layers else layers[len(layers) // 2], key=f"ce_layer_{family}_{split}",
                         format_func=lambda L: f"L{L}")
MEAS = {"‖h−μ‖/‖h‖": lambda g: g["norm_x"] / g["norm_h"], "‖μ‖/‖h‖": lambda g: g["norm_mu"] / g["norm_h"], "cos(h, μ)": lambda g: g["cos"]}[measure]

TOP_TOKENS = 9
tok_count: dict[str, int] = {}
for f in geo_scope:
    for (_, L, _), g in sources.geometry(f, split, "zero", "", mtime(f)).items():
        if L == layer:
            tok_count[vis(g["token"])] = tok_count.get(vis(g["token"]), 0) + 1
top_toks = set(sorted(tok_count, key=lambda t: -tok_count[t])[:TOP_TOKENS])


def category(f: str, i: str, L: int, p: int, tok: str, a) -> str:
    if cat == "family":
        return f
    if cat == "read token":
        t = vis(tok)
        return f"“{t}”" if t in top_toks else "other"
    if cat == "target in top 10 here":
        return ("in top 10" if (i, L, p) in HITS[f, a.name] else
                "other form in top 10" if (i, L, p) in FORM_HITS[f, a.name] else "not in top 10")
    if cat == "none":
        return "all cells"
    field = next(k for k, lab in FIELDS.items() if lab == cat)
    return str(ITEMS[f][i].get(field) or "–").replace("_", " ")


def order(cats) -> list[str]:
    n: dict[str, int] = {}
    for c in cats:
        n[c] = n.get(c, 0) + 1
    return sorted(n, key=lambda c: (c in ("other", "–"), -n[c], c))


PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#86bcb6"]


def cat_colours(cats: list[str]) -> dict[str, str]:
    out, k = {}, 0
    for c in cats:
        if c in ("other", "–"):
            out[c] = ui.c("line-2")
        else:
            out[c], k = PALETTE[k % len(PALETTE)], k + 1
    return out


def rgba(hexc: str, alpha: float) -> str:
    return f"rgba({int(hexc[1:3], 16)},{int(hexc[3:5], 16)},{int(hexc[5:7], 16)},{alpha})"


# ------------------------------------------------------------------ how much of h is left
ui.section("How much of h each centre leaves", "The centred lens reads J (h − μ), so ‖h − μ‖ / ‖h‖ is the share of the "
           "state it still reads: 1 for the plain lens, 0 if μ were h itself. ‖μ‖ / ‖h‖ and cos(h, μ) say how large μ is "
           "and how closely it points along h; together they fix ‖h − μ‖ / ‖h‖.", eyebrow="Norms")

n_left, n_right = st.columns(2, gap="large")
fig = go.Figure()
if measure == "‖h−μ‖/‖h‖":
    fig.add_hline(y=1, line=dict(color=ui.c("h"), width=1.5, dash="dash"),
                  annotation_text="plain lens (μ = 0)", annotation_font=dict(size=11, color=ui.c("muted")))
for a in centred:
    q = []
    for L in layers:
        v = [MEAS(g) for f in geo_scope for (_, LL, _), g in G[f, a.name].items() if LL == L]
        q.append(np.percentile(v, [25, 50, 75]) if v else [np.nan] * 3)
    q = np.array(q)
    fig.add_trace(go.Scatter(x=layers + layers[::-1], y=list(q[:, 2]) + list(q[::-1, 0]), fill="toself",
                             fillcolor=rgba(a.colour, 0.14), line=dict(width=0), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=layers, y=q[:, 1], mode="lines+markers", name=a.label,
                             line=dict(color=a.colour, width=2, dash=a.dash),
                             marker=dict(size=6, color=a.colour), customdata=q[:, [0, 2]],
                             hovertemplate=f"<b>{ui.esc(a.label)}</b> L%{{x}}: median %{{y:.2f}} "
                                           "(IQR %{customdata[0]:.2f}–%{customdata[1]:.2f})<extra></extra>"))
fig.add_vline(x=layer, line=dict(color=ui.c("line-2"), width=1, dash="dash"))
ui.plot_layout(fig, 280)
fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=16, b=8))
fig.update_xaxes(tickvals=layers, ticktext=[f"L{L}" for L in layers])
fig.update_yaxes(title=dict(text=measure, font=dict(size=12, color=ui.c("muted"))))
with n_left:
    ui.label(f"{measure} by layer", "median · band = IQR · dashed = layer below")
    ui.chart(fig, f"ce_keep_{family}_{split}_{measure}")
n_left.caption("Median over read cells at each layer; the band is the interquartile range. The dashed line marks the layer "
           "below.")

# per category at the chosen layer
fig = go.Figure()
all_cats = []
for a in centred:
    xs, ys, hov = [], [], []
    for f in geo_scope:
        for (i, L, p), g in G[f, a.name].items():
            if L != layer:
                continue
            xs.append(category(f, i, L, p, g["token"], a))
            ys.append(MEAS(g))
            hov.append(f"{i} · “{ui.esc(vis(g['token']))}”")
    all_cats += xs
    fig.add_trace(go.Box(x=xs, y=ys, name=a.label, marker=dict(color=a.colour, size=3), line=dict(color=a.colour, width=1.5),
                         fillcolor=rgba(a.colour, 0.18), offsetgroup=a.name, boxpoints="outliers", text=hov,
                         hovertemplate="%{text}<br>%{y:.2f}<extra></extra>"))
cats_order = order(all_cats)
ui.plot_layout(fig, 280)
fig.update_layout(boxmode="group", margin=dict(l=8, r=8, t=12, b=8), boxgap=0.25, boxgroupgap=0.12)
fig.update_xaxes(categoryorder="array", categoryarray=cats_order)
fig.update_yaxes(title=dict(text=f"{measure} at L{layer}", font=dict(size=12, color=ui.c("muted"))))
with n_right:
    ui.label(f"By {cat} at L{layer}", f"{len(all_cats) // max(len(centred), 1)} read cells")
    ui.chart(fig, f"ce_box_{family}_{split}_{measure}_{cat}_{layer}")

rows = []
for a in centred:
    gs = [g for f in geo_scope for (_, L, _), g in G[f, a.name].items() if L == layer]
    keep = np.array([g["norm_x"] / g["norm_h"] for g in gs])
    sup = np.array([g["support"] for g in gs])
    hit = np.array([(i, L, p) in HITS[f, a.name] for f in geo_scope for (i, L, p) in G[f, a.name] if L == layer])
    lo, hi = np.percentile(keep, [25, 75])
    split_at = np.median(keep)
    rows.append([tag(a), f"{len(gs)}", f"{np.median(keep):.2f} <span style='color:var(--muted)'>[{lo:.2f}, {hi:.2f}]</span>",
                 f"{np.median([g['norm_mu'] / g['norm_h'] for g in gs]):.2f}", f"{np.median([g['cos'] for g in gs]):.2f}",
                 f"{np.median(sup):g} <span style='color:var(--muted)'>({sup.min()}–{sup.max()})</span>",
                 f"{np.mean([g['fallback'] for g in gs]):.0%}",
                 f"{hit[keep < split_at].mean():.2f} / {hit[keep >= split_at].mean():.2f}"])
ui.table(["centre", "cells", "‖h−μ‖/‖h‖ [IQR]", "‖μ‖/‖h‖", "cos(h, μ)", "reference cells behind μ", "fell back",
          "in top 10: low / high keep"], rows, num={1, 2, 3, 4, 5, 6, 7})
st.caption(f"All at L{layer}, medians over read cells. Reference cells: how many captured states μ averages (own item and "
           "its group excluded); “fell back” is the share of cells where the same-token centre had too few and used the "
           "family mean. Last column: share of cells with a target in the top 10, among cells keeping less than the "
           "median share of ‖h‖ vs the rest.")

# ------------------------------------------------------------------ the clouds
ui.section("The clouds", "Left: the states h in their top principal directions (about their mean), with each centre's μ "
           "and the origin, which is the plain lens's μ = 0. Right: each centre's read vectors h − μ, in principal "
           "directions about 0, not about their mean: the lens is linear in h − μ, so distance from the origin is what it "
           "reads, and a cloud sitting off the origin still carries a common offset.", eyebrow="PCA")


@st.cache_data(show_spinner="Projecting the states…", max_entries=24)
def clouds(fs: tuple, split: str, layer: int, arm_keys: tuple, k: int, _mt: tuple) -> dict:
    from jlm import geometry as jgeo

    meta, Hs, MUs = [], [], {ak: [] for ak in arm_keys}
    sup = {ak: [] for ak in arm_keys}
    for f in fs:
        s = sources.states(f, split, layer, sources.captures_mtime(f, split))
        meta += [(f, i, p, t) for i, p, t in s["cells"]]
        Hs.append(s["H"])
        for ak in arm_keys:
            c = sources.centres_at(f, split, *ak, layer, sources.captures_mtime(f, split, ak[1]))
            MUs[ak].append(c["MU"])
            sup[ak] += c["support"]
    H = torch.from_numpy(np.concatenate(Hs))
    basis, origin, share = jgeo.pca(H, k)
    out = {"meta": meta, "states": jgeo.project(H, basis, origin).numpy(), "share": share.numpy(),
           "origin": jgeo.project(torch.zeros(1, H.shape[1]), basis, origin).numpy()[0], "mu": {}, "reads": {}}
    for ak in arm_keys:
        MU = np.concatenate(MUs[ak])
        uniq, idx = np.unique(MU, axis=0, return_index=True)
        out["mu"][ak] = {"xy": jgeo.project(torch.from_numpy(uniq), basis, origin).numpy(),
                         "support": [sup[ak][j] for j in idx], "where": [meta[j] for j in idx]}
        X = H - torch.from_numpy(MU)
        b, o, sh = jgeo.pca(X, k, centred=False)
        out["reads"][ak] = {"xy": jgeo.project(X, b, o).numpy(), "share": sh.numpy()}
    b, o, sh = jgeo.pca(H, k, centred=False)  # the plain lens reads h itself
    out["reads"][("zero", "")] = {"xy": jgeo.project(H, b, o).numpy(), "share": sh.numpy()}
    return out


v1, v2, _ = st.columns([1, 1.4, 3], vertical_alignment="bottom")
dims = v1.segmented_control("View", ["2D", "3D"], default="2D", key="ce_dims") or "2D"
show_origin = v2.toggle("Show the origin", value=True, key="ce_origin",
                        help="The origin can sit far from the cloud and squash it; hide it to see the cloud's shape.")
k = 3 if dims == "3D" else 2
arm_keys = tuple(dict.fromkeys((a.centre, a.ref) for a in centred))
C = clouds(tuple(geo_scope), split, layer, arm_keys, 3, tuple(mtime(f) for f in geo_scope))
label_of = {(a.centre, a.ref): a for a in reversed(centred)}  # mu does not depend on the map: the J-lens arm names it


def cloud_cats(a) -> list[str]:
    G0 = {f: sources.geometry(f, split, "zero", "", mtime(f)) for f in geo_scope}
    return [category(f, i, layer, p, G0[f][i, layer, p]["token"], a) for f, i, p, _ in C["meta"]]


def axis_titles(share) -> list[str]:
    return [f"PC{j + 1} · {share[j]:.0%}" for j in range(k)]


def scatter(fig, xy, cats, colours, hover):
    for c in order(cats):
        m = [j for j, x in enumerate(cats) if x == c]
        kw = dict(mode="markers", name=c, text=[hover[j] for j in m], hovertemplate="%{text}<extra>" + ui.esc(c) + "</extra>")
        if k == 3:
            fig.add_trace(go.Scatter3d(x=xy[m, 0], y=xy[m, 1], z=xy[m, 2], marker=dict(size=3, color=colours[c], opacity=0.8), **kw))
        else:
            fig.add_trace(go.Scatter(x=xy[m, 0], y=xy[m, 1], marker=dict(size=6, color=colours[c], opacity=0.75,
                                                                          line=dict(width=0.5, color=ui.c("surface"))), **kw))


def marker(fig, pts, colour, symbol, size, hover, name):
    pts = np.atleast_2d(pts)
    kw = dict(mode="markers", name=name, text=hover, hovertemplate="%{text}<extra></extra>")
    if k == 3:
        fig.add_trace(go.Scatter3d(x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], marker=dict(
            size=[s / 2 for s in size], color=colour, symbol="diamond" if symbol == "diamond" else "x", line=dict(color=ui.c("ink"), width=1)), **kw))
    else:
        fig.add_trace(go.Scatter(x=pts[:, 0], y=pts[:, 1], marker=dict(size=size, color=colour, symbol=symbol,
                                                                         line=dict(color=ui.c("ink"), width=1.2)), **kw))


def finish(fig, share, key, height=440):
    ui.plot_layout(fig, height)
    t = axis_titles(share)
    fig.update_layout(margin=dict(l=8, r=8, t=12, b=8), hovermode="closest")
    if k == 3:
        ax = dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=ui.c("line"), zerolinecolor=ui.c("line-2"),
                  color=ui.c("muted"), showspikes=False)
        fig.update_layout(scene=dict(xaxis=dict(title=t[0], **ax), yaxis=dict(title=t[1], **ax), zaxis=dict(title=t[2], **ax),
                                     aspectmode="cube"))
    else:
        fig.update_xaxes(title=dict(text=t[0], font=dict(size=12, color=ui.c("muted"))))
        fig.update_yaxes(title=dict(text=t[1], font=dict(size=12, color=ui.c("muted"))), scaleanchor="x", scaleratio=1)
    ui.chart(fig, key)


ref_arm = centred[0]  # colours the left panel when the category depends on the centre
cats0 = cloud_cats(ref_arm)
colours = cat_colours(list(dict.fromkeys(order(cats0) + [c for a in chosen for c in order(cloud_cats(a))])))
hover = [f"{f} · {i} · “{ui.esc(vis(t))}”" for f, i, p, t in C["meta"]]
st.html('<div class="jm-legend">' + "".join(f'<span><i style="background:{colours[c]};border-radius:50%"></i>{ui.esc(c)}</span>'
                                            for c in order(cats0)) + "</div>")

left, right = st.columns([1, 1], gap="large")
with left:
    ui.label("States h, centres μ and the origin", f"L{layer} · {len(C['meta'])} cells")
    fig = go.Figure()
    scatter(fig, C["states"], cats0, colours, hover)
    for ak, m in C["mu"].items():
        a = label_of[ak]
        smax = max(m["support"]) or 1
        marker(fig, m["xy"], a.colour, "diamond", [9 + 9 * (s / smax) ** 0.5 for s in m["support"]],
               [f"<b>μ · {ui.esc(a.label)}</b><br>{ui.esc(f)} · for {ui.esc(i)} (“{ui.esc(vis(t))}”) · {s} reference cells"
                for (f, i, p, t), s in zip(m["where"], m["support"], strict=True)], a.label)
    if show_origin:
        marker(fig, C["origin"], ui.c("h"), "x", [14], ["<b>origin</b>: the plain lens's μ = 0"], "origin")
    finish(fig, C["share"], f"ce_states_{family}_{split}_{layer}_{cat}_{dims}_{show_origin}_{'-'.join(a.name for a in centred)}")
    n_mu = {label_of[ak].label: len(m["xy"]) for ak, m in C["mu"].items()}
    st.caption("Diamonds: distinct μ vectors, sized by the reference cells behind each (" + ", ".join(
        f"{lab}: {n}" for lab, n in n_mu.items()) + "). A leave-one-out mean gives one μ per item, so its diamonds nearly "
        "coincide." + (f" Colours by {cat} follow {ref_arm.label}." if cat == "target in top 10 here" else ""))

with right:
    read_key = {"zero": ("zero", ""), **{"@".join(ak): ak for ak in arm_keys}}  # widget options must be strings
    read_label = {"zero": "Plain J-lens (h itself)", **{"@".join(ak): label_of[ak].label for ak in arm_keys}}
    first = "@".join(arm_keys[0])
    pick = read_key[st.segmented_control("Read vectors of", list(read_key), default=first, format_func=read_label.get,
                                         key=f"ce_read_{family}_{split}") or first]
    rd = C["reads"][pick]
    a = label_of.get(pick) or next((x for x in chosen if x.centre == "zero"), None)
    cats = cloud_cats(a) if a else cats0
    fig = go.Figure()
    scatter(fig, rd["xy"], cats, colours, hover)
    if show_origin:
        marker(fig, np.zeros(3), ui.c("h"), "x", [14], ["<b>origin</b>: h − μ = 0"], "origin")
    finish(fig, rd["share"], f"ce_reads_{family}_{split}_{layer}_{cat}_{dims}_{show_origin}_{pick}")
    st.caption("Principal directions about 0 of this centre's h − μ (fitted per centre, so the axes differ between centres; "
               "the shares are of Σ‖h − μ‖²). For the plain lens the first direction is the shared mean of h, which "
               "centring removes.")
