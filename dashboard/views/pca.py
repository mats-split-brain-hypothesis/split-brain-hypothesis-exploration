"""Removing principal components: what pco<k> does (studies/S7.md), why it helps multihop and hurts multilingual_mt,
the family's PCs read through the J-lens, and the scores. Data: out/analysis/S7/extra/{explainer,pcs}.json
(experiments/s7_pc_explainer.py, experiments/s7_pcs.py), out/analysis/S7/ (the val battery), out/eval/*/fit (k sweep)."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import figures
import gloss
import sources
import ui

stamp = sources.stamp()
PC = sources.pc_explainer(stamp)
EXP, TGT = PC["explainer"], PC["targets"]
LAYERS = ["36", "44", "48", "56"]
#: Categorical slots in fixed order (dataviz reference palette, validated), light / dark; "other" is grey.
CAT = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500"),
       ("#e87ba4", "#d55181"), ("#008300", "#008300"), ("#6250d6", "#9085e9"), ("#e34948", "#e66767")]
#: Multihop val cells where the family mean reads the final answer and pco16 the bridge (found from the readouts).
EXAMPLES = [("dev-mh-b-004", 44), ("dev-mh-a-058", 44), ("dev-mh-a-028", 44)]


def cat(k: int) -> str:
    return CAT[k][1 if ui.night() else 0]


def dec(tok: str) -> str:
    return sources.decode_token(tok).replace("\n", "\\n")


def glossed(tok: str) -> str:
    t = dec(tok)
    g = gloss.gloss(t)
    return f"{t.strip() or '␣'} ({g})" if g else (t.strip() or "␣")


def hit(tok: str, marks: dict[str, str]) -> str | None:
    """The colour token of the word in ``marks`` (lower-case) that a readout token spells, directly, as a 3+ letter
    prefix, or through its English gloss (委内瑞拉 -> Venezuela); None when it spells none."""
    text = dec(tok)
    for key in (text.strip().lower(), (gloss.gloss(text) or "").strip().lower()):
        for w, c in marks.items():
            if key and (key == w or (len(key) >= 3 and w.startswith(key))):
                return c
    return None


def chip_row(tokens: list[str], marks: dict[str, str]) -> str:
    """Token chips, a token spelling a word of ``marks`` coloured with that word's colour token."""
    out = []
    for t in tokens:
        text = dec(t)
        hit_ = hit(t, marks)
        g = gloss.gloss(text)
        style = (f' style="background:var(--{hit_}-soft);color:var(--{hit_});font-weight:600"' if hit_ else "")
        out.append(f'<span class="jm-chip"{style}>{ui.esc(text.strip() or "␣")}'
                   + (f'<span style="color:var(--muted);font-size:11px"> {ui.esc(g)}</span>' if g else "") + "</span>")
    return '<div class="jm-chips">' + "".join(out) + "</div>"


def marks_for(fam: str, item: dict) -> dict[str, str]:
    """Words to colour in a readout: on multihop the bridge (scored, teal) and the final answer (unscored, amber)."""
    m = {}
    if fam.startswith("multihop"):
        for b in item.get("intermediates") or []:
            m[b.lower()] = "delta"
        if item.get("target"):
            m[item["target"].lower()] = "mu"
    elif item.get("target"):
        m[item["target"].lower()] = "delta"
    return m


ui.header(
    "Understand",
    "Removing principal components",
    'The <code>pco</code> centres read <span class="m">J<sub>l</sub> (I − V<sub>k</sub>V<sub>k</sub><sup>⊤</sup>)'
    '(<span class="c-h">h</span> − <span class="c-mu">μ</span><sub>fam</sub>)</span>: centre on the family mean, then also '
    "remove the state's component along the family's top <i>k</i> principal directions. This page explains what those "
    "directions are, why removing them helps on some families (multihop above all) and hurts on others, and what the "
    "directions themselves read as through the J-lens. Study S7 (with jle's earlier pco, x90f–x99).",
)

if EXP is None:
    st.info("out/analysis/S7/extra/explainer.json is missing: run `python experiments/s7_pc_explainer.py` (about 7 min "
            "on a Mac, loads the lens) or pull it from the shared dataset.")
    st.stop()

var16 = {f: sum(EXP[f]["layers"]["48"]["var16"]) for f in EXP}
st.html('<div class="jm-stats">'
        '<div class="jm-stat"><span class="v c-d">+0.11</span><span class="l">multihop, pco16 vs family mean, val strict '
        "[+0.02, +0.19]</span></div>"
        '<div class="jm-stat"><span class="v c-d">+0.039</span><span class="l">macro over 11 families, val strict '
        "(+0.034 without UM)</span></div>"
        f'<div class="jm-stat"><span class="v">{min(var16.values()):.0%}–{max(var16.values()):.0%}</span><span class="l">'
        "of a family's between-item variance in its top 16 PCs (L48, fit)</span></div>"
        '<div class="jm-stat"><span class="v" style="color:var(--bad)">−0.11</span><span class="l">multilingual_mt, '
        "judged: the cost that kept pco16 unregistered</span></div></div>")

# ------------------------------------------------------------------ 1
ui.section("What the principal components of a family are", eyebrow="1 · The construction")
left, right = st.columns([1, 1], gap="large")
with left:
    ui.figure(figures.pc_split(), "<b>Schematic, two of 5,120 dimensions.</b> Grey dots are the family's fit read "
              "cells. The family mean removes what every item shares; the principal directions are where the items "
              "then still differ most. pco reads only the teal part.", narrow=True)
with right:
    ui.prose(
        "Take one family (say multihop) and one layer. Its <b>reference cells</b> are the read cells of the family's "
        "<code>fit</code> items, about 85 states of dimension 5,120 (the read cell's own item group is always left out). "
        'Subtract the family mean <span class="m c-mu">μ</span><sub>fam</sub> from each and run a PCA. The top '
        'direction <span class="m">v<sub>1</sub></span> is the single axis along which these items differ most, '
        '<span class="m">v<sub>2</sub></span> the next one at right angles, and so on.',
        "Because the lens is read off one state per item, the cloud has at most 84 real directions. The top 16 hold most "
        f"of its spread: {var16['multihop']:.0%} of the variance on multihop at L48, "
        f"{min(var16.values()):.0%}–{max(var16.values()):.0%} across families. Removing them takes out on average about "
        "60 % of a multihop cell's centred ‖x‖².",
        "So the family mean removes <i>what every item shares</i> (the template, the continuation prior). The top PCs "
        "remove the next layer down: <i>the ways items in this family typically differ from each other</i>. What is "
        "left is what is unusual about this particular item.",
    )
    ui.eq(r"x = h - \mu_{\text{fam}}, \qquad \text{read } J_l\,(I - V_k V_k^{\top})\,x"
          r"\quad\Longleftrightarrow\quad g(h) = \mu_{\text{fam}} + V_k V_k^{\top}(h - \mu_{\text{fam}})", key=True,
          note="As a centre, g moves with h along the family's main axes: it is the best guess of h from its coordinates "
               "on those axes. That is why pco behaves like a soft token mean or a kNN mean (S4, insight 7).")

ui.section("Why this can help: recurring variation versus item-specific content", eyebrow="2 · The intuition")
left, right = st.columns([1, 1], gap="large")
with left:
    ui.prose(
        "PCA ranks directions by how much <i>many</i> items move along them. A direction ranks high only when the "
        "variation it carries <b>recurs</b>: a group of items all shift the same way. In a family that is usually "
        "something structural, such as which token is being read, the prompt's genre, the type of answer, or the language.",
        "An item's specific content tends to be idiosyncratic. Each multihop item's bridge (Hungary, Venezuela, sulfur) "
        "points its own way in the residual stream, so no single bridge contributes much to any top direction. Removing "
        "the top directions therefore strips recurring structure and mostly spares item-specific content. Word-embedding "
        "work found the same effect (\"all-but-the-top\": remove the mean and the top few PCs, and similarities improve).",
        "Because the lens is linear, the readout splits exactly:",
    )
    ui.eq(r"L(x) \;=\; L(V_k V_k^{\top} x) \;+\; L\big((I - V_k V_k^{\top})\,x\big)",
          note="Every vocabulary token's score is the removed part's score plus the kept part's. pco16 subtracts the "
               "removed part's readout from the family-mean readout.")
with right:
    x = EXP["multihop"]["layers"]["44"]["cells"]
    ex = next((c for c in x if c["id"] == EXAMPLES[0][0]), None)
    if ex and "read" in ex:
        item = EXP["multihop"]["items"][ex["id"]]
        mk = marks_for("multihop", item)
        part = {k: [(glossed(t), hit(t, mk)) for t in v] for k, v in ex["read"].items()}
        ui.figure(figures.pc_readout_split(part["full"], part["removed"], part["kept"]),
                  f'<b>One real cell</b>, multihop/val <code>{ex["id"]}</code> at L44: “{ui.esc(item["prompt"])}”. '
                  f'Bridge <b style="color:var(--delta)">{ui.esc(", ".join(item["intermediates"]))}</b> (scored), final '
                  f'answer <b style="color:var(--mu)">{ui.esc(item["target"])}</b> (not scored). Top 6 tokens of each part.')

# ------------------------------------------------------------------ 3
ui.section("What a top PC can hold, and what removing it does", "Three regimes that S7's diagnosis found. Which one a "
           "family is in decides whether pco helps it.", eyebrow="3 · Three cases")
ui.figure(figures.pc_cases(), "<b>Schematic.</b> Amber: the part along the top axis, removed. Teal: the part off it, "
          "kept and read. The numbers are val strict paired differences against the family mean (multilingual_mt: Haiku-"
          "judged). The decoded PCs below show which regime each family's axes are in.")

# ------------------------------------------------------------------ 4
ui.section("The PCs themselves, read through the J-lens",
           "Each principal direction is a vector in the residual stream, so it can be read like any state: scale it to a "
           "typical centred norm and take the cos readout <span class=\"m\">W<sub>U</sub> J<sub>l</sub> v</span>. A "
           "direction has no preferred sign, so both ends are shown. PCs fitted on the fit split, exactly as the pco16 "
           "val arm uses them.", eyebrow="4 · Decoding the directions")
fams = list(EXP)
c1, c2, c3 = st.columns([2, 2, 3])
fam = c1.selectbox("Family", fams, index=fams.index("multihop"), key="pca_fam")
layer = c2.segmented_control("Layer", LAYERS, default="48", key="pca_layer") or "48"
D = EXP[fam]["layers"][layer]
c3.html(f'<div style="font-size:13px;color:var(--muted);padding-top:30px">{D.get("n_fit", "?")} fit cells · top 16 PCs hold '
        f'{sum(D["var16"]):.0%} of the variance · removing them takes '
        f'{np.mean([c["share"] for c in D["cells"]]):.0%} of a val cell\'s centred ‖x‖² on average</div>')
rows = []
for j in range(len(D["decoded"]["+"])):
    rows.append([f"<b>PC{j + 1}</b>", f"{D['var16'][j]:.1%}",
                 '<span class="wrap">' + " · ".join(ui.esc(glossed(t)) for t in D["decoded"]["+"][j]) + "</span>",
                 '<span class="wrap">' + " · ".join(ui.esc(glossed(t)) for t in D["decoded"]["-"][j]) + "</span>"])
ui.table(["PC", "variance", "+ end reads", "− end reads"], rows, num={1}, mono={2, 3})
st.caption("Glosses in brackets are from the one-time Haiku table (data/gloss/en.json), a reading aid only. Things to "
           "look for: multihop's axes are answer types (country / city names, numbers, months, materials); "
           "multilingual_mt's include languages and 'what is it called'; user_modeling's are the prompt's genre "
           "(biography, Wikipedia, realistic / hypothetical); directed_modulation's include end-of-text and sentence "
           "punctuation, i.e. position in the sentence.")

# ------------------------------------------------------------------ 5
ui.section("Where the held-out items sit on those axes",
           "Each dot is one val read cell, projected onto two of the fit PCs (the same directions as the table above). "
           "Clusters along an axis are the groups of items that axis separates.", eyebrow="5 · The cloud")
items = EXP[fam]["items"]
fields = [f for f in ("subfamily", "lang") if len({(items.get(c["id"]) or {}).get(f) for c in D["cells"]} - {None}) > 1]
c1, c2, c3 = st.columns([2, 2, 3])
pair = c1.selectbox("Axes", ["PC1 × PC2", "PC1 × PC3", "PC2 × PC3", "PC3 × PC4", "PC1 × PC4", "PC5 × PC6"], key="pca_pair")
colour_by = c2.selectbox("Colour by", [*fields, "read token"], key="pca_colour")
a, b = (int(p.strip()[2:]) - 1 for p in pair.split("×"))


def label_of(c: dict) -> str:
    if colour_by == "read token":
        return dec(c["token"]).strip() or "␣"
    return str((items.get(c["id"]) or {}).get(colour_by) or "–")


labs = [label_of(c) for c in D["cells"]]
order = [k for k, _ in sorted(((k, labs.count(k)) for k in set(labs)), key=lambda kv: (-kv[1], kv[0]))]
shown = order[: len(CAT) - 1] if len(order) > len(CAT) else order
left, right = st.columns([3, 2], gap="large")
with left:
    fig = go.Figure()
    for k, name in enumerate([*shown, "other"]):
        idx = [i for i, lab in enumerate(labs) if (lab == name if name != "other" else lab not in shown)]
        if not idx:
            continue
        cs = [D["cells"][i] for i in idx]
        hover = []
        for c in cs:
            it = items.get(c["id"]) or {}
            p = (it.get("prompt") or "")[-90:]
            hover.append(f"<b>{ui.esc(c['id'])}</b> · read “{ui.esc(dec(c['token']).strip())}”<br>…{ui.esc(p)}<br>"
                         f"target {ui.esc(it.get('target') or '')}"
                         + (f" · bridge {ui.esc(', '.join(it['intermediates']))}" if it.get("intermediates") else "")
                         + f"<br>removed share of ‖x‖² {c['share']:.0%}")
        fig.add_scatter(x=[c["z"][a] for c in cs], y=[c["z"][b] for c in cs], mode="markers", name=f"{name} ({len(cs)})",
                        marker=dict(size=9, color=cat(k) if name != "other" else ui.c("line-2"),
                                    line=dict(width=1.5, color=ui.c("surface"))),
                        hovertext=hover, hoverinfo="text")
    ui.plot_layout(fig, 430)
    fig.update_layout(showlegend=True, legend=dict(orientation="v", x=1.01, y=1, font=dict(size=12)))
    fig.update_xaxes(title=f"PC{a + 1} coordinate", zeroline=True, zerolinecolor=ui.c("line-2"))
    fig.update_yaxes(title=f"PC{b + 1} coordinate", zeroline=True, zerolinecolor=ui.c("line-2"))
    ui.chart(fig, "pca_cloud")
with right:
    ev = np.cumsum(D["ev"][:48])
    fig = go.Figure()
    fig.add_scatter(x=list(range(1, len(ev) + 1)), y=ev, mode="lines+markers", line=dict(color=ui.c("h"), width=2),
                    marker=dict(size=5), hovertemplate="top %{x} PCs: %{y:.0%} of the variance<extra></extra>")
    fig.add_vline(x=16, line=dict(color=ui.c("mu"), dash="dash", width=1.5))
    fig.add_annotation(x=16, y=0.05, text="k = 16 (pco16)", showarrow=False, xanchor="left", xshift=6,
                       font=dict(color=ui.c("mu"), size=12))
    ui.plot_layout(fig, 430)
    fig.update_xaxes(title="number of top PCs")
    fig.update_yaxes(title="share of the family's variance (fit)", tickformat=".0%", range=[0, 1])
    ui.chart(fig, "pca_spectrum")
st.caption(f"{fam} · L{layer} · {len(D['cells'])} val read cells, none of which helped fit the PCs. Hover a dot for its "
           "prompt. On multihop, colour by subfamily: the country items, whose answers are capitals, separate from the "
           "calendar, number and material items along the top axes, and those axes decode to the answer types.")

# ------------------------------------------------------------------ 6
ui.section("Multihop: removing the answer frees the bridge",
           "For each val cell, where does the target rank in the readout of the removed part, and where in the kept part? "
           "A low rank means that part carries the target. Median over items, PCs fitted on fit (experiments/s7_pcs.py).",
           eyebrow="6 · Where the target lives")
if TGT:
    c1, _ = st.columns([2, 5])
    tfam = c1.selectbox("Family", list(TGT), index=list(TGT).index("multihop"), key="pca_tfam")
    T = TGT[tfam]["rows"]
    tl = [20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60][: len(T["removed"])]
    left, right = st.columns([3, 2], gap="large")
    with left:
        fig = go.Figure()
        series = [("removed", "target in the removed part", "mu", "solid"), ("kept", "target in the kept part (pco16)", "delta", "solid"),
                  ("answer removed", "final answer in the removed part", "mu", "dot"),
                  ("answer kept", "final answer in the kept part", "delta", "dot")]
        for key, name, tok, dash in series:
            if key in T:
                fig.add_scatter(x=tl, y=[v + 1 for v in T[key]], name=name, mode="lines+markers",
                                line=dict(color=ui.c(tok), width=2, dash=dash), marker=dict(size=8),
                                hovertemplate=f"{name}<br>L%{{x}}: median rank %{{customdata}}<extra></extra>",
                                customdata=T[key])
        fig.add_hrect(y0=1, y1=10, fillcolor=ui.rgba("good", 0.08), line_width=0)
        fig.add_annotation(x=tl[0], y=np.log10(3), text="top 10", showarrow=False, xanchor="left",
                           font=dict(color=ui.c("good"), size=11))
        ui.plot_layout(fig, 400)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.18, font=dict(size=12)))
        fig.update_yaxes(type="log", autorange="reversed", title="median rank + 1 (log; up is better)")
        fig.update_xaxes(title="layer")
        ui.chart(fig, "pca_targets")
    with right:
        fig = go.Figure()
        fig.add_bar(x=tl, y=T["share"], marker=dict(color=ui.c("mu"), cornerradius=4),
                    hovertemplate="L%{x}: %{y:.0%} of ‖x‖² removed<extra></extra>")
        ui.plot_layout(fig, 400)
        fig.update_yaxes(title="share of the centred ‖x‖² removed", tickformat=".0%", range=[0, 1])
        fig.update_xaxes(title="layer")
        ui.chart(fig, "pca_share")
    if tfam == "multihop":
        ui.prose(
            "The two parts carry different things. The unscored <b style=\"color:var(--mu)\">final answer</b> is "
            "well represented in the removed part (median rank 360 at L44, 30 at L56): the top PCs are the answer-type "
            "axes. The scored <b style=\"color:var(--delta)\">bridge</b> ranks thousands deep there (3,877 at L44) but "
            "reaches the top 10 in the kept part from L52. Subtracting the removed part's readout pushes the answer's type "
            "down (in the example above: city, 首都, столицы) and the answer with it, which leaves room in the top 10 for "
            "the bridge: that is the +0.11.")
    elif tfam == "multilingual_mt":
        ui.prose("Here the pattern reverses at L36–44: the target concept ranks better in the <b style=\"color:var(--mu)\">"
                 "removed</b> part (41–82) than in the kept part (70–135). The family's top axes are its content (the "
                 "language and the concept), so removing them removes the answer. This is the judged −0.11.")

# ------------------------------------------------------------------ 7
ui.section("Read any cell three ways", "The centred state (what the family mean reads), the removed part, and the kept "
           "part (what pco16 reads), at one cell. One-cell families only. Multihop: bridge in teal, final answer in amber.",
           eyebrow="7 · Cell by cell")
split_fams = [f for f in EXP if any("read" in c for c in EXP[f]["layers"]["44"]["cells"])]


def cell_by_cell(split_fams: list[str]) -> None:
    c1, c2, c3 = st.columns([2, 4, 2])
    rfam = c1.selectbox("Family", split_fams, index=split_fams.index("multihop") if "multihop" in split_fams else 0, key="pca_rfam")
    ids = list(dict.fromkeys(c["id"] for c in EXP[rfam]["layers"]["44"]["cells"]))
    default = ids.index(EXAMPLES[0][0]) if rfam == "multihop" and EXAMPLES[0][0] in ids else 0
    ex_ids = [i for i, _ in EXAMPLES]

    def item_label(i: str) -> str:
        it = EXP[rfam]["items"].get(i) or {}
        star = "★ " if i in ex_ids else ""
        return f"{star}{i} · {(it.get('prompt') or '')[-60:]}"

    iid = c2.selectbox("Item (★ = found where fam reads the answer and pco16 the bridge)", ids, index=default,
                       format_func=item_label, key="pca_item")
    rl = c3.segmented_control("Layer", LAYERS, default="44", key="pca_rlayer") or "44"
    cell = next(c for c in EXP[rfam]["layers"][rl]["cells"] if c["id"] == iid)
    it = EXP[rfam]["items"][iid]
    mk = marks_for(rfam, it)
    st.html(f"""<div class="jm-ex">
      <div class="hd"><span class="prompt">{ui.esc(it.get('prompt') or '')}</span>
        <span class="loc">{iid} · L{rl} · read “{ui.esc(dec(cell['token']).strip())}” · target <b style="color:var(--delta)">{ui.esc(', '.join(it.get('intermediates') or []) if rfam.startswith('multihop') else it.get('target') or '')}</b>
        {f' · final answer <b style="color:var(--mu)">{ui.esc(it.get("target") or "")}</b>' if rfam.startswith('multihop') else ''} · {cell['share']:.0%} of ‖x‖² removed</span></div>
      <div class="row"><div class="lab"><b>x = h − μ (fam)</b>the family-mean readout</div>{chip_row(cell['read']['full'], mk)}</div>
      <div class="row"><div class="lab"><b style="color:var(--mu)">V Vᵀ x</b>removed by pco16</div>{chip_row(cell['read']['removed'], mk)}</div>
      <div class="row"><div class="lab"><b style="color:var(--delta)">(I − V Vᵀ) x</b>what pco16 reads</div>{chip_row(cell['read']['kept'], mk)}</div>
    </div>""")


if split_fams:
    cell_by_cell(split_fams)
else:
    st.info("This explainer.json has no per-cell readouts: rerun experiments/s7_pc_explainer.py.")

# ------------------------------------------------------------------ 8
ui.section("Does it help? Scores and controls", eyebrow="8 · The numbers")
S7 = sources.analysis("S7", stamp)["banks"]
left, right = st.columns([3, 2], gap="large")
with left:
    ui.label("Held-out val, strict: paired change against the family mean", "95 % intervals")
    arms = [("pco16@fit|cos", "pco16", "delta"), ("pcr16@fit|cos", "random 16-dim subspace (control)", "line-2"),
            ("shuf.pco16@fit|cos", "another cell's g (control)", "muted")]
    banks_ = [b for b in S7 if b.endswith("/val")]
    fig = go.Figure()
    for k, (arm, name, tok) in enumerate(arms):
        ds, lo, hi = [], [], []
        for bnk in banks_:
            p = (((S7[bnk]["arms"].get(arm) or {}).get("vs") or {}).get("fam@fit|cos") or {}).get("paired") or {}
            d = p.get("diff")
            ds.append(d)
            lo.append(d - p["ci95"][0] if d is not None else None)
            hi.append(p["ci95"][1] - d if d is not None else None)
        fig.add_scatter(y=[b.split("/")[0] for b in banks_], x=ds, mode="markers", name=name,
                        marker=dict(size=10 if k == 0 else 8, color=ui.c(tok), symbol="circle" if k == 0 else "diamond",
                                    line=dict(width=1.5, color=ui.c("surface"))),
                        error_x=dict(type="data", symmetric=False, array=hi, arrayminus=lo, color=ui.c(tok), thickness=1.5, width=0),
                        offsetgroup=str(k), hovertemplate=f"{name}<br>%{{y}}: %{{x:+.3f}}<extra></extra>")
    fig.add_vline(x=0, line=dict(color=ui.c("ink-2"), width=1))
    ui.plot_layout(fig, 470)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.12, font=dict(size=12)), scattermode="group")
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Δ pass vs family mean", tickformat="+.2f")
    ui.chart(fig, "pca_val")
with right:
    ui.label("Fit split: macro over families as k grows", "strict, leave-one-group-out")
    R = sources.results(stamp)

    def macro(arm: str) -> float | None:
        vs = [R[f]["fit"]["arms"][arm]["v"] for f in R if "fit" in R[f] and arm in R[f]["fit"]["arms"]]
        return float(np.mean(vs)) if len(vs) >= 10 else None

    ks = [4, 8, 16, 32, 64]
    fig = go.Figure()
    for pre, name, tok in (("pco", "pco<k>: the family's top k PCs", "delta"), ("pcr", "pcr<k>: a random k-dim subspace", "line-2"),
                           ("xpco", "xpco<k>: other families' PCs", "muted")):
        pts = [(k, m) for k in ks if (m := macro(f"{pre}{k}@self|cos")) is not None]
        if pts:
            fig.add_scatter(x=[k for k, _ in pts], y=[m for _, m in pts], mode="lines+markers", name=name,
                            line=dict(color=ui.c(tok), width=2), marker=dict(size=8),
                            hovertemplate=f"{pre}%{{x}}: macro %{{y:.3f}}<extra></extra>")
    for arm, name, tok in (("fam@self|cos", "family mean", "mu"), ("tok@self|cos", "token mean", "h")):
        if (m := macro(arm)) is not None:
            fig.add_hline(y=m, line=dict(color=ui.c(tok), dash="dash", width=1.5))
            fig.add_annotation(x=np.log10(64), y=m, text=name, showarrow=False, xanchor="right", yshift=9,
                               font=dict(color=ui.c(tok), size=11.5))
    ui.plot_layout(fig, 470)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.12, font=dict(size=12)))
    fig.update_xaxes(type="log", tickvals=ks, title="k (number of directions removed)")
    fig.update_yaxes(title="macro strict pass (fit)", tickformat=".2f")
    ui.chart(fig, "pca_k")
st.write("")
c1, c2, c3 = st.columns(3, gap="large")
c1.html(ui.note("key", "The directions matter, not the dimension count",
                "A random 16-dimensional subspace (pcr16) and another cell's g (shuf.pco16) sit at the family mean "
                "(−0.003, −0.001 macro on val). Other families' PCs (xpco) are no better than random: a family's useful "
                "axes are its own."))
c2.html(ui.note("key", "Fair where token matching is not",
                "Mention control: pco16 reads a concept the model is asked to hold 0.82 of the time and one merely "
                "mentioned in the prompt 0.24 (tok: 0.82 / 0.59). On DM it has the profile of the fair centres "
                "(judged 0.61; u1rel 0.57, u1endcar 0.64)."))
c3.html(ui.note("open", "Why it is not registered",
                "Judged multilingual_mt drops 0.34 → 0.23 (−0.11 [−0.21, −0.02]): the family's PCs are its language and "
                "concept axes. UM's +0.10 does not count either (S11: UM cannot separate user modelling from prompt "
                "reading). Next: a pco that spares the language, or S14's readout-aware removal."))
st.page_link("views/study.py", label="Study S7 in full: card, notes, battery", icon=":material/science:")
