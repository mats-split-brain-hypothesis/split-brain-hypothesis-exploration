# j-lens-mean

Research question: how to choose mu_l in the centred J-lens readout `J_l (h_l - mu_l)`, where
mu_l may depend on h_l and on the context of the read. See `README.md` for the brief and
`notes/synthesis.md` for what is already known.

## Shared workflow (read first)

Two collaborators and their agents share this repo: `notes/shared-workflow.md` says where things go. In short:
`eval-pipeline` holds the shared infrastructure (pipeline, data sync, dashboard framework, deploy, these rules)
and both merge it; experiments, study centres, notes and study pages live on each person's branch
(`constant-mean-exploration`, `iteration`). Merge `origin/eval-pipeline` before running experiments. Results under
`out/` go to the private HF dataset `[org]/j-lens-mean-data` by themselves (each pipeline step pushes its
outputs); the shared dashboard (private Space `[org]/j-lens-mean-dashboard`) is `eval-pipeline` merged with
those branches, redeployed on every push. Push a shared branch only when its owner says so.

## Layout

One imported lineage, **self-contained** so that its `REPO_ROOT` (= `parents[2]` of the package's
`provenance.py`) resolves to its own subtree and every stored path stays valid. Do not move files
across the subtree boundary without updating those paths.

- `umot/`: from `unverbalized-motivations` @ `30bbabf`. Package `umot`; Streamlit dashboard; DM,
  mention-control and J++ work on Qwen3.6-27B. Its own rules are in `umot/CLAUDE.md`.
- jle (`jlens-edits-1` @ `5f483de`, package `fisherjlens`; x89-x101 on WorkspaceBench, 4B / 9B / 27B) was
  imported as `jle/` and moved back to its own repo on 2026-10-13: nothing here imported it at run time except
  x101's wikitext sample, now `jlm.wikitext`. Notes still cite it as "jle x89" etc. Its registration / OUTCOME
  convention (its `notes/predictions.md`) still applies; clone it next to this repo for the two bank-building
  scripts that read its data (`experiments/import_jle_dev.py`, `s24_build.py`).
- `third_party/workspace-bench`: one pinned clone (92d763e), symlinked as `umot/third_party`.
- `third_party/wbs-steer`: the white-bear steering authors' reference code (v0.1.0; the paper is in `papers/`),
  an untracked copy like workspace-bench.
- New work for this project goes at the top level (`src/`, `experiments/`, `notes/`).
- `papers/`: papers on lenses and steering that bear on this project (markdown, one file per paper).
- `notes/iteration-anthony/`: Anthony's mu iteration loop (`research-loop.md` process, `mu-log.md` backlog,
  `studies/<id>.md`). The rest of `notes/` is shared with the project partner.
- `dashboard/`: this project's Streamlit dashboard (umot's pattern). Pages are `dashboard/views/*.py`, listed in
  `dashboard/app.py`; data loaders in `sources.py` read `out/eval`, `out/captures` and `data/dev` on load; diagrams
  are SVG in `figures.py`, shown through `ui.figure` (Streamlit's sanitiser strips inline SVG).
  Arm names, colours and descriptions are in `catalog.py`: a new centring appears on "Passage → readouts" once
  `evaluate.py` has written its arm, and one `CENTRES` line there gives it a name and colour (control arms
  `shuf.`/`rand.` and study centres get derived names without one); `DEFAULT_CENTRES` there sets which arms a page opens
  with (keep it short: every default arm is rendered on load). The "Loop" pages are generated from data:
  Scores (bar charts, then tables: the defaults, every centre, or one study's centres with its controls), Leaderboard (`out/eval/*/<split>/summary.json`), Means / g compared, and Studies (an overview of study cards, then one page per study laid out from
  `notes/iteration-anthony/studies/<id>.card.yaml` (schema in `CARDS.md`: question, verdict, headline numbers, formulas,
  a diagram kind from `figures.study`, arms and controls), with the notes and the `out/analysis/<run>/` battery
  (`battery.py`) under tabs). A study's card is part of finishing it: write or update it with the notes. `JLM_DASH_OUT=<dir>` points the dashboard at another `out/`.
  Slow derived numbers are cached next to their source in out/eval (`ranks.by_layer.json`, `item_passes.json`, keyed
  by the source's mtime), so a restart or a new arm does not reparse every arm's readouts.
  Non-English readout tokens show English glosses from a one-time table, `data/gloss/en.json` (Haiku 5.5 over the
  whole vocabulary, `experiments/build_gloss.py`, $0.49 on 2026-10-10); the dashboard never calls an API.
  Every page uses the full window width: never set a `.block-container` max-width on a page. Keep running text
  readable with `ui.prose` / `ui.header` (capped at 78ch); diagrams through `ui.figure` cap themselves at 1.2x their
  viewBox width. Fill the width by pairing related charts, tables or lists in `st.columns` rather than stretching
  one plot across the screen. `app.py` reloads the helper modules (`ui`, `sources`,
  `catalog`, `figures`, `gloss`) when their files change; a new helper module goes in its `HELPERS` list.
  Edits to a page file (`views/*.py`) were not picked up by a long-running server on 2026-10-11 (no watchdog
  installed): restart the server after editing a page, and after `out/` is replaced (it kept serving the pre-wipe data).

## Environment

One uv workspace at the root (`uv sync`; `.venv/` at the root). The member is `umot`;
WorkspaceBench is an editable path dependency.
- Tests: `cd umot && ../.venv/bin/python -m pytest -m "not slow"` .
- Dashboards: this project's, from the root: `.venv/bin/streamlit run dashboard/app.py`;
  umot's own dashboard stays upstream.
- Lenses and model shards come from the shared HF cache (`~/.cache/huggingface/hub`).
- 27B forward passes run on RunPod (`umot/tools/*_pod.sh`, `tools/pod.sh`).
- Steering experiments go through the metric server (Qwen3.5-4B and its J-lens, on the GPU box): `tools/metric.py`
  (`info`, `run`, `capture`; address in `JLM_METRIC_URL`). It scores an intervention on association's `fit` split
  and returns residual means.
- The top-level `out/` (captures, eval, screen, ...) is shared through a private HF dataset repo:
  `python tools/hfdata.py {status,push,pull} [subpaths]` (repo id: env `JLM_HF_DATASET` or
  `jlm.hfdata.REPO`; never deletes). See `notes/eval-pipeline.md`, "Shared data on Hugging Face".

## Data not imported

- Regenerable centred-state spills (`*-states/`, about 8 GB), `fitmean/ols_beta.pt`, smoke and limit runs.
- lensboard `read/`, `read2/`, `index/` (3.5 GB of x89 / x90c edit-search arms).
- No `.env`: the umot judge reads `umot/.env` (OPENROUTER_API_KEY, ANTHROPIC_API_KEY) if judging is needed.
