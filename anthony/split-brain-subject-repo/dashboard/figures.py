"""Explanatory diagrams as inline SVG strings. Colours are the page's CSS tokens (var(--h) etc.), so
every figure follows night mode without branching. Marker ids are prefixed per figure: all SVGs
share one DOM.
"""

import math
import re
from html import escape


def _marker(id_: str, token: str = "ink-2") -> str:
    return (f'<marker id="{id_}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0 0 L10 5 L0 10 z" fill="var(--{token})"/></marker>')


def _rng(seed: int):
    s = seed

    def r():
        nonlocal s
        s = (s * 9301 + 49297) % 233280
        return s / 233280

    return r


# ------------------------------------------------------------------ overview


def formula() -> str:
    return """
<svg viewBox="0 0 720 230" role="img" aria-label="The readout J_l times h_l minus mu_l, each symbol annotated: the released lens matrix, the residual at the read cell, and the centre this project chooses.">
  <text x="360" y="92" text-anchor="middle" class="t-m" font-size="68"><tspan>J</tspan><tspan font-size="34" dy="14">l</tspan><tspan dy="-14"> (</tspan><tspan style="fill:var(--h)">h</tspan><tspan style="fill:var(--h)" font-size="34" dy="14">l</tspan><tspan dy="-14"> − </tspan><tspan style="fill:var(--mu)">μ</tspan><tspan style="fill:var(--mu)" font-size="34" dy="14">l</tspan><tspan dy="-14">)</tspan></text>
  <g fill="none" stroke-width="1.5">
    <path d="M178 120 v10 h44 v-10" stroke="var(--muted)"/><path d="M318 120 v10 h66 v-10" stroke="var(--h)"/>
    <path d="M448 120 v10 h66 v-10" stroke="var(--mu)"/>
    <line x1="200" y1="130" x2="130" y2="160" stroke="var(--muted)"/><line x1="351" y1="130" x2="351" y2="160" stroke="var(--h)"/>
    <line x1="481" y1="130" x2="590" y2="160" stroke="var(--mu)"/>
  </g>
  <g font-size="13" text-anchor="middle">
    <text x="130" y="180" font-weight="600">the lens</text>
    <text x="130" y="198" class="t-mut">mean Jacobian of the final</text><text x="130" y="214" class="t-mut">residual w.r.t. block l (fixed)</text>
    <text x="351" y="180" font-weight="600" style="fill:var(--h)">the state</text>
    <text x="351" y="198" class="t-mut">residual at the read cell:</text><text x="351" y="214" class="t-mut">one layer, one token position</text>
    <text x="590" y="180" font-weight="600" style="fill:var(--mu)">the centre (our choice)</text>
    <text x="590" y="198" class="t-mut">may depend on h, the token,</text><text x="590" y="214" class="t-mut">the position, the context</text>
  </g>
</svg>"""


def readout_path(top10: list[str], target: str) -> str:
    """One read cell: grid of layers x positions -> h - mu -> J_l -> readout -> W_U -> top 10."""
    x0, y0, cols, rows, cw, ch, rr, rc = 24, 44, 9, 12, 24, 19, 5, 6
    grid = []
    for r in range(rows):
        for col in range(cols):
            read = r == rr and col == rc
            fill = "var(--h)" if read else ("var(--h-soft)" if col == rc else "var(--sunk)")
            grid.append(f'<rect x="{x0 + col * cw}" y="{y0 + r * ch}" width="{cw - 4}" height="{ch - 4}" rx="3" fill="{fill}"/>')
    grid.append(f'<text x="{x0 - 6}" y="{y0 + 11}" text-anchor="end" font-size="10" class="t-mut">L60</text>')
    grid.append(f'<text x="{x0 - 6}" y="{y0 + (rows - 1) * ch + 11}" text-anchor="end" font-size="10" class="t-mut">L20</text>')
    grid.append(f'<text x="{x0 + cols * cw / 2}" y="{y0 + rows * ch + 14}" text-anchor="middle" font-size="11" class="t-mut">token positions →</text>')
    grid.append(f'<text x="{x0 + rc * cw + 10}" y="{y0 - 6}" text-anchor="middle" font-size="11" style="fill:var(--h)">read cell</text>')
    grid.append(f'<line x1="{x0 + rc * cw + cw - 4}" y1="{y0 + rr * ch + 7}" x2="252" y2="150" stroke="var(--h)" stroke-width="1.5"/>')
    toks = []
    for i, t in enumerate(top10):
        y, hit = 46 + i * 22, t.strip().lower() == target.lower()
        toks.append(f'<rect x="786" y="{y}" width="100" height="18" rx="3" fill="var(--{"delta-soft" if hit else "sunk"})"/>'
                    f'<text x="794" y="{y + 13}" font-size="11" class="t-mono" style="fill:var(--{"delta" if hit else "ink-2"})">{escape(t.strip() or "·")}</text>')
    return f"""
<svg viewBox="0 0 900 300" role="img" aria-label="Readout path: the residual h at layer l and one token position has mu subtracted, is mapped to the final layer by J_l, normalised by the cos or rms readout, unembedded by W_U, and the top ten tokens are kept.">
  <defs>{_marker("rp-a")}{_marker("rp-d", "delta")}{_marker("rp-m", "mu")}</defs>
  <text x="20" y="20" font-size="12" class="t-mut">Qwen3.6-27B · 64 blocks</text>
  {"".join(grid)}
  <g font-size="13">
    <line x1="252" y1="150" x2="318" y2="150" stroke="var(--h)" stroke-width="2"/>
    <text x="285" y="140" text-anchor="middle" class="t-m" font-size="17" style="fill:var(--h)">h<tspan font-size="11" dy="4">l</tspan></text>
    <circle cx="345" cy="150" r="22" fill="var(--surface)" stroke="var(--ink-2)" stroke-width="1.5"/>
    <text x="345" y="156" text-anchor="middle" font-size="20">−</text>
    <line x1="345" y1="240" x2="345" y2="176" stroke="var(--mu)" stroke-width="2" marker-end="url(#rp-m)"/>
    <rect x="300" y="240" width="90" height="34" rx="6" fill="var(--mu-soft)" stroke="var(--mu)"/>
    <text x="345" y="262" text-anchor="middle" class="t-m" font-size="17" style="fill:var(--mu)">μ<tspan font-size="11" dy="4">l</tspan></text>
    <line x1="367" y1="150" x2="430" y2="150" stroke="var(--delta)" stroke-width="2" marker-end="url(#rp-d)"/>
    <text x="398" y="140" text-anchor="middle" class="t-m" font-size="15" style="fill:var(--delta)">h − μ</text>
    <rect x="432" y="122" width="86" height="56" rx="8" fill="var(--surface)" stroke="var(--ink-2)" stroke-width="1.5"/>
    <text x="475" y="150" text-anchor="middle" class="t-m" font-size="20">J<tspan font-size="12" dy="5">l</tspan></text>
    <text x="475" y="168" text-anchor="middle" font-size="10.5" class="t-mut">5120 × 5120</text>
    <line x1="518" y1="150" x2="556" y2="150" stroke="var(--ink-2)" stroke-width="1.5" marker-end="url(#rp-a)"/>
    <rect x="558" y="122" width="96" height="56" rx="8" fill="var(--sunk)" stroke="var(--line-2)"/>
    <text x="606" y="146" text-anchor="middle" font-size="12.5" font-weight="600">readout</text>
    <text x="606" y="164" text-anchor="middle" font-size="11" class="t-mono t-mut">cos | rms</text>
    <line x1="654" y1="150" x2="690" y2="150" stroke="var(--ink-2)" stroke-width="1.5" marker-end="url(#rp-a)"/>
    <rect x="692" y="122" width="58" height="56" rx="8" fill="var(--surface)" stroke="var(--ink-2)" stroke-width="1.5"/>
    <text x="721" y="155" text-anchor="middle" class="t-m" font-size="18">W<tspan font-size="11" dy="5">U</tspan></text>
    <line x1="750" y1="150" x2="782" y2="150" stroke="var(--ink-2)" stroke-width="1.5" marker-end="url(#rp-a)"/>
    {"".join(toks)}
    <text x="836" y="34" text-anchor="middle" font-size="12" class="t-mut">top 10 of 248k</text>
  </g>
  <text x="606" y="214" text-anchor="middle" font-size="11.5" class="t-mut">cos: score / ‖Jᵀ W_U[t]‖ (the bench)</text>
  <text x="606" y="231" text-anchor="middle" font-size="11.5" class="t-mut">rms: RMS-norm, then W_U (jle)</text>
</svg>"""


def repo_map() -> str:
    return f"""
<svg viewBox="0 0 900 260" role="img" aria-label="Repository map: umot and jle subtrees and the pinned WorkspaceBench clone feed the top-level jlm package, which writes captures and eval outputs that this dashboard reads.">
  <defs>{_marker("rm-a")}</defs>
  <g font-size="12.5">
    <rect x="20" y="20" width="250" height="70" rx="8" fill="var(--surface)" stroke="var(--line-2)"/>
    <text x="36" y="44" font-weight="600" class="t-mono">umot/</text>
    <text x="36" y="63" class="t-mut">unverbalized-motivations @ 30bbabf</text><text x="36" y="80" class="t-mut">DM, mention control, J++, Streamlit</text>
    <rect x="20" y="102" width="250" height="70" rx="8" fill="var(--surface)" stroke="var(--line-2)"/>
    <text x="36" y="126" font-weight="600" class="t-mono">jle/</text>
    <text x="36" y="145" class="t-mut">jlens-edits-1 @ 5f483de · x89–x101</text><text x="36" y="162" class="t-mut">4B / 9B / 27B, dev bank v2, lensboard</text>
    <rect x="20" y="184" width="250" height="62" rx="8" fill="var(--sunk)" stroke="var(--line-2)" stroke-dasharray="4 3"/>
    <text x="36" y="208" font-weight="600" class="t-mono">third_party/workspace-bench</text><text x="36" y="226" class="t-mut">pinned 92d763e · items, judge</text>
    <path d="M270 55 C 330 55, 330 120, 368 128" fill="none" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#rm-a)"/>
    <text x="318" y="64" class="t-mut" font-size="11">capture, Centre</text>
    <line x1="270" y1="137" x2="368" y2="137" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#rm-a)"/>
    <text x="318" y="130" class="t-mut" font-size="11" text-anchor="middle">dev banks</text>
    <path d="M270 215 C 330 215, 330 152, 368 146" fill="none" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#rm-a)"/>
    <text x="318" y="210" class="t-mut" font-size="11">bench, judge</text>
    <rect x="370" y="92" width="200" height="90" rx="10" fill="var(--delta-soft)" stroke="var(--delta)" stroke-width="1.5"/>
    <text x="470" y="122" text-anchor="middle" font-weight="600" class="t-mono" style="fill:var(--delta)">src/jlm</text>
    <text x="470" y="142" text-anchor="middle" class="t-2" font-size="11.5">banks · capture · centres</text>
    <text x="470" y="159" text-anchor="middle" class="t-2" font-size="11.5">lens · read · score · judge</text>
    <line x1="570" y1="137" x2="638" y2="137" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#rm-a)"/>
    <text x="604" y="128" text-anchor="middle" class="t-mut" font-size="11">writes</text>
    <rect x="640" y="62" width="240" height="56" rx="8" fill="var(--surface)" stroke="var(--line-2)"/>
    <text x="656" y="86" font-weight="600" class="t-mono">out/captures/</text><text x="656" y="104" class="t-mut">residuals at read cells, bf16</text>
    <rect x="640" y="130" width="240" height="56" rx="8" fill="var(--surface)" stroke="var(--line-2)"/>
    <text x="656" y="154" font-weight="600" class="t-mono">out/eval/&lt;fam&gt;/&lt;split&gt;/</text><text x="656" y="172" class="t-mut">readouts, ranks, summary, judge</text>
    <line x1="760" y1="186" x2="760" y2="214" stroke="var(--ink-2)" stroke-width="1.3" marker-end="url(#rm-a)"/>
    <text x="760" y="234" text-anchor="middle" class="t-mono t-2" font-size="12">dashboard/ reads on load</text>
  </g>
</svg>"""


# ------------------------------------------------------------------ why centre


def linearisation() -> str:
    """f(h) with the tangent at 0 (off the data) and at mu (on the data cloud)."""
    def X(h):
        return 60 + h * 38

    def Y(v):
        return 290 - v * 26

    def f(h):
        return 1.2 + 7.2 / (1 + math.exp(-(h - 5.2) * 0.9)) + 0.08 * h

    def df(h):
        e = math.exp(-(h - 5.2) * 0.9)
        return 7.2 * 0.9 * e / (1 + e) ** 2 + 0.08

    curve = "M" + " L".join(f"{X(h / 10):.1f} {Y(f(h / 10)):.1f}" for h in range(0, 101))

    def tangent(h0, a, b):
        return f"M{X(a):.1f} {Y(f(h0) + df(h0) * (a - h0)):.1f} L{X(b):.1f} {Y(f(h0) + df(h0) * (b - h0)):.1f}"

    mu, rnd = 7.3, _rng(7)
    dots = "".join(f'<circle cx="{X(mu + (rnd() - 0.5) * 2.6):.1f}" cy="{284 - rnd() * 6:.1f}" r="2.4" fill="var(--h)" opacity="0.6"/>'
                   for _ in range(22))
    return f"""
<svg viewBox="0 0 460 330" role="img" aria-label="A curved map f from a residual direction to the output. Real residuals sit in a cloud far from zero. The tangent at zero misses the curve there; the tangent at mu follows it.">
  <defs>{_marker("ln-a", "muted")}</defs>
  <line x1="40" y1="290" x2="440" y2="290" stroke="var(--muted)" marker-end="url(#ln-a)"/>
  <line x1="60" y1="310" x2="60" y2="20" stroke="var(--muted)" marker-end="url(#ln-a)"/>
  <text x="436" y="312" text-anchor="end" font-size="12" class="t-mut">residual h (one direction)</text>
  <text x="68" y="26" font-size="12" class="t-mut">final residual f(h)</text>
  <rect x="268" y="40" width="120" height="250" fill="var(--h-soft)"/>
  <text x="328" y="58" text-anchor="middle" font-size="11.5" style="fill:var(--h)">where real h live</text>
  {dots}
  <line x1="{X(mu):.1f}" y1="{Y(f(mu)):.1f}" x2="{X(mu):.1f}" y2="290" stroke="var(--mu)" stroke-dasharray="2 3"/>
  <path d="{curve}" fill="none" stroke="var(--ink)" stroke-width="2.2"/>
  <path d="{tangent(0, 0, 10)}" fill="none" stroke="var(--h)" stroke-width="1.8" stroke-dasharray="6 4"/>
  <path d="{tangent(mu, 5.4, 9.8)}" fill="none" stroke="var(--delta)" stroke-width="2"/>
  <circle cx="{X(0)}" cy="{Y(f(0)):.1f}" r="5" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>
  <circle cx="{X(mu):.1f}" cy="{Y(f(mu)):.1f}" r="6" fill="var(--mu)" stroke="var(--surface)" stroke-width="2"/>
  <text x="60" y="306" text-anchor="middle" font-size="13" class="t-m">0</text>
  <text x="{X(mu):.1f}" y="306" text-anchor="middle" font-size="15" class="t-m" style="fill:var(--mu)">μ</text>
  <text x="{X(0.6):.1f}" y="{Y(f(0) + df(0) * 0.6) - 30:.1f}" font-size="12" style="fill:var(--h)">tangent at 0: J h</text>
  <text x="{X(5.0):.1f}" y="{Y(f(mu) + df(mu) * (9.6 - mu)) - 16:.1f}" font-size="12" style="fill:var(--delta)">tangent at μ: J (h − μ)</text>
</svg>"""


def decomposition(delta_tokens: str) -> str:
    """h = mu + delta: a long shared mu, a short item-specific delta."""
    rnd = _rng(3)
    dots = []
    for _ in range(26):
        a, r = rnd() * 6.283, math.sqrt(rnd()) * 54
        dots.append(f'<circle cx="{330 + math.cos(a) * r:.1f}" cy="{92 + math.sin(a) * r * 0.9:.1f}" r="2.6" fill="var(--h)" opacity="0.45"/>')
    return f"""
<svg viewBox="0 0 460 300" role="img" aria-label="A long amber arrow mu runs from the origin to the centre of a cloud of residuals; each residual h is mu plus a short teal arrow delta. J mu decodes to a continuation prior; J delta carries the content.">
  <defs>{_marker("dc-h", "h")}{_marker("dc-m", "mu")}{_marker("dc-d", "delta")}</defs>
  <circle cx="330" cy="92" r="66" fill="var(--h-soft)"/>
  {"".join(dots)}
  <circle cx="50" cy="260" r="4" fill="var(--ink)"/><text x="42" y="282" font-size="13" class="t-m">0</text>
  <line x1="50" y1="260" x2="324" y2="97" stroke="var(--mu)" stroke-width="3" marker-end="url(#dc-m)"/>
  <line x1="50" y1="260" x2="368" y2="60" stroke="var(--h)" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#dc-h)"/>
  <line x1="330" y1="92" x2="368" y2="60" stroke="var(--delta)" stroke-width="2.6" marker-end="url(#dc-d)"/>
  <text x="160" y="200" font-size="17" class="t-m" style="fill:var(--mu)">μ</text>
  <text x="196" y="134" font-size="17" class="t-m" style="fill:var(--h)">h</text>
  <text x="378" y="50" font-size="16" class="t-m" style="fill:var(--delta)">δ = h − μ</text>
  <text x="330" y="182" text-anchor="middle" font-size="11.5" class="t-mut">states from one family</text>
  <text x="236" y="258" font-size="12" class="t-2">J μ → <tspan class="t-mono" font-size="11.5" style="fill:var(--mu)">&lt;|im_end|&gt;  \\n\\n  This  The</tspan></text>
  <text x="236" y="278" font-size="12" class="t-2">J δ → <tspan class="t-mono" font-size="11.5" style="fill:var(--delta)">{escape(delta_tokens)}</tspan></text>
</svg>"""


#: The mu ladder, with the results already in hand (notes/synthesis.md).
LADDER = [
    ("0", "μ = 0", "the released lens", "bench 0.55–0.68", 0.08, ""),
    ("G1", "corpus mean", "wikitext / pile", "does nothing", 0.2, ""),
    ("G2", "same-token corpus", "corpus states, this token", "+0.01 to +0.06", 0.33, ""),
    ("ctr1", "other families", "leave-one-family-out", "+0.02 to +0.08", 0.45, ""),
    ("fam", "own family", "one μ per layer", "27B 0.59 → 0.77", 0.6, "star"),
    ("tok", "same read token", "within the family", "DM 0.21 → 0.82", 0.7, ""),
    ("carpos", "same sentence & position", "matched carrier", "DM 0.89, reads prompt", 0.88, "bad"),
]


def ladder() -> str:
    x0, step, base, top = 92, 116, 360, 70
    g = []
    for i, (k, lab, sub, res, h, kind) in enumerate(LADDER):
        x, y = x0 + i * step, base - (base - top) * h
        fill, op = ("var(--bad)", 0.35) if kind == "bad" else ("var(--mu)", 0.85 if kind == "star" else 0.35)
        g.append(f'<rect x="{x - 32}" y="{y:.0f}" width="64" height="{base - y:.0f}" rx="4" fill="{fill}" opacity="{op}"/>'
                 f'<text x="{x}" y="{y - 46:.0f}" text-anchor="middle" font-size="12.5" font-weight="600">{escape(lab)}</text>'
                 f'<text x="{x}" y="{y - 30:.0f}" text-anchor="middle" font-size="11" class="t-mut">{escape(sub)}</text>'
                 f'<text x="{x}" y="{y - 12:.0f}" text-anchor="middle" font-size="11" class="t-mono" style="fill:var(--{"bad" if kind == "bad" else "ink-2"})">{escape(res)}</text>'
                 f'<text x="{x}" y="{base - 8}" text-anchor="middle" font-size="10.5" class="t-mono" style="fill:var(--{"surface" if kind == "star" else "ink-2"})">{k}</text>')
    xa, xb = x0 - 40, x0 + 5 * step + 46
    return f"""
<svg viewBox="0 0 900 410" role="img" aria-label="The ladder of centres, ordered by how much of the context they condition on, from mu = 0 to the same sentence and position. Tighter matching removes more background but eventually subtracts or re-reads the prompt.">
  <defs>
    <linearGradient id="ld-risk" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="var(--mu)" stop-opacity="0"/><stop offset="0.65" stop-color="var(--mu)" stop-opacity="0.08"/>
      <stop offset="1" stop-color="var(--bad)" stop-opacity="0.2"/>
    </linearGradient>{_marker("ld-a", "muted")}
  </defs>
  <rect x="40" y="40" width="830" height="320" fill="url(#ld-risk)" rx="6"/>
  <line x1="40" y1="375" x2="870" y2="375" stroke="var(--muted)" marker-end="url(#ld-a)"/>
  <text x="40" y="398" font-size="12" class="t-mut">C conditions on less</text>
  <text x="866" y="398" font-size="12" class="t-mut" text-anchor="end">C conditions on more of the read cell's context</text>
  <text x="866" y="28" font-size="12" text-anchor="end" style="fill:var(--bad)">reads or subtracts the prompt</text>
  {"".join(g)}
  <path d="M{xa} 52 v-8 H{xb} v8" fill="none" stroke="var(--delta)" stroke-width="1.5"/>
  <text x="{(xa + xb) / 2}" y="36" text-anchor="middle" font-size="12" font-weight="600" style="fill:var(--delta)">label-free and fair: where the answer must lie</text>
</svg>"""


# ------------------------------------------------------------------ pipeline


def stages() -> str:
    S = [  # x, y, w, label, sub, code, is_g
        (30, 52, 130, "banks", "data/dev, bench items", "jlm.banks", False),
        (190, 52, 160, "capture", "read cells, 12 layers", "capture.py", False),
        (380, 52, 180, "context capture", "every position, + wikitext", "capture_ctx.py", False),
        (30, 160, 130, "study g", "one module per study", "jlm/mu/<id>.py", True),
        (190, 160, 160, "centre g", "fit(refs) → h − g", "jlm.centres", True),
        (380, 160, 160, "read", "J (h − g), cos | rms", "jlm.read", False),
        (570, 160, 160, "score", "strict, rank, controls", "evaluate.py", False),
        (760, 160, 170, "analyse", "battery, macro gain", "analyse.py", False),
        (570, 290, 160, "judge", "Haiku 5.5 on val", "judge.py", False),
    ]
    boxes = []
    for x, y, w, lab, sub, code, key in S:
        boxes.append(f'<rect x="{x}" y="{y}" width="{w}" height="58" rx="8" fill="var(--{"mu-soft" if key else "surface"})" '
                     f'stroke="var(--{"mu" if key else "ink-2"})" stroke-width="{1.8 if key else 1.2}"/>'
                     f'<text x="{x + 12}" y="{y + 20}" font-size="13" font-weight="600"{" style=\"fill:var(--mu)\"" if key else ""}>{lab}</text>'
                     f'<text x="{x + 12}" y="{y + 36}" font-size="11" class="t-2">{escape(sub)}</text>'
                     f'<text x="{x + 12}" y="{y + 51}" font-size="10" class="t-mono t-mut">{escape(code)}</text>')

    def arrow(d, lab="", lx=0, ly=0, anchor="middle", dash=False):
        a = (f'<path d="{d}" fill="none" stroke="var(--{"line-2" if dash else "ink-2"})" stroke-width="1.3"'
             f'{" stroke-dasharray=\"4 3\"" if dash else ""} marker-end="url(#st-a)"/>')
        return a + (f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="10.5" class="t-mut">{escape(lab)}</text>' if lab else "")

    arrows = (arrow("M160 81 H188") + arrow("M95 52 V38 H470 V50")
              + arrow("M270 110 V158", "read cells", 276, 140, "start")
              + arrow("M470 110 V132 H330 V158", "all positions", 400, 127, dash=True)
              + arrow("M160 189 H188") + arrow("M350 189 H378") + arrow("M540 189 H568") + arrow("M730 189 H758")
              + arrow("M460 218 V319 H568", "top-10 bags", 470, 312, "start", dash=True)
              + arrow("M730 319 H845 V220", "verdicts", 790, 312))
    return f"""
<svg viewBox="0 0 960 372" role="img" aria-label="Pipeline stages. On RunPod, with a shared network volume: banks feed the read-cell capture and the every-position context capture of the 27B. On a pod GPU or the Mac: a centre, possibly from a study module, turns each state into h minus g; read applies the lens; score computes strict pass, ranks and the free controls; analyse runs the battery. The judge reads top-10 bags through the OpenRouter API and its verdicts go to the analysis.">
  <defs>{_marker("st-a")}</defs>
  <rect x="10" y="20" width="940" height="98" rx="8" fill="var(--sunk)"/>
  <text x="936" y="40" text-anchor="end" class="t-mono t-mut" font-size="11">RUNPOD · 27B forward passes · shared volume jlm-shared</text>
  <text x="936" y="56" text-anchor="end" font-size="10.5" class="t-mut">HF cache, captures, ctx, eval: written once, read by every pod</text>
  <rect x="10" y="126" width="940" height="140" rx="8" fill="none" stroke="var(--line-2)" stroke-dasharray="4 3"/>
  <text x="24" y="256" class="t-mono t-mut" font-size="11">POD GPU (default) OR MAC · no 27B: W_U, final norm, lens</text>
  <text x="570" y="240" font-size="10.5" class="t-2">every arm also gets: prompt echo,</text>
  <text x="570" y="255" font-size="10.5" class="t-2">prompt-masked top 10, next-token overlap</text>
  <rect x="10" y="274" width="940" height="88" rx="8" fill="var(--sunk)"/>
  <text x="24" y="296" class="t-mono t-mut" font-size="11">OPENROUTER API · the only per-call spend</text>
  <text x="24" y="318" font-size="11" class="t-2">A new g only touches the amber boxes:</text>
  <text x="24" y="334" font-size="11" class="t-2">capture, read, scoring, controls and judge are shared.</text>
  <text x="745" y="340" font-size="10.5" class="t-mut">pinned Gemini 3.8 Flash for the bench</text>
  {"".join(boxes)}{arrows}
</svg>"""


def arm_grammar() -> str:
    return """
<svg viewBox="0 0 820 190" role="img" aria-label="The arm name fam@fit|cos split into the centre kind, the reference split it is fitted on, and the readout.">
  <text x="410" y="70" text-anchor="middle" class="t-mono" font-size="44"><tspan style="fill:var(--mu)">fam</tspan><tspan class="t-mut">@</tspan><tspan>fit</tspan><tspan class="t-mut">|</tspan><tspan style="fill:var(--h)">cos</tspan></text>
  <g fill="none" stroke-width="1.5">
    <path d="M265 88 v8 h76 v-8" stroke="var(--mu)"/><path d="M370 88 v8 h80 v-8" stroke="var(--ink-2)"/><path d="M478 88 v8 h80 v-8" stroke="var(--h)"/>
    <line x1="303" y1="96" x2="150" y2="122" stroke="var(--mu)"/><line x1="410" y1="96" x2="410" y2="122" stroke="var(--ink-2)"/>
    <line x1="518" y1="96" x2="670" y2="122" stroke="var(--h)"/>
  </g>
  <g font-size="12.5" text-anchor="middle">
    <text x="150" y="140" font-weight="600" style="fill:var(--mu)">centre</text>
    <text x="150" y="158" class="t-mut"><tspan class="t-mono">zero</tspan> · <tspan class="t-mono">fam</tspan> (one μ per layer) · <tspan class="t-mono">tok</tspan></text>
    <text x="150" y="175" class="t-mut">(same read token)</text>
    <text x="410" y="140" font-weight="600">reference split</text>
    <text x="410" y="158" class="t-mut"><tspan class="t-mono">self</tspan>: the read bank, own item left out</text>
    <text x="410" y="175" class="t-mut"><tspan class="t-mono">fit</tspan>: held out from val and bench</text>
    <text x="670" y="140" font-weight="600" style="fill:var(--h)">readout</text>
    <text x="670" y="158" class="t-mut"><tspan class="t-mono">cos</tspan>: the bench's normalised score</text>
    <text x="670" y="175" class="t-mut"><tspan class="t-mono">rms</tspan>: jle's RMS-norm read</text>
  </g>
</svg>"""


def splits() -> str:
    rows = [("fit", "fit centres · choose among arms · free scoring only", "use freely", False),
            ("val", "confirm the chosen arms · LLM judge runs here", "confirm", False),
            ("bench", "WorkspaceBench · once per registered method", "once", True)]
    g = []
    for i, (k, sub, tag, last) in enumerate(rows):
        y = 20 + i * 92
        g.append(f'<rect x="20" y="{y}" width="400" height="66" rx="8" fill="var(--{"mu-soft" if last else "surface"})" stroke="var(--{"mu" if last else "line-2"})"/>'
                 f'<text x="36" y="{y + 26}" class="t-mono" font-weight="500" font-size="14">{k}</text>'
                 f'<text x="36" y="{y + 48}" class="t-{"2" if last else "mut"}" font-size="12">{sub}</text>'
                 f'<text x="404" y="{y + 26}" text-anchor="end" class="t-mono{"" if last else " t-mut"}" font-size="11"{" style=\"fill:var(--mu)\"" if last else ""}>{tag}</text>')
        if not last:
            g.append(f'<line x1="220" y1="{y + 66}" x2="220" y2="{y + 90}" stroke="var(--ink-2)" marker-end="url(#sp-a)"/>')
    return f"""
<svg viewBox="0 0 440 290" role="img" aria-label="Three splits: fit is used to fit centres and choose arms with free scoring; val confirms with the judge; bench is read once per registered method.">
  <defs>{_marker("sp-a")}</defs>{"".join(g)}
</svg>"""


def cellref() -> str:
    fields = [("item", "dev-ty-a-066"), ("group", "dev-ty-a-066"), ("family", "typo"), ("layer", "44"), ("pos", "8"),
              ("token", '"ck"'), ("context", "…a sudden attac")]
    rows = "".join(f'<text x="36" y="{72 + i * 21}">{k}</text><text x="132" y="{72 + i * 21}" class="t-mut">{escape(v)}</text>'
                   for i, (k, v) in enumerate(fields))
    return f"""
<svg viewBox="0 0 440 290" role="img" aria-label="A centre sees a CellRef: item id, family, layer, read position, read token and the prompt up to the cell. It never sees the targets, and the item's own group is never in its own reference set; a centre may instead take a Batch of cells with their states.">
  <g font-size="12">
    <rect x="20" y="20" width="240" height="250" rx="10" fill="var(--surface)" stroke="var(--line-2)"/>
    <text x="36" y="46" font-weight="600" class="t-mono">CellRef</text>
    <g class="t-mono">{rows}<text x="132" y="219" class="t-mut">ck</text></g>
    <text x="36" y="244" font-size="11.5" style="fill:var(--good)">→ centre(cell) = μ, or</text>
    <text x="36" y="260" font-size="11.5" style="fill:var(--good)">→ transform(Batch) = h − g</text>
    <rect x="290" y="70" width="130" height="80" rx="8" fill="none" stroke="var(--bad)" stroke-dasharray="5 4"/>
    <text x="355" y="98" text-anchor="middle" font-weight="600" style="fill:var(--bad)">targets</text>
    <text x="355" y="118" text-anchor="middle" class="t-mono t-mut">"attack"</text>
    <text x="355" y="138" text-anchor="middle" font-size="11" style="fill:var(--bad)">never passed</text>
    <line x1="268" y1="102" x2="282" y2="118" stroke="var(--bad)" stroke-width="2"/><line x1="282" y1="102" x2="268" y2="118" stroke="var(--bad)" stroke-width="2"/>
    <text x="355" y="196" text-anchor="middle" font-size="11.5" class="t-2">own group never in</text>
    <text x="355" y="212" text-anchor="middle" font-size="11.5" class="t-2">its own reference set</text>
  </g>
</svg>"""


# ------------------------------------------------------------------ study diagrams (Studies page; notes/iteration-anthony/studies/CARDS.md)


def _sub(s: str) -> str:
    """An SVG subscript (tspan), e.g. f"h{_sub('l')}"."""
    return f'<tspan baseline-shift="sub" font-size="72%">{escape(s)}</tspan>'


def _wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def _arrow(x1, y1, x2, y2, mid: str, token: str = "ink-2", width: float = 1.6, dash: str = "") -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="var(--{token})" stroke-width="{width}"{d} '
            f'marker-end="url(#{mid})"/>')


_POOL_TITLE = {
    "family": "the family's reference cells", "cluster": "h's cluster (k-means over the pool)",
    "knn": "the k nearest reference cells", "token": "cells with h's read token",
    "position": "cells at h's position in the read span", "language": "cells whose prompt is in h's language",
    "other_language": "cells whose prompt is in another language", "neutral": "neutral fills of h's prompt",
    "all": "every reference cell",
}


def study_pool(select: str = "family", exclude: str = "") -> str:
    """A cloud of reference cells in two families; the subset g averages is filled, its mean is the diamond, and the
    read vector h - g runs from it to h."""
    rnd = _rng(11)
    fams = [(150, 150, "A"), (330, 120, "B"), (270, 250, "C")]
    tokens, langs, poss = ["the", "of", "and", "Paris"], ["en", "fr", "id"], ["−1", "−2", "−3"]
    pts = []
    for fi, (cx, cy, _) in enumerate(fams):
        for k in range(18):
            a, r = rnd() * 6.283, 18 + rnd() * 52
            pts.append({"x": cx + math.cos(a) * r * 1.25, "y": cy + math.sin(a) * r * 0.8, "fam": fi,
                        "sub": 0 if math.cos(a) > 0 else 1, "tok": tokens[k % 4], "lang": langs[(k + fi) % 3],
                        "pos": poss[(k * 7 + fi) % 3], "sent": k % 6})
    h = {"x": 212, "y": 122, "fam": 0, "sub": 0, "tok": "the", "lang": "id", "pos": "−1", "sent": 0}
    for p in pts:
        p["d"] = math.hypot(p["x"] - h["x"], p["y"] - h["y"])
    excluded = (lambda p: p["fam"] == 0 and p["sent"] == 0) if exclude in ("own_sentence", "own_group") else (lambda p: False)
    rule = {
        "family": lambda p: p["fam"] == 0, "cluster": lambda p: p["fam"] == 0 and p["sub"] == 0,
        "token": lambda p: p["tok"] == h["tok"], "position": lambda p: p["pos"] == h["pos"],
        "language": lambda p: p["lang"] == h["lang"], "other_language": lambda p: p["lang"] != h["lang"],
        "all": lambda p: True, "neutral": lambda p: False,
    }
    if select == "knn":
        near = sorted((p for p in pts if not excluded(p)), key=lambda p: p["d"])[:8]
        chosen = {id(p) for p in near}
        sel = lambda p: id(p) in chosen  # noqa: E731
    else:
        sel = rule.get(select, rule["family"])
    neutral = []
    if select == "neutral":
        for k in range(6):
            a = rnd() * 6.283
            neutral.append({"x": h["x"] - 70 + math.cos(a) * 22, "y": h["y"] + 62 + math.sin(a) * 10})
    picked = [p for p in pts if sel(p) and not excluded(p)] + neutral
    mx = sum(p["x"] for p in picked) / len(picked)
    my = sum(p["y"] for p in picked) / len(picked)
    label = {"token": "tok", "language": "lang", "other_language": "lang", "position": "pos"}.get(select)
    out = []
    label_at = [(-70, -66, "end"), (70, -66, "start"), (0, 80, "middle")]  # outer edges, clear of g's label
    for i, (cx, cy, name) in enumerate(fams):
        dx, dy, anchor = label_at[i]
        out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="92" ry="62" fill="var(--sunk)" opacity="0.7"/>'
                   f'<text x="{cx + dx}" y="{cy + dy}" text-anchor="{anchor}" font-size="11" class="t-mut">family {name}</text>')
    if select == "cluster":
        out.append(f'<line x1="150" y1="88" x2="150" y2="212" stroke="var(--line-2)" stroke-dasharray="4 3"/>')
    if select == "knn":
        r = max(p["d"] for p in pts if sel(p)) + 6
        out.append(f'<circle cx="{h["x"]}" cy="{h["y"]}" r="{r:.1f}" fill="none" stroke="var(--mu)" stroke-dasharray="4 3"/>')
    for p in pts:
        if excluded(p):
            out.append(f'<g stroke="var(--muted)" stroke-width="1.4"><line x1="{p["x"] - 3.5:.1f}" y1="{p["y"] - 3.5:.1f}" '
                       f'x2="{p["x"] + 3.5:.1f}" y2="{p["y"] + 3.5:.1f}"/><line x1="{p["x"] - 3.5:.1f}" y1="{p["y"] + 3.5:.1f}" '
                       f'x2="{p["x"] + 3.5:.1f}" y2="{p["y"] - 3.5:.1f}"/></g>')
            continue
        on = sel(p)
        out.append(f'<circle cx="{p["x"]:.1f}" cy="{p["y"]:.1f}" r="{4 if on else 3}" fill="{"var(--mu)" if on else "var(--line-2)"}" '
                   f'opacity="{0.95 if on else 0.8}"/>')
        if label and on:
            out.append(f'<text x="{p["x"] + 5:.1f}" y="{p["y"] - 4:.1f}" font-size="8.5" class="t-mut t-mono">{escape(p[label])}</text>')
    for p in neutral:
        out.append(f'<rect x="{p["x"] - 3.5:.1f}" y="{p["y"] - 3.5:.1f}" width="7" height="7" fill="var(--mu)"/>')
    if neutral:
        out.append(f'<text x="{h["x"] - 70}" y="{h["y"] + 92}" text-anchor="middle" font-size="10.5" style="fill:var(--mu)">neutral fills</text>')
    out.append(_arrow(mx, my, h["x"] - 4, h["y"] + 3, "sp-a", "delta", 2.2))
    out.append(f'<path d="M{mx:.1f} {my - 7:.1f} l7 7 l-7 7 l-7 -7 z" fill="var(--mu)" stroke="var(--surface)" stroke-width="1.5"/>')
    out.append(f'<circle cx="{h["x"]}" cy="{h["y"]}" r="6" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>')
    out.append(f'<text x="{h["x"] - 10}" y="{h["y"] - 9}" text-anchor="end" font-size="15" class="t-m" style="fill:var(--h)">h</text>')
    out.append(f'<text x="{mx - 10:.1f}" y="{my + 5:.1f}" text-anchor="end" font-size="14" class="t-m" style="fill:var(--mu)" '
               f'paint-order="stroke" stroke="var(--surface)" stroke-width="3">g(h)</text>')
    excl = {"own_sentence": "× own sentence left out", "own_group": "× own item group left out"}.get(exclude, "")
    title = escape(_POOL_TITLE.get(select, select))
    return f"""
<svg viewBox="0 0 480 330" role="img" aria-label="Reference cells in three families; g is the mean of {title}; the read vector runs from g to h.">
  <defs>{_marker("sp-a", "delta")}</defs>
  {''.join(out)}
  <g font-size="11.5">
    <circle cx="26" cy="300" r="4" fill="var(--mu)"/><text x="36" y="304">averaged by g: {title}</text>
    <circle cx="26" cy="318" r="3" fill="var(--line-2)"/><text x="36" y="322" class="t-mut">other reference cells</text>
    <line x1="300" y1="314" x2="326" y2="314" stroke="var(--delta)" stroke-width="2.2"/>
    <text x="332" y="318" style="fill:var(--delta)">read vector h − g</text>
    {f'<text x="300" y="300" class="t-mut">{excl}</text>' if excl else ''}
  </g>
</svg>"""


def study_subspace(k: int = 16) -> str:
    """g = family mean + h's component along the family's top principal directions: what is left is the off-axis part."""
    cx, cy = 200, 165
    rnd = _rng(5)
    dots = []
    for _ in range(70):
        u, v = (rnd() - 0.5) * 2, (rnd() - 0.5) * 2
        x, y = u * 130, v * 42
        dots.append(f'<circle cx="{cx + x * 0.94 - y * 0.34:.1f}" cy="{cy + x * 0.34 + y * 0.94:.1f}" r="2.6" fill="var(--line-2)"/>')
    ux, uy = 0.94, 0.34
    hx, hy = cx + 95, cy - 40
    t = (hx - cx) * ux + (hy - cy) * uy
    gx, gy = cx + t * ux, cy + t * uy
    return f"""
<svg viewBox="0 0 480 330" role="img" aria-label="A family cloud with its principal axis. g is the family mean plus h's projection on the top {k} directions; the read vector h - g is the part of h off those directions.">
  <defs>{_marker("ss-a", "delta")}{_marker("ss-p", "mu")}{_marker("ss-m", "muted")}</defs>
  <ellipse cx="{cx}" cy="{cy}" rx="150" ry="56" transform="rotate(20 {cx} {cy})" fill="var(--sunk)"/>
  {''.join(dots)}
  {_arrow(cx - 150 * ux, cy - 150 * uy, cx + 165 * ux, cy + 165 * uy, "ss-m", "muted", 1.2, "5 4")}
  <text x="{cx - 150 * ux:.0f}" y="{cy - 150 * uy - 10:.0f}" font-size="11" class="t-mut">top {k} principal directions of the family</text>
  {_arrow(cx, cy, gx - 3, gy - 1, "ss-p", "mu", 2)}
  {_arrow(gx, gy, hx + 2, hy + 5, "ss-a", "delta", 2.2)}
  <circle cx="{cx}" cy="{cy}" r="5" fill="var(--ink-2)"/>
  <text x="{cx - 8}" y="{cy + 20}" font-size="14" class="t-m" text-anchor="end">μ{_sub("fam")}</text>
  <path d="M{gx:.1f} {gy - 7:.1f} l7 7 l-7 7 l-7 -7 z" fill="var(--mu)" stroke="var(--surface)" stroke-width="1.5"/>
  <text x="{gx + 10:.1f}" y="{gy + 18:.1f}" font-size="14" class="t-m" style="fill:var(--mu)">g(h)</text>
  <circle cx="{hx}" cy="{hy}" r="6" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>
  <text x="{hx + 10}" y="{hy - 6}" font-size="15" class="t-m" style="fill:var(--h)">h</text>
  <g font-size="11.5">
    <line x1="20" y1="300" x2="44" y2="300" stroke="var(--mu)" stroke-width="2"/>
    <text x="50" y="304" style="fill:var(--mu)">P{_sub(str(k))}(h − μ{_sub("fam")}): h along the family's shared axes, removed</text>
    <line x1="20" y1="318" x2="44" y2="318" stroke="var(--delta)" stroke-width="2.2"/>
    <text x="50" y="322" style="fill:var(--delta)">read vector h − g: what is off those axes</text>
  </g>
</svg>"""


def study_layer(lag: int = 4, axis: str = "layer") -> str:
    """g taken from the same cell's own state ``lag`` layers below, or (axis position) ``lag`` positions earlier."""
    if axis == "position":
        return _study_position_lag(lag)
    layers = list(range(64, 15, -4))
    x, y0, w, hgt = 150, 24, 120, 19
    read = 40
    src = read - lag
    rows = []
    for i, L in enumerate(layers):
        y = y0 + i * (hgt + 3)
        fill = "var(--h)" if L == read else ("var(--mu)" if L == src else "var(--sunk)")
        tc = "var(--surface)" if L in (read, src) else "var(--muted)"
        rows.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hgt}" rx="3" fill="{fill}"/>'
                    f'<text x="{x + w / 2}" y="{y + 13.5}" text-anchor="middle" font-size="11" style="fill:{tc}">L{L}</text>')
    yr = y0 + layers.index(read) * (hgt + 3) + hgt / 2
    ys = (y0 + layers.index(src) * (hgt + 3) + hgt / 2) if src in layers else yr + (hgt + 3) * lag / 4
    if src not in layers:
        rows.append(f'<rect x="{x}" y="{ys - hgt / 2:.1f}" width="{w}" height="{hgt}" rx="3" fill="var(--mu)"/>'
                    f'<text x="{x + w / 2}" y="{ys + 4:.1f}" text-anchor="middle" font-size="11" style="fill:var(--surface)">L{src}</text>')
    return f"""
<svg viewBox="0 0 480 330" role="img" aria-label="A column of layers at one token position. g is the same cell's own state {lag} layer(s) below the read layer.">
  <defs>{_marker("sl-a", "mu")}</defs>
  {''.join(rows)}
  <path d="M{x + w + 6} {ys:.1f} C {x + w + 60} {ys:.1f}, {x + w + 60} {yr:.1f}, {x + w + 8} {yr:.1f}" fill="none" stroke="var(--mu)"
        stroke-width="2" marker-end="url(#sl-a)"/>
  <text x="{x + w + 66}" y="{(ys + yr) / 2 + 4:.1f}" font-size="14" class="t-m" style="fill:var(--mu)">g(h{_sub("l")}) = h{_sub(f"l−{lag}")}</text>
  <text x="{x - 12}" y="{yr + 5:.1f}" text-anchor="end" font-size="14" class="t-m" style="fill:var(--h)">read: h{_sub("l")}</text>
  <text x="{x + w / 2}" y="318" text-anchor="middle" font-size="11.5" class="t-mut">one token position, layers of the residual stream</text>
</svg>"""


def _study_position_lag(lag: int) -> str:
    """One layer, a row of token positions: g from the state ``lag`` positions before the read cell."""
    toks = ["The", "capital", "of", "France", "is"]
    x0, w, gap, y = 40, 72, 10, 120
    read = len(toks) - 1
    src = read - lag
    out = []
    for i, t in enumerate(toks):
        x = x0 + i * (w + gap)
        fill = "var(--h)" if i == read else "var(--mu)" if i == src else "var(--sunk)"
        tc = "var(--surface)" if i in (read, src) else "var(--ink-2)"
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="5" fill="{fill}"/>'
                   f'<text x="{x + w / 2}" y="{y + 22}" text-anchor="middle" font-size="12.5" class="t-mono" style="fill:{tc}">{escape(t)}</text>')
    xs, xr = x0 + src * (w + gap) + w / 2, x0 + read * (w + gap) + w / 2
    return f"""
<svg viewBox="0 0 480 300" role="img" aria-label="One layer, a row of token positions. g comes from the read cell's own state {lag} position(s) earlier.">
  <defs>{_marker("spl-a", "mu")}</defs>
  <text x="240" y="70" text-anchor="middle" font-size="11.5" class="t-mut">one layer l, token positions of the prompt</text>
  {''.join(out)}
  <path d="M{xs} {y + 38} C {xs} {y + 90}, {xr} {y + 90}, {xr} {y + 42}" fill="none" stroke="var(--mu)" stroke-width="2"
        marker-end="url(#spl-a)"/>
  <text x="{(xs + xr) / 2}" y="{y + 110}" text-anchor="middle" font-size="14" class="t-m" style="fill:var(--mu)">g(h{_sub("l,t")}) = F(h{_sub(f"l,t−{lag}")})</text>
  <text x="{xr}" y="{y - 10}" text-anchor="middle" font-size="14" class="t-m" style="fill:var(--h)">read: h{_sub("l,t")}</text>
  <text x="240" y="276" text-anchor="middle" font-size="11.5" class="t-mut">F: a map fitted on a text corpus (the predicted next state)</text>
</svg>"""


def study_word(word: str = "category") -> str:
    """The state of a category word in the prompt, subtracted from the read cell's state."""
    toks = ["Name", "a", word, "word", "for", "the", "idea", ":"]
    x, out = 24, []
    for i, t in enumerate(toks):
        w = 16 + 7.6 * len(t)
        fill = "var(--mu-soft)" if t == word else ("var(--h-soft)" if i == len(toks) - 1 else "var(--sunk)")
        stroke = "var(--mu)" if t == word else ("var(--h)" if i == len(toks) - 1 else "none")
        out.append(f'<rect x="{x:.1f}" y="70" width="{w:.1f}" height="30" rx="5" fill="{fill}" stroke="{stroke}"/>'
                   f'<text x="{x + w / 2:.1f}" y="90" text-anchor="middle" font-size="13" class="t-mono">{escape(t)}</text>')
        if t == word:
            wx = x + w / 2
        if i == len(toks) - 1:
            rx = x + w / 2
        x += w + 6
    return f"""
<svg viewBox="0 0 480 300" role="img" aria-label="A prompt; the state at the word '{escape(word)}' is scaled and subtracted from the read cell's state.">
  <defs>{_marker("sw-a", "mu")}{_marker("sw-b", "delta")}</defs>
  <text x="24" y="52" font-size="11.5" class="t-mut">the prompt (one layer of the residual stream)</text>
  {''.join(out)}
  {_arrow(wx, 104, wx, 168, "sw-a", "mu", 2)}
  {_arrow(rx, 104, rx, 168, "sw-b", "h", 2)}
  <text x="{wx}" y="190" text-anchor="middle" font-size="14" class="t-m" style="fill:var(--mu)">g = α · h{_sub("word")}</text>
  <text x="{rx}" y="190" text-anchor="middle" font-size="14" class="t-m" style="fill:var(--h)">h (read cell)</text>
  <text x="240" y="240" text-anchor="middle" font-size="15" class="t-m">J{_sub("l")} ( h − α · h{_sub("word")} )</text>
  <text x="240" y="264" text-anchor="middle" font-size="11.5" class="t-mut">α &gt; 0 removes the word's direction; α &lt; 0 adds it back</text>
</svg>"""


def study_probe(left: str = "self-described", right: str = "quoted about someone else", left_text: str = "",
                right_text: str = "") -> str:
    """Two prompts that carry the same content but differ in what the bench should credit."""
    def box(x, title, text, token):
        lines = _wrap(text or "…", 25)[:6]
        body = "".join(f'<text x="{x + 14}" y="{100 + 17 * i}" font-size="11.5" class="t-mono t-2">{escape(s)}</text>'
                       for i, s in enumerate(lines))
        return (f'<rect x="{x}" y="58" width="212" height="150" rx="8" fill="var(--surface)" stroke="var(--{token})" stroke-width="1.6"/>'
                f'<text x="{x + 14}" y="78" font-size="12.5" font-weight="600" style="fill:var(--{token})">{escape(title)}</text>{body}')
    return f"""
<svg viewBox="0 0 480 290" role="img" aria-label="Two prompts compared: {escape(left)} and {escape(right)}.">
  <text x="240" y="34" text-anchor="middle" font-size="12" class="t-mut">same content, different attribution</text>
  {box(20, left, left_text, "h")}
  {box(248, right, right_text, "mu")}
  <text x="240" y="240" text-anchor="middle" font-size="12.5">a readout that credits user modelling should surface the</text>
  <text x="240" y="258" text-anchor="middle" font-size="12.5">attribute for the left prompt and not for the right one</text>
</svg>"""


def study_maps() -> str:
    """One residual read through two maps (J-lens and J++), compared top 10 against top 10."""
    return f"""
<svg viewBox="0 0 480 280" role="img" aria-label="One centred state h minus g is read through the J-lens and through J++; the two top-10 lists are compared.">
  <defs>{_marker("sm-a", "ink-2")}</defs>
  <rect x="24" y="112" width="96" height="46" rx="8" fill="var(--h-soft)" stroke="var(--h)"/>
  <text x="72" y="140" text-anchor="middle" font-size="15" class="t-m" style="fill:var(--h)">h − g</text>
  {_arrow(122, 124, 196, 76, "sm-a")}{_arrow(122, 146, 196, 194, "sm-a")}
  <rect x="200" y="50" width="104" height="48" rx="8" fill="var(--surface)" stroke="var(--ink-2)"/>
  <text x="252" y="80" text-anchor="middle" font-size="14">J-lens J{_sub("l")}</text>
  <rect x="200" y="172" width="104" height="48" rx="8" fill="var(--surface)" stroke="var(--mu)"/>
  <text x="252" y="202" text-anchor="middle" font-size="14" style="fill:var(--mu)">J++</text>
  {_arrow(306, 74, 352, 74, "sm-a")}{_arrow(306, 196, 352, 196, "sm-a")}
  <text x="358" y="70" font-size="12" class="t-mono">top 10</text><text x="358" y="86" font-size="11" class="t-mut">tokens</text>
  <text x="358" y="192" font-size="12" class="t-mono">top 10</text><text x="358" y="208" font-size="11" class="t-mut">tokens</text>
  <path d="M386 96 C 410 120, 410 150, 386 174" fill="none" stroke="var(--delta)" stroke-width="1.8" stroke-dasharray="4 3"/>
  <text x="414" y="140" font-size="12" style="fill:var(--delta)">overlap</text>
  <text x="240" y="262" text-anchor="middle" font-size="11.5" class="t-mut">same state, same centre: only the map differs</text>
</svg>"""


def study_bridge() -> str:
    """A two-hop prompt: the bench scores the bridge; a family mean shares, and so removes, the bridge's category."""
    return f"""
<svg viewBox="0 0 480 290" role="img" aria-label="A two-hop question. Hop one reaches a bridge entity, hop two the answer. The family mean shares the bridge's category and removes it.">
  <defs>{_marker("sb-a", "ink-2")}</defs>
  <rect x="16" y="104" width="128" height="62" rx="8" fill="var(--sunk)"/>
  <text x="80" y="130" text-anchor="middle" font-size="12" class="t-mono">"the capital of</text>
  <text x="80" y="148" text-anchor="middle" font-size="12" class="t-mono">the country …"</text>
  {_arrow(146, 135, 192, 135, "sb-a")}
  <text x="169" y="126" text-anchor="middle" font-size="11" class="t-mut">hop 1</text>
  <rect x="196" y="104" width="112" height="62" rx="8" fill="var(--h-soft)" stroke="var(--h)"/>
  <text x="252" y="131" text-anchor="middle" font-size="13" font-weight="600" style="fill:var(--h)">bridge</text>
  <text x="252" y="150" text-anchor="middle" font-size="11.5" class="t-mut">e.g. a country</text>
  {_arrow(310, 135, 356, 135, "sb-a")}
  <text x="333" y="126" text-anchor="middle" font-size="11" class="t-mut">hop 2</text>
  <rect x="360" y="104" width="104" height="62" rx="8" fill="var(--surface)" stroke="var(--line-2)"/>
  <text x="412" y="131" text-anchor="middle" font-size="13" font-weight="600">answer</text>
  <text x="412" y="150" text-anchor="middle" font-size="11.5" class="t-mut">e.g. a city</text>
  <rect x="196" y="190" width="112" height="40" rx="8" fill="var(--mu-soft)" stroke="var(--mu)"/>
  <text x="252" y="215" text-anchor="middle" font-size="12" style="fill:var(--mu)">μ{_sub("fam")} ∋ "a country"</text>
  <path d="M252 188 L252 170" stroke="var(--mu)" stroke-width="2" stroke-dasharray="3 3"/>
  <text x="252" y="256" text-anchor="middle" font-size="12">every item in the family shares the bridge's category,</text>
  <text x="252" y="274" text-anchor="middle" font-size="12">so subtracting the family mean subtracts it too</text>
  <text x="240" y="40" text-anchor="middle" font-size="12" class="t-mut">multihop: the bench scores the bridge (both banks)</text>
</svg>"""


# ------------------------------------------------------------------ removing principal components (views/pca.py)


def pc_split() -> str:
    """One family's centred cloud, its top principal axis, and a read cell's x = h - mu split into the part along the
    axis (removed) and the part off it (kept, what pco reads)."""
    cx, cy, ux, uy = 230, 178, math.cos(math.radians(-14)), math.sin(math.radians(-14))
    nx, ny = -uy, ux  # the axis normal (pointing down-right in SVG coordinates is +; we use -n for "up")
    rnd = _rng(21)
    dots = []
    for _ in range(80):
        a, b = (rnd() - 0.5) * 2 * 175, (rnd() - 0.5) * 2 * 38
        dots.append(f'<circle cx="{cx + a * ux + b * nx:.1f}" cy="{cy + a * uy + b * ny:.1f}" r="2.6" fill="var(--line-2)"/>')
    t, o = 118, -78  # h's coordinates: along the axis, off it (negative = above)
    px, py = cx + t * ux, cy + t * uy
    hx, hy = px + o * nx, py + o * ny
    sq = 9  # right-angle mark
    a1x, a1y = px - sq * ux, py - sq * uy
    corner = f"M{a1x:.1f} {a1y:.1f} L{a1x + sq * -nx:.1f} {a1y + sq * -ny:.1f} L{px + sq * -nx:.1f} {py + sq * -ny:.1f}"
    return f"""
<svg viewBox="0 0 500 350" role="img" aria-label="A family's read cells form an elongated cloud around the family mean. A read cell's centred state x splits into a component along the cloud's main axis, which pco removes, and a component off it, which pco reads.">
  <defs>{_marker("pcs-x", "h")}{_marker("pcs-r", "mu")}{_marker("pcs-k", "delta")}{_marker("pcs-m", "muted")}</defs>
  <ellipse cx="{cx}" cy="{cy}" rx="190" ry="48" transform="rotate(-14 {cx} {cy})" fill="var(--sunk)"/>
  {''.join(dots)}
  {_arrow(cx - 205 * ux, cy - 205 * uy, cx + 215 * ux, cy + 215 * uy, "pcs-m", "muted", 1.2, "5 4")}
  <text x="{cx - 205 * ux - 6:.0f}" y="{cy - 205 * uy + 34:.0f}" font-size="11.5" class="t-mut">top principal direction v₁</text>
  <text x="20" y="34" font-size="11.5" class="t-mut">grey: this family's other items (fit split), centred</text>
  {_arrow(cx, cy, hx - 5 * ux, hy + 4, "pcs-x", "h", 1.8, "5 3")}
  {_arrow(cx, cy, px - 4 * ux, py - 4 * uy, "pcs-r", "mu", 2.6)}
  {_arrow(px, py, hx + 1, hy + 5, "pcs-k", "delta", 2.6)}
  <path d="{corner}" fill="none" stroke="var(--ink-2)" stroke-width="1"/>
  <circle cx="{cx}" cy="{cy}" r="5" fill="var(--ink-2)"/>
  <text x="{cx - 6}" y="{cy + 22}" font-size="14" class="t-m" text-anchor="end">μ{_sub("fam")}</text>
  <circle cx="{hx:.1f}" cy="{hy:.1f}" r="6" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>
  <text x="{hx + 10:.1f}" y="{hy - 4:.1f}" font-size="15" class="t-m" style="fill:var(--h)">h</text>
  <text x="{(cx + hx) / 2 - 16:.1f}" y="{(cy + hy) / 2 - 6:.1f}" font-size="14" class="t-m" text-anchor="end" style="fill:var(--h)">x = h − μ</text>
  <text x="{(cx + px) / 2 + 4:.1f}" y="{(cy + py) / 2 + 24:.1f}" font-size="13.5" class="t-m" style="fill:var(--mu)">V Vᵀ x</text>
  <text x="{px + 12:.1f}" y="{(py + hy) / 2 + 4:.1f}" font-size="13.5" class="t-m" style="fill:var(--delta)">(I − V Vᵀ) x</text>
  <g font-size="11.5">
    <line x1="20" y1="302" x2="44" y2="302" stroke="var(--mu)" stroke-width="2.6"/>
    <text x="50" y="306" style="fill:var(--mu)">along the top axes: how h differs the way items usually do. Removed.</text>
    <line x1="20" y1="324" x2="44" y2="324" stroke="var(--delta)" stroke-width="2.6"/>
    <text x="50" y="328" style="fill:var(--delta)">off those axes: what is unusual about this item. Read by the lens.</text>
  </g>
</svg>"""


#: The three things a family's top axis turned out to hold in S7 (studies/S7.md, diagnosis), one panel each.
PC_CASES = [
    {"title": "Form", "fam": "user_modeling · directed_modulation", "groups": ["The", "draft", "was"],
     "axis": "read token / prompt genre", "target": "off", "verdict": "good",
     "lines": ["Removing the axis takes out which", "token is being read: token matching", "without a token key. DM +0.19."]},
    {"title": "A rival answer", "fam": "multihop", "groups": ["cities", "months", "numbers"],
     "axis": "type of the final answer", "target": "off", "rival": True, "verdict": "good",
     "lines": ["The unscored answer's type (city,", "capital) sits on the axis; the bridge", "(Venezuela) is off it. Multihop +0.11."]},
    {"title": "The content itself", "fam": "multilingual_mt", "groups": ["Arabic", "Polish", "Indonesian"],
     "axis": "source language / concept", "target": "on", "verdict": "bad",
     "lines": ["The target concept and its language", "lie along the axis: removal deletes", "them. Judged −0.11: guardrail fails."]},
]


def pc_cases() -> str:
    """Three panels: what a family's top principal axis can hold, and what removing it does to the readout."""
    w, out = 320, []
    for i, case in enumerate(PC_CASES):
        x0 = i * w
        cx, cy = x0 + 160, 128
        rnd = _rng(31 + i)
        out.append(f'<rect x="{x0 + 8}" y="8" width="{w - 16}" height="334" rx="10" fill="var(--surface)" stroke="var(--line)"/>')
        out.append(f'<text x="{x0 + 24}" y="34" font-size="14" font-weight="600">{escape(case["title"])}</text>')
        out.append(f'<text x="{x0 + 24}" y="52" font-size="11" class="t-mut t-mono">{escape(case["fam"])}</text>')
        out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="128" ry="30" fill="var(--sunk)"/>')
        for g, gx in zip(case["groups"], (-82, 0, 82), strict=True):
            for _ in range(9):
                out.append(f'<circle cx="{cx + gx + (rnd() - 0.5) * 40:.1f}" cy="{cy + (rnd() - 0.5) * 34:.1f}" r="2.4" '
                           f'fill="var(--line-2)"/>')
            out.append(f'<text x="{cx + gx}" y="{cy + 34}" text-anchor="middle" font-size="10.5" class="t-mut">{escape(g)}</text>')
        out.append(_arrow(cx - 140, cy, cx + 142, cy, "pcc-m", "muted", 1.1, "5 4"))
        out.append(f'<text x="{cx}" y="{cy + 58}" text-anchor="middle" font-size="11" class="t-mut">'
                   f'PC1 (dashed) = {escape(case["axis"])}</text>')
        hx, hy = cx + 58, cy - 62
        if case["target"] == "on":  # the target's direction is the axis itself: removal takes it
            out.append(_arrow(cx, cy, hx - 2, cy, "pcc-r", "mu", 2.6))
            out.append(_arrow(hx, cy, hx, hy + 7, "pcc-k", "delta", 2.2))
            out.append(f'<path d="M{hx - 6} {cy - 13} l6 -6 l6 6 l-6 6 z" fill="var(--bad)"/>')
            out.append(f'<text x="{hx - 12}" y="{cy - 20}" text-anchor="end" font-size="11" style="fill:var(--bad)">target</text>')
        else:
            out.append(_arrow(cx, cy, hx - 2, cy, "pcc-r", "mu", 2.6))
            out.append(_arrow(hx, cy, hx, hy + 7, "pcc-k", "delta", 2.6))
            out.append(f'<text x="{hx + 8}" y="{(cy + hy) / 2 + 4}" font-size="11" style="fill:var(--delta)">'
                       f'{"bridge" if case.get("rival") else "concept"}</text>')
            if case.get("rival"):
                out.append(f'<text x="{(cx + hx) / 2}" y="{cy + 16}" text-anchor="middle" font-size="11" style="fill:var(--mu)">answer</text>')
        out.append(f'<circle cx="{hx}" cy="{hy}" r="5.5" fill="var(--h)" stroke="var(--surface)" stroke-width="2"/>')
        out.append(f'<text x="{hx + 9}" y="{hy - 3}" font-size="14" class="t-m" style="fill:var(--h)">h</text>')
        col = "var(--good)" if case["verdict"] == "good" else "var(--bad)"
        out.append(f'<text x="{x0 + 24}" y="{226}" font-size="12" font-weight="600" style="fill:{col}">'
                   f'{"Removal helps" if case["verdict"] == "good" else "Removal hurts"}</text>')
        for k, line in enumerate(case["lines"]):
            out.append(f'<text x="{x0 + 24}" y="{250 + k * 18}" font-size="12" class="t-2">{escape(line)}</text>')
        out.append(f'<line x1="{x0 + 24}" y1="316" x2="{x0 + 44}" y2="316" stroke="var(--mu)" stroke-width="2.6"/>'
                   f'<text x="{x0 + 50}" y="320" font-size="10.5" style="fill:var(--mu)">removed</text>'
                   f'<line x1="{x0 + 120}" y1="316" x2="{x0 + 140}" y2="316" stroke="var(--delta)" stroke-width="2.6"/>'
                   f'<text x="{x0 + 146}" y="320" font-size="10.5" style="fill:var(--delta)">kept</text>')
    return f"""
<svg viewBox="0 0 960 350" role="img" aria-label="Three panels. In each, a family's items spread along their top principal axis in three groups. Form: the axis is the read token, and the concept is off the axis, so removal helps. Rival: the axis is the final answer's type, the bridge is off it, so removal helps. Content: the target concept lies along the axis, so removal deletes it.">
  <defs>{_marker("pcc-r", "mu")}{_marker("pcc-k", "delta")}{_marker("pcc-m", "muted")}</defs>
  {''.join(out)}
</svg>"""


def pc_readout_split(full: list[tuple], removed: list[tuple], kept: list[tuple]) -> str:
    """The lens is linear, so the readout of x is the readout of the removed part plus that of the kept part. Each list
    is one real cell's top tokens as (text, colour token or None), the colour marking a target."""
    def toks(ts, x, y):
        out = []
        for k, (t, tok) in enumerate(ts[:6]):
            style = f' style="fill:var(--{tok});font-weight:600"' if tok else ' class="t-mono t-2"'
            out.append(f'<text x="{x}" y="{y + k * 17}" font-size="12" font-family="IBM Plex Mono, monospace"{style}>'
                       f'{escape(t.strip() or "␣")}</text>')
        return "".join(out)

    return f"""
<svg viewBox="0 0 760 250" role="img" aria-label="The centred state x is split into its removed part and its kept part. Each is read through the lens; the full readout is the sum of the two parts' readouts.">
  <defs>{_marker("prs-r", "mu")}{_marker("prs-k", "delta")}{_marker("prs-x", "h")}</defs>
  <rect x="14" y="94" width="96" height="44" rx="8" fill="var(--h-soft)"/>
  <text x="62" y="121" text-anchor="middle" font-size="15" class="t-m" style="fill:var(--h)">x = h − μ</text>
  {_arrow(110, 104, 196, 46, "prs-r", "mu", 2)}
  {_arrow(110, 128, 196, 188, "prs-k", "delta", 2)}
  <rect x="200" y="24" width="120" height="44" rx="8" fill="var(--mu-soft)"/>
  <text x="260" y="51" text-anchor="middle" font-size="14" class="t-m" style="fill:var(--mu)">V Vᵀ x</text>
  <rect x="200" y="166" width="120" height="44" rx="8" fill="var(--delta-soft)"/>
  <text x="260" y="193" text-anchor="middle" font-size="14" class="t-m" style="fill:var(--delta)">(I − V Vᵀ) x</text>
  {_arrow(322, 46, 392, 46, "prs-r", "mu", 1.6)}
  {_arrow(322, 188, 392, 188, "prs-k", "delta", 1.6)}
  <text x="357" y="38" text-anchor="middle" font-size="11" class="t-mut">W_U J</text>
  <text x="357" y="180" text-anchor="middle" font-size="11" class="t-mut">W_U J</text>
  <text x="400" y="14" font-size="11.5" font-weight="600" style="fill:var(--mu)">removed part reads</text>
  {toks(removed, 400, 32)}
  <text x="400" y="156" font-size="11.5" font-weight="600" style="fill:var(--delta)">kept part reads (pco16)</text>
  {toks(kept, 400, 174)}
  <text x="570" y="14" font-size="11.5" font-weight="600" style="fill:var(--h)">x reads (fam)</text>
  {toks(full, 570, 32)}
  <text x="570" y="156" font-size="11.5" class="t-mut">L(x) = L(V Vᵀ x) + L((I − V Vᵀ) x)</text>
  <text x="570" y="174" font-size="11.5" class="t-mut">for every vocabulary token: removing</text>
  <text x="570" y="192" font-size="11.5" class="t-mut">the PCs subtracts the removed part's</text>
  <text x="570" y="210" font-size="11.5" class="t-mut">scores from the family-mean readout.</text>
</svg>"""


def _fmt(s: str) -> str:
    """Escaped SVG text with TeX-style sub / superscripts as tspans: ``B_l``, ``T_{1..k}``, ``J^T``."""
    s = escape(s)
    sub = lambda m: f'<tspan baseline-shift="sub" font-size="72%">{m[1]}</tspan>'  # noqa: E731
    sup = lambda m: f'<tspan baseline-shift="super" font-size="72%">{m[1]}</tspan>'  # noqa: E731
    s = re.sub(r"_\{([^}]*)\}", sub, s)
    s = re.sub(r"_([A-Za-z0-9]+)", sub, s)
    s = re.sub(r"\^\{([^}]*)\}", sup, s)
    return re.sub(r"\^([A-Za-z0-9]+)", sup, s)


def study_template() -> str:
    """S14's geometry: the template reading directions span a small subspace B; g(h) = P_B h is h's shadow in it, and
    the read vector (I - P_B) h is the part of h at right angles to it, where every template token scores 0."""
    ox, oy = 200, 222
    plane = "60,252 330,252 410,192 140,192"
    hx, hy = 300, 64  # tip of h
    fx, fy = 300, 214  # foot of h on B (its shadow)
    return f"""
<svg viewBox="0 0 480 360" role="img" aria-label="h, its projection on the template subspace B (removed) and the part of h at right angles to B (read).">
  <defs>{_marker("tp-h", "h")}{_marker("tp-m", "mu")}{_marker("tp-d", "delta")}{_marker("tp-r", "muted")}{_marker("tp-c", "good")}</defs>
  <polygon points="{plane}" fill="var(--sunk)" stroke="var(--line-2)"/>
  <text x="70" y="272" font-size="11" class="t-mut">B: the span of the template tokens' reading directions</text>
  <text x="70" y="286" font-size="11" class="t-mut">(64 of h's 5120 dimensions at each layer)</text>
  {_arrow(ox, oy, 126, 240, "tp-r", "muted", 1.5)}
  <text x="120" y="230" font-size="11.5" text-anchor="end" class="t-mut t-mono">r(____)</text>
  {_arrow(ox, oy, 262, 200, "tp-r", "muted", 1.5)}
  <text x="236" y="196" font-size="11.5" class="t-mut">r(是什么意思)</text>
  {_arrow(ox, oy, hx - 2, hy + 6, "tp-h", "h", 2.4)}
  <text x="{hx + 8}" y="{hy + 4}" font-size="15" class="t-m" style="fill:var(--h)">h</text>
  {_arrow(ox, oy, fx - 6, fy + 1, "tp-m", "mu", 2.2)}
  <text x="{fx + 10}" y="{fy + 26}" font-size="13" class="t-m" style="fill:var(--mu)">g(h) = P{_sub("B")} h  (removed)</text>
  <line x1="{fx}" y1="{fy}" x2="{hx}" y2="{hy + 10}" stroke="var(--line-2)" stroke-dasharray="4 3"/>
  <path d="M{fx - 9} {fy} l0 -9 l9 0" fill="none" stroke="var(--line-2)"/>
  {_arrow(ox, oy, ox, hy + 4, "tp-d", "delta", 2.4)}
  <text x="{ox - 8}" y="{hy + 2}" font-size="13" text-anchor="end" class="t-m" style="fill:var(--delta)">h − g = (I − P{_sub("B")}) h</text>
  <text x="{ox - 8}" y="{hy + 18}" font-size="11" text-anchor="end" class="t-mut">what the lens reads</text>
  {_arrow(ox, oy, 104, 146, "tp-c", "good", 1.6)}
  <text x="98" y="142" font-size="11.5" text-anchor="end" style="fill:var(--good)">r(curiosity)</text>
  <circle cx="{ox}" cy="{oy}" r="3.5" fill="var(--ink-2)"/>
  <g font-size="11.5">
    <text x="20" y="314"><tspan class="t-mut">template token t:</tspan> r<tspan baseline-shift="sub" font-size="72%">t</tspan> lies in B, so r<tspan baseline-shift="sub" font-size="72%">t</tspan> · (I − P<tspan baseline-shift="sub" font-size="72%">B</tspan>) h = 0 exactly</text>
    <text x="20" y="334"><tspan class="t-mut">content token c:</tspan> r<tspan baseline-shift="sub" font-size="72%">c</tspan> nearly ⟂ B, so its score r<tspan baseline-shift="sub" font-size="72%">c</tspan> · h is (almost) kept</text>
  </g>
</svg>"""


def study_template_build() -> str:
    """S14's pipeline: token sources -> the ordered list T -> each token's reading direction at layer l -> an orthonormal
    basis B_l -> the centre."""
    boxes = [
        ("1 · Sources", ["chat template specials", "strings the decoded", "reference means share", "(≥ 3 families, L ≥ 36)",
                         "chat corpus top tokens", "a short hand list", "− every fit / val target"]),
        ("2 · Ordered list T", ["197 tokens, ordered so", "“the first k” is meaningful:", "specials, then shared", "strings by #families,", "then frequent tokens", "k = 64 chosen on fit"]),
        ("3 · Directions r_t", ["for each t in T_{1..k}", "at layer l (cos map):", "r_t = J_l^T W_U[t] / ‖·‖,", "the unit vector whose", "dot product with h", "is t's score"]),
        ("4 · Basis B_l", ["stack the 64 r_t,", "SVD → orthonormal", "B_l (5120 × 64);", "full rank at every", "layer; precomputed", "once (out/lens)"]),
        ("5 · Centre", ["g(h) = B_l B_l^T h", "read J_l (h − g):", "every t in T now", "scores exactly 0;", "no reference cell,", "no family label"]),
    ]
    w, gap, x0, y0, hgt = 132, 18, 12, 30, 176
    out = []
    for i, (title, lines) in enumerate(boxes):
        x = x0 + i * (w + gap)
        tok = "mu" if i == 4 else "line-2"
        out.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{hgt}" rx="10" fill="var(--surface)" stroke="var(--{tok})"/>')
        out.append(f'<text x="{x + 10}" y="{y0 + 22}" font-size="12.5" font-weight="600">{_fmt(title)}</text>')
        for j, ln in enumerate(lines):
            cls = ' style="fill:var(--bad)"' if ln.startswith("−") else ' class="t-2"'
            out.append(f'<text x="{x + 10}" y="{y0 + 46 + j * 19}" font-size="11.2"{cls}>{_fmt(ln)}</text>')
        if i < len(boxes) - 1:
            out.append(_arrow(x + w + 2, y0 + hgt / 2, x + w + gap - 2, y0 + hgt / 2, "tb-a", "muted", 1.6))
    return f"""
<svg viewBox="0 0 770 236" role="img" aria-label="How S14 builds its subspace: token sources, the ordered list T, reading directions, an orthonormal basis, the centre.">
  <defs>{_marker("tb-a", "muted")}</defs>
  <text x="12" y="18" font-size="11.5" class="t-mut">once, offline (tokenizer, decoded means, the lens's J and W{_sub("U")})  →  at read time: one 5120 × 64 matrix per layer</text>
  {''.join(out)}
</svg>"""


def study_template_scores() -> str:
    """What removing B does to one cell's scores: template tokens fall to 0, content tokens keep their score, and the
    top-10 cutoff moves down to the content (a sketch of the association example on the page)."""
    rows = [("______", 0.92, 0.0, "t"), ("是什么意思", 0.88, 0.0, "t"), ("这句话", 0.81, 0.0, "t"), ("？", 0.74, 0.0, "t"),
            ("…", 0.58, 0.21, "p"), (" curiosity", 0.55, 0.53, "c"), (" boredom", 0.52, 0.51, "c"), (" behavior", 0.49, 0.47, "c")]
    out = []
    for k, (name, x0) in enumerate((("plain lens: r_t · h", 120), ("after: r_t · (I − P_B) h", 350))):
        out.append(f'<text x="{x0}" y="26" font-size="12" font-weight="600">{_fmt(name)}</text>')
        out.append(f'<line x1="{x0}" y1="36" x2="{x0}" y2="250" stroke="var(--line-2)"/>')
        cut = 0.60 if k == 0 else 0.50
        cx = x0 + cut * 120
        out.append(f'<line x1="{cx:.0f}" y1="36" x2="{cx:.0f}" y2="250" stroke="var(--delta)" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{cx + 4:.0f}" y="262" font-size="10.5" style="fill:var(--delta)">top-10 cutoff</text>')
        for j, (tok, before, after, kind) in enumerate(rows):
            v = before if k == 0 else after
            y = 48 + j * 25
            col = {"t": "var(--muted)", "p": "var(--mu)", "c": "var(--good)"}[kind]
            if k == 0:
                out.append(f'<text x="{x0 - 8}" y="{y + 11}" font-size="11.5" text-anchor="end" class="t-mono">{escape(tok)}</text>')
            if v > 0:
                out.append(f'<rect x="{x0}" y="{y}" width="{v * 120:.0f}" height="15" rx="2" fill="{col}" opacity="0.85"/>')
            else:
                out.append(f'<circle cx="{x0}" cy="{y + 7.5}" r="3.5" fill="{col}"/><text x="{x0 + 8}" y="{y + 11}" font-size="10.5" class="t-mut">0</text>')
    return f"""
<svg viewBox="0 0 520 300" role="img" aria-label="Scores before and after removing B: template tokens fall to zero, content tokens keep their scores and enter the top 10.">
  {''.join(out)}
  <g font-size="11">
    <rect x="20" y="276" width="10" height="10" fill="var(--muted)"/><text x="34" y="285">template token (in T): set to 0</text>
    <rect x="200" y="276" width="10" height="10" fill="var(--mu)"/><text x="214" y="285">partly template-like: lowered</text>
    <rect x="400" y="276" width="10" height="10" fill="var(--good)"/><text x="414" y="285">content: kept</text>
  </g>
</svg>"""


def study_template_schedule() -> str:
    """S14's label-free finalists as depth schedules: a cluster mean up to L40, the template projection (of h minus a
    partial neighbour mean) above it."""
    x0, x1, split = 150, 800, 40
    X = lambda L: x0 + (L - 20) / 40 * (x1 - x0)  # noqa: E731
    rows = [("S14k", "(I − P_B) h", "α = 0: template removal alone"),
            ("S14b", "(I − P_B)(h − ½ μ_{clu}(h))", "half the cluster mean comes off first (α = ½, chosen on fit)"),
            ("S14b-x", "(I − P_B)(h − ½ m_8(h))", "m_8: mean of h's 8 nearest fit cells from other carrier sentences"),
            ("S14bL", "(I − P_B)(h − ½ m_8(h))", "as S14b-x, and none in h's own non-English prompt language")]
    step, hb = 58, 44
    out = [f'<line x1="{x0}" y1="44" x2="{x1}" y2="44" stroke="var(--line-2)"/>']
    for L in range(20, 61, 4):
        out.append(f'<text x="{X(L):.0f}" y="36" font-size="10.5" text-anchor="middle" class="t-mut">L{L}</text>')
    out.append(f'<line x1="{X(split):.0f}" y1="40" x2="{X(split):.0f}" y2="{56 + step * len(rows)}" stroke="var(--delta)" stroke-dasharray="4 3"/>')
    out.append(f'<text x="{X(split) + 6:.0f}" y="{70 + step * len(rows)}" font-size="10.5" style="fill:var(--delta)">switch at L40 '
               f'(chosen on fit; centring acts at L ≥ 40, S17)</text>')
    for i, (name, late, note) in enumerate(rows):
        y = 56 + i * step
        out.append(f'<text x="{x0 - 12}" y="{y + 26}" font-size="13" font-weight="600" text-anchor="end">{escape(name)}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{X(split) - x0 - 3:.0f}" height="{hb}" rx="6" fill="var(--sunk)" stroke="var(--line-2)"/>')
        out.append(f'<text x="{(x0 + X(split)) / 2:.0f}" y="{y + 27}" font-size="12.5" text-anchor="middle" class="t-m">{_fmt("h − μ_{clu}(h)")}</text>')
        out.append(f'<rect x="{X(split) + 3:.0f}" y="{y}" width="{x1 - X(split) - 3:.0f}" height="{hb}" rx="6" fill="var(--surface)" stroke="var(--mu)"/>')
        out.append(f'<text x="{X(split) + 14:.0f}" y="{y + 19}" font-size="12.5" class="t-m" style="fill:var(--mu)">{_fmt(late)}</text>')
        out.append(f'<text x="{X(split) + 14:.0f}" y="{y + 36}" font-size="10.5" class="t-mut">{_fmt(note)}</text>')
    return f"""
<svg viewBox="0 0 820 {96 + step * len(rows)}" role="img" aria-label="Depth schedules: a cluster mean up to L40, the template projection of h minus a partial neighbour mean above.">
  <text x="{x0}" y="16" font-size="11.5" class="t-mut">{_fmt("read vector h − g(h) at each layer · μ_{clu}: h's k-means cluster mean (64 clusters of every family's fit cells, no labels)")}</text>
  {''.join(out)}
</svg>"""


def study(kind: str, **params) -> str | None:
    """The diagram a study card names (CARDS.md); None for an unknown kind."""
    fn = {"pool": study_pool, "subspace": study_subspace, "layer": study_layer, "word": study_word, "probe": study_probe,
          "maps": study_maps, "bridge": study_bridge, "template": study_template, "template_build": study_template_build,
          "template_scores": study_template_scores, "template_schedule": study_template_schedule}.get(kind)
    if fn is None:
        return None
    import inspect

    ok = inspect.signature(fn).parameters
    return fn(**{k: v for k, v in params.items() if k in ok})
