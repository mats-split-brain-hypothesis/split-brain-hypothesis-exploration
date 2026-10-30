# Split-brain research review

Open `dist/index.html` directly in a browser. The dashboard works offline: no build service, remote fonts, analytics or model requests. It is a local research artifact, not a published site.

The frozen 27 October 2026 review covers 95 finding families (42 ImpossibleBench and 53 School of Reward Hacks), presented through 66 charts and 26 descriptive tables. Four new scientific figures have SVG, PNG, PDF and derived-data exports. Repeated graphs and overlapping cohorts are not independent replications.

The casebook contains 19 new comparisons from 65 current record IDs plus one synthesis of the previously completed AISI-style pilot. Reading was purposive: some short records were read fully, while longer records were examined at selected decisions or beginning/end ranges. Every case states that scope. This is not an exhaustive transcript census. Families without new direct reading remain explicitly marked as source/result audits.

## Rebuild and verify

Run from this worktree using the existing project environment:

```sh
.venv/bin/python src/build_research_dashboard.py
.venv/bin/python src/validate_research_dashboard.py
```

The build uses the frozen catalogs and scalar exports in `source_data`, reviewed prose in `editorial.json` and `overrides.json`, and `notes/reasoning_review_observations.json`. The latter is the authoritative reviewed observation file; `src/add_review_observations.py` is an earlier authoring helper and is not a build step.

The local transcript cache, manifests and inspection ledger reside in the shared `logs/reasoning_review/2026-10-27` directory. The builder also resolves source notes in the main checkout and other agent worktrees. Keep those local inputs available to regenerate evidence pages. Source-page snapshots include their paths and SHA256 hashes; a later rebuild may capture newer source notes, while the copied scalar catalogs remain frozen. The main checkout and ongoing experiments are not modified.

The validator checks unique IDs, finding/case cross-references, count bounds, all 1,809 local links, and 34 exact quotations against the cached source text. It also independently checks the 24 share-metric pairs and the 21 shorter/higher-share results. Its machine-readable output is `dist/validation.json`. These checks verify assembly and quoted evidence, not the truth of a model's expressed reasoning or a causal interpretation.

See [analysis/README.md](analysis/README.md) for the scientific figures' pairing rules, exclusions, units and reproduction commands. No new model calls were made for this review. Historical experiment costs are labeled separately in the dashboard.

## Evidence and interpretation

The main synthesis is that inferred objective direction and instruction priority explain substantial variation. Real-use belief as a causal mediator remains unresolved. The evidence map distinguishes subclaims and competing explanations; each finding gives a useful next contrast rather than treating all results as support for one mechanism.

The presentation separates original-test code passes, edited-test passes, submission composites, missing outputs, selected continuation pools, and final padding judgments. Descriptive tables replace binomial charts for unsuitable denominators. Remaining Wilson intervals describe displayed proportions; they do not account for task clustering, shared prefixes or selected prompts and are not population treatment-effect intervals.

Complete source-note and transcript pages live in ignored `dist/evidence/`. They remain accessible locally but are not staged in Git. The tracked dashboard includes selected quoted excerpts and provenance. Do not publish this directory without reviewing its contents and the intended audience.
