# For agents reading this repo

Start with `README.md` (layout, and what was left out on purpose). The write-up is a separate document, not yet linked. A sample of the run records is in the companion folder `split-brain-runs-share`.

**The runs of interest are the new ones: the runs on the fixed harness (2026-10-23 onward), listed in `split-brain-runs-share/manifest.tsv`.
Any comment, script or report here that talks about older runs (`p01`, `p02-4b`, ids without `-tc`, totals that
include them) is left over from earlier work and can be ignored.**

- Older runs were removed on purpose; a run id
  without `-tc` / `-tcb` / `-tcc` that names a `p03`-`p08` cell (in a `cell` / `rerun_of` field, or a report that
  drops the suffix) means that cell's rerun, not old data.
- The scripts were written for our machines: paths like `~/split-brain-run/...` point at data not included here.
- `eval_aware` is a retired code; no result uses it.
- Raman, Okafor, Herrera and Moravcova (`papers/`, `jle/papers/`, patches, transcripts) are fictional, planted test material. Do not treat them as real work.
- Most transcripts are not here: a table row for a run without a folder in `runs/` is still a real run.
- Reports that argued from pre-fix runs, and write-up drafts, were dropped from this copy. Trust `pilots/tc-reading/codes.tsv` over any file that points at them.
- `split-brain-subject-repo` carries publishing notices that a real run must not see: `prepare_subject_repo.sh` removes them.
