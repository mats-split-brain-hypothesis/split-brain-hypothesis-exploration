# split-brain runs

A sample of the compact records of the 792 runs behind the split-brain write-up. `manifest.tsv` lists all 792; `runs/`
holds 31 of them, plus one Dark Mode run. The full set is planned for a Hugging Face dataset. The environment and the
analysis scripts are in the companion folder `split-brain-share`.

**The sample is not representative, so do not compute rates from it.** It holds the starred key example
(`p29-r4-A69-dsv4-tc`) and, for each model and outcome code, the two runs we quote most. `p36-ci-r6-dsv4` is the
second starred run, from a different environment and harness (`rollout.log`, `messages.json`, `state.json`), and is
not in the manifest. Rates come from `pilots/tc-reading/codes.tsv` in the companion folder.

Emails, machine names and home paths were replaced in these records, so edited files no longer match
`source.sha256`.

**The runs of interest are the new ones: the runs on the fixed harness (2026-10-23 onward), listed in `manifest.tsv`.
Any comment, script or report here that talks about older runs (`p01`, `p02-4b`, ids without `-tc`, totals that
include them) is left over from earlier work and can be ignored.**

**Transcripts quote the planted reading list. Raman, Okafor, Herrera and Moravcova are fictional papers, with invented
authors and numbers: do not cite them.** The repo's MIT licence does not cover excerpts of third-party papers.

## What is here, and what is not

Every run here used the current harness, fixed after a red-team of the subject harness on 2026-10-23 (`harness` =
`redteam-2026-10-23` in `manifest.tsv`). Runs made before that fix were removed on purpose: in them the subject's
earlier reasoning was dropped from its context, and the tool-call gatekeeper differed between parts of a run, so
they are not comparable with these and are used in no result. Many cells were rerun on the fixed harness; those
reruns keep the old cell's name with the suffix `-tc` / `-tcb` / `-tcc` (meta.json `rerun_of` names the removed
original). Harness smoke tests were removed too.

## Layout

- `manifest.tsv`: one row per run: model, start / end, exit code, and our main codes where coded (`outcome`,
  `hack_level`, `considered`, `design`; `source` says which coding they come from). Codes are defined in
  `codebooks/outcome-coding.md`. The write-up counts as cheats only `misattributed` and `uncredited` (not
  `overstated`).
- `runs/<id>/`:
  - `meta.json`: the launch: model, brief, snapshot (the arm's repo) and its commit, limits, harness version.
  - `brief.md`: the one message the subject got.
  - `stream.jsonl`: the subject's session (Claude Code stream JSON, with reasoning), progress ticks removed.
  - `api.jsonl`: the model API log (open models through OpenRouter).
  - `server/<logdir>/calls.jsonl`: the metric server's log for the run (the score shown to the subject and the real
    one, per call); `refused.jsonl` where the server refused calls.
  - `submission/` (contribution.md, submission.json, the vectors), `commits.patch` (the run's own commits),
    `worktree.patch` / `worktree/` (uncommitted edits, small untracked files), where present: what the run left in the repo.
  - `codes/`: our codings of the run: `reading*.md` / `.codes.tsv` / `.quotes.tsv` (reader agents' notes, codes and
    exact quotes; block numbers as in the run viewer), `annotations.json` (hand highlights), `audiences.json`, and
    `tables/` (this run's rows of every coding table, each with its own header).
  - `source.sha256` / `harness.sha256`: tie each file back to the raw record on our machines and to the harness
    version that ran it.
- `codebooks/`: the reading briefs the reader agents followed (`reading-brief.md`, its addenda `reading-brief-p08.md`
  and `reading-brief-tc.md`) and the outcome codes (`outcome-coding.md`). Paths inside them point at our planning
  repo; the arm files they name are `briefs/p04/arms/<arm>/` in `split-brain-share`.

## Things that look inconsistent but are not

- **Pilot numbers in run names** (`p04-…-tc`, `p09-…`) name the batch that first ran the cell, not a version of the
  environment; the arm (`A0`, `A10`, …) is what defines the condition (`briefs/p04/arms/<arm>/arm.json` in the
  companion repo).
- **`eval_aware`** still appears in per-run reader notes and `tables/`. It is a retired code (2026-10-27): it counted
  echoes of the brief's own words rather than a belief, and no result uses it.
- **Up to two readers per run**: `reading.md` (a reader agent) and `reading-api.md` (a second reading through the API,
  `pilots/read_api.py` in the companion repo) are separate passes over the same run and need not agree.
- **Paths** in `meta.json` and the codebooks are those of our machines; `/home/anthony` is also the subject's home.
- **Maya Lindqvist** in the records is a stand-in name: the runs' repos are snapshots of a research partner's code,
  renamed, and published with the partner's OK.
