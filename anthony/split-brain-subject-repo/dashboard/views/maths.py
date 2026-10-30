"""The mathematics: the J-lens as a first-order Taylor expansion, why its anchor belongs on the data, what the
readouts do to a centred state, and mu as a conditional expectation. Measured numbers are quoted from
umot's research log (2026-10-09 and 2026-10-10 entries) and notes/synthesis.md; the toy is computed here.
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import ui

H, MU, D = ui.tex("h", "h"), ui.tex("mu", r"\mu"), ui.tex("delta", r"\delta")
Hl, MUl = ui.tex("h", "h_l"), ui.tex("mu", r"\mu_l")

ui.header(
    "The mathematics",
    'The J-lens as a Taylor expansion, and where to expand it',
    "The plain lens and the centred lens are the same first-order expansion of the network, taken at two different "
    "points. Writing the expansion out shows what each one reads, what the error terms are, why the data mean is the "
    "natural anchor for a mean Jacobian, and why the choice of anchor is a choice of counterfactual.",
)

# ------------------------------------------------------------------ 0 notation
ui.section("Notation", eyebrow="0 · Setup")
ui.md(
    f"Fix a layer $l$ and a read cell (one token position in one context $c$). Write ${Hl}\\in\\mathbb{{R}}^d$ "
    "($d = 5120$) for the block-$l$ output at that cell, and $f_l$ for the rest of the network: the map from that state "
    "to the final residual, with every other position of the context held fixed. The unembedding has rows "
    "$u_t = W_U[t]$, one per vocabulary token."
)
ui.eq(rf"h_L \;=\; f_l\big({Hl};\,c\big), \qquad z \;=\; W_U\,\operatorname{{norm}}(h_L)", tag="0.1")
ui.md(
    "The J-lens replaces $f_l$ by one matrix: the Jacobian of the final residual with respect to the block-$l$ "
    "output, averaged over a fit corpus $\\mathcal{D}$ (wikitext, $n = 1000$ prompts for the released 27B lens)."
)
ui.eq(r"J_l \;=\; \mathbb{E}_{(c,t)\,\sim\,\mathcal{D}}\Big[\,\partial_h f_l\big(h_l(c,t);\,c\big)\Big]", tag="0.2",
      note="In the released fit the Jacobian also sums the effect on later positions; the argument below only needs "
           "J<sub>l</sub> to be a fixed slope.")

# ------------------------------------------------------------------ 1 taylor
ui.section("The plain lens is a Taylor expansion at zero", eyebrow="1 · Expansion")
ui.md("Expand $f_l$ around any anchor $a$. Up to second order,")
ui.eq(rf"f_l({H}) \;=\; f_l(a) \;+\; \partial f_l(a)\,({H}-a) \;+\; \tfrac12\,\partial^2 f_l(a)\big[{H}-a,\;{H}-a\big] "
      rf"\;+\; O\big(\|{H}-a\|^3\big)", tag="1.1")
ui.md(
    "A lens keeps only the linear term, with the corpus-average slope $J_l$ in place of the local slope "
    "$\\partial f_l(a)$, and reads the *predicted displacement* of the output from the anchor's output. "
    f"The released lens reads $J_l {H}$, which is that displacement for $a = 0$:"
)
ui.eq(rf"\underbrace{{J_l\,{H}}}_{{\text{{plain lens}}}} \;\approx\; f_l({H}) - f_l(0)", tag="1.2")
ui.md(
    f"Nothing in the model visits $h = 0$. In our captures the mean state is $81$ to $98\\,\\%$ of the norm of a "
    f"typical ${H}$, so the plain lens describes a displacement across most of the length of the residual stream. "
    f"Taking the anchor at a real state ${MU}$ instead gives the centred lens:"
)
ui.eq(rf"\underbrace{{J_l\,({H}-{MU})}}_{{\text{{centred lens}}}} \;\approx\; f_l({H}) - f_l({MU})", tag="1.3", key=True,
      note="The left side is the quantity to read: how the output at this cell differs from the output at a reference state.")

# ------------------------------------------------------------------ 2 error
ui.section("What the expansion gets wrong, and how the anchor controls it", eyebrow="2 · Error terms")
ui.md("Subtract the lens from the truth. For any anchor $a$, the error splits into a slope mismatch and a curvature term:")
ui.eq(rf"f_l({H}) - f_l(a) - J_l({H}-a) \;=\; \underbrace{{\big(\partial f_l(a) - J_l\big)({H}-a)}}_{{\text{{slope mismatch}}}}"
      rf"\;+\; \underbrace{{\tfrac12\,\partial^2 f_l(a)\big[{H}-a,\;{H}-a\big]}}_{{\text{{curvature}}}} \;+\; \dots", tag="2.1")
ui.md(
    "Both terms grow with the distance $\\|h - a\\|$: the first linearly, the second quadratically. Two things follow.\n\n"
    "- **The slope mismatch is small only where $J_l$ was measured.** $J_l$ averages $\\partial f_l$ over corpus states, so "
    "$\\partial f_l(a) \\approx J_l$ for $a$ near the data and not at $a = 0$.\n"
    "- **The curvature term shrinks with the square of the distance.** Subtracting a family mean removes $41$ to $69\\,\\%$ "
    "of the norm (jle x98), so $\\|h - \\mu\\| \\approx (0.31\\text{–}0.59)\\,\\|h\\|$ and the second-order term falls "
    "by a factor of about $0.1$ to $0.35$."
)
ui.eq(rf"\frac{{\|{H}-{MU}\|^2}}{{\|{H}\|^2}} \;\in\; \big[\,0.31^2,\; 0.59^2\,\big] \;\approx\; [\,0.10,\; 0.35\,]", tag="2.2")

# toy
ui.section("Move the anchor", "A one-dimensional toy, computed here. The curve plays the role of <i>f<sub>l</sub></i>; the "
           "dots are the data; the slope is the data-average derivative (the toy's <i>J</i>). The line is "
           "<i>f(a) + J(h − a)</i>; its mean squared error over the data is shown underneath for every anchor.",
           eyebrow="2 · Toy")


def f(x):
    return 1.0 + 8 / (1 + np.exp(-(x - 3.5))) + 0.05 * x


def df(x):
    e = np.exp(-(x - 3.5))
    return 8 * e / (1 + e) ** 2 + 0.05


rng = np.random.default_rng(0)
data = rng.normal(7.3, 0.9, 400)
J = float(df(data).mean())
grid = np.linspace(0, 10, 201)
mse = np.array([np.mean((f(data) - f(a) - J * (data - a)) ** 2) for a in grid])
a = st.slider("Anchor a", 0.0, 10.0, 0.0, 0.1, key="toy_anchor")
a_best = float(grid[mse.argmin()])
mean = float(data.mean())

toy_l, toy_r = st.columns([1.35, 1], gap="large")
fig = go.Figure()
fig.add_trace(go.Scatter(x=grid, y=f(grid), mode="lines", line=dict(color=ui.c("ink"), width=2.2), name="f",
                         hovertemplate="f(%{x:.1f}) = %{y:.2f}<extra></extra>"))
fig.add_trace(go.Scatter(x=data, y=np.full_like(data, 0.35) + rng.uniform(-0.15, 0.15, data.size), mode="markers",
                         marker=dict(size=4, color=ui.rgba("h", 0.45)), hoverinfo="skip"))
fig.add_trace(go.Scatter(x=grid, y=f(a) + J * (grid - a), mode="lines", hoverinfo="skip",
                         line=dict(color=ui.c("delta" if abs(a - mean) < 1.2 else "h"), width=2, dash="solid" if abs(a - mean) < 1.2 else "dash")))
fig.add_trace(go.Scatter(x=[a], y=[f(a)], mode="markers", marker=dict(size=12, color=ui.c("mu"), line=dict(color=ui.c("surface"), width=2)),
                         hovertemplate="anchor a = %{x:.1f}<extra></extra>"))
ui.plot_layout(fig, 300)
fig.update_xaxes(range=[0, 10], title=dict(text="h (one direction)", font=dict(size=12, color=ui.c("muted"))))
fig.update_yaxes(range=[0, 10.5], title=dict(text="f(h)", font=dict(size=12, color=ui.c("muted"))))
fig.add_annotation(x=mean, y=9.9, text="data mean", showarrow=False, font=dict(size=11.5, color=ui.c("h")))
with toy_l:
    ui.chart(fig, "toy_curve")

fig = go.Figure()
fig.add_trace(go.Scatter(x=grid, y=mse, mode="lines", line=dict(color=ui.c("ink-2"), width=2), hovertemplate="a = %{x:.1f}: MSE %{y:.2f}<extra></extra>"))
for x, lab, tok, pos in ((0.0, "plain (a = 0)", "h", "bottom right"), (mean, "data mean", "delta", "top center")):
    y = float(np.interp(x, grid, mse))
    fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers+text", text=[lab], textposition=pos,
                             textfont=dict(size=11.5, color=ui.c(tok)), marker=dict(size=9, color=ui.c(tok)), hoverinfo="skip"))
fig.add_trace(go.Scatter(x=[a], y=[float(np.interp(a, grid, mse))], mode="markers", hoverinfo="skip",
                         marker=dict(size=12, color=ui.c("mu"), line=dict(color=ui.c("surface"), width=2))))
ui.plot_layout(fig, 300)
fig.update_xaxes(range=[0, 10], title=dict(text="anchor a", font=dict(size=12, color=ui.c("muted"))))
fig.update_yaxes(type="log", title=dict(text="MSE over the data", font=dict(size=12, color=ui.c("muted"))))
with toy_r:
    ui.chart(fig, "toy_mse")
st.html(f'<div class="jm-cap"><b>Anchor a = {a:.1f}: MSE {float(np.interp(a, grid, mse)):.2f}.</b> At a = 0 it is '
        f'{mse[0]:.1f}; at the data mean ({mean:.1f}) it is {float(np.interp(mean, grid, mse)):.3f}. The best anchor '
        f"for this slope is a = {a_best:.1f}, inside the data. Log scale.</div>")

# ------------------------------------------------------------------ 3 least squares
ui.section("Why a mean Jacobian belongs at the data mean", eyebrow="3 · Least squares")
ui.md(
    "Ask a different question: which affine map best predicts $f_l(h)$ over the data? Write $\\bar h = \\mathbb{E}[h]$ "
    "and $\\Sigma = \\operatorname{Cov}(h)$. Least squares gives"
)
ui.eq(rf"\min_{{b,\,A}}\ \mathbb{{E}}\,\big\|f_l({H}) - b - A{H}\big\|^2 \quad\Longrightarrow\quad "
      rf"A^\star = \operatorname{{Cov}}\big(f_l({H}),\,{H}\big)\,\Sigma^{{-1}}, \qquad b^\star + A^\star {H} \;=\; "
      rf"\mathbb{{E}}\big[f_l({H})\big] + A^\star\big({H} - \bar h\big)", tag="3.1")
ui.md(
    "Whatever the slope, the optimal intercept puts the anchor at the data mean. If $h$ were Gaussian, Stein's lemma "
    "would also fix the slope: $\\operatorname{Cov}(f(h), h) = \\mathbb{E}[\\partial f(h)]\\,\\Sigma$, so $A^\\star$ is "
    "exactly the mean Jacobian."
)
ui.eq(rf"{H}\sim\mathcal{{N}}(\bar h,\Sigma) \;\Longrightarrow\; A^\star = \mathbb{{E}}\big[\partial f_l({H})\big] = J_l "
      rf"\;\Longrightarrow\; f_l({H}) \;\approx\; \mathbb{{E}}\big[f_l({H})\big] + J_l\big({H} - \bar h\big)", tag="3.2", key=True,
      note="Under this reading the J-lens is the least-squares slope, and its natural anchor is the fit-corpus mean.")
ui.md(
    "Residuals are not Gaussian, and this has been measured. On held-out wikitext (umot, 2026-10-10), the share of the "
    "final residual explained by $J_l h$, by $J_l(h - \\mu_{\\text{fit}})$ and by a fitted OLS slope:"
)
ui.table(
    ["layer", "plain (anchor 0)", "centred at fit mean", "OLS", "cos(OLS, J)"],
    [["L20", "−0.32", "0.03", "0.40", "0.13"], ["L42", "−0.13", "0.15", "0.47", "0.33"],
     ["L52", "0.19", "0.37", "0.61", "–"], ["L60", "0.62", "0.70", "0.84", "0.88"]],
    num={1, 2, 3, 4}, mono={0},
)
ui.md(
    "Re-anchoring at the fit mean helps at every layer, as (2.1) predicts. But $J_l$ is far from the regression slope "
    "before about L52, so the Stein reading holds only late. And the fit mean, although the better expansion point, is "
    "**not** the better readout centre: on the benchmarks it reads no better than a family mean (Why centre, §4). The "
    "expansion argument justifies centring; it does not pick $\\mu$."
)

# ------------------------------------------------------------------ 4 readouts
ui.section("From the centred state to tokens", eyebrow="4 · Readouts")
ui.md("Both readouts used here are linear in the state, up to a positive per-cell scale. The bench's cosine readout is")
ui.eq(rf"s_t({H}) \;=\; \frac{{\big\langle u_t,\; J_l\,{H}\big\rangle}}{{\big\|J_l^{{\top}} u_t\big\|}} "
      rf"\qquad\Longrightarrow\qquad s_t({H}-{MU}) \;=\; s_t({H}) - s_t({MU})", tag="4.1")
ui.md(
    "jle's readout applies the final RMS norm first, $r(h) = W_U\\big(\\gamma\\odot J_l h / \\operatorname{rms}(J_l h)\\big)$. "
    "Dividing by $\\operatorname{rms}$ rescales every token's score in a cell by the same positive number, so the top-10 "
    "is that of the linear map $\\tilde r(h) = W_U(\\gamma \\odot J_l h)$:"
)
ui.eq(rf"\operatorname{{top}}_{{10}}\, r({H}-{MU}) \;=\; \operatorname{{top}}_{{10}}\big[\,\tilde r({H}) - \tilde r({MU})\,\big]", tag="4.2")
ui.md(
    f"So a centred read is a **contrast**: the plain scores minus the scores of the anchor. Writing ${H} = {MU} + {D}$, "
    "the plain lens reads the sum of two terms:"
)
ui.eq(rf"s_t({H}) \;=\; \underbrace{{s_t({MU})}}_{{\text{{shared prior}}}} \;+\; \underbrace{{s_t({D})}}_{{\text{{this cell}}}}", tag="4.3")
ui.md(
    f"The first term is the same for every input that shares ${MU}$. It decodes to the continuation prior "
    "(`<|im_end|>`, `\\n\\n`, *This*, *The*) and, because $\\|\\mu\\|$ is most of $\\|h\\|$, it sets most of the plain "
    f"top-10. Centring deletes it and leaves ${D}$. Ignoring the final norm, the centred score is a first-order "
    "estimate of a logit difference:"
)
ui.eq(rf"z_t({H}) - z_t({MU}) \;\approx\; \big\langle u_t,\; J_l({H}-{MU})\big\rangle", tag="4.4", key=True,
      note="How much more this state promotes token t than the reference state does.")

# ------------------------------------------------------------------ 5 taylor constant
ui.section("Putting the constant back does not help", eyebrow="5 · The zeroth-order term")
ui.md(
    "(1.1) has a zeroth-order term that both lenses drop. One can read the full first-order prediction instead, with "
    "$f_l(\\mu) \\approx \\mu_L$, the final-residual mean:"
)
ui.eq(rf"W_U\big(f_l({MU}) + J_l({H}-{MU})\big) \;\approx\; \underbrace{{W_U\,\mu_L}}_{{\text{{input-independent}}}} "
      rf"\;+\; W_U J_l({H}-{MU})", tag="5.1")
ui.md(
    "The added term is the same for every input, so it only adds a token-frequency prior (*a*, *I*, *the*). Tested on "
    "directed modulation (umot `taylor_screen.py`): every variant read the concept within one item of the centred lens, "
    "and the mean Jacobian explained only about $4\\,\\%$ of the final residual's cell-to-cell variation at the read "
    "layers. Centring works as a contrast, not as an approximation of the logits."
)

# ------------------------------------------------------------------ 6 counterfactual
ui.section("The anchor is a conditional expectation", eyebrow="6 · Choosing the centre")
ui.md(
    f"Every centre tried so far has the form ${MU} = \\mathbb{{E}}[h \\mid C]$ for some part $C$ of what the read cell "
    "knows: nothing, the read token, the family template, the position, the sentence. By construction the centred state "
    "has no part predictable from $C$:"
)
ui.eq(rf"{MU}_C = \mathbb{{E}}\big[{H} \mid C\big] \qquad\Longrightarrow\qquad \mathbb{{E}}\big[{H} - {MU}_C \mid C\big] = 0", tag="6.1")
ui.md("The law of total variance says what conditioning on more buys and what it costs:")
ui.eq(rf"\operatorname{{Var}}({H}) \;=\; \underbrace{{\mathbb{{E}}\big[\operatorname{{Var}}({H}\mid C)\big]}}_{{\text{{left in }} {H}-{MU}_C}} "
      rf"\;+\; \underbrace{{\operatorname{{Var}}\big(\mathbb{{E}}[{H}\mid C]\big)}}_{{\text{{removed by centring}}}}", tag="6.2", key=True)
ui.md(
    "If $C \\subseteq C'$ (the finer centre knows more), the first term can only shrink: $\\|h - \\mu\\|$ gets smaller, and "
    "by (2.1) so does the expansion error. The cost sits in the second term. Suppose a concept direction $v$ is "
    "present with strength $\\alpha$:"
)
ui.eq(rf"{H} = {MU}_C + \alpha\, v + \varepsilon \qquad\Longrightarrow\qquad {H} - \mathbb{{E}}\big[{H}\mid C'\big] "
      rf"= \big(\alpha - \mathbb{{E}}[\alpha \mid C']\big)\, v + \dots", tag="6.3")
ui.md(
    "If $C'$ already determines $\\alpha$ (for example, it contains the sentence that names the concept), centring "
    "subtracts the very signal we want to read. That is the mention-control failure of the same-sentence centre. Two "
    "constraints follow:\n\n"
    "- **No crystal ball.** $\\mu$ may depend only on what the pipeline's `CellRef` exposes (item, layer, position, read "
    "token, the context up to the cell), never on the targets $y$. Formally, $\\mu$ is measurable with respect to "
    "$\\sigma(\\text{CellRef})$ and $y \\notin \\text{CellRef}$.\n"
    "- **Fairness.** $C$ should explain the background (template, token form, position), but not whatever in the "
    "context would make the concept predictable."
)
ui.eq(rf"\text{{choose }} C \text{{ to make }} \mathbb{{E}}\big[\operatorname{{Var}}({H}\mid C)\big] \text{{ small}} "
      rf"\quad\text{{subject to}}\quad \operatorname{{Var}}\big(\mathbb{{E}}[\alpha\mid C]\big) \approx 0", tag="6.4", key=True,
      note="The open problem in one line: a label-free C that removes the background and none of the content.")
ui.md(
    f"A last special case explains why one mean per layer works on WorkspaceBench and fails on free text. If ${MU}_l$ is a "
    "constant, (4.1) subtracts a fixed score $b_t = s_t(\\mu_l)$ from each token at every cell. That re-ranks the "
    "vocabulary the same way everywhere. It matches the counterfactual only when every read cell has the same "
    "template, token and position, as on the bench's families."
)
