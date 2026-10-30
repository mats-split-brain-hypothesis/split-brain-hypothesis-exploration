"""One study run's standard battery (experiments/analyse.py output in out/analysis/<run>/), drawn on the Studies page:
the paired change against each reference across banks, the mention control, and bank by bank the arms with their
controls, pass by layer, rank moves, slices, decoded g and ||g|| / ||h||. Moved here from views/study.py so the page can
show it under a tab."""

import json
from collections import Counter

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import catalog
import sources
import ui

ARMS: dict = {}


def tag(a: str) -> str:
    x = ARMS.get(a) or catalog.parse(a)
    return (f'<span class="jm-armtag" title="{ui.esc(a)}"><i style="background:{x.colour}"></i>{ui.esc(x.label)}'
            f' <span style="color:var(--muted);font-size:12px">{ui.esc(x.readout)}</span></span>')


def rate(r: dict | None) -> str:
    return "–" if not r or r.get("value") is None else f"{r['value']:.2f}"


def num(x) -> str:
    return "–" if x is None else f"{x:.3f}"


def diff(r: dict | None) -> str:
    if not r or r.get("diff") is None:
        return "–"
    lo, hi = r["ci95"]
    col = "--good" if lo > 0 else "--bad" if hi < 0 else "--ink-2"
    flag = " ▲" if lo > 0 else " ▼" if hi < 0 else ""
    return (f'<span style="color:var({col})">{r["diff"]:+.2f}{flag}</span>'
            f'<br><span style="color:var(--muted);font-size:11px">[{lo:+.2f}, {hi:+.2f}]</span>')



def render(study: str, stamp: float) -> None:
    """The battery of run ``study`` (an out/analysis/ folder name)."""
    global ARMS
    S = sources.analysis(study, stamp)
    B = S["banks"]
    if not B:
        st.caption(f"out/analysis/{study}/ has no per-bank battery.")
        if S["summary"]:
            st.markdown(S["summary"])
        return
    ARMS = {a: catalog.parse(a) for r in B.values() for a in r["arms"]}
    # ------------------------------------------------------------------ across banks
    refs = sorted({ref for r in B.values() for d in r["arms"].values() for ref in d.get("vs", {})},
                  key=lambda a: (ARMS.get(a) or catalog.parse(a)).sort_key)
    arm_names = sorted(ARMS, key=lambda a: ARMS[a].sort_key)
    ui.section("Against each reference, across banks", "Paired change in pass (strict / piece proxy) per bank, 95 % "
               "interval below. ▲ / ▼: the interval excludes 0. Macro: the mean over banks; guardrail: banks where the arm "
               "loses outside the interval.", eyebrow="")
    if refs:
        ref = st.segmented_control("Reference", refs, default=refs[0], key=f"st_ref_{study}",
                                   format_func=lambda a: (ARMS.get(a) or catalog.parse(a)).label + f" ({a})") or refs[0]
        cols = [a for a in arm_names if a != ref and any(ref in r["arms"].get(a, {}).get("vs", {}) for r in B.values())]
        rows, gains, harms = [], {a: [] for a in cols}, {a: [] for a in cols}
        for bank, r in B.items():
            cells = []
            for a in cols:
                v = r["arms"].get(a, {}).get("vs", {}).get(ref)
                cells.append(diff(v["paired"]) if v else "–")
                if v and v["paired"].get("diff") is not None:
                    gains[a].append(v["paired"]["diff"])
                    if v["paired"]["ci95"][1] < 0:
                        harms[a].append(bank)
            rows.append([f'<span class="mono">{ui.esc(bank)}</span>', str(r.get("n_scored", "")), *cells])
        rows.append(["<b>macro</b>", "", *[f"<b>{np.mean(gains[a]):+.3f}</b>" if gains[a] else "–" for a in cols]])
        rows.append(["guardrail", "", *[('<span style="color:var(--good)">ok</span>' if not harms[a] else
                                         '<span style="color:var(--bad)">' + ", ".join(harms[a]) + "</span>") if gains[a] else "–"
                                        for a in cols]])
        ui.table(["bank", "n", *[tag(a) for a in cols]], rows, num=set(range(1, len(cols) + 2)))
    else:
        st.caption("No reference arms in this study's battery.")
    if S["summary"]:
        with st.expander("summary.md as written by analyse.py"):
            st.markdown(S["summary"])

    # ------------------------------------------------------------------ mention control
    runs = sorted((sources.ANALYSIS / study).glob("mention*/summary.json"))
    if runs:
        ui.section("Mention control", "umot's bank (experiments/u1_mention.py): pass@10 of the concept the prompt asks the "
                   "model to hold vs the same concept only mentioned, in the same carrier sentences. A fair centre raises "
                   "held far above mentioned; a prompt reader raises both. Only meaningful when the centre's references "
                   "contain the probe's own carriers (research-loop.md, Controls).", eyebrow="")
        mc_cols = st.columns(min(len(runs), 2))
        for k, p in enumerate(runs):
            rows = []
            for a, by_scope in json.loads(p.read_text())["arms"].items():
                cells = []
                for sc in ("all", "mid-sentence", "final . L>=42"):
                    x = by_scope.get(sc, {})
                    cells += [num(x.get("held")), num(x.get("mentioned")), diff(x.get("held - mentioned"))]
                rows.append([f'<span class="mono">{ui.esc(a)}</span>', *cells])
            with mc_cols[k % len(mc_cols)]:
                st.caption(p.parent.name)
                ui.table(["arm", "held", "mentioned", "diff", "mid: held", "mentioned", "diff", "final .: held",
                          "mentioned", "diff"], rows, num=set(range(1, 10)))

    # ------------------------------------------------------------------ one bank
    ui.section("Bank by bank")
    bank = st.selectbox("Bank", list(B), key=f"st_bank_{study}")
    r = B[bank]
    arms_here = sorted(r["arms"], key=lambda a: ARMS[a].sort_key)
    st.caption(f"{bank} · {r.get('scorer', '')} · n scored {r.get('n_scored', '')}.")

    rows = []
    for a in arms_here:
        d = r["arms"][a]
        first = Counter({k: v for k, v in d.get("first_layer", {}).items() if k != "None"})
        mode = first.most_common(1)[0][0] if first else "–"
        never = d.get("first_layer", {}).get("None", 0)
        j = d.get("judged")
        rows.append([tag(a), rate(d.get("pass")), rate(d.get("strict_masked")),
                     rate(j) + (f' <span style="color:var(--muted);font-size:11px">{ui.esc(sources.run_label(j["run"]))}</span>' if j else ""),
                     num(d.get("echo")), num(d.get("next_overlap")), f"L{mode}" if mode != "–" else "–", str(never)])
    ui.table(["arm", "pass", "masked pass", "judged", "echo", "next-token overlap", "first pass (mode)", "never pass"], rows,
             num={1, 2, 3, 4, 5, 6, 7})

    left, right = st.columns(2, gap="large")
    with left:
        ui.label("Pass by layer", "share of scored items with a target in the top 10 at that layer")
        fig = go.Figure()
        Ls = r.get("layers") or sorted({int(L) for d in r["arms"].values() for L in d.get("layer_curve", {})})
        for a in arms_here:
            lc = {int(L): v for L, v in r["arms"][a].get("layer_curve", {}).items()}
            if lc:
                x = ARMS[a]
                fig.add_trace(go.Scatter(x=Ls, y=[lc.get(L) for L in Ls], mode="lines+markers", name=x.label,
                                         line=dict(color=x.colour, width=2, dash=x.dash), marker=dict(size=6, color=x.colour),
                                         hovertemplate=f"<b>{ui.esc(x.label)}</b> L%{{x}}: %{{y:.2f}}<extra></extra>"))
        ui.plot_layout(fig, 280)
        fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=12, b=8))
        fig.update_xaxes(tickvals=Ls, ticktext=[f"L{L}" for L in Ls])
        fig.update_yaxes(range=[0, 1.02])
        ui.chart(fig, f"st_layers_{study}_{bank}")
        ui.legend_arms([ARMS[a] for a in arms_here])

    with right:
        vs = {(a, b) for a in arms_here for b in r["arms"][a].get("vs", {})}
        # each pair once: a reference against an arm it sorts before is the mirror of that arm against it
        pairs = sorted(((a, b) for a, b in vs if not ((b, a) in vs and ARMS[a].sort_key < ARMS[b].sort_key)),
                       key=lambda ab: (ARMS[ab[0]].sort_key, ARMS[ab[1]].sort_key))
        ui.label("How item ranks moved", "best target rank per item, arm against reference")
        if pairs:
            CATS = [("entered top 10", "good"), ("improved outside", "delta"), ("stayed in top 10", "line-2"),
                    ("unchanged outside", "line"), ("worsened outside", "warn"), ("left top 10", "bad"),
                    ("no single-token target", "sunk")]
            fig = go.Figure()
            ylab = [f"{ARMS[a].label} vs {(ARMS.get(b) or catalog.parse(b)).label}" for a, b in pairs]
            for cat, col in CATS:
                xs = [r["arms"][a]["vs"][b]["ranks"]["categories"].get(cat, 0) for a, b in pairs]
                if any(xs):
                    fig.add_trace(go.Bar(y=ylab, x=xs, orientation="h", name=cat, marker=dict(color=ui.c(col)),
                                         hovertemplate=f"%{{y}}<br>{cat}: %{{x}}<extra></extra>"))
            ui.plot_layout(fig, 70 + 34 * len(pairs))
            fig.update_layout(barmode="stack", margin=dict(l=8, r=8, t=12, b=8), showlegend=True,
                              legend=dict(orientation="h", y=-0.15, font=dict(size=11)))
            fig.update_yaxes(autorange="reversed")
            ui.chart(fig, f"st_ranks_{study}_{bank}")
            with st.expander("Items won and lost"):
                for a, b in pairs:
                    v = r["arms"][a]["vs"][b]
                    st.html(f'<div style="font-size:13px;margin-bottom:6px">{tag(a)} vs {tag(b)}: '
                            f'<span style="color:var(--good)">won {len(v["won"])}</span> '
                            f'<span class="mono" style="font-size:11.5px">{ui.esc(" ".join(v["won"]))}</span> · '
                            f'<span style="color:var(--bad)">lost {len(v["lost"])}</span> '
                            f'<span class="mono" style="font-size:11.5px">{ui.esc(" ".join(v["lost"]))}</span></div>')
        else:
            st.caption("No reference comparisons in this bank.")

    # slices | decoded g
    left, right = st.columns(2, gap="large")
    with left:
        sl = r.get("slices") or {}
        if sl:
            sname = st.selectbox("Slice", list(sl), key=f"st_slice_{study}_{bank}")
            vals = sl[sname]
            ui.label(f"Pass by {sname}", "n items per value under the bars")
            xs = [f"{v} (n {d['n']})" for v, d in vals.items()]
            fig = go.Figure()
            for a in arms_here:
                if any(a in d for d in vals.values()):
                    x = ARMS[a]
                    fig.add_trace(go.Bar(x=xs, y=[d.get(a) for d in vals.values()], name=x.label, marker=dict(color=x.colour),
                                         hovertemplate=f"<b>{ui.esc(x.label)}</b> %{{x}}: %{{y:.2f}}<extra></extra>"))
            ui.plot_layout(fig, 300)
            fig.update_layout(barmode="group", margin=dict(l=8, r=8, t=12, b=8), bargap=0.25)
            fig.update_yaxes(range=[0, 1.02])
            ui.chart(fig, f"st_slice_{study}_{bank}_{sname}")
        else:
            st.caption("No slices in this bank's battery.")
    with right:
        ui.label("L(mean g) decoded", "what each centre removes on average")
        dec = r.get("g_decoded") or {}
        if dec:
            Ls = sorted({int(L) for per in dec.values() for L in per})
            L = st.select_slider("Layer", Ls, value=Ls[len(Ls) // 2], format_func=lambda L: f"L{L}", key=f"st_dec_{study}_{bank}")
            rows = []
            for a, per in dec.items():
                toks = per.get(str(L)) or per.get(L) or []
                rows.append([tag(a), '<div class="jm-chips">' + "".join(
                    f'<span class="jm-chip">{ui.esc(sources.decode_token(t).replace(chr(10), "↵") or "∅")}</span>' for t in toks[:12])
                    + "</div>"])
            ui.table(["arm", f"top tokens of L(mean g) at L{L}"], rows)
        else:
            st.caption("Not decoded for this bank: run analyse.py with `--decode-g` (loads the lens).")
        gh = {a: {int(L): v for L, v in r["arms"][a].get("g_over_h", {}).items()} for a in arms_here}
        gh = {a: v for a, v in gh.items() if v}
        if gh:
            ui.label("‖g‖ / ‖h‖ by layer", "from the rank sidecar")
            fig = go.Figure()
            for a, v in gh.items():
                x = ARMS[a]
                fig.add_trace(go.Scatter(x=list(v), y=list(v.values()), mode="lines+markers", name=x.label,
                                         line=dict(color=x.colour, width=2, dash=x.dash), marker=dict(size=5, color=x.colour)))
            ui.plot_layout(fig, 200)
            fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=12, b=8))
            fig.update_yaxes(rangemode="tozero")
            ui.chart(fig, f"st_gh_{study}_{bank}")
