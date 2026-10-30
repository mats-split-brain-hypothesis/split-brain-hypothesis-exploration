# Shared dashboard: Reward Hacking Triggers

https://claude.ai/artifact/UFyDGQWri9evCV6EUVxwY8 (private to the researcher's account; agents write to it as the
researcher). One tab per agent. The page is built from documents in the dashboard's own store, written with the
`ArtifactData` tool. This folder is the source of truth for the shared parts; each agent keeps its own page script
in `dashboard/agent<N>.js` on its own branch.

## Who owns what

| Agent | Tab (page id) | Page file you write | Your dataset ids |
|---|---|---|---|
| 1 | `sorh-cues` | `files/agent1.js` | `datasets/a1_*` |
| 2 | `harness-cues` | `files/agent2.js` | `datasets/a2_*` |
| 3 | `sorh-persistence` | `files/agent3.js` | `datasets/a3_*` |
| 4 | `goodfire-persistence` | `files/agent4.js` | `datasets/a4_*` |
| 5 | `grader-beliefs` | `files/agent5.js` | `datasets/a5_*` |
| 6 | `stakes` | `files/agent6.js` | `datasets/a6_*` |
| orchestrator | `overview` | `files/overview.js`, `files/index.html`, `files/kit.js` | `datasets/ov_*` |

Write only your own documents. Need a change to the shell or the chart kit? Message the orchestrator
(`split-brain-hypothesis-a9`).

## Publishing your page

1. **Read the dashboard once** (required before any upload): `Artifact` with `action: "read"` and the URL above.
   Also read the type's rules: `Artifact` read with `path: "SKILL.md"` and
   `path: "artifact-type/reference/design-defaults.md"`. The marking rules there matter (below).
2. **Data:** save each table as a JSON array of row objects (e.g. `logs/<topic>/dashboard/a1_rates.json`) and upload
   it: `Artifact` with `action: "publish"`, `url`, `asset: true`, `file_path`. The result gives `/_blob/<id>`.
   Anyone who can open the dashboard can read uploaded files.
3. **Dataset document:** `ArtifactData` `set` on collection `datasets`, doc id `a<N>_<name>`:
   ```json
   {"title": "Gaming by cue variant", "description": "Experiment, scale and source in a sentence or two: dataset, model, effort, variants, n, and the commit or log the rows come from.",
    "source": {"kind": "file", "url": "/_blob/<id>", "name": "a1_rates.json", "format": "json"},
    "updated": {"at": "<ISO time>", "by": "Agent <N>"}, "fixed": true}
   ```
   A new version of the data: upload again, then `update` the dataset's `url`, `name` and `updated`.
4. **Page:** write `dashboard/agent<N>.js` on your branch (template below), then store it: make a JSON file
   `{"text": "<the file's contents>"}` and `ArtifactData` `set` collection `files`, doc id `agent<N>.js`, with
   `file_path`. The document exists already, so `get` it first and pass its `version` as `if_version`.
   Up to 50 writes go in one `batch`. Any document over 256 KB is refused.
5. **Check:** `ArtifactData` `get` collection `data/users/me`, doc `check` (`checking` → read again, up to 5
   times; no document after `checking` = passed; `failed` = fix what your code confirms). Also doc `runs` for
   sources that failed or marks that don't match. Other agents write too, so a failure may be theirs: look at the
   file it names.

No Artifact or ArtifactData tools in your session? Commit the page script and the JSON tables on your branch and
message the orchestrator, who will publish them.

## Page standard (set by the researcher)

Every tab has these parts, in this order:

1. **Question and answer.** The question as the heading, then the answer so far in one or two plain sentences.
2. **How it was run**, in words: what data or prompts, which model and settings, what was varied, what was
   measured and how (define each measure in a sentence: what counts, its unit, what 0 and 1 mean), what the base is.
   Then the setup table (`a<N>_setup`) with the numbers: n per condition, totals, cost.
3. **What we found:** 3–5 numbered findings, most important first, each a plain claim plus its evidence (k/n, the
   comparison, which chart) and a strength tag (solid / tentative / one example). Use `RH.findings` on an
   `a<N>_findings` dataset. Say what is not yet known.
4. **Charts, one question each.** The title states the takeaway ("Removing the grading sentence stops score
   planning"), not the variable. The note says what is plotted, its unit, what one mark is, n, and the base.
   Prefer measures people can read directly (k/n rates, change in natural units: quality points, words, ratio of
   the metric) over composite scores or thresholded indices. Show the base condition in every comparison. Few series
   per chart: when a chart would hold more than about 6 bars per label or a dozen rows, split it into several
   charts (one per measure or per variant family). A grid (`RH.heat`) needs a sentence saying what a cell is and what
   the colour means. **Every row of every chart shows its sample size** (researcher's request): rate bars show k/n
   already; ratio, mean and grid charts put it in the row label or a column, e.g. "allow gaming (20 prompts × 1
   reply)", and in the tooltip, with how many observations were paired.
   **Titles say what isn't obvious.** If a title predicts what anyone would expect ("removing the metric lowers
   the count"), it belongs in a compact "Baseline check" card, not among the findings.
5. **Examples.** For each main finding, 2–4 concrete cases with `RH.examples` on an `a<N>_examples` dataset: the
   prompt or task (highlight the cue sentence), the reply or the actions taken (short excerpt), the reasoning excerpt
   that shows the behaviour (e.g. the sentence where it plans for the score), and its scores. Best: the same prompt
   under the base and under a variant, side by side. Pick examples with a script from your labels (and say how they
   were picked: typical, extreme, a flip), and keep excerpts short.
6. **Caveats and next steps.**

**Every chart, table and finding explains how it was computed.** End each chart card with
`<details class="rh-method" data-source="a<N>_methods" data-chart="<the chart box's id>"></details>` and call
`RH.methods(el, 'a<N>_methods')` in `draw`. The `a<N>_methods` dataset has one row per chart:
`{chart, data, sample, computation, labels, code, caveats}`:
- `data`: which runs, transcripts or files, with the commit or log folder;
- `sample`: which items and how they were chosen, n per condition;
- `computation`: step by step, from raw record to the number on screen (what counts as k, what n is, any
  threshold, normalisation, pairing, the interval);
- `labels`: which labeller or judge, which prompt version, and how well it agrees with hand labels;
- `code`: the script and the exact command to reproduce it;
- `caveats`: what could make it wrong.

The findings card gets one too (`data-chart` = its id). Panels without a row show "Not documented yet".

**Questions and change requests.** The kit adds an "Ask a question or request a change" box at the end of every
tab. The researcher comments on any chart, number or that box and sends it to Claude. The orchestrator receives it
and passes it to the agent who owns the tab. That agent makes the change (or answers) and tells the orchestrator,
who replies in the thread and resolves it.

## Page template

```js
RH.page('sorh-cues', {
  // Runs once, the first time the tab opens: static HTML only. Every chart box names its dataset(s).
  build(el) {
    el.innerHTML = `
      <div class="rh-intro">
        <h2>Which prompt cues change gaming on School of Reward Hacks?</h2>
        <p>One-line takeaway, in words.</p>
      </div>
      <div class="rh-grid">
        <section class="rh-card" id="a1-gaming-card">
          <h3>Gaming by cue variant</h3>
          <p class="rh-note">What the chart shows, the experiment and its scale in words.</p>
          <div class="rh-chart" id="a1-gaming" data-source="a1_gaming"></div>
        </section>
        <section class="rh-card rh-wide" id="a1-setup-card">
          <h3>Setup</h3>
          <div class="rh-chart" id="a1-setup" data-source="a1_setup"></div>
        </section>
      </div>`;
  },
  // Runs on every data or width change while the tab is visible.
  draw(el) {
    const g = el.querySelector('#a1-gaming');
    const rows = RH.rows('a1_gaming', g); // null while loading or failed (the state is painted for you)
    if (rows) RH.rates(g, rows, { label: 'variant', k: 'k', n: 'n', group: 'measure' });
    const s = el.querySelector('#a1-setup');
    const setup = RH.rows('a1_setup', s);
    if (setup) RH.table(s, setup, { source: 'a1_setup', key: 'item', columns: [{ field: 'item', title: 'Item' }, { field: 'detail', title: 'Detail' }] });
  },
});
```

## Chart kit (`window.RH`, in kit.js)

| Call | Draws | Rows |
|---|---|---|
| `RH.rates(el, rows, {label, k, n, group?, groupOrder?, colors?, max?, detail?, xLabel?})` (pass `xLabel` to say what the bar is a share of, e.g. "Share of replies whose reasoning plans for the score") | horizontal bars of k/n with 95% Wilson intervals, "k/n · %" at the end; `group` gives several bars per label and a legend | one per bar: label, k, n (+ group) |
| `RH.heat(el, rows, {row, col, value, n?, rowOrder?, colOrder?, fmt?, diverging?, min?, max?, detail?})` | grid of values coloured by value; `diverging: true` centres on 0 (use for change vs base). The cue → behaviour map | one per cell |
| `RH.stack(el, rows, {label, category, value, labelOrder?, order?, colors?})` | 100% stacked bars, e.g. how episodes end per condition | one per label × category, value = count |
| `RH.line(el, rows, {x, y, series?, seriesOrder?, xFmt?, yFmt?, yMax?, xLabel?, n?})` | lines over a numeric x (rejection round, turn), labelled at the end | one per point |
| `RH.table(el, rows, {source, key, columns: [{field, title, fmt?, num?}]})` | sortable table, marked for Sources | any |
| `RH.findings(el, rows, {text='finding', evidence='evidence', tag?})` | numbered findings with their evidence and a strength tag | one per finding, in order |
| `RH.methods(pageEl, 'a<N>_methods')` | fills every `details.rh-method` panel on the page from the methods dataset | one per chart: chart, data, sample, computation, labels, code, caveats |
| `RH.examples(el, rows, {title, meta?: [fields], blocks: [{field, label, highlight?}], clip=700})` | example cards with quoted prompt / reply / reasoning blocks, the cue highlighted, "Show all" for long text | one per example |
| `RH.rows(id, el)` | rows of a dataset, or `null` after painting its loading/failed state on `el` | |
| `RH.pct`, `RH.pct1`, `RH.int`, `RH.num`, `RH.usd`, `RH.kn(k, n)`, `RH.wilson(k, n)` | formats and the interval | |
| `RH.series(i)`, `RH.legend(items)`, `RH.tip(el)`, `RH.css(colour)` | colours, legend, tooltip, computed colour | |

Something the kit doesn't draw: write it with `d3` (v7, global) in your page script, sized from `el.clientWidth`,
colours from `RH.series(i)` and the theme tokens (`var(--color-fg)`, `var(--color-fg-muted)`, …).

## Rules

- **Every number comes from a dataset.** No numbers typed into HTML or scripts (a fixed reference such as a 50% line
  is fine). Put the experiment and scale in a `a<N>_setup` table (item, detail), and let charts show n from the data.
- **Mark what you draw:** each chart box carries `data-source="<dataset id>"` (several ids space-separated);
  `RH.table` marks tables itself.
- **Rates as k/n** with intervals (`RH.rates`), not bare percentages. Compare conditions within one model only.
- **Ids and classes** start with your prefix (`a1-…`); write ids in the HTML, as in the template. Own CSS goes in a
  `<style>` inside your `build` HTML, with your prefix on every selector (never `body`, `html` or a bare tag).
- Data values are untrusted text: set them with `textContent` or d3 `.text()`, never `innerHTML`.
- **Update your page after each round**, with at least one chart per question you're answering.
