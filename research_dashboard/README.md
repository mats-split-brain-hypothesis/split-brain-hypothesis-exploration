# Local research dashboard

Buildless HTML/CSS/JavaScript. No packages, CDN, analytics, remote fetches, or publication. Open `dist/index.html` locally, or serve the owning repository with a loopback static server so local source links resolve.

The site loads a root-owned `window.RESEARCH_DATA` object from `dist/data.js`. The checked-in empty data file intentionally contains no invented findings or measurements. Copy `index.html`, `styles.css`, and `app.js` into the integration worktree; preserve its populated `data.js`.

## Data contract

All fields are optional unless needed for a particular item. Text is escaped; limited inline `**bold**` and backtick code are supported in prose. IDs must be unique within findings/cases. Models use `qwen24`, `deepseek`, `glm52`, `qwen27`; subclaims use strings `1a`, `1b`, `2`, `3`, `4`.

```js
window.RESEARCH_DATA = {
  meta: { title, updated, scope, summary, cost, coverageNote },
  models: [{ id, label, color, provider }],
  subclaims: [{ id, title, description }],
  overview: { lead, paragraphs: [], takeaways: [{ title, text, findingIds: [] }] },
  findings: [{
    id, benchmark, title, claim, summary, status,
    models: [], subclaims: [], tags: [], scale, cost,
    charts: [],
    evidence: [],
    reasoningObservations: [{ title, text, caseIds: [], scope }],
    alternatives: [], hypothesisMeaning, nextQuestion,
    sources: [{ label, href }], caseIds: []
  }],
  cases: [{
    id, title, benchmark, model, condition, findingIds: [], tags: [],
    prompt, reasoningExcerpt, reasoningNote, behavior, analysis,
    scope, alternatives: [], sources: [{ label, href }]
  }],
  methods: [{ title, text, sources: [{ label, href }] }],
  coverage: [{ family, status, note, source: { label, href } }]
};
```

Benchmarks are `IB` or `SoRH`. Evidence status is an explicit root judgment, not inferred from plot values; supported display classes are `supported`, `tentative`, `mixed`, `unresolved`, `descriptive`. The coverage ledger accepts free-form labels such as `latest / direct reading`, `legacy / linked analysis`, `ongoing / excluded`, or `no reasoning available`.

## Chart contract

All chart types accept `id`, `title`, `measure`, `note`, `sources`, and `exportHref` (a root-generated scientific plot). Rows may carry `caseIds` (first available case opens when a mark is clicked), `findingId`, `source: {label, href}`, and `ref`. Without a case the mark opens the owning finding.

```js
// k/n, with computed Wilson 95% intervals.
{ type: 'binomial', rows: [{ id, label, model, condition, k, n, caseIds, source, ref }] }

// Connected condition proportions, each with its own interval.
// A connecting line does not establish paired individual outcomes.
{ type: 'dumbbell', beforeLabel, afterLabel,
  pairs: [{ label, model, before: {label, k, n}, after: {label, k, n}, caseIds, source, ref }] }

// Continuous/descriptive values: no binomial interval, shared numeric axis.
{ type: 'value', unit,
  rows: [{ label, model, condition, value, unit, n, caseIds, source, ref }] }

// Local scientific figure, with substantive accessible description and exports.
{ type: 'image', src: 'figures/plot.svg', alt: 'Description of the result and scope',
  exportHref: 'figures/plot.pdf', sources: [{label: 'Derived values', href: 'figures/data.json'}] }
```

For value charts, `n` means actual sample size only; omit it when unavailable. The existing exported reasoning-length charts' `n0`…`n3` fields are axis maxima and must not be passed as sample sizes. Invalid binomial counts and n=0 render as unavailable, never as a zero success rate. Underlying tables retain all rows even when a card preview is abbreviated.

## Navigation and accessibility

- Routes: `#view=overview`, `ib`, `sorh`, `casebook`, `evidence`, `methods`.
- Deep links: `#view=ib&finding=<id>` or `#view=casebook&case=<id>`.
- Comparison cases can use `models: [id, ...]` in addition to a primary `model`; `model: "multiple"` displays All models. Model filtering includes both fields.
- Filters: search, model, subclaim and evidence status. The casebook searches prompt, excerpt, action and interpretation.
- Native modal dialog with Escape/close, keyboard-focusable marks and source links, SVG descriptions, data tables, skip link, responsive layout, reduced-motion and print modes.
- The evidence map encodes **relevance**, not votes or support. It must not be summed into a support score.

## Validation completed

JavaScript parsed with Node's VM through the available node runtime tool (no shell `node` binary). Offline checks exercised empty dashboard rendering, Wilson boundaries0/1 and1/1, n=0, invalid counts, continuous units, label escaping and unsafe-URL rejection. No network needed. Root owns populated-data browser QA before delivery.
