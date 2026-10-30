# unverbalized-motivations

Can activation readers (J-lens and its single-token relatives, NLAs, the oracle /
modulation lens) surface motivations that Qwen3.6-27B acts on but never writes down?
Exploration stage of a research project.

## Getting started (any macOS/Linux machine)

```bash
git clone <this repo> && cd unverbalized-motivations
bash tools/bootstrap.sh          # uv venv + pinned WorkspaceBench in third_party/
.venv/bin/pytest -m "not slow"   # offline checks
```

In VS Code the venv is activated automatically in new terminals (`.vscode/settings.json`).
The 27B model runs on a GPU pod, not a laptop: see `notes/setup.md`.

## Dashboard

```bash
.venv/bin/streamlit run dashboard/app.py      # http://localhost:8501
```

Overview, progress and research log, explanations of the readers and the scoring, reader
comparisons, judge agreement, cost, and a passage → readout explorer. Every number is read from
`out/`, the pinned bench and `notes/` on load, so rsyncing artefacts back is enough to update it.
Milestones and next steps live in `dashboard/plan.py`; reader and family descriptions in
`dashboard/catalog.py`; one page per file in `dashboard/views/`. Night mode is in the sidebar.
`UMOT_DASH_OUT=<dir>` points it at another artefact tree.

`CLAUDE.md` is the project brief (goals, scope, rules); `notes/` holds the setup guide,
research log and candidate findings.
