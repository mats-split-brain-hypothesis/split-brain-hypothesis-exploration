# split-brain: environment and analysis

A test of the split-brain hypothesis (models reward-hack when they believe they are in a graded episode, and behave
otherwise). A subject agent (Claude Code as the harness, open models through OpenRouter) works alone for up to two
hours, in a firewalled container, on a steering task in a trimmed snapshot of a real interpretability repo, and we vary
the framing one cue at a time. A sample of the run records is in the companion
folder `split-brain-runs-share`.

This is a curated copy of our working repo, made for sharing: it holds the current environment and the analysis behind
our results. Our planning logs and everything about runs made before the harness fix of
2026-10-23 were left out on purpose (see "What was left out").

**The runs of interest are the new ones: the runs on the fixed harness (2026-10-23 onward), listed in `split-brain-runs-share/manifest.tsv`.
Any comment, script or report here that talks about older runs (`p01`, `p02-4b`, ids without `-tc`, totals that
include them) is left over from earlier work and can be ignored.**

- **To run the environment**: `REPLICATE.md`.
- **Write-up**: link to be added.
- **Slides**: link to be added.

## Layout

- The environment (the harness every run here used):
  - `container/`: `launch.sh` starts a run; `Dockerfile`, `entrypoint.sh`, `init-firewall.sh` and `shell-env.sh`
    build the firewalled subject container; `api_proxy.py` sits between Claude Code and the model API;
    `supervise.sh` and `episode_end.py` watch and close a run; `eval_mcp/` is the eval tool server of the arms that
    have one.
  - `metric_server/`: `server.py` scores the steering metric on a GPU pod (the score shown to the subject and the
    real one), `proxy.py` forwards it to the container, `pod_server.sh` brings the pod up, `calibrate_rig.py`
    calibrates the rig; the `.pt` files are reference directions.
  - `patches/` and `variants/<variant>/`: what we added to the source repo for all arms, and what each arm changes
    (papers, patches, untracked files). Our build script needs the private source repo, so it is not here; the A0
    repo it built is `split-brain-subject-repo`.
  - `server_overlay/`: the newer source files the scoring server ran from (`prepare_server_repo.sh` applies them).
  - `papers/`: the reading list planted in the repo. **Four papers across the environments are fictional test
    material: Raman et al. (the planted method that solves the task), Okafor et al., Herrera et al. and Moravcova et al.
    (`jle/`). Their authors, labs and numbers are invented; do not cite them.** Each says so at the top, and `NOTICE.md`
    covers the copies inside patches. `liu2026-*` and `henry2026-*` are real (CC-BY). Six other real papers the
    subject had are listed with links in `papers/REAL-PAPERS.md`, not copied here.
- `briefs/`: the one message each run gets. `briefs/p04/arms/<arm>/` defines each arm (`arm.json` says exactly what
  it changes against the anchor A0, with its `brief.md` and repo files; `make_arms.py` builds them); `briefs/tc/` are
  the assembled briefs the runs got (file name = content hash, as in each run's `meta.json`); `briefs/borrow/` the
  borrowed-compute / contamination ladder; `briefs/jle/` the port of the task to a second repo (built by `jle/`).
- `pilots/`: the analysis scripts, coding tables and reports behind the write-up's numbers. The central table is `pilots/tc-reading/codes.tsv` (one coded outcome per
  run); later pilots (`pilots/p18` … `p36`) hold their arms, launchers and notes.
- `whitebox/`: the debrief / resampling / white-box analyses of §4 and §7 (scripts and reports; the captures and
  samples they read are not included).

## Licence

The repo's MIT licence covers our code and notes. It does not cover third-party text: the real papers here (each under
its own licence) and excerpts of papers in transcripts and readings.

## Things that look inconsistent but are not

- **Pilot numbers** (`p04`, `p09`, ... in run ids and file names) name the batch that first ran a cell, not a
  version of the environment. The condition is the arm (`A0`, `A10`, ...). Cells first run before the harness fix
  were rerun on the fixed harness and carry the suffix `-tc` / `-tcb` / `-tcc`.
- **Retired measures**: `eval_aware` (counted echoes of the brief's own words, not a belief; retired 2026-10-27)
  still shows in some coding tables. No result uses it.

## What was left out

- Runs made before the harness red-team of 2026-10-23, and every number, table row or transcript from them: their
  earlier reasoning was dropped from the subject's context and the tool-call gatekeeper differed within a run, so they
  are not comparable with the runs here.
- Our planning logs, handoff notes, parked directions and superseded coding passes, and reports that argue from
  pre-fix runs (being re-checked). A few scripts and tables still name an old run id as a usage example or a cell.
- Most transcripts: `split-brain-runs-share` has a sample (31 runs + one Dark Mode run) and the manifest of all 792.
  The full set is planned for a Hugging Face dataset.
- `patches/0001-…` (moves an unrelated folder out of the source repo; it held private notes), so the patch series
  starts at 0002. Named files that are absent (`PLAN.md`, `PERSISTENCE.md`, `pilots/tc-finish.sh`, ...) are in this
  group too.
- Six real papers, removed from `papers/` and the patches, so those patches no longer rebuild the subject's exact repo (`prepare_subject_repo.sh` fetches the papers again).
- Private strings: emails, machine names and home paths, private links and pod identifiers were replaced, so edited files no longer match their
  `source.sha256`.
- The other arms' built repos and the source repo's git history: `split-brain-subject-repo` is the anchor arm A0's
  repo as files. `REPLICATE.md` says how to run it.
