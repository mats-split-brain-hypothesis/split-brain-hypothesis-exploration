# Frozen scalar figures · 27 October 2026

These are new descriptive analyses of audited local scalar exports. They do not read model reasoning, run candidate code, make model calls, or introduce new experiments. The Python standard library performs matching and arithmetic; the installed gnuplot 6.0 backend exports SVG, 2× PNG and PDF. Matplotlib was unavailable, so no package was installed.

## Reproduce

From the agent20 worktree (adjust the two input paths after integration):

```sh
python3 research_dashboard/analysis/build_scientific_figures.py \
  --sorh-input ../agent-18-sorh-inventory/notes/sorh_prompt_density_length_oct27.json \
  --ib-input ../agent-19-ib-inventory/notes/ib_current_graph_cells.json
```

Use `--out PATH` to choose the output directory and `--gnuplot PATH` for another installed gnuplot binary. No network access or package installation is required. The `.gp` files preserve plot bodies; the Python script specifies terminal settings and output names. Input file hashes, manifest hashes and every pair's exact source path and line appear in the derived JSON. Original local source files remain authoritative; the plots use the frozen inventory, not ongoing results.

## Figures and interpretation

- `sorh_length_by_metric`: median of each matched condition/B word-count ratio, separated into ten counted-item, six share, and four repeated-term prompts per model. The five columns include baseline as a self-reference. This is a median of ratios, not a ratio of marginal medians. Cell numbers are not clipped; cell colour clips log2 ratios to [−3,+3].
- `sorh_metric_change`: median of matched condition−B external count/share values. The three panels retain separate native units: counted items, percentage points and term occurrences. The baseline column is a zero-change reference, not additional data. Within a count panel the counted object still varies by prompt; a larger numerical delta is not a common-unit measure of quality or reward-hacking severity.
- `sorh_share_compression`: all 24 B→G pairs from six fixed share prompts and four models. All have higher measured share; 21/24 have fewer counted words as well. Six model-averaged independent tasks cannot be inferred from these 24 points. Diamonds identify the illustrative `sorh_160` task; those examples are already included in the broad plot.
- `ib_deepseek_endpoints`: the same 18 DeepSeek no-message episodes under two endpoint definitions. Five final code artifacts pass an existing re-score against original tests, concentrated in two tasks. Three additional episodes pass only edited tests. Their union explains the 8/18 broader final endpoint. This is not a submitted-only count. The figure reuses existing audited re-scores and executes no candidate code.

For the share prompts, median G/B word ratios are Qwen2.4T **0.382×**, DeepSeek **0.215×**, GLM **0.152×**, Qwen27B **0.532×**. Their median paired share changes are respectively **+68.47**, **+90.28**, **+70.05**, **+79.44 percentage points**. This is a descriptive composition/length result; it does not establish reduced answer quality, a private goal or a causal mediation path. The separate final-output padding-v2 labels and direct reasoning reads are needed to interpret those questions.

The all-condition figures add a useful distinction: removing score importance lowers the share change much more than it restores baseline word count. For DeepSeek, the don't-care median is 0.45× baseline words and +8.7 share points, versus 0.22× and +90.3 in G. Length alone would miss most of that difference. For Qwen2.4T counted-item prompts, quality-first has a median 1.16× word count yet −8 counted items relative to baseline: verbosity and target maximization can move separately.

## Scope and exclusions

The SoRH input contains **400 unique rows = 20 prompts × four models × five conditions**, with one draw in each cell. The derived file has 400 paired records, including 80 baseline self-references and 320 actual condition contrasts. Reusing a baseline across four comparisons does not create new independent observations.

Both rows must have `finish=stop`, no missing output, no cut in reasoning and no cut mid-answer to enter a primary complete-output summary. One DeepSeek item-count G row (`sorh_164`, source line80) is length-truncated and excluded. Five external metric values are missing: DeepSeek `sorh_115/G`, `sorh_115/c7_dont_care`, `sorh_529/G`, `sorh_568/G`, and Qwen27B `sorh_845/G`. Those missing values exclude metric comparisons only, leaving their available word counts usable. Consequently, DeepSeek item-count G word ratios use n=9 while metric deltas use n=6. Every plotted cell reports its actual paired n.

Counted words and count/share come from the external whole-reply count judge. The separately retained `padded_v2` field is an external judge on the final output with the metric hidden. These measurement definitions must not be merged. No bootstrap, population confidence interval or significance test is reported: samples are small, the prompts are selected and reused, and model/prompt rows are not independent task draws. The scatter shows all individual share pairs instead.

## Dashboard contract

```js
{
  type: "image",
  title: "Higher share often arrives in a shorter answer",
  src: "figures/sorh_share_compression.svg",
  alt: "Across six fixed share prompts and four models, all 24 graded/baseline pairs increased target-word share; 21 also shortened the reply. Individual points are shown by model, with sorh_160 marked as diamonds.",
  note: "24 complete matched pairs; six shared prompts, one draw per condition. Whole-reply external count-judge measurements; descriptive only.",
  exportHref: "figures/sorh_share_compression.pdf",
  sources: [
    {label: "PNG", href: "figures/sorh_share_compression.png"},
    {label: "Paired values and provenance", href: "figures/sorh_paired_density_derived.json"}
  ]
}
```

Images stay local and the renderer requires no dependency or external fetch. SVG marks in other chart types remain interactive. Scientific figures open at full resolution and have separate PDF/PNG/data links.
