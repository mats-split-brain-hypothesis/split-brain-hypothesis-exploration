# Shared workflow (for both collaborators and their agents)

Two people (Maya, Anthony) and their Claude instances work in this repo. This is how code, results and the
dashboard move between them. `CLAUDE.md` points every session here; read it before running experiments,
changing the pipeline or the dashboard, or pushing.

## Branches

| branch | holds | who changes it |
|---|---|---|
| `eval-pipeline` | shared infrastructure: the pipeline (`src/jlm`, `experiments/{evaluate,judge,analyse,report,agreement}.py`, capture), the data sync (`jlm.hfdata`, `tools/hfdata.py`), the dashboard framework and its generic pages and helpers, `tools/deploy_space.py`, these instructions | either, for things the other also needs; both merge it into their own branch |
| `constant-mean-exploration` | Maya's experiments (x1-x12, `src/jlm/mu/constant_mu.py`), their notes and dashboard page | Maya and her agents |
| `iteration` | Anthony's research loop (`src/jlm/mu/<study>.py`, `notes/iteration-anthony/`) and its pages | Anthony and his agents |

- Infrastructure goes to `eval-pipeline`: a pipeline fix, a new dashboard helper or generic page, sync or deploy
  changes. Keep it working (`.venv/bin/python -m pytest tests`) and never force-push it.
- Study content stays on its branch: centres in `src/jlm/mu/<study>.py`, study scripts, study notes, study pages,
  and their `dashboard/catalog.py` entries (names, colours, `OPT_IN` heads).
- Merge `origin/eval-pipeline` into your branch before running experiments, and run them from your branch's
  checkout: provenance stamps every artefact with branch@commit. In a git worktree run with
  `PYTHONPATH=src:umot/src` (the shared venv's `umot` points at the main checkout, and provenance stamps the
  checkout `umot` is imported from).
- Push a shared branch (`eval-pipeline`), or anyone else's, only when its owner says so.

## Results: the shared dataset

Everything under the git-ignored `out/` lives in one private HF dataset, `[org]/j-lens-mean-data`
(`notes/eval-pipeline.md`, "Shared data on Hugging Face").

- Every pipeline step pushes what it wrote as it finishes (`hfdata.share`): `evaluate.py` the bank's directory,
  `judge.py` the run's directory, `analyse.py` the study's directory, capture and the generators their capture.
  It needs a login with write access to the org (`hf auth login`, or `HF_TOKEN` on a pod); without one it says
  so and the run goes on. Push anything else with `python tools/hfdata.py push <subpaths>`.
- Throwaway runs: `JLM_HF_AUTOPUSH=0`, or write them outside `out/` (`--out /tmp/...`): neither is shared.
- `python tools/hfdata.py pull` brings the other side's results into your `out/`; it never overwrites a file
  you changed since your last sync, and bank summaries merge (both sides' arms kept).
- One arm name, one meaning: the same arm on the same bank from different code is a conflict in the dataset
  (listed by the push, not overwritten). Give a new variant a new centre name.

## The dashboard

One shared copy: https://huggingface.co/spaces/[org]/j-lens-mean-dashboard (private to the org; log in
to HF). It is `eval-pipeline` merged with the branches in `.github/dashboard-branches`, redeployed by
`.github/workflows/deploy-dashboard.yml` on every push to one of them that touches the dashboard or the code it
imports. Results appear without a deploy: the Space pulls the dataset every 5 minutes ("Shared data" page: what
arrived, from whom, from which branch).

- A page for your study: `dashboard/views/<page>.py` on your branch, listed in `dashboard/app.py`'s navigation.
  It reaches the shared dashboard on your next push. Use the helpers that exist on `eval-pipeline`
  (`sources`, `ui`, `catalog`, `figures`); a new helper, or a change to one, goes to `eval-pipeline` first.
- Two branches changing the same lines stop the deploy; the workflow's log names the files. Resolve it on one
  branch (usually: move the shared part to `eval-pipeline`) and push again.
- Locally: `.venv/bin/streamlit run dashboard/app.py` shows your branch with the same synced data.
- By hand (no CI): `python tools/deploy_space.py --space [org]/j-lens-mean-dashboard --dataset
  [org]/j-lens-mean-data` (merges the branches from origin; `--stage DIR` builds without uploading).
