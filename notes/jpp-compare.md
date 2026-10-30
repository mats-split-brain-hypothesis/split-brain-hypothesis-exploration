# J++ lens on our families (2026-10-10)

The J++ lens (Ayonrinde & Lindsey 2026; `koayon/jpp-lenses` @ `6c96867`, `qwen3.6-27b/lens.pt`) is a different
map `J_l`, not a centre. We read it through the same pipeline as the J-lens so it can sit in comparisons. It is
never a centre's lens (notes/iteration-anthony/research-loop.md).

**How.** An arm prefix: `jpp:zero|cos` reads `J++_l h`, `jpp:fam@fit|cos` reads `J++_l (h - mu)` with the same
centre as `fam@fit|cos`. Directories are `jpp~zero__cos` etc. (`:` is not allowed in Windows paths). `jlm.lens.LENSES`
holds the maps; the J++ `Lens` shares W_U, the norm and the tokenizer with the J-lens one. Any centre works with
the prefix. On the dashboard J++ arms are opt-in: a "Compare with J++" toggle on Results, and unselected pills
on Passage → readouts and Centres in detail.

**Run.** 6 arms (`jpp:{zero,fam@fit,tok@fit}|{cos,rms}`) on all 11 families x fit / val / bench, one A100 pod,
16 min, $0.66. Free scores only (strict, or the piece proxy on `*_mt`); nothing judged yet.

## Results: strict pass@10 (ours, not WorkspaceBench scores), cos readout

| family | split | n | J-lens | J-lens fam@fit | J++ | J++ fam@fit | J++ tok@fit |
|---|---|---|---|---|---|---|---|
| typo | val | 91 | 0.69 | 0.92 | 0.96 | 0.98 | 0.98 |
| | bench | 100 | 0.54 | 0.76 | **0.94** | 0.92 | 0.92 |
| association | val | 102 | 0.41 | 0.75 | 0.53 | 0.80 | 0.80 |
| | bench | 98 | 0.38 | 0.55 | 0.48 | **0.64** | **0.64** |
| basic_readout | val | 35 | 0.91 | 0.91 | 0.97 | 0.89 | 0.97 |
| | bench | 68 | 0.93 | **0.99** | 0.97 | 0.91 | **0.99** |
| multihop | val | 83 | 0.63 | 0.61 | 0.61 | 0.65 | 0.67 |
| | bench | 94 | 0.80 | 0.77 | 0.86 | **0.89** | 0.87 |
| multilingual | val | 82 | 0.98 | 0.95 | 0.96 | 0.95 | 0.95 |
| | bench | 100 | 0.94 | 0.92 | **0.99** | 0.94 | 0.93 |
| user_modeling * | val | 61 | 0.72 | 0.72 | 0.75 | 0.84 | 0.87 |
| | bench | 50 | 0.42 | 0.44 | 0.46 | 0.52 | 0.54 |
| directed_modulation * | val | 74 | 0.07 | 0.05 | 0.09 | 0.11 | 0.31 |
| | bench | 100 | 0.07 | 0.07 | 0.05 | 0.08 | 0.12 |
| typo_mt (proxy) | bench | 82 | 0.16 | 0.23 | 0.22 | 0.30 | 0.30 |
| multihop_mt (proxy) | bench | 100 | 0.13 | 0.11 | 0.16 | 0.09 | 0.08 |
| basic_readout_mt (proxy) | bench | 100 | 0.40 | 0.51 | 0.46 | 0.47 | 0.46 |
| multilingual_mt (proxy) | bench | 100 | 0.14 | 0.16 | 0.12 | 0.14 | 0.07 |

\* strict does not track the judge here (notes/eval-pipeline.md): not a valid comparison until judged.
Full tables, rms included: `out/eval/report-{val,bench}.md`. On rms the J-lens is weak and J++ is not
(typo bench 0.32 vs 0.90).

## What it says

- Plain J++ is the best arm we have on typo (bench 0.94 against 0.76 for the best J-lens centre) and is at or above
  the plain J-lens on every single-token family except multihop val.
- Centring J++ is mixed: the family mean helps on association (+0.16 bench) and multihop, and hurts on
  basic_readout and multilingual. umot found centring hurt J++ on the J++ paper's own evals, so no general rule.
- Centring the J-lens closes part of the gap to J++ (association: J-lens fam@fit 0.55 vs plain J++ 0.48), as
  umot's `jpp_compare.py` found (about 45 % of the gap on the paper's tasks).
- Echo is low for every J++ arm (0.01-0.18) and masked pass is within 0.03 of strict outside DM, so the J++ gains
  are not prompt read-back. (The J-lens arms in these summaries predate the echo and mask columns; re-read them
  to compare.) On DM masked pass collapses for every arm, as expected: the instruction names the concept.

## Open

- Where the two maps differ, through our tools (battery, centres, the difference map, clusters): card U4 in
  `notes/iteration-anthony/mu-log.md`.
- Judge J++ on user_modeling, directed_modulation and the `*_mt` families (Haiku, val, 4 layers): about $2.90 for
  `jpp:zero|cos`, double with `jpp:tok@fit|cos`. Deferred by the user (2026-10-10).
- J++ was fitted on the J++ paper's typo / multihop / multilingual / association items. Check overlap with our
  dev and bench concepts before reading the typo gap as a pure lens effect.
- `tok@fit` was never run for the J-lens on the five single-token families, so that comparison has no J-lens column.
