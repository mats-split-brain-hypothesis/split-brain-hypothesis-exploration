# Study cards (`<id>.card.yaml`)

The dashboard's Studies page lays each study out from a short card next to its notes: `S4.md` + `S4.card.yaml`.
The notes stay the full record; the card is what a reader sees first. A study without a card still shows (its notes
and its battery), just without the structured header, formula, diagram and result charts. Update the card when the
study's verdict changes; keep every number traceable to the notes.

```yaml
id: S4                          # = the notes file's stem
title: Cluster and nearest-neighbour means          # <= 8 words, no id
owner: A (j-lens-mean-c0), pilot-1
# notes: S6.md                 # optional: the notes file, when not <id>.md (a study written up inside another's)
status: finalist                # finalist | negative | diagnostic | closed | open
question: >                     # 1-2 sentences; inline maths as $...$
  Does a regime-conditioned mean beat one family mean, and can a label-free cluster replace the family label?
verdict: >                      # 2-4 sentences: the answer, with its main cost or caveat
  ...
tiles:                          # 2-4 headline numbers, verbatim from the notes
  - {label: "val strict, Δ vs fam", value: "+0.049", sub: "+0.020 without UM / DM"}
formulas:                       # how g is built: 1-3 display equations (KaTeX), each with a one-line note
  - latex: 'g(h) = \frac{1}{k}\sum_{r \in N_k(h)} r'
    note: "N_k(h): the k nearest fit read cells of any family (cosine), own group excluded."
diagram:                        # one of the kinds below
  kind: pool
  select: knn
  caption: "..."
split: val                      # the split the result charts read (val if the study has val arms, else fit)
arms: ["knnx8@fit|cos", "kmx64@fit|cos"]                 # main arms, exact out/eval names on that split
controls: ["shuf.knnx8@fit|cos", "rand.knnx8@fit|cos"]   # their controls on that split ([] if none)
insights:                       # 2-6, most important first
  - {lead: "Clusters recover the family label without being told", text: "..."}
next: ["S4d: a cross-language kNN ..."]                  # open follow-ups ([] if none)
explainer:                      # optional: an "In depth" section after Method, one block per step (S14 has one)
  - heading: "What the lens reads: one direction per token"
    text: >                     # markdown, inline maths as $...$ (use `|` when the text holds a list)
      ...
    equations: [{latex: 's_t(h) = r_t^{\top} h', note: "..."}]   # optional display equations under the text
    after: >                    # optional text under the equations
      ...
    figure: {kind: template_build, caption: "..."}               # optional diagram (kinds below)
    panel: s14_norms            # optional live panel (dashboard/explainers.py PANELS), reads out/analysis JSON only
    wide: true                  # text, then the figure / panel full width (default: side by side)
```

Notation (formulas and inline maths): $h$ = $h_l$, the read cell's residual at layer $l$; $g(h)$ the centre, read
as $J_l(h - g(h))$; $\mathcal{R}$ the reference cells; $\bar h_S = \frac{1}{|S|}\sum_{r\in S} r$; $N_k(h)$ the $k$
nearest reference cells; $\mu_{\text{fam}}$ the family mean; $P_k$ a projection onto $k$ directions. Write LaTeX
that KaTeX renders (no `\newcommand`, no `align`; use `\begin{aligned}` if needed).

Diagram kinds (dashboard/figures.py, `study_*`):

| kind | params | draws |
|---|---|---|
| `pool` | `select`: family, cluster, knn, token, position, language, other_language, neutral, all; `exclude` (optional): own_sentence, own_group | a cloud of reference cells, the subset g averages highlighted, its mean, and h - g |
| `subspace` | `k` | a family cloud with its top principal axes; g = family mean + h's component along them |
| `layer` | `lag`, `axis` (layer or position) | g taken from the cell's own state `lag` layers earlier (axis layer), or `lag` token positions earlier at the same layer (axis position) |
| `word` | `word` | the state of a category word (e.g. "language") subtracted from h |
| `probe` | `left`, `right` (short labels), `left_text`, `right_text` (the prompts) | two prompts side by side (a control: e.g. self-described vs quoted) |
| `maps` | – | the J-lens and J++ maps read from one state (map comparison) |
| `bridge` | – | a two-hop chain: prompt -> bridge -> answer, and which step a centre removes |
| `template` | – | h, its shadow P_B h in a subspace of token reading directions (removed), and the read vector at right angles (S14) |
| `template_build` | – | S14's pipeline: token sources -> ordered list T -> reading directions -> orthonormal basis -> centre (wide) |
| `template_scores` | – | one cell's scores before / after removing B: template tokens to 0, content kept, the top-10 cutoff moves |
| `template_schedule` | – | S14k / S14b / S14b-x / S14bL as depth schedules: a cluster mean to L40, a partial mean + projection above (wide) |

Panels for `explainer` blocks (dashboard/explainers.py): `s14_examples` (val cells where the plain lens reads the template
and s14t64 the target; zero / fam / s14t64 top 10), `s14_tokens` (T's first 64 by source), `s14_norms` (share of h and
of the family mean in B by layer). They read `out/analysis/S14-explainer/explainer.json` (`experiments/s14_explainer.py`).
