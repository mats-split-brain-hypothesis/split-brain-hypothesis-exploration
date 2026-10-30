"""Means / g compared: two to four centres on one bank, side by side. Per layer, how large g is against h
(||g|| / ||h||, from the rank sidecar where the arm wrote it, else rebuilt from the captures), how closely the arms'
mean g point the same way (cosine per layer, jlm.geometry), and what the mean g decodes to (L(mean g), from the analysis
battery's --decode-g when a study ran it). g is the vector subtracted before the lens: for a mean centre, g = mu."""

import itertools

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import catalog
import sources
import ui

ui.header(
    "Loop",
    "Means / g compared",
    "What each centre subtracts. The centred read is J (h − g); for a mean centre g is μ. Pick a bank and two to four "
    "centres: how large g is against h at each layer, whether their mean g point the same way, and what that mean "
    "decodes to through the lens (what the centre removes on average). Controls (shuffled and random g) keep the "
    "inner centre's ‖g‖ by construction, so their norm curves sit on it; their mean g differs.",
)

fams = sources.families_with_readouts()
if not fams:
    st.info("No readouts under out/eval yet: run experiments/evaluate.py first.")
    st.stop()
stamp = sources.stamp()

c1, c2, c3 = st.columns([1.4, 1.1, 4], vertical_alignment="bottom")
family = c1.selectbox("Family", fams, key="mg_family")
splits = sources.splits_with_readouts(family)
split = c2.segmented_control("Split", splits, default="val" if "val" in splits else splits[0], key=f"mg_split_{family}") or splits[0]

# g does not depend on the readout or the map: one entry per (centre, ref), named by its J-lens arm when there is one
dirs = {catalog.from_dir(d): d for d in sources.arm_dirs(family, split)}
reps: dict[tuple[str, str], catalog.Arm] = {}
for a in sorted((catalog.parse(n) for n in dirs), key=lambda a: (a.lens != "jlens", a.readout != "cos")):
    if a.centre != "zero":
        reps.setdefault((a.centre, a.ref), a)
if not reps:
    st.info(f"No centred arms on {family}/{split}.")
    st.stop()
opts = sorted(reps.values(), key=lambda a: a.sort_key)
by_name = {a.name: a for a in opts}
held = "self" if split == "fit" else "fit"
default = [a.name for a in opts if a.ref == held][:4] or [opts[0].name]
with c3:
    picked = ui.grouped_pills("Centres (2–4)", [a.name for a in opts], lambda n: catalog.group(by_name[n]), default,
                              order=catalog.group_order, fold=catalog.folded, beside=catalog.beside, format_func=lambda n: by_name[n].label, key=f"mg_arms_{family}_{split}",
                              help="g is the same for every readout and lens, so each centre appears once.")
chosen = [by_name[n] for n in sorted(picked or [], key=lambda n: by_name[n].sort_key)][:4]
if not chosen:
    st.info("Select at least one centre (two to four to compare).")
    st.stop()
if len(picked or []) > 4:
    st.caption("Showing the first four selected centres.")
ui.legend_arms(chosen)


def arm_dirs_of(a) -> list[str]:
    """Every evaluated directory with this arm's g (any readout or map)."""
    return [d for n, d in dirs.items() if (catalog.parse(n).centre, catalog.parse(n).ref) == (a.centre, a.ref)]


# ------------------------------------------------------------------ ||g|| / ||h|| per layer
GH, SRC = {}, {}
for a in chosen:
    for d in arm_dirs_of(a):
        gh = sources.g_over_h(family, split, d, sources.readouts_mtime(family, split, d, "ranks"))
        if gh:
            GH[a.name], SRC[a.name] = gh, "ranks.jsonl"
            break
    else:
        try:
            geo = sources.geometry(family, split, a.centre, a.ref, sources.captures_mtime(family, split, a.ref))
        except Exception:  # no captures, or a centre that needs more than they hold (context)
            continue
        acc: dict[int, list[float]] = {}
        for (_, L, _), g in geo.items():
            acc.setdefault(L, []).append(g["norm_mu"] / g["norm_h"])
        GH[a.name], SRC[a.name] = {L: float(np.mean(v)) for L, v in sorted(acc.items())}, "captures"

MEAN, MISSING = {}, []
for a in chosen:
    try:
        MEAN[a.name] = sources.mean_g(family, split, a.centre, a.ref, sources.captures_mtime(family, split, a.ref))
    except Exception as e:  # missing captures, or a centre that needs the context store
        MISSING.append(f"{a.label} ({type(e).__name__})")

left, right = st.columns(2, gap="large")
with left:
    ui.label("‖g‖ / ‖h‖ by layer", "mean over read cells · 1 = g as large as h")
    fig = go.Figure()
    for a in chosen:
        if a.name in GH:
            Ls = list(GH[a.name])
            fig.add_trace(go.Scatter(x=Ls, y=[GH[a.name][L] for L in Ls], mode="lines+markers", name=a.label,
                                     line=dict(color=a.colour, width=2, dash=a.dash), marker=dict(size=6, color=a.colour),
                                     hovertemplate=f"<b>{ui.esc(a.label)}</b> L%{{x}}: %{{y:.3f}}<extra></extra>"))
    if fig.data:
        ui.plot_layout(fig, 280)
        fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=12, b=8))
        Ls = sorted({L for v in GH.values() for L in v})
        fig.update_xaxes(tickvals=Ls, ticktext=[f"L{L}" for L in Ls])
        fig.update_yaxes(rangemode="tozero", title=dict(text="‖g‖ / ‖h‖", font=dict(size=12, color=ui.c("muted"))))
        ui.chart(fig, f"mg_norm_{family}_{split}_{'-'.join(a.name for a in chosen)}")
        st.caption("Source per centre: " + ", ".join(f"{a.label}: {SRC[a.name]}" for a in chosen if a.name in SRC)
                   + ". ranks.jsonl carries h_norm and g_norm from evaluate.py; older arms are rebuilt from the captures.")
    else:
        st.caption("Neither a rank sidecar with g_norm nor captures on disk for these centres.")

with right:
    ui.label("cos between the mean g of two centres", "per layer · 1 = same direction")
    fig = go.Figure()
    pairs = [(a, b) for a, b in itertools.combinations([a for a in chosen if a.name in MEAN], 2)]
    PAIR_COL = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#b07aa1"]
    for k, (a, b) in enumerate(pairs):
        ma, mb = MEAN[a.name], MEAN[b.name]
        Ls = [L for L in ma["layers"] if L in mb["layers"]]
        va = ma["mean"][[ma["layers"].index(L) for L in Ls]]
        vb = mb["mean"][[mb["layers"].index(L) for L in Ls]]
        cos = (va * vb).sum(1) / np.maximum(np.linalg.norm(va, axis=1) * np.linalg.norm(vb, axis=1), 1e-12)
        fig.add_trace(go.Scatter(x=Ls, y=cos, mode="lines+markers", name=f"{a.label} · {b.label}",
                                 line=dict(color=PAIR_COL[k % len(PAIR_COL)], width=2), marker=dict(size=6),
                                 hovertemplate=f"<b>{ui.esc(a.label)}</b> vs <b>{ui.esc(b.label)}</b> L%{{x}}: %{{y:.3f}}<extra></extra>"))
    if fig.data:
        ui.plot_layout(fig, 280)
        fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=12, b=8))
        Ls = sorted({L for m in MEAN.values() for L in m["layers"]})
        fig.update_xaxes(tickvals=Ls, ticktext=[f"L{L}" for L in Ls])
        fig.update_yaxes(range=[-1.02, 1.02], title=dict(text="cos(mean g, mean g′)", font=dict(size=12, color=ui.c("muted"))))
        ui.chart(fig, f"mg_cos_{family}_{split}_{'-'.join(a.name for a in chosen)}")
        st.html('<div class="jm-legend">' + "".join(
            f'<span><i style="background:{PAIR_COL[k % len(PAIR_COL)]}"></i>{ui.esc(a.label)} · {ui.esc(b.label)}</span>'
            for k, (a, b) in enumerate(pairs)) + "</div>")
    elif len(chosen) < 2:
        st.caption("Select a second centre to compare directions.")
    else:
        st.caption("No captures on disk for these centres, so their g cannot be rebuilt.")
if MISSING:
    st.caption("Could not rebuild g from the captures for " + ", ".join(MISSING) + ".")

# ------------------------------------------------------------------ mean g, size and direction, as a table
if MEAN:
    rows = []
    for a in chosen:
        if a.name not in MEAN:
            continue
        m = MEAN[a.name]
        nm = np.linalg.norm(m["mean"], axis=1)
        rows.append([f'<span class="jm-armtag"><i style="background:{a.colour}"></i>{ui.esc(a.label)}</span>',
                     *[f"{x:.1f}" for x in nm]])
    Ls = MEAN[next(iter(MEAN))]["layers"]
    ui.label("‖mean g‖ by layer", "the norm of the average g: near ‖g‖ when g barely varies across cells, small when it does")
    ui.table(["centre", *[f"L{L}" for L in Ls]], rows, num=set(range(1, len(Ls) + 1)))

# ------------------------------------------------------------------ decoded
ui.section("What the mean g decodes to", "Top tokens of L(mean g) under the arm's readout: what the centre removes on "
           "average. From the analysis battery (experiments/analyse.py --decode-g), which loads the lens; arms it has not "
           "decoded show “–”.", eyebrow="L(mean g)")
DEC = sources.g_decoded(family, split, stamp)


def decoded_of(a) -> dict[int, list[str]] | None:
    """The decode of any evaluated arm with this g (the battery keys by arm name)."""
    return next((DEC[n] for n in [a.name, *dirs] if n in DEC and (catalog.parse(n).centre, catalog.parse(n).ref) == (a.centre, a.ref)), None)


have = {a.name: d for a in chosen if (d := decoded_of(a))}
if not have:
    st.caption(f"No decoded g for these centres on {family}/{split} yet: run "
               "`experiments/analyse.py --study <id> --decode-g` (loads the lens; pod or a free Mac).")
else:
    Ls = sorted({L for d in have.values() for L in d})
    head = ["layer", *[f'<span class="jm-armtag"><i style="background:{a.colour}"></i>{ui.esc(a.label)}</span>' for a in chosen]]

    def chips(toks: list[str] | None) -> str:
        if not toks:
            return '<span style="color:var(--muted)">–</span>'
        return '<div class="jm-chips">' + "".join(
            f'<span class="jm-chip">{ui.esc(sources.decode_token(t).replace(chr(10), "↵") or "∅")}</span>' for t in toks[:10]) + "</div>"

    ui.table(head, [[f'<span class="mono">L{L}</span>', *[chips(have.get(a.name, {}).get(L)) for a in chosen]] for L in Ls],
             mono={0})
