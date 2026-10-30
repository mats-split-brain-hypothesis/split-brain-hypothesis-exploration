"""Diagrams for the local-linearisation programme (views/local_lin.py; notes/iteration-anthony/local-linearisation/).

Same conventions as figures.py: inline SVG strings, colours as CSS tokens (resolved by ui.figure), marker ids
prefixed per figure. Blue = h and the plain lens, amber = the anchor mu, teal = the centred / consistent readout.
Every figure here is a schematic: no number in it is a measurement unless its caption says so.
"""

import math

from figures import _marker, _rng

def _s(base: str, sub: str) -> str:
    """base with a subscript, the baseline restored afterwards (rare subscript glyphs such as ₜ are missing in most fonts)."""
    return f'{base}<tspan font-size="0.72em" dy="0.32em">{sub}</tspan><tspan dy="-0.32em">\u200b</tspan>'


# soft fills for clusters: (fill, stroke)
CL = [("h-soft", "h"), ("delta-soft", "delta"), ("mu-soft", "mu"), ("sunk", "muted")]


def _f(h):
    """The schematic transport map, one direction: flat near 0, a bend, then a gentle rise."""
    return 1.0 + 6.0 / (1 + math.exp(-(h - 4.6) * 1.15)) + 0.12 * h


def _df(h):
    e = math.exp(-(h - 4.6) * 1.15)
    return 6.0 * 1.15 * e / (1 + e) ** 2 + 0.12


# ------------------------------------------------------------------ three views


def three_views() -> str:
    cards = [
        ("Workspace", "tokens the model is", "differentially disposed to say",
         "differential to what?", "μ is the reference"),
        ("Iterative inference", "f(h) ≈ f(μ) + J (h − μ)", "J as the Taylor term of transport",
         "a Taylor term has", "an expansion point: μ"),
        ("Unsupervised probe", f"{_s('p', 't')} = Jᵀ {_s('W', 'U')}[t],  score {_s('p', 't')} · h", "one linear probe per token",
         "a probe needs a bias:", f"{_s('b', 't')} = − {_s('p', 't')} · μ"),
    ]
    g = []
    for i, (title, l1, l2, m1, m2) in enumerate(cards):
        x = 20 + i * 293
        g.append(f'<rect x="{x}" y="16" width="275" height="226" rx="12" fill="var(--surface)" stroke="var(--line-2)"/>')
        g.append(f'<text x="{x + 20}" y="44" font-size="11" class="t-mono t-mut" letter-spacing="1.2">VIEW {i + 1}</text>')
        g.append(f'<text x="{x + 20}" y="68" font-size="17" font-weight="600">{title}</text>')
        g.append(_view_glyph(i, x + 20, 84))
        g.append(f'<text x="{x + 20}" y="178" font-size="12.5" class="t-2">{l1}</text>')
        g.append(f'<text x="{x + 20}" y="195" font-size="12" class="t-mut">{l2}</text>')
        g.append(f'<line x1="{x + 20}" y1="207" x2="{x + 255}" y2="207" stroke="var(--line)"/>')
        g.append(f'<circle cx="{x + 26}" cy="225" r="5" fill="var(--mu)"/>')
        g.append(f'<text x="{x + 38}" y="229" font-size="12.5" style="fill:var(--mu)">{m1} <tspan font-weight="600">{m2}</tspan></text>')
    return f"""
<svg viewBox="0 0 900 258" role="img" aria-label="The three views of the J-lens from the J++ paper (workspace, iterative inference, unsupervised probe), each with the place where the centre mu enters: the reference, the expansion point, the probe bias.">
  <defs>{_marker("tv-a", "ink-2")}{_marker("tv-d", "delta")}</defs>
  {"".join(g)}
</svg>"""


def _view_glyph(i: int, x: float, y: float) -> str:
    if i == 0:  # speech bubble of tokens, the reference faded behind
        toks = [("Paris", "delta", 1), ("warm", "delta", 1), (" the", "muted", 0.55), (" ,", "muted", 0.55)]
        out = [f'<path d="M{x} {y + 6} q0 -6 6 -6 h150 q6 0 6 6 v52 q0 6 -6 6 h-118 l-14 14 l2 -14 h-20 q-6 0 -6 -6 z" '
               f'fill="var(--sunk)" stroke="var(--line-2)"/>']
        cx = x + 10
        for t, tok, op in toks:
            w = 9 + 7.2 * len(t)
            out.append(f'<rect x="{cx}" y="{y + 12}" width="{w}" height="20" rx="4" fill="var(--{tok})" opacity="{0.16 if tok == "muted" else 0.18}"/>'
                       f'<text x="{cx + 5}" y="{y + 26}" font-size="11.5" class="t-mono" style="fill:var(--{tok})" opacity="{op}">{t}</text>')
            cx += w + 5
        out.append(f'<text x="{x + 10}" y="{y + 52}" font-size="10.5" class="t-mut">− what it would say anyway</text>')
        return "".join(out)
    if i == 1:  # curve with a tangent at mu
        def X(h):
            return x + 8 + h * 21

        def Y(v):
            return y + 74 - v * 9

        curve = "M" + " L".join(f"{X(h / 10):.1f} {Y(_f(h / 10)):.1f}" for h in range(0, 101, 2))
        mu = 6.2
        t = f"M{X(4.6):.1f} {Y(_f(mu) + _df(mu) * (4.6 - mu)):.1f} L{X(8.6):.1f} {Y(_f(mu) + _df(mu) * (8.6 - mu)):.1f}"
        return (f'<path d="{curve}" fill="none" stroke="var(--ink)" stroke-width="1.8"/>'
                f'<path d="{t}" stroke="var(--delta)" stroke-width="2"/>'
                f'<circle cx="{X(mu):.1f}" cy="{Y(_f(mu)):.1f}" r="4.5" fill="var(--mu)" stroke="var(--surface)" stroke-width="1.5"/>'
                f'<line x1="{x + 8}" y1="{y + 76}" x2="{x + 232}" y2="{y + 76}" stroke="var(--line-2)"/>')
    # two clouds, the probe hyperplane through mu
    rnd, out = _rng(11), []
    for cx, cy, tok in ((x + 150, y + 22, "delta"), (x + 95, y + 52, "muted")):
        for _ in range(14):
            out.append(f'<circle cx="{cx + (rnd() - 0.5) * 44:.1f}" cy="{cy + (rnd() - 0.5) * 26:.1f}" r="2.3" fill="var(--{tok})" opacity="0.7"/>')
    out.append(f'<line x1="{x + 92}" y1="{y + 2}" x2="{x + 152}" y2="{y + 74}" stroke="var(--mu)" stroke-width="2"/>')
    out.append(f'<line x1="{x + 122}" y1="{y + 38}" x2="{x + 160}" y2="{y + 6}" stroke="var(--delta)" stroke-width="1.6" marker-end="url(#tv-d)"/>')
    out.append(f'<text x="{x + 170}" y="{y + 66}" font-size="11" class="t-mut">plane through μ</text>')
    return "".join(out)


# ------------------------------------------------------------------ the anchor mismatch


def tangent_mismatch() -> str:
    """Expert J_i is the tangent at mu_i; J++ reads it anchored at 0."""
    def X(h):
        return 64 + h * 44

    def Y(v):
        return 318 - v * 30

    curve = "M" + " L".join(f"{X(h / 20):.1f} {Y(_f(h / 20)):.1f}" for h in range(0, 201))
    clusters = [(2.4, 0.7, 0), (6.4, 0.8, 1), (9.0, 0.5, 2)]
    rnd, g = _rng(5), []
    for c, w, k in clusters:
        fill, stroke = CL[k]
        g.append(f'<rect x="{X(c - w):.1f}" y="40" width="{X(c + w) - X(c - w):.1f}" height="278" fill="var(--{fill})" opacity="0.8"/>')
        for _ in range(9):
            g.append(f'<circle cx="{X(c + (rnd() - 0.5) * 1.6 * w):.1f}" cy="{311 - rnd() * 5:.1f}" r="2.2" fill="var(--{stroke})" opacity="0.7"/>')
    # small tangents at the other clusters
    for c, _, k in (clusters[0], clusters[2]):
        a, b = c - 0.9, c + 0.9
        g.append(f'<path d="M{X(a):.1f} {Y(_f(c) + _df(c) * (a - c)):.1f} L{X(b):.1f} {Y(_f(c) + _df(c) * (b - c)):.1f}" '
                 f'stroke="var(--ink-2)" stroke-width="1.3" opacity="0.6"/>')
    mu = 6.4
    s = _df(mu)
    tangent = f"M{X(4.3):.1f} {Y(_f(mu) + s * (4.3 - mu)):.1f} L{X(8.4):.1f} {Y(_f(mu) + s * (8.4 - mu)):.1f}"
    y0 = _f(0)
    anchored = f"M{X(0):.1f} {Y(y0):.1f} L{X(mu + 0.6):.1f} {Y(y0 + s * (mu + 0.6)):.1f}"
    yt, ya = Y(_f(mu)), Y(y0 + s * mu)
    return f"""
<svg viewBox="0 0 560 360" role="img" aria-label="A curved transport map with three clusters of real states. Expert J_i is the slope of the curve inside cluster i. Anchored at mu_i the tangent follows the curve; the same slope anchored at the origin, which is what J++ reads, misses it by a constant.">
  <defs>{_marker("tm-a", "muted")}</defs>
  {"".join(g)}
  <line x1="44" y1="318" x2="540" y2="318" stroke="var(--muted)" marker-end="url(#tm-a)"/>
  <line x1="64" y1="338" x2="64" y2="22" stroke="var(--muted)" marker-end="url(#tm-a)"/>
  <text x="536" y="354" text-anchor="end" font-size="12" class="t-mut">residual h at layer l (one direction)</text>
  <text x="72" y="28" font-size="12" class="t-mut">final residual f(h)</text>
  <text x="{X(2.4):.1f}" y="298" text-anchor="middle" font-size="12" style="fill:var(--h)">C₁</text>
  <text x="{X(6.4) - 22:.1f}" y="298" text-anchor="middle" font-size="12" style="fill:var(--delta)">C₂</text>
  <text x="{X(9.0):.1f}" y="298" text-anchor="middle" font-size="12" style="fill:var(--mu)">C₃</text>
  <path d="{curve}" fill="none" stroke="var(--ink)" stroke-width="2.4"/>
  <path d="{anchored}" stroke="var(--h)" stroke-width="2" stroke-dasharray="7 5"/>
  <path d="{tangent}" stroke="var(--delta)" stroke-width="2.6"/>
  <line x1="{X(mu):.1f}" y1="{yt:.1f}" x2="{X(mu):.1f}" y2="318" stroke="var(--mu)" stroke-dasharray="2 3"/>
  <path d="M{X(mu) + 12:.1f} {yt:.1f} h6 V{ya:.1f} h-6" fill="none" stroke="var(--bad)" stroke-width="1.5"/>
  <text x="{X(mu) + 24:.1f}" y="{(yt + ya) / 2 - 4:.1f}" font-size="12" style="fill:var(--bad)">constant error</text>
  <text x="{X(mu) + 24:.1f}" y="{(yt + ya) / 2 + 12:.1f}" font-size="11.5" class="t-mono" style="fill:var(--bad)">f(μ₂) − f(0) − J₂μ₂</text>
  <circle cx="{X(0)}" cy="{Y(y0):.1f}" r="5" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>
  <circle cx="{X(mu):.1f}" cy="{yt:.1f}" r="6.5" fill="var(--mu)" stroke="var(--surface)" stroke-width="2"/>
  <text x="64" y="336" text-anchor="middle" font-size="13" class="t-m">0</text>
  <text x="{X(mu):.1f}" y="336" text-anchor="middle" font-size="15" class="t-m" style="fill:var(--mu)">μ₂</text>
  <text x="{X(0.3):.1f}" y="{Y(y0 + s * 0.3) - 64:.1f}" font-size="12.5" style="fill:var(--h)">J₂ h: the slope from C₂,</text>
  <text x="{X(0.3):.1f}" y="{Y(y0 + s * 0.3) - 48:.1f}" font-size="12.5" style="fill:var(--h)">anchored at 0 (what J++ reads)</text>
  <text x="{X(4.3) - 6:.1f}" y="{Y(_f(mu) + s * (4.3 - mu)) - 34:.1f}" text-anchor="end" font-size="12.5" style="fill:var(--delta)">J₂ (h − μ₂): the slope</text>
  <text x="{X(4.3) - 6:.1f}" y="{Y(_f(mu) + s * (4.3 - mu)) - 18:.1f}" text-anchor="end" font-size="12.5" style="fill:var(--delta)">anchored where it was taken</text>
</svg>"""


# ------------------------------------------------------------------ mean-value form


def segment_paths() -> str:
    """2-D residual space: the segment 0 -> h crosses regimes; mu_i -> h stays inside one."""
    regions = [((205, 150), (64, 40), 0, "C₁"), ((360, 96), (66, 38), 3, "C₂"),
               ((430, 232), (74, 50), 1, "C₃"), ((262, 268), (60, 36), 2, "C₄")]
    rnd, g = _rng(19), []
    for (cx, cy), (rx, ry), k, lab in regions:
        fill, stroke = CL[k]
        g.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="var(--{fill})" stroke="var(--{stroke})" stroke-opacity="0.5"/>')
        for _ in range(16):
            a, r = rnd() * 6.283, math.sqrt(rnd()) * 0.85
            g.append(f'<circle cx="{cx + math.cos(a) * r * rx:.1f}" cy="{cy + math.sin(a) * r * ry:.1f}" r="2.2" fill="var(--{stroke})" opacity="0.55"/>')
        g.append(f'<text x="{cx - rx * 0.72:.1f}" y="{cy + ry * 0.86:.1f}" font-size="12" style="fill:var(--{stroke})">{lab}</text>')
    o, h, m3, mg = (60, 336), (462, 206), (430, 232), (318, 186)
    return f"""
<svg viewBox="0 0 560 380" role="img" aria-label="Residual space with four clusters. The straight path from the origin to a state h in cluster 3 passes the norm singularity at zero and crosses cluster 4; the path from cluster 3's mean to h stays inside cluster 3, where expert J_3 is the right slope.">
  <defs>
    <radialGradient id="sp-sing"><stop offset="0" stop-color="var(--bad)" stop-opacity="0.35"/><stop offset="1" stop-color="var(--bad)" stop-opacity="0"/></radialGradient>
    {_marker("sp-h", "h")}{_marker("sp-d", "delta")}{_marker("sp-m", "mu")}
  </defs>
  <circle cx="{o[0]}" cy="{o[1]}" r="46" fill="url(#sp-sing)"/>
  {"".join(g)}
  <line x1="{o[0]}" y1="{o[1]}" x2="{h[0] - 6}" y2="{h[1] + 3}" stroke="var(--h)" stroke-width="2" stroke-dasharray="7 5" marker-end="url(#sp-h)"/>
  <line x1="{mg[0]}" y1="{mg[1]}" x2="{h[0] - 6}" y2="{h[1] + 1}" stroke="var(--mu)" stroke-width="1.6" stroke-dasharray="2 4"/>
  <line x1="{m3[0]}" y1="{m3[1]}" x2="{h[0] - 5}" y2="{h[1] + 4}" stroke="var(--delta)" stroke-width="3" marker-end="url(#sp-d)"/>
  <circle cx="{o[0]}" cy="{o[1]}" r="4.5" fill="var(--ink)"/>
  <circle cx="{mg[0]}" cy="{mg[1]}" r="5.5" fill="var(--surface)" stroke="var(--mu)" stroke-width="2"/>
  <circle cx="{m3[0]}" cy="{m3[1]}" r="6" fill="var(--mu)" stroke="var(--surface)" stroke-width="2"/>
  <circle cx="{h[0]}" cy="{h[1]}" r="5.5" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>
  <text x="{o[0] - 10}" y="{o[1] + 22}" font-size="14" class="t-m">0</text>
  <text x="20" y="282" font-size="11.5" style="fill:var(--bad)">RMSNorm singular at 0</text>
  <text x="{h[0] + 10}" y="{h[1] - 8}" font-size="16" class="t-m" style="fill:var(--h)">h</text>
  <text x="{m3[0] - 6}" y="{m3[1] + 22}" font-size="15" class="t-m" style="fill:var(--mu)">μ₃</text>
  <text x="{mg[0] - 32}" y="{mg[1] - 10}" font-size="14" class="t-m" style="fill:var(--mu)">μ̄</text>
  <text x="112" y="366" font-size="12" style="fill:var(--h)">0 → h: leaves the singularity, crosses C₄</text>
  <text x="380" y="356" font-size="12" style="fill:var(--delta)">μ₃ → h: stays in C₃</text>
  <text x="380" y="372" font-size="11.5" class="t-mut">the right slope is J₃</text>
  <text x="24" y="30" font-size="13" class="t-2">f(h) − f(m) = [ ∫₀¹ J(m + t(h − m)) dt ] (h − m)</text>
  <text x="24" y="48" font-size="11.5" class="t-mut">the slope that belongs to (h − m) is J averaged along the segment</text>
</svg>"""


# ------------------------------------------------------------------ the design space


GRID = [  # row, col, title, formula, status, note
    (0, 0, "J-lens", "J h", "done", "baseline"),
    (0, 1, "global centring", f"J (h − {_s('μ', 'fam')})", "done", "fam, ctr1"),
    (0, 2, "local centring", f"J (h − {_s('μ', 'kNN')}(h))", "done", "S4: knnx8 +0.05 vs fam"),
    (1, 0, "J++ (released)", "Σ wᵢ Jᵢ h", "done", "Fig 3: beats every expert"),
    (1, 1, "J++ centred", f"Σ wᵢ Jᵢ (h − {_s('μ', 'fam')})", "done", "U4: adds on ours, hurts on theirs"),
    (1, 2, "paired anchors", "Σ wᵢ Jᵢ (h − μᵢ)", "new", "H1, H5: = J⁺⁺h − b"),
    (2, 0, "routed experts", "Σ rᵢ(h) Jᵢ h", "hurt", "J++ Fig 14"),
    (2, 1, "routed, one anchor", "Σ rᵢ(h) Jᵢ (h − μ)", "new", "control for H6"),
    (2, 2, "piecewise affine", "Σ rᵢ(h) Jᵢ (h − μᵢ)", "new", "H6: does routing return?"),
]


def design_grid() -> str:
    cols = ["0  (no anchor)", "one global μ", "regime μᵢ  or  kNN μ(h)"]
    rows = [("pooled", "one J"), ("filtered", "Σ wᵢ Jᵢ, fixed w"), ("routed", "rᵢ(h) Jᵢ")]
    x0, y0, cw, rh, gap = 182, 76, 232, 92, 10
    g = []
    g.append(f'<rect x="{x0 + 2 * (cw + gap) - 6}" y="{y0 - 48}" width="{cw + 12}" height="{3 * (rh + gap) + 50}" rx="12" '
             f'fill="var(--delta-soft)" opacity="0.55"/>')
    g.append(f'<rect x="{x0 - 6}" y="{y0 - 6}" width="{cw + 12}" height="{3 * (rh + gap) + 2}" rx="12" fill="none" '
             f'stroke="var(--h)" stroke-dasharray="5 4" stroke-opacity="0.7"/>')
    for j, c in enumerate(cols):
        g.append(f'<text x="{x0 + j * (cw + gap) + cw / 2}" y="{y0 - 18}" text-anchor="middle" font-size="13" font-weight="600" '
                 f'style="fill:var(--mu)">{c}</text>')
    g.append(f'<text x="{x0 + 1.5 * (cw + gap)}" y="{y0 - 44}" text-anchor="middle" font-size="11" class="t-mono t-mut" letter-spacing="1.2">'
             f'INTERCEPT  (EXPANSION POINT)  →  more local</text>')
    for i, (a, b) in enumerate(rows):
        y = y0 + i * (rh + gap)
        g.append(f'<text x="{x0 - 16}" y="{y + rh / 2 - 2}" text-anchor="end" font-size="14" font-weight="600" style="fill:var(--h)">{a}</text>')
        g.append(f'<text x="{x0 - 16}" y="{y + rh / 2 + 16}" text-anchor="end" font-size="11.5" class="t-mut">{b}</text>')
    g.append(f'<text x="22" y="{y0 + 1.5 * (rh + gap)}" font-size="11" class="t-mono t-mut" letter-spacing="1.2" '
             f'transform="rotate(-90 22 {y0 + 1.5 * (rh + gap)})" text-anchor="middle">SLOPE  →  more local</text>')
    style = {"done": ("surface", "line-2", "good", "in hand"), "new": ("surface", "delta", "delta", "new"),
             "hurt": ("surface", "line-2", "bad", "hurt")}
    for r, c, title, form, st, note in GRID:
        x, y = x0 + c * (cw + gap), y0 + r * (rh + gap)
        fill, stroke, tag, word = style[st]
        sw = 2 if st == "new" else 1
        g.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="9" fill="var(--{fill})" stroke="var(--{stroke})" stroke-width="{sw}"/>')
        g.append(f'<text x="{x + 14}" y="{y + 24}" font-size="13" font-weight="600">{title}</text>')
        g.append(f'<rect x="{x + cw - 66}" y="{y + 11}" width="54" height="18" rx="9" fill="var(--{tag})" opacity="0.15"/>'
                 f'<text x="{x + cw - 39}" y="{y + 24}" text-anchor="middle" font-size="10.5" font-weight="600" style="fill:var(--{tag})">{word}</text>')
        g.append(f'<text x="{x + 14}" y="{y + 52}" font-size="15" class="t-m">{form}</text>')
        g.append(f'<text x="{x + 14}" y="{y + 76}" font-size="11.5" class="t-mut">{note}</text>')
    yb = y0 + 3 * (rh + gap) + 18
    return f"""
<svg viewBox="0 0 920 {yb + 26}" role="img" aria-label="Design space: rows are how local the slope is (pooled J, filtered J++, routed experts), columns how local the intercept is (none, one global mean, a regime or nearest-neighbour mean). Five cells are in hand; the paired-anchor and piecewise-affine cells are new.">
  {"".join(g)}
  <text x="{x0}" y="{yb + 10}" font-size="12" class="t-2">Highlighted column: the hypothesis <tspan font-weight="600" style="fill:var(--delta)">global slope, local intercept</tspan>. Dashed: where J++ searched, slope only.</text>
</svg>"""


# ------------------------------------------------------------------ the user's readout, two forms


def filter_vs_router() -> str:
    sub = "₁₂₃₄"

    def panel(x, routed):
        out = [f'<rect x="{x}" y="14" width="430" height="334" rx="12" fill="var(--surface)" stroke="var(--line-2)"/>',
               f'<text x="{x + 20}" y="42" font-size="11" class="t-mono t-mut" letter-spacing="1.2">'
               f'{"ROUTED WEIGHTS r(h)" if routed else "GLOBAL WEIGHTS w (J++)"}</text>',
               f'<text x="{x + 20}" y="64" font-size="16" font-weight="600">{"a piecewise-affine lens" if routed else "one affine map per layer"}</text>']
        hx, hy, bx0, bw0, bh, step, top = x + 42, 177, x + 166, 118, 34, 50, 92
        out.append(f'<circle cx="{hx}" cy="{hy}" r="18" fill="var(--h-soft)" stroke="var(--h)" stroke-width="1.5"/>'
                   f'<text x="{hx}" y="{hy + 6}" text-anchor="middle" font-size="17" class="t-m" style="fill:var(--h)">h</text>')
        weights = [0.08, 0.86, 0.04, 0.02] if routed else [0.55, 0.62, -0.28, 0.12]
        sx = hx + 18
        if routed:
            out.append(f'<line x1="{hx + 18}" y1="{hy}" x2="{x + 82}" y2="{hy}" stroke="var(--ink-2)" stroke-width="1.3"/>'
                       f'<path d="M{x + 82} {hy} l17 -17 l17 17 l-17 17 z" fill="var(--sunk)" stroke="var(--ink-2)"/>'
                       f'<text x="{x + 99}" y="{hy + 34}" text-anchor="middle" font-size="10.5" class="t-mut">router</text>')
            sx = x + 116
        for i, w in enumerate(weights):
            ey = top + i * step
            cy = ey + bh / 2
            fill, stroke = CL[i]
            if routed:
                stroke_w, op, col = 1 + 6 * w, 0.95 if w > 0.3 else 0.4, stroke
            else:
                stroke_w, op, col = 1.4, 0.85, "ink-2"
            out.append(f'<path d="M{sx} {hy} C{sx + 30} {hy}, {bx0 - 30} {cy}, {bx0} {cy}" fill="none" '
                       f'stroke="var(--{col})" stroke-width="{stroke_w:.1f}" opacity="{op}"/>')
            out.append(f'<rect x="{bx0}" y="{ey}" width="{bw0}" height="{bh}" rx="7" fill="var(--{fill})" stroke="var(--{stroke})"/>'
                       f'<text x="{bx0 + bw0 / 2}" y="{ey + 22}" text-anchor="middle" font-size="14" class="t-m">'
                       f'J{sub[i]} (h − μ{sub[i]})</text>')
            mid, half = x + 330, 34
            bar = "bad" if w < 0 else (stroke if routed else "delta")
            out.append(f'<line x1="{bx0 + bw0}" y1="{cy}" x2="{mid - half - 4}" y2="{cy}" stroke="var(--line-2)"/>'
                       f'<line x1="{mid}" y1="{ey + 4}" x2="{mid}" y2="{ey + bh - 4}" stroke="var(--line-2)"/>'
                       f'<rect x="{mid if w >= 0 else mid + w * half:.1f}" y="{cy - 6}" width="{max(abs(w) * half, 1.5):.1f}" height="12" rx="2" fill="var(--{bar})"/>'
                       f'<path d="M{mid + half + 4} {cy} C{mid + half + 22} {cy}, {x + 386} {hy}, {x + 396} {hy}" fill="none" stroke="var(--line-2)"/>')
        out.append(f'<text x="{x + 330}" y="{top - 10}" text-anchor="middle" font-size="11" class="t-mut">{"r(h)" if routed else "w (signed)"}</text>')
        out.append(f'<circle cx="{x + 408}" cy="{hy}" r="12" fill="var(--surface)" stroke="var(--ink-2)" stroke-width="1.5"/>'
                   f'<text x="{x + 408}" y="{hy + 5}" text-anchor="middle" font-size="15">Σ</text>')
        if routed:
            l1, l2 = "changes with h: each state is read", "with the tangent of its own regime"
        else:
            l1, l2 = f"= J⁺⁺ h − b,   b = Σ {_s('w', 'i')} {_s('J', 'i')} {_s('μ', 'i')}", "one fixed bias per layer: no read-time cost"
        out.append(f'<line x1="{x + 20}" y1="{top + 4 * step}" x2="{x + 410}" y2="{top + 4 * step}" stroke="var(--line)"/>')
        out.append(f'<text x="{x + 20}" y="{top + 4 * step + 26}" font-size="14.5" class="t-m" style="fill:var(--delta)">{l1}</text>')
        out.append(f'<text x="{x + 20}" y="{top + 4 * step + 44}" font-size="11.5" class="t-mut">{l2}</text>')
        return "".join(out)

    return f"""
<svg viewBox="0 0 900 358" role="img" aria-label="Two forms of the paired readout. Left: every expert reads h minus its own cluster mean and the results are mixed with J++'s fixed signed weights, which equals the J++ map applied to h minus one fixed bias. Right: a router weights the experts by the state, giving a piecewise-affine lens.">
  {panel(10, False)}{panel(460, True)}
</svg>"""


# ------------------------------------------------------------------ H2: rescue


def rescue() -> str:
    """Dumbbells per expert: alone (J_i h) vs with its own anchor (prediction)."""
    alone = [0.42, 0.02, 0.31, 0.01, 0.05, 0.36, 0.01, 0.12]
    pred = [0.46, 0.30, 0.38, 0.22, 0.33, 0.40, 0.08, 0.29]
    x0, y0, w, h = 70, 54, 440, 210

    def Y(v):
        return y0 + h - v / 0.5 * h

    pooled = 0.26
    g = [f'<line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="var(--line-2)"/>',
         f'<line x1="{x0}" y1="{Y(pooled):.1f}" x2="{x0 + w}" y2="{Y(pooled):.1f}" stroke="var(--mu)" stroke-dasharray="5 4" opacity="0.8"/>',
         f'<rect x="{x0}" y="{Y(0.04):.1f}" width="{w}" height="{Y(0) - Y(0.04):.1f}" fill="var(--bad)" opacity="0.1"/>']
    for i, (a, p) in enumerate(zip(alone, pred)):
        x = x0 + 30 + i * 54
        bad = a < 0.06
        g.append(f'<line x1="{x}" y1="{Y(a) - 5:.1f}" x2="{x}" y2="{Y(p) + 7:.1f}" stroke="var(--delta)" stroke-width="{2.4 if bad else 1.6}" '
                 f'stroke-dasharray="{"none" if bad else "3 3"}" opacity="{1 if bad else 0.6}"/>')
        g.append(f'<circle cx="{x}" cy="{Y(a):.1f}" r="5.5" fill="var(--{"bad" if bad else "h"})"/>')
        g.append(f'<circle cx="{x}" cy="{Y(p):.1f}" r="6.5" fill="var(--surface)" stroke="var(--delta)" stroke-width="2.2"/>')
        g.append(f'<text x="{x}" y="{y0 + h + 20}" text-anchor="middle" font-size="13" class="t-m">{_s("J", str(i + 1))}</text>')
    g.append(f'<text x="{x0 - 14}" y="{y0 + h / 2}" text-anchor="middle" font-size="11.5" class="t-mut" transform="rotate(-90 {x0 - 14} {y0 + h / 2})">recall@10, each expert alone</text>')
    lg = [(x0, "h", "solid", f"{_s('J', 'i')} h"), (x0 + 96, "bad", "solid", "filtered by J++ (&lt; 2 %)"),
          (x0 + 268, "delta", "ring", f"{_s('J', 'i')} (h − {_s('μ', 'i')}): H2")]
    for lx, tok, kind, lab in lg:
        mark = (f'<circle cx="{lx + 6}" cy="20" r="5" fill="var(--{tok})"/>' if kind == "solid" else
                f'<circle cx="{lx + 6}" cy="20" r="5.5" fill="var(--surface)" stroke="var(--{tok})" stroke-width="2"/>')
        g.append(mark + f'<text x="{lx + 17}" y="24" font-size="12" style="fill:var(--{tok})">{lab}</text>')
    g.append(f'<line x1="{x0}" y1="40" x2="{x0 + 20}" y2="40" stroke="var(--mu)" stroke-dasharray="5 4"/>'
             f'<text x="{x0 + 27}" y="44" font-size="12" style="fill:var(--mu)">pooled J</text>')
    return f"""
<svg viewBox="0 0 540 330" role="img" aria-label="Schematic of hypothesis H2: each expert's recall alone, read as J_i h, and the predicted recall read with its own anchor J_i (h - mu_i). The prediction is that the experts J++ filters out gain the most.">
  {"".join(g)}
  <text x="{x0}" y="{y0 + h + 44}" font-size="11.5" class="t-mut">Schematic of an early layer (L8–16), shaped like J++ Fig 3; no data yet.</text>
  <text x="{x0}" y="{y0 + h + 60}" font-size="11.5" class="t-mut">Refuted if the filtered experts stay near zero when anchored.</text>
</svg>"""


# ------------------------------------------------------------------ H4: depth


def depth() -> str:
    layers = [8, 16, 24, 32, 40, 48, 56]
    x0, y0, w, h = 60, 30, 440, 200

    def X(u):
        return x0 + u * w

    def Y(v):
        return y0 + h - v * h

    def line(fn):
        return "M" + " L".join(f"{X(k / 100):.1f} {Y(fn(k / 100)):.1f}" for k in range(101))

    slope = lambda u: 0.1 + 0.78 * math.exp(-u / 0.32)
    inter = lambda u: 0.62 + 0.03 * math.sin(u * 5)
    ticks = "".join(f'<text x="{X(i / 6):.1f}" y="{y0 + h + 18}" text-anchor="middle" font-size="11" class="t-mono t-mut">L{l}</text>'
                    for i, l in enumerate(layers))
    return f"""
<svg viewBox="0 0 540 300" role="img" aria-label="Schematic of hypothesis H4 across depth: the gain from a local slope falls with depth, following the J++ finding that experts disagree early and agree late; the gain from a local intercept stays roughly flat.">
  <rect x="{x0}" y="{y0}" width="{X(2 / 6) - x0:.1f}" height="{h}" fill="var(--h-soft)" opacity="0.7"/>
  <text x="{x0 + 8}" y="{y0 + h - 26}" font-size="11" style="fill:var(--h)">experts disagree</text>
  <text x="{x0 + 8}" y="{y0 + h - 10}" font-size="11" class="t-mut">(J++ Fig 17)</text>
  <line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="var(--line-2)"/>
  {ticks}
  <path d="{line(inter)}" fill="none" stroke="var(--delta)" stroke-width="2.8" stroke-linecap="round"/>
  <path d="{line(slope)}" fill="none" stroke="var(--h)" stroke-width="2.8" stroke-linecap="round"/>
  <text x="{X(0.62):.1f}" y="{Y(inter(0.62)) - 12:.1f}" font-size="12.5" style="fill:var(--delta)">gain from a local intercept</text>
  <text x="{X(0.55):.1f}" y="{Y(slope(0.55)) - 12:.1f}" font-size="12.5" style="fill:var(--h)">gain from a local slope</text>
  <text x="{x0 - 14}" y="{y0 + h / 2}" text-anchor="middle" font-size="11.5" class="t-mut" transform="rotate(-90 {x0 - 14} {y0 + h / 2})">readout gain (schematic)</text>
  <text x="{x0}" y="{y0 + h + 44}" font-size="11.5" class="t-mut">Prediction, not data. Refuted if the intercept gain also vanishes late,</text>
  <text x="{x0}" y="{y0 + h + 60}" font-size="11.5" class="t-mut">or if the slope gain stays high there.</text>
</svg>"""


# ------------------------------------------------------------------ probe view


def probe_bias() -> str:
    rnd, g = _rng(23), []
    pres, absn = (318, 104), (242, 176)
    for (cx, cy), tok in ((pres, "delta"), (absn, "muted")):
        for _ in range(26):
            a, r = rnd() * 6.283, math.sqrt(rnd())
            g.append(f'<circle cx="{cx + math.cos(a) * r * 44:.1f}" cy="{cy + math.sin(a) * r * 30:.1f}" r="2.6" fill="var(--{tok})" opacity="0.7"/>')
    o = (54, 290)
    mu = ((pres[0] + absn[0]) / 2, (pres[1] + absn[1]) / 2)
    d = (72, 76)  # along the plane (perpendicular to p = (76, -72))
    n = math.hypot(*d)
    d = (d[0] / n, d[1] / n)

    def seg(p, a, b):
        return f'x1="{p[0] + d[0] * a:.1f}" y1="{p[1] + d[1] * a:.1f}" x2="{p[0] + d[0] * b:.1f}" y2="{p[1] + d[1] * b:.1f}"'

    pt = _s("p", "t")
    return f"""
<svg viewBox="0 0 470 330" role="img" aria-label="The probe view. Each token's lens vector is a linear probe. Through the origin its decision plane is far from the data, so every state scores positive; through mu the plane separates states where the token is present from those where it is absent.">
  <defs>{_marker("pb-d", "delta")}</defs>
  {"".join(g)}
  <line {seg(o, -60, 40)} stroke="var(--h)" stroke-width="2" stroke-dasharray="7 5"/>
  <line {seg(mu, -110, 118)} stroke="var(--mu)" stroke-width="2.4"/>
  <line x1="{mu[0]:.1f}" y1="{mu[1]:.1f}" x2="{mu[0] + 46:.1f}" y2="{mu[1] - 43:.1f}" stroke="var(--delta)" stroke-width="2.2" marker-end="url(#pb-d)"/>
  <circle cx="{o[0]}" cy="{o[1]}" r="4.5" fill="var(--ink)"/>
  <circle cx="{mu[0]:.1f}" cy="{mu[1]:.1f}" r="6" fill="var(--mu)" stroke="var(--surface)" stroke-width="2"/>
  <text x="{o[0] - 4}" y="{o[1] + 22}" font-size="14" class="t-m">0</text>
  <text x="{mu[0] - 24:.1f}" y="{mu[1] + 6:.1f}" font-size="15" class="t-m" style="fill:var(--mu)">μ</text>
  <text x="{mu[0] + 30:.1f}" y="{mu[1] - 48:.1f}" font-size="15" class="t-m" style="fill:var(--delta)">{pt}</text>
  <text x="{pres[0] + 30}" y="{pres[1] - 38}" font-size="12" style="fill:var(--delta)">t in the workspace</text>
  <text x="{absn[0] - 92}" y="{absn[1] + 40}" font-size="12" class="t-mut">t absent</text>
  <text x="{o[0] + 34}" y="{o[1] + 6}" font-size="12" style="fill:var(--h)">{pt} · h = 0: every state scores &gt; 0</text>
  <text x="{mu[0] + 50:.1f}" y="{mu[1] + 96:.1f}" font-size="12" style="fill:var(--mu)">{pt} · (h − μ) = 0</text>
  <text x="{mu[0] + 50:.1f}" y="{mu[1] + 112:.1f}" font-size="11.5" class="t-mut">the bias −{pt} · μ splits them</text>
</svg>"""


# ------------------------------------------------------------------ roadmap


PHASES = [
    ("LL0", "Our experts", "one backward sweep, many clusterings; reproduce J++", "≈ $100 pod", "mu"),
    ("LL1", "Diagnostics", "geometry; Taylor error by anchor", "H3", "h"),
    ("LL2", "Single experts", "each expert × own, other, global and kNN anchors", "H1 · H2", "delta"),
    ("LL3", "Combined maps", "the slope × intercept grid", "H4 · H6", "delta"),
    ("LL4", "Joint fitting", "refit w on centred inputs; offsets", "H5", "delta"),
    ("LL5", "Beyond first order", "path-integrated slope; Hessian term", "open", "muted"),
]


def roadmap() -> str:
    x0, step, y = 26, 146, 50
    g = [f'<line x1="{x0 + 20}" y1="{y}" x2="{x0 + 5 * step + 20}" y2="{y}" stroke="var(--line-2)" stroke-width="2"/>']
    for i, (pid, title, what, ans, tok) in enumerate(PHASES):
        x = x0 + i * step
        g.append(f'<circle cx="{x + 20}" cy="{y}" r="15" fill="var(--surface)" stroke="var(--{tok})" stroke-width="2.4"/>'
                 f'<text x="{x + 20}" y="{y + 4}" text-anchor="middle" font-size="10" font-weight="600" class="t-mono" style="fill:var(--{tok})">{pid}</text>')
        g.append(f'<text x="{x}" y="{y + 40}" font-size="13.5" font-weight="600">{title}</text>')
        lines, cur = [], ""
        for word in what.split():
            if len(cur) + len(word) > 21:
                lines.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}".strip()
        lines.append(cur)
        for k, ln in enumerate(lines):
            g.append(f'<text x="{x}" y="{y + 60 + k * 15}" font-size="11.5" class="t-2">{ln}</text>')
        g.append(f'<rect x="{x}" y="{y + 112}" width="{14 + 7 * len(ans)}" height="20" rx="10" fill="var(--{tok})" opacity="0.14"/>'
                 f'<text x="{x + 7}" y="{y + 126}" font-size="11" font-weight="600" style="fill:var(--{tok})">{ans}</text>')
    return f"""
<svg viewBox="0 0 900 196" role="img" aria-label="Roadmap of the programme: LL0 fit our own expert Jacobians, LL1 diagnostics, LL2 single experts, LL3 combined maps, LL4 joint fitting, LL5 beyond first order, each with the hypotheses it answers.">
  {"".join(g)}
</svg>"""


# ================================================================== night-2 results (views/ll_results.py)
# Unlike the schematics above, sweep_bins, fitted_lens and answer_grid draw measured numbers passed in by the page.

_SEG = ["h", "delta", "mu", "muted"]


def _wrap(s: str, n: int) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + len(word) > n:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return [*lines, cur]


def sweep_bins(counts: dict[str, list[int]], layer: int) -> str:
    """LL0: one backward sweep, every kept position binned by five clusterings at once (measured bin sizes)."""
    g = []
    # left: one prompt, its kept positions
    g.append('<text x="20" y="34" font-size="11" class="t-mono t-mut" letter-spacing="1.2">ONE BACKWARD SWEEP</text>')
    for i in range(13):
        x = 20 + i * 17
        kept = 2 <= i <= 11
        g.append(f'<rect x="{x}" y="50" width="13" height="13" rx="3" fill="var(--{"h-soft" if kept else "sunk"})" '
                 f'stroke="var(--{"h" if kept else "line-2"})" stroke-width="1"/>')
    g.append('<text x="20" y="80" font-size="10.5" class="t-mut">first 16 skipped</text>'
             '<text x="236" y="80" font-size="10.5" class="t-mut" text-anchor="end">kept positions p</text>')
    g.append('<rect x="20" y="96" width="232" height="96" rx="10" fill="var(--surface)" stroke="var(--line-2)"/>'
             '<text x="34" y="120" font-size="12" class="t-2">for every kept p, layer l:</text>'
             f'<text x="34" y="146" font-size="15" class="t-m" style="fill:var(--h)">{_s("h", "l")}[p]</text>'
             '<text x="34" y="176" font-size="15" class="t-m">'
             f'{_s("G", "p")} = Σ<tspan font-size="0.7em" dy="0.3em">p′≥p</tspan><tspan dy="-0.3em"> </tspan>∂{_s("h", "fin")}[p′] / ∂{_s("h", "l")}[p]</text>')
    g.append('<text x="20" y="218" font-size="11.5" class="t-2">353 wikitext prompts</text>'
             f'<text x="20" y="234" font-size="11.5" class="t-2">{sum(counts["w1"]):,} positions per layer</text>'
             '<text x="20" y="250" font-size="11.5" class="t-mut">3 × H100, ≈ $37</text>')
    # middle: the five clusterings, measured bin sizes
    names = [("w1", "pooled", "k = 1"), ("w8", "J++ router", "k = 8"), ("w16", "J++ router", "k = 16"),
             ("o8", "our fit cells", "k = 8"), ("r8", "random bins", "w8's sizes")]
    bx, bw, y0, rh = 410, 300, 50, 42
    g.append(f'<text x="{bx}" y="34" font-size="11" class="t-mono t-mut" letter-spacing="1.2">BINNED FIVE WAYS AT ONCE (L{layer}, measured sizes)</text>')
    for r, (key, a, b) in enumerate(names):
        y = y0 + r * rh
        g.append(f'<path d="M254 144 C 300 144, 320 {y + 12}, {bx - 108} {y + 12}" fill="none" stroke="var(--line-2)" stroke-width="1.2"/>')
        g.append(f'<text x="{bx - 100}" y="{y + 10}" font-size="13" font-weight="600" class="t-mono">{key}</text>'
                 f'<text x="{bx - 66}" y="{y + 10}" font-size="11.5" class="t-2">{a}</text>'
                 f'<text x="{bx - 66}" y="{y + 24}" font-size="10.5" class="t-mut">{b}</text>')
        c = counts[key]
        tot = sum(c)
        x = bx
        for i, n in enumerate(c):
            w = bw * n / tot
            if w <= 0:
                continue
            tok = _SEG[i % 4] if key != "w1" else "h"
            op = 0.75 if (i // 4) % 2 == 0 else 0.4
            g.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 1, 0.6):.1f}" height="18" rx="2" fill="var(--{tok})" opacity="{op}"/>')
            x += w
        starved = sum(1 for n in c if n < 200)
        note = f"{starved} of {len(c)} bins under 200 positions" if starved else f"smallest bin {min(c):,}"
        red = ' style="fill:var(--bad)"' if starved else ""
        g.append(f'<text x="{bx}" y="{y + 32}" font-size="10.5" class="t-mut"{red}>{note}</text>')
    # right: what each bin keeps
    rx = 734
    g.append(f'<path d="M{bx + bw + 4} 150 L{rx - 6} 150" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#sb-a)"/>')
    g.append(f'<rect x="{rx}" y="56" width="170" height="196" rx="12" fill="var(--delta-soft)" stroke="var(--delta)"/>'
             f'<text x="{rx + 14}" y="80" font-size="11" class="t-mono t-mut" letter-spacing="1.2">EACH BIN i KEEPS</text>'
             f'<text x="{rx + 14}" y="104" font-size="13.5" class="t-m">ΣG,  {_s("n", "i")},  Σh</text>'
             f'<line x1="{rx + 14}" y1="116" x2="{rx + 156}" y2="116" stroke="var(--delta)" stroke-opacity="0.4"/>'
             f'<text x="{rx + 14}" y="142" font-size="15" class="t-m" style="fill:var(--h)">{_s("J", "i")} = ΣG / {_s("n", "i")}</text>'
             f'<text x="{rx + 14}" y="168" font-size="15" class="t-m" style="fill:var(--mu)">{_s("μ", "i")} = Σh / {_s("n", "i")}</text>'
             f'<text x="{rx + 14}" y="198" font-size="11" class="t-2">the anchor is the mean of</text>'
             f'<text x="{rx + 14}" y="213" font-size="11" class="t-2">exactly the positions that</text>'
             f'<text x="{rx + 14}" y="228" font-size="11" class="t-2">made the expert</text>')
    return f"""
<svg viewBox="0 0 920 270" role="img" aria-label="The LL0 sweep: each kept position of each wikitext prompt gives its state and its J-lens gradient; five clusterings bin it at once (pooled, J++'s router with 8 and 16 clusters, our fit cells, random bins), and each bin keeps the sum of gradients, the count and the sum of states, so every expert has its own matching anchor. Bin widths are measured.">
  <defs>{_marker("sb-a", "ink-2")}</defs>
  {"".join(g)}
</svg>"""


def patch_test() -> str:
    """H3: patch the anchor in at one position, run the rest of the network, compare with the lens's prediction."""
    g = []
    xs = [40 + i * 46 for i in range(8)]
    s = 3
    yL, yF = 196, 66
    g.append(f'<rect x="{xs[s] - 18}" y="{yF - 24}" width="{xs[-1] - xs[s] + 36}" height="34" rx="10" fill="var(--h-soft)" opacity="0.8"/>')
    for i, x in enumerate(xs):
        hit = i >= s
        g.append(f'<line x1="{x}" y1="{yL - 14}" x2="{x}" y2="{yF + 12}" stroke="var(--{"h" if hit else "line-2"})" '
                 f'stroke-width="{1.4 if hit else 1}" stroke-opacity="{0.7 if hit else 0.6}"/>')
        g.append(f'<circle cx="{x}" cy="{yF}" r="9" fill="var(--surface)" stroke="var(--{"h" if hit else "line-2"})" stroke-width="1.4"/>')
        if i == s:
            g.append(f'<circle cx="{x}" cy="{yL}" r="13" fill="var(--mu-soft)" stroke="var(--mu)" stroke-width="2"/>'
                     f'<text x="{x}" y="{yL + 5}" text-anchor="middle" font-size="15" class="t-m" style="fill:var(--mu)">m</text>'
                     f'<text x="{x}" y="{yL + 36}" text-anchor="middle" font-size="11" class="t-2">h → m at s</text>')
        else:
            g.append(f'<circle cx="{x}" cy="{yL}" r="9" fill="var(--surface)" stroke="var(--line-2)" stroke-width="1.2"/>')
    # cross-position arrows from s (attention carries the patch forward)
    for x in xs[s + 1:]:
        g.append(f'<path d="M{xs[s]} {yL - 14} Q {(xs[s] + x) / 2} {yL - 50}, {x} {yF + 40}" fill="none" stroke="var(--mu)" stroke-opacity="0.45" stroke-dasharray="3 3"/>')
    g.append(f'<text x="14" y="{yL + 5}" font-size="12" class="t-m">l</text><text x="8" y="{yF + 5}" font-size="12" class="t-mut">final</text>')
    g.append(f'<text x="{(xs[s] + xs[-1]) / 2}" y="{yF - 32}" text-anchor="middle" font-size="13" class="t-m" style="fill:var(--h)">'
             f'F = Σ<tspan font-size="0.7em" dy="0.3em">t ≥ s</tspan><tspan dy="-0.3em"> </tspan>{_s("h", "fin")}[t]   (what the lens linearises)</text>')
    g.append('<text x="40" y="250" font-size="11.5" class="t-2">Run the rest of the network with m in place of h at one position.</text>')
    # right: the vectors
    ox, oy = 560, 214
    g.append('<rect x="440" y="16" width="470" height="244" rx="12" fill="var(--surface)" stroke="var(--line-2)"/>'
             '<text x="458" y="40" font-size="11" class="t-mono t-mut" letter-spacing="1.2">WHAT CAME OUT (MEDIANS, L24–L40)</text>')

    def arrow(dx, dy, tok, dash="", w=2.4):
        da = f'stroke-dasharray="{dash}" ' if dash else ""
        return (f'<line x1="{ox}" y1="{oy}" x2="{ox + dx}" y2="{oy - dy}" stroke="var(--{tok})" stroke-width="{w}" '
                f'{da}marker-end="url(#pt-{tok})"/>')

    g.append(arrow(250, 70, "ink"))
    g.append(f'<text x="{ox + 256}" y="{oy - 74}" font-size="13.5" class="t-m">F(h) − F(m)</text>')
    a = math.radians(84)
    L = 26
    g.append(arrow(L * math.cos(a) + 3, L * math.sin(a) + 10, "delta"))
    g.append(f'<text x="{ox - 8}" y="{oy - 50}" font-size="12.5" class="t-m" style="fill:var(--delta)" text-anchor="end">J (h − m)</text>')
    g.append(f'<text x="{ox - 8}" y="{oy - 34}" font-size="10.5" class="t-mut" text-anchor="end">averaged J</text>')
    a2 = math.radians(48)
    g.append(arrow(260 * math.cos(a2), 140 * math.sin(a2) + 52, "mu", dash="6 4", w=2))
    g.append(f'<text x="{ox + 186}" y="{oy - 160}" font-size="12.5" class="t-m" style="fill:var(--mu)">local tangent at m</text>')
    g.append(f'<line x1="{ox - 100}" y1="{oy}" x2="{ox + 320}" y2="{oy}" stroke="var(--line)"/>')
    g.append(f'<text x="458" y="{oy + 26}" font-size="11" class="t-2"><tspan style="fill:var(--delta)" font-weight="600">Averaged J:</tspan> 5–20× too short, cos 0.02–0.18: '
             'predicts ≈ 5 % of the response.</text>'
             f'<text x="458" y="{oy + 41}" font-size="11" class="t-2"><tspan style="fill:var(--mu)" font-weight="600">Local tangent:</tspan> cos 0.4–0.8 but 2–8× too long (saturation).</text>')
    return f"""
<svg viewBox="0 0 920 274" role="img" aria-label="H3's test. At layer l one position's state h is replaced by the anchor m and the rest of the network runs; F is the sum of the final residual over positions from s on. The true change F(h) minus F(m) is compared with the lens's prediction J times (h minus m): the averaged J's prediction is short and nearly orthogonal; the local tangent at m points roughly the right way but overshoots.">
  <defs>{_marker("pt-ink", "ink")}{_marker("pt-delta", "delta")}{_marker("pt-mu", "mu")}</defs>
  {"".join(g)}
</svg>"""


def fitted_lens(w: list[float], alone: list[float], share: list[float], counts: list[int], layer: int, router: str) -> str:
    """LL4: one layer's experts, each with its single-expert pass, where our bank cells land, and the fitted signed weight
    (all measured), summed into one map."""
    k = len(w)
    rh = 30 if k <= 8 else 17
    y0 = 74
    cols = {"e": 22, "n": 64, "alone": 150, "share": 300, "w": 520}
    bar = {"alone": 110, "share": 110, "w": 90}
    g = [f'<text x="{cols["e"]}" y="34" font-size="11" class="t-mono t-mut" letter-spacing="1.2">{router.upper()} EXPERTS AT L{layer} (MEASURED)</text>']
    hd = [("e", "expert"), ("n", "positions"), ("alone", "pass alone (per layer)"), ("share", "share of bank cells"), ("w", "fitted weight w (signed)")]
    for c, t in hd:
        g.append(f'<text x="{cols[c] if c != "w" else cols["w"] - bar["w"]}" y="60" font-size="11" class="t-2" font-weight="600">{t}</text>')
    amax = max(max(alone), 1e-6)
    smax = max(max(share), 1e-6)
    wmax = max(abs(x) for x in w)
    i_bad = sorted(range(k), key=lambda i: alone[i])[: 2]
    i_cells = max(range(k), key=lambda i: share[i])
    for i in range(k):
        y = y0 + i * rh
        cy = y + rh / 2
        g.append(f'<text x="{cols["e"]}" y="{cy + 4}" font-size="{12 if k <= 8 else 10.5}" class="t-mono">e{i}</text>'
                 f'<text x="{cols["n"]}" y="{cy + 4}" font-size="{11 if k <= 8 else 10}" class="t-mut">{counts[i]:,}</text>')
        aw = bar["alone"] * alone[i] / amax
        g.append(f'<rect x="{cols["alone"]}" y="{cy - 5}" width="{max(aw, 1):.1f}" height="10" rx="2" fill="var(--{"bad" if i in i_bad else "muted"})" opacity="0.75"/>'
                 f'<text x="{cols["alone"] + aw + 6:.1f}" y="{cy + 4}" font-size="10" class="t-mut">{alone[i]:.2f}</text>')
        sw = bar["share"] * share[i] / smax
        g.append(f'<rect x="{cols["share"]}" y="{cy - 5}" width="{max(sw, 1):.1f}" height="10" rx="2" fill="var(--mu)" opacity="0.75"/>'
                 f'<text x="{cols["share"] + sw + 6:.1f}" y="{cy + 4}" font-size="10" class="t-mut">{share[i]:.0%}</text>')
        mid = cols["w"]
        ww = bar["w"] * w[i] / wmax
        g.append(f'<line x1="{mid}" y1="{y + 3}" x2="{mid}" y2="{y + rh - 3}" stroke="var(--line-2)"/>'
                 f'<rect x="{mid + min(ww, 0):.1f}" y="{cy - 6}" width="{max(abs(ww), 1.2):.1f}" height="12" rx="2" '
                 f'fill="var(--{"bad" if w[i] < 0 else "delta"})"/>'
                 f'<text x="{mid + bar["w"] + 8}" y="{cy + 4}" font-size="10.5" class="t-mono t-2">{w[i]:+.2f}</text>')
        g.append(f'<path d="M{mid + bar["w"] + 52} {cy} C {mid + bar["w"] + 90} {cy}, {mid + bar["w"] + 100} {y0 + k * rh / 2}, '
                 f'{mid + bar["w"] + 128} {y0 + k * rh / 2}" fill="none" stroke="var(--line-2)" stroke-opacity="{0.25 + 0.75 * abs(w[i]) / wmax:.2f}"/>')
    yb = y0 + k * rh
    sx = cols["w"] + bar["w"] + 140
    sy = y0 + k * rh / 2
    g.append(f'<circle cx="{sx}" cy="{sy}" r="13" fill="var(--surface)" stroke="var(--ink-2)" stroke-width="1.5"/>'
             f'<text x="{sx}" y="{sy + 5}" text-anchor="middle" font-size="15">Σ</text>'
             f'<line x1="{sx + 13}" y1="{sy}" x2="{sx + 34}" y2="{sy}" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#fl-a)"/>'
             f'<rect x="{sx + 38}" y="{sy - 34}" width="128" height="68" rx="10" fill="var(--delta-soft)" stroke="var(--delta)"/>'
             f'<text x="{sx + 102}" y="{sy - 10}" text-anchor="middle" font-size="15" class="t-m">{_s("J", "w")} = Σ {_s("w", "i")} {_s("J", "i")}</text>'
             f'<text x="{sx + 102}" y="{sy + 12}" text-anchor="middle" font-size="11" class="t-2">read {_s("J", "w")} h, uncentred</text>'
             f'<text x="{sx + 102}" y="{sy + 26}" text-anchor="middle" font-size="10.5" class="t-mut">one map per layer</text>')
    # call-outs
    bad = ", ".join(f"e{i}" for i in i_bad)
    g.append(f'<text x="{cols["e"]}" y="{yb + 26}" font-size="11.5" class="t-2"><tspan style="fill:var(--bad)" font-weight="600">Weakest alone ({bad}):</tspan> '
             f'weights {", ".join(f"{w[i]:+.2f}" for i in i_bad)}: filtered out, as J++ does.</text>')
    heavy = [i for i in range(k) if share[i] >= 0.5 * share[i_cells]]  # the experts most bank cells land in
    j = min(heavy, key=lambda i: w[i])
    if w[j] < 0:
        line = (f'<tspan style="fill:var(--mu)" font-weight="600">e{j} holds {share[j]:.0%} of bank cells</tspan> '
                f'yet gets {w[j]:+.2f}: subtracted, a generic slope removed rather than the cells\' own region chosen.')
    else:
        line = (f'<tspan style="fill:var(--mu)" font-weight="600">Most bank cells (e{i_cells}, {share[i_cells]:.0%}):</tspan> '
                f'weight {w[i_cells]:+.2f}.')
    g.append(f'<text x="{cols["e"]}" y="{yb + 44}" font-size="11.5" class="t-2">{line}</text>')
    return f"""
<svg viewBox="0 0 920 {yb + 58}" role="img" aria-label="LL4 at one layer: each expert's position count, its pass rate when read alone, the share of our bank cells that the router sends to it, and the signed weight fitted on the fit split. The weighted sum is one linear map, read uncentred.">
  <defs>{_marker("fl-a", "ink-2")}</defs>
  {"".join(g)}
</svg>"""


def answer_grid(rows: list[tuple[str, str, list[float | None]]], base: float, split: str) -> str:
    """H4 / H6, measured: slope (rows) x intercept (columns), macro pass on ``split``; colour = gain over pooled J, 0."""
    cols = [("0", "no anchor"), ("wiki μ", "global mean"), ("wiki μᵢ", "own cluster's mean"), ("fam", "bank family mean"), ("knnx8", "bank 8-NN mean")]
    x0, y0, cw, rh, gap = 230, 92, 124, 50, 6
    g = []
    g.append(f'<rect x="{x0 + 1 * (cw + gap) - 4}" y="{y0 - 54}" width="{2 * cw + gap + 8}" height="{len(rows) * (rh + gap) + 56}" rx="10" fill="var(--sunk)" opacity="0.6"/>'
             f'<rect x="{x0 + 3 * (cw + gap) - 4}" y="{y0 - 54}" width="{2 * cw + gap + 8}" height="{len(rows) * (rh + gap) + 56}" rx="10" fill="var(--delta-soft)" opacity="0.6"/>')
    g.append(f'<text x="{x0 + 1 * (cw + gap) + cw + gap / 2}" y="{y0 - 38}" text-anchor="middle" font-size="11" class="t-mono t-mut" letter-spacing="1">WIKITEXT INTERCEPTS (LL)</text>'
             f'<text x="{x0 + 3 * (cw + gap) + cw + gap / 2}" y="{y0 - 38}" text-anchor="middle" font-size="11" class="t-mono" style="fill:var(--delta)" letter-spacing="1">BANK INTERCEPTS (S4)</text>')
    for j, (a, b) in enumerate(cols):
        x = x0 + j * (cw + gap) + cw / 2
        g.append(f'<text x="{x}" y="{y0 - 18}" text-anchor="middle" font-size="12.5" font-weight="600" style="fill:var(--mu)">{a}</text>'
                 f'<text x="{x}" y="{y0 - 5}" text-anchor="middle" font-size="10" class="t-mut">{b}</text>')
    vals = [v for _, _, r in rows for v in r if v is not None]
    best = max(vals)
    span = max(max(abs(v - base) for v in vals), 1e-6)
    for i, (name, sub, r) in enumerate(rows):
        y = y0 + i * (rh + gap)
        g.append(f'<text x="{x0 - 14}" y="{y + 22}" text-anchor="end" font-size="13" font-weight="600" style="fill:var(--h)">{name}</text>'
                 f'<text x="{x0 - 14}" y="{y + 38}" text-anchor="end" font-size="10.5" class="t-mut">{sub}</text>')
        for j, v in enumerate(r):
            x = x0 + j * (cw + gap)
            if v is None:
                g.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="7" fill="none" stroke="var(--line)" stroke-dasharray="3 3"/>'
                         f'<text x="{x + cw / 2}" y="{y + 30}" text-anchor="middle" font-size="12" class="t-mut">not run</text>')
                continue
            d = v - base
            tok = "good" if d > 0.003 else "bad" if d < -0.003 else "muted"
            op = 0.1 + 0.5 * min(abs(d) / span, 1)
            edge = ' stroke="var(--ink)" stroke-width="2"' if v == best else ' stroke="var(--line)"'
            g.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="7" fill="var(--surface)"{edge}/>'
                     f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="7" fill="var(--{tok})" opacity="{op:.2f}"/>'
                     f'<text x="{x + cw / 2}" y="{y + 23}" text-anchor="middle" font-size="15" font-weight="600" class="t-mono">{v:.3f}</text>'
                     f'<text x="{x + cw / 2}" y="{y + 40}" text-anchor="middle" font-size="10.5" class="t-2">{"base" if abs(d) < 1e-9 and i == 0 and j == 0 else f"{100 * d:+.1f}"}</text>')
    yb = y0 + len(rows) * (rh + gap)
    g.append(f'<text x="{x0 - 200}" y="{yb + 22}" font-size="11.5" class="t-2">Macro strict pass@10 on <tspan font-weight="600">{split}</tspan>, '
             'item rule over L24–L56, cos readout (the screen scorer). Small numbers: points over the pooled J read uncentred. '
             'Outlined: best cell.</text>')
    return f"""
<svg viewBox="0 0 920 {yb + 38}" role="img" aria-label="The design grid of the plan with measured scores: rows are the slope (pooled, filtered by fitted weights, routed by cluster, random routing, J++'s released map), columns the intercept (none, wikitext global or cluster mean, bank family or nearest-neighbour mean). Filtering and bank intercepts help; wikitext intercepts and routing do not.">
  {"".join(g)}
</svg>"""
