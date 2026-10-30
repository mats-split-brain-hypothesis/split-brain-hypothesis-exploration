# Real or Graded: the results site

A multi-page claude.ai HTML artifact in Anthony's dashboard style (his look, not his branding): Inter / Newsreader /
JetBrains Mono, colour as meaning (blue = a person / reads as real; orange = graded / test-like; grey = control), a
sidebar of pages, numbered sections, tiles, cards, callouts and a closing "how far to trust this" section.

## Rule: every number comes from a sourced dataset

- `datasets/<module>.py` defines `datasets()`, returning dataset dicts (shape in `lib.py`). Each names its source:
  a notes file, a section heading and a commit. Each row can carry `_cites`: strings that must appear in that
  section (a list of alternatives where formatting varies), and `_src` to override the source for that row.
- `build.py` writes `site/data/<id>.json` and `site/data/manifest.json`. `build.py <module>` rebuilds one module.
- `check.py` fails if a cited string is missing from its source, a value slot on a page doesn't resolve to exactly
  one row, or a page names a dataset that doesn't exist. Run it before every publish.
- Pages never hold numbers in markup. A value is `<span class="v" data-ds="<id>" data-f="<field>"
  data-w="col=value&amp;col=value">—</span>`; charts and tables are drawn from `RG.load([...])` in the page script,
  and every figure has `<p class="src" data-src="<ids>"></p>`, which shows its sources.
- Model reasoning: only quotes already verified on our pages (judges' citations).

## Adding a page (e.g. sorh.html, ib.html)

1. Add `datasets/<page>.py`; run `build.py <page>` and `check.py`.
2. Copy `goodfire.html` as a template: full document head, `data-page="<file>"` on `.shell`, the shared assets.
3. Flip the page's `ready` flag in `PAGES` at the top of `site/assets/site.js`.
4. Publish to the same artifact URL with only your files in `files` (files left out are kept).

`pending_runs.json` lists runs results still rest on; mark an entry done (and point it at its notes) and rebuild.
