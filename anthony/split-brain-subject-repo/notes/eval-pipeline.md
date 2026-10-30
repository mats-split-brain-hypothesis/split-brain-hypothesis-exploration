# The shared evaluation pipeline (`src/jlm`)

> **Judge used for development: Claude Haiku 5.5 via OpenRouter (`anthropic/claude-haiku-5.5`),
> NOT the bench's pinned judge.** Every judged dev number in this note and in `out/eval` comes from
> Haiku unless it says otherwise. Haiku runs are unpinned (`pinned_instrument: false`), stored
> under `judged-claude-haiku-5.5*/`, and are never WorkspaceBench scores. The bench's pinned judge
> (Gemini 3.8 Flash; Claude Sonnet 5 for two families) is kept for final bench numbers of record
> (`--judge-model pinned`, stored under `judged/`). Why: our OpenRouter account caps Gemini at 20
> requests per minute (see "Judge runs"). Haiku and Gemini agreement has not been measured on our
> families yet; `umot` measured Haiku via the API against Haiku via OpenRouter only.

**What the captures are.** The 27B residuals h_l at each item's read cells and grid layers (bf16),
computed once per bank on the pod. Centres are fitted from them and J_l (h - mu) is read from
them, so a new mu needs no 27B forward pass: only W_U, the final norm and the lens.

Started 2026-10-10. Decisions taken with the user: 27B only; the families we have worked with, plus
the multi-token ones (kept separate in reports); the LLM judge runs on dev `val` (and the bench);
new experiments follow jle's REGISTERED / OUTCOME convention, kept light.

## Progress (hand-off)

Branch `eval-pipeline` (pushed). As of 2026-10-10:

**Done**
- The package `src/jlm` and the scripts `experiments/{evaluate,judge,agreement,capture,import_jle_dev}.py`
  and `tools/capture_pod.sh`. 8 offline tests in `tests/test_jlm.py`.
- Lens: the released J-lens only (neuronpedia n1000 wikitext, pinned `a4114d7`). Never J++.
  J++ is read only as a comparison: the arm prefix `jpp:` (e.g. `jpp:zero|cos`), see `notes/jpp-compare.md`.
  Readouts `cos` (the bench's) and `rms` (jle's). Arms so far: `zero`, `fam@self`, `fam@fit`, `tok`.
- Five single-token families done end to end: typo, association, basic_readout, multihop and
  multilingual. Each has dev `fit` / `val` banks, pod captures of fit, val and bench, strict + rank
  scores for 6 arms, and Haiku judging of `val`. Bench parity with jle x100 holds (see Status).
- Judge adapters: the 6 bank-judge families and user_modeling.
- user_modeling: dev banks imported (61 / 61); not captured yet.

**How to run** (Mac unless noted)
1. `python experiments/import_jle_dev.py --families F` (or write `data/dev/F/{fit,val}.json` by hand)
2. Pod: `BANKS=F/fit,F/val,F/bench bash tools/capture_pod.sh`. Ship the repo as a git bundle, put
   `HF_HOME` on the container disk, copy `out/captures/` back with tar over ssh, then terminate.
3. `python experiments/evaluate.py --banks F/fit,F/val,F/bench --arms "zero|cos,fam@fit|cos,..."`
4. `python experiments/judge.py --family F --split val --arms ...`: Haiku 5.5 by default;
   `--judge-model pinned` for Gemini, which is capped at 20 rpm.
5. `python experiments/agreement.py --family F --split val --arms ...`

- user_modeling: captured (fit / val / bench, about 21 read cells per item) and evaluated on
  fit and val. Bench and DM evaluation are running.
- directed_modulation: judge adapter. The dev bank is new, from `data/dev/directed_modulation/source.json`
  via `experiments/build_dm_dev.py`: 53 pairs, 24 secrets and 24 preferences, with concepts and
  carriers disjoint from the bench and the bench's templates. Gated on the pod with the bench's
  rule: 154/154 pass. Split by pair into fit 78 / val 76, and captured. Centres exclude the
  item's whole group (DM: the twin, which holds the same concept), as umot did.
- Faster reads: ranks and token names are vectorised per block, and centre means are memoised.
  Output is byte-identical to the stored readouts (checked on 12 files). `--device cuda` runs
  the same code on a GPU.

**Calibration: user_modeling** (2026-10-10, Haiku, `zero|cos` on val, layers 24 / 36 / 48 / 60, $1.80).
Strict 0.64 vs judge 0.89, kappa 0.29 (items) / 0.36 (cells), 17 discordant items. The judge
credits *inferred* attributes from related tokens ("beard, testosterone" -> male; "泰国, Thai" ->
Thailand; "pottery, ceramics" -> potter), which is the bench's intent. A few credits look generous
(a CJK chat style -> Asia). One item passes strict and fails the judge. **Strict is not a usable
proxy on user_modeling.** Rank centres there with judged runs on a few layers, or a better free
proxy (to be discussed: anything built from the target values is target-specific work).

- GPU evaluation: `tools/eval_pod.sh` (no 27B model; W_U, the final norm and the lens only).
  The user_modeling bench (10 arms x 23k cells) and DM (30 arms) took about 3 minutes on an A100
  (6 s per UM bench arm, against about 140 s on the Mac). The whole pod session, including setup
  and the 690 MB capture upload, took about 12 minutes.
  GPU vs CPU on 4 UM bench arms (92,928 rows): scores within 1e-4, 3 rows differ in top-10 order
  and 1 in top-10 set (near-ties), 0 items change strict pass.
- user_modeling bench parity with x100: n 50; zero 0.42 / 0.40, fam@self 0.44 / 0.46 (cos / rms),
  identical. tok@fit|cos 0.50 = x100's devtok1. On val, token-matched centres help:
  0.72 -> 0.79 (cos) and 0.62 -> 0.87 (rms).
- DM: jle's leak exclusion is off for DM (`score.NAMED_IN_PROMPT`). The instruction names the
  concept by design, so the leak rule had excluded exactly the items strict can credit. Most DM
  concepts are rare words that no single token spells (bench 81/100, dev about 50/76), so strict
  can credit at most about a quarter of items. Strict on val (cos): zero 0.07, tok@fit 0.31.

**Calibration: directed_modulation** (2026-10-10, Haiku, val, layers 24 / 36 / 48 / 60, $1.73).
Judge headline (content_bound): `zero|cos` 0.18 -> `tok@fit|cos` 0.79. This is held out on the new
dev bank and close to umot's bench result (0.21 -> 0.82). Strict vs judge: zero 0.04 vs 0.18
(kappa 0.33); tok@fit 0.31 vs 0.78 (kappa 0.04; 39 items pass only the judge, 4 only strict).
**Strict is not a usable item-level proxy on DM either.** At arm level it orders the two arms
the same way as the judge.

**Next**
1. Ranking centres on user_modeling and DM: decided (see "Using it for new mu").
2. Multi-token families: deferred by the user (2026-10-10).
3. Multi-token families: free regex scorer, judged path via the summarizer, gate jle's 163 candidates.
4. Optional: a pinned Gemini agreement sample, to calibrate Haiku.

## Using it for new mu (agreed with the user, 2026-10-10)

**Running from a git worktree.** The shared `.venv` installs `umot` editable from the main checkout, and
provenance (`umot.provenance`) stamps the git sha of the checkout `umot` is imported from. In a worktree
run with `PYTHONPATH=src:umot/src`, or every artefact is stamped with the main checkout's commit instead
of the code that ran (happened on 2026-10-11: the first post-merge plain-family run was stamped
`9e3c3e5`; it was re-run on `5b2c503` with correct stamps and compared cell by cell).

**Screening policy**
1. Screen every new centre with strict match on all 7 families (`fit` and `val`), on the pod GPU
   (`tools/eval_pod.sh`, a few minutes for everything).
2. On user_modeling and directed_modulation, strict does not track the judge. Judge only the
   promising centres there, on `val` at 4 layers (24 / 36 / 48 / 60): about $0.80 per DM arm and
   $1.80 per UM arm with Haiku.
3. Judge final picks on the bench with the pinned Gemini judge (`--judge-model pinned`; 20 rpm
   cap, about an hour per arm). These are the numbers of record.
4. `python experiments/report.py --split val|bench` gives one table across families.

**Adding a centre**
- Write a class in `src/jlm/centres.py`: `fit(ref captures, family, groups)` and
  `__call__(CellRef) -> mu [d]`. `KeyedMean` plus a `key(cell)` covers any "mean over matching
  cells" centre; see `FamilyMean` and `TokenMean`. Register it in `CENTRES`.
- A centre sees only `CellRef`: item id, group, family, layer, read position and token, and the
  rendered context up to the cell. It never sees targets. It is fitted on `@self` (own group
  excluded) or `@fit` (held out).
- Arm name `<centre>@<ref>|<readout>`, e.g. `mycentre@fit|cos`. Add a test in `tests/test_jlm.py`.

**Multi-token families** (typo_mt, multihop_mt, basic_readout_mt, multilingual_mt; 2026-10-10)
- A J-lens token bag can never spell a multi-token form, so the bench's "regex" families judge bags
  through its LLM summarizer and then the regex (`jlm.judge` adapter). That costs about $0.07 per
  `val` arm with Haiku, so judge every centre on these families.
- Free score: the distinctive-piece proxy (`jlm.mtproxy`). It credits a form when one of its
  pieces of at least 3 characters, not occurring in the prompt, is in a top 10. Every required
  unit must hit at one layer. Item kappa against the judge is 0.21-0.68, and it is neither a lower
  nor an upper bound. At arm level it moves the same way as the judge in all four families: use it
  as a first look only.
- Dev banks: new, authored in the bench's schema (`data/dev/mt-authoring/`) and validated with the
  bench's own contract and token-count stamp (`experiments/build_mt_dev.py`). They are gated with
  the bench's own questions (`wsbench.capable`) on the 27B, greedy plus at least 8/10 at T=0.7,
  graded by Haiku with the bench's grading prompt; multihop bridges must pass too. Pass rates:
  typo_mt 93/100, multihop_mt 79/100, basic_readout_mt 97/100, multilingual_mt 107/200 (two rounds;
  batch 1 lost many items to ambiguous prompts). fit / val: 48 / 45, 40 / 39, 49 / 48, 54 / 53.
- Results on val, cos, Haiku judge: uncentred -> fam@fit is typo_mt 0.18 -> 0.51, multihop_mt
  0.28 -> 0.23, basic_readout_mt 0.40 -> 0.58, multilingual_mt 0.21 -> 0.34. That is the same
  pattern as the single-token families: centring helps everything except multihop.

**Known gaps** (not blocking the 11 families)
- multilingual_multihop and multilingual_typo: no dev banks yet.
- Captures hold only the read cells. Centres that need other positions (g(h_t, h_{t-1}, ...)
  beyond the read span) or other corpora (G1 / G2-style corpus means, neutral contexts) need a new
  capture type: a pod run per corpus.
- Captures live only in `out/` on the Mac (git-ignored, about 1.5 GB). Another machine needs them
  copied or re-captured. Tooling for a shared store exists now: see "Shared data on Hugging Face".
- `tok` arms were not run on the 5 single-token families yet. They are cheap to add in the next
  screen.
- The pinned Gemini path is only smoke-tested (33 calls), not run on a full arm.
- No registration has been written for this pipeline yet. Register the first mu experiment in
  `jle`'s style before reading its bench numbers.

## Shared data on Hugging Face

GitHub holds code, notes and small data (`data/`). Everything under the git-ignored `out/` goes to
one private HF **dataset** repo, through `tools/hfdata.py` (`src/jlm/hfdata.py`). The repo mirrors
`out/` (`out/eval/typo/val/...` <-> `eval/typo/val/...`), so a pull drops files in place.

**Setup (once)**
1. Log in with a write token: `hf auth login` (saved under `~/.cache/huggingface/`), or
   `export HF_TOKEN=...` (pods).
2. Name the repo: `export JLM_HF_DATASET=owner/name`, or set `REPO` in `src/jlm/hfdata.py` and commit
   it (then nobody needs the env). Unset, every command except `push --dry-run` stops with a message.
3. One person runs `python tools/hfdata.py create`: private (`--public` overrides), a card with
   `viewer: false`, an empty `MANIFEST.json`. The other needs write access (org repo, or collaborator).

**Use**
```
python tools/hfdata.py status                 # per top-level dir: same / local-only / local-newer / remote-only / remote-newer / conflict
python tools/hfdata.py push --dry-run         # what would go up, per dir; --dry-run writes nothing anywhere
python tools/hfdata.py push                   # default: captures eval screen concept-labels analysis
python tools/hfdata.py push eval/typo/val     # or any subpath of out/
python tools/hfdata.py pull captures          # same paths; ctx and lens only when named
```
`--out DIR` (or `JLM_OUT`) points at another `out/`; `-v` lists every file.

**Rules**
- Never deletes, on either side. A remote file goes only by hand on the Hub (and its manifest line).
- `MANIFEST.json` at the repo root: per file size, sha256, pushed by (user@host), git branch@sha,
  time. Each push merges its entries after the upload (retried if another push lands first). Status,
  pull and the dashboard read only the manifest, never a repo listing. A push interrupted before
  its manifest commit resends those files next time (hf_xet deduplicates, so it is cheap).
- Conflicts. Each machine records in `out/.hfdata/synced.jsonl` the remote sha256 it last pushed,
  pulled or found equal (the base). Push replaces a repo file only if it still equals the base; pull
  replaces a local file only if it still equals the base. Anything else that differs is a conflict,
  left alone and listed; `--force` takes this side (push) or the repo's (pull).
- Bank summaries (`eval|screen/<family>/<split>/summary.json`) are merged, never conflicted: arms
  and paired diffs unioned as `evaluate.py` merges runs, when both copies scored the same items (else a
  conflict). Their `summary.md` is rendered from them and not shared.
- Never shared: hidden names (`.cache/` from hf_hub_download, `.hfdata/`, `.env`, `.DS_Store`,
  `.summary.lock/`), `__pycache__`, `*-limit*` smoke runs, `*.lock`, `*.log`, `*.tmp` and partial
  downloads, `*.env`. Symlinks are not followed; paths outside `out/` are refused.
- `ctx/` (every-position stores, large) and `lens/` (caches rebuilt from the HF lens) go only when
  named. Other top-level dirs (here `gate/`, `e8/`, backups) are listed as "not in scope".
- Dashboard: `hfdata.listing(prefix)` (files here or in the manifest) and `hfdata.ensure(rel)` (the
  local path, downloading that one file if only the repo has it). Offline or unconfigured they
  return what is local, never raise. Only manifest-listed files are fetched; the manifest is
  re-read at most every 5 min, and a failed call pauses remote access for 1 min.
- `tools/sync.sh` (branch `iteration`) rsyncs `out/` between the Mac and the RunPod volume; the HF
  repo is the store shared between people. From a pod: `HF_TOKEN=... python tools/hfdata.py --out
  /workspace/out push eval analysis`, then the Mac pulls. `ctx/` can stay on the volume.

**How results reach the shared dashboard (any branch).** Every pipeline step pushes what it wrote as soon as it
finishes: `evaluate.py` each bank's dir, `judge.py` each run's dir, `analyse.py` the study's dir, capture, and
any generation script that calls it, its capture (`hfdata.share`, a no-op without a dataset or a token, never fails a run;
`JLM_HF_AUTOPUSH=0` turns it off; scratch runs outside `out/` are not shared). So on any branch that has merged
eval-pipeline, a run's results land in the dataset with who pushed them and the branch@commit they ran on, and every
dashboard (hosted or local) pulls them within 5 minutes. Bank summaries merge, so two people's arms sit side by side;
the same arm on the same bank from different code is a conflict, listed by the push and left alone. The **Shared
data** page lists what arrived, from whom and from which branch. The dashboard's code is eval-pipeline merged with
the collaborators' branches (`.github/dashboard-branches`): `.github/workflows/deploy-dashboard.yml` redeploys the
Space on every push to one of them that touches it (needs the GitHub repository secret `HF_TOKEN`, a write token for
the org). Where each kind of change goes: `notes/shared-workflow.md`.

**The shared dashboard** (one copy for everyone, always on): https://huggingface.co/spaces/[org]/j-lens-mean-dashboard,
private to the org (dataset: `[org]/j-lens-mean-data`). The repo's dashboard runs unchanged as a Docker Space
(org Spaces need HF's Team plan; [org] has it). By hand: `python tools/deploy_space.py --space
[org]/j-lens-mean-dashboard --dataset [org]/j-lens-mean-data` (merges the listed branches from origin;
the workflow does the same on every push). It needs the Space
secret `HF_TOKEN` (a READ token for the dataset; Space settings, or `--read-token-env VAR`). Whoever
runs experiments pushes (`tools/hfdata.py push eval analysis`, captures when new); the dashboard,
hosted or local, pulls results itself on start and every 5 min (`dashboard/hfsync.py`, sidebar shows
the last sync) and fetches captures only when a page rebuilds centres from them. Checked: every page
runs in a clean env with only the Space's requirements (CPU torch, empty model cache).

Dry run on Maya's box (2026-10-11, empty remote): captures 92 files 3.9 GB, concept-labels 40 /
61 kB, eval 1784 / 617 MB; 1916 files, 4.5 GB. Excluded: one `-limit3` judge run (2 files). Not in
scope: `screen-premerge` 777 / 309 MB, `lens` 11 / 11 MB, `eval-judged-readouts-backup` 4 / 9 MB,
`gate` 1 / 27 kB, `e8` and `x8-gen-resume.log` (logs only).

## Stages

| stage | module | where | output |
|---|---|---|---|
| banks | `jlm.banks` | anywhere | bench `items.json` in place; dev banks `data/dev/<family>/{fit,val}.json`, same format |
| capture | `jlm.capture`, `experiments/capture.py`, `tools/capture_pod.sh` | pod | `out/captures/<family>-<split>.pt` (umot `ItemCapture`, bf16); umot's bench captures are read in place (`LEGACY`) |
| centre | `jlm.centres` | Mac | `fit(reference captures)` then `mu(CellRef)` |
| read | `jlm.lens`, `jlm.read` | Mac | `out/eval/<family>/<split>/<arm>/readouts.jsonl` (bench contract) and `ranks.jsonl` |
| score | `jlm.score`, `experiments/evaluate.py` | Mac | strict pass rate, CI, paired diffs vs `zero`, median best target rank; `summary.{json,md}` |
| judge | `jlm.judge` | Mac + API | the bench's judge on any bank; `results.json` and `cells.jsonl` (verdict cache) |

An **arm** is `centre[@ref]|readout`, for example `fam@fit|cos`:
- `ref` is the split the centre is fitted on. `self` means the read bank, with the cell's own item
  always excluded, so `fam@self` is jle's loo1 and `fam@fit` read on `val` or `bench` is its dev1.
- The readout is `cos` (the bench's) or `rms` (jle's).

## Splits and rules

- `fit`: fit centres, choose among arms, free scoring only. `val`: confirm with the judge. `bench`:
  once per registered method.
- A centre sees a `CellRef` (item id, family, layer, read position and token, prompt context up to
  the cell), never the targets.
- Dev items may not share a target with the bench (`target_in_bench` items are dropped on import).
  The exception is user_modeling: its targets are values of closed attribute sets (every Gender
  item is "male" or "female"), so overlap is kept. No dev prompt reuses a bench prompt (checked).
- Judge spend: dry run, then `limit=3`, then an estimate; ask before more than about $5 or a full arm.

## Scoring tiers

- Free: jle's strict rule (whole top-10 token equals a target) on jle's confirmatory subset
  (reachable, not leaky, basic_readout without implicit items), plus the full-vocabulary target rank.
  These are our numbers, not WorkspaceBench scores.
- Free, strict + forms (2026-10-11, `jlm.forms`): strict with each target's other forms accepted too,
  so `swims` passes a `swimming` item. The forms are inflections in every single-token family, and in
  association also words derived from the target that name the same thing (swimmer, miner). They come
  from a reviewed table, `data/forms/<family>.json`: a Haiku 5.5 draft ($0.01) cleaned by the rules in
  `experiments/build_forms.py --clean`, which keep only regular inflections and listed irregular forms
  outside association, and drop numbers, other senses and translations by hand. The leak exclusion uses the added
  forms too, so its scored set can be smaller than strict's. Target ranks stay on strict's forms.
  Strict stays the score of record, so past studies remain comparable. In `summary.json` the new score is
  each arm's `forms` block, with `diffs_forms` beside it. Every bank also reports both scores on its
  reachable items alone (`strict_reachable`, `forms.reachable`, `n_reachable`): on
  directed_modulation only 27 of 74 scored val items have a single-token target. `evaluate.py`
  writes these for new arms; `evaluate.py --rescore` recomputes them for every stored arm from
  its readouts, with no lens and no forward pass (about 25 s a bank). An `evaluate.py` process
  started before this change drops the fields when it rewrites a summary: rescore afterwards.
- Judged: the bench's pinned judge. For J-lens token bags the multi-token families' "regex" contract
  calls the Gemini summarizer first, so they are judged too. The free tier for them will be the
  regex on the raw bag only.
- Before trusting the free tier on a family, judge one dev arm and measure its agreement with strict.

## Status

- typo, bench parity with jle x100 (2026-10-10, umot's bf16 bench captures, 11-layer grid). Strict
  pass rates are identical: `zero|cos` 0.54, `zero|rms` 0.32, `fam@self|cos` 0.78, `fam@self|rms` 0.84
  (x100: none 0.54 / 0.32, loo1 0.78 / 0.84). Median best rank is within 1 (7.5 / 25.5 / 1.5 / 0.5
  against 6.5 / 25 / 1.5 / 0). Probable cause: jle captured in fp32 and these captures are bf16.
- typo dev: `fit` / `val` imported from jle bank-v2 (94 / 93 items) and captured on the pod
  (2026-10-10, `out/captures/typo-{fit,val}.pt`; pod note: `/workspace` there is a quota-limited
  shared mount, so `HF_HOME` must be on the container disk).
- typo, held-out centre (strict, ours). On `val` (91 scored, 2 leaky items excluded): `zero` 0.69 / 0.57
  (cos / rms), `fam@fit` 0.92 / 0.90. On the bench: `fam@fit` 0.76 / 0.82, against x100's dev1
  0.78 / 0.82 (dev1 was fitted on the whole dev bank, `fam@fit` on its A half only).
- Judge adapters: the single-token bank-judge families and user_modeling (its `load_bank` is
  pointed at our bank for the call; test in `tests/test_jlm.py`). Owed: directed_modulation (a
  module-level `BANK`), the multi-token families.
- association, basic_readout, multihop, multilingual (2026-10-10): dev banks imported from jle
  bank-v2. Items sharing a target with the bench were dropped (basic_readout lost 77, multilingual 13,
  multihop 1). Multihop dev items read the last word, as on the bench; the rule reproduces all 100
  bench offsets. All 12 banks (fit / val / bench) were captured on the pod.
- Scored subset: jle's x89 rule. "Unreachable" means no target is a single word. Items whose
  single-word target takes several tokens are scored but cannot pass (association bench: 20 such
  items). An earlier version also excluded those items: association bench n was 78, not jle's 98.
- Bench parity with x100 (strict, ours). The n's match for all five families. `zero` and `fam@self`
  are equal to x100's none / loo1, or one item off: multihop zero, association fam@self|rms,
  multilingual fam@self|cos. `fam@fit` is within one item of x100's dev1, which was fitted on the
  whole bank-v2 rather than the filtered `fit` half.

### Results so far (J-lens n1000; strict, ours; family mean fitted on `fit`)

| family | val n | val zero / fam@fit (cos) | Haiku zero / fam@fit (cos) | bench n | bench zero / fam@fit (cos) |
|---|---|---|---|---|---|
| typo | 91 | 0.69 / 0.92 | 0.74 / 0.97 | 100 | 0.54 / 0.76 |
| association | 102 | 0.41 / 0.75 | 0.43 / 0.80 | 98 | 0.38 / 0.55 |
| basic_readout | 35 | 0.91 / 0.91 | 0.91 / 0.97 | 68 | 0.93 / 0.99 |
| multihop | 83 | 0.63 / 0.61 | 0.69 / 0.70 | 94 | 0.80 / 0.77 |
| multilingual | 82 | 0.98 / 0.95 | 0.98 / 0.95 | 100 | 0.94 / 0.92 |

- Strict vs Haiku on `val`: no item passes strict and fails the judge in any family.
  Strict is a clean lower bound. The judge's margin is 0-0.08; the largest is on multihop,
  where the judge also credits inflections and aliases. Item kappas are 0.81-1.00, except near
  ceiling (basic_readout fam@fit|cos 0.48, from 2 discordant items).
- One mean per layer helps typo and association a lot, is near ceiling on basic_readout, and
  slightly hurts multihop and multilingual, as jle found. Per-arm details:
  `out/eval/<family>/<split>/summary.md` and `<arm>/agreement-judged-claude-haiku-5.5.json`.

- Owed: a dev DM bank (umot's mention-control set is built from the bench's DM pairs, so it is not
  held out); a context window in captures for context-dependent mu; a regex free scorer for the
  multi-token families; concept-aware exclusion (umot `Centre`) for DM.

## Judge runs

The OpenRouter account caps the pinned Gemini 3.8 Flash at 20 requests per minute
(`new-account-rpm`, measured 2026-10-10: 30 concurrent calls gave 20 x 200 and 10 x 429). The key is
paid with a $100 cap. Development judging therefore uses Haiku 5.5 via OpenRouter (unpinned), as in
umot. `experiments/judge.py` defaults to it at 1200 rpm with 64 calls in parallel. **Lifted (measured 2026-10-11):** 60 concurrent calls to `google/gemini-3.8-flash` all returned 200 in 12 s ($0.0009); the key reports no request limit (paid, $50 spend cap). Pinned judging now runs at the pipeline's concurrency; the constraint is the spend cap.

| date | bank | arms | judge | calls | spend |
|---|---|---|---|---|---|
| 2026-10-10 | typo/val | zero\|cos smoke (3 items) | gemini-3.8-flash (pinned) | 33 | $0.018 |
| 2026-10-10 | typo/val | zero\|cos, partial | gemini-3.8-flash (pinned) | about 70 | about $0.04 |
| 2026-10-10 | typo/val | zero, fam@fit x cos, rms, full | haiku-5.5 (unpinned) | 4 x 1023 | about $0.48 |
| 2026-10-10 | association, basic_readout, multihop, multilingual /val | zero, fam@fit x cos, rms, full | haiku-5.5 (unpinned) | 4 x 3322 | $1.50 |
| 2026-10-10 | user_modeling/val | zero\|cos smoke (3 items) | haiku-5.5 (unpinned) | 693 summaries + 693 MC | $0.23 |
| 2026-10-10 | user_modeling/val | zero\|cos, layers 24/36/48/60 | haiku-5.5 (unpinned) | about 5.3k | $1.80 |
| 2026-10-10 | directed_modulation/val | zero\|cos smoke (3 items), 4 layers | haiku-5.5 (unpinned) | 104 | $0.03 |
| 2026-10-10 | directed_modulation/val | zero\|cos, tok@fit\|cos, layers 24/36/48/60 | haiku-5.5 (unpinned) | about 2.7k each | $1.70 |
| 2026-10-10 | directed_modulation/val | zero\|rms smoke (3 items), all layers | haiku-5.5 (unpinned) | 284 | $0.08 |
| 2026-10-10 | directed_modulation/val | zero\|rms, all 11 layers, stopped part way (moved to the agreed 4 layers; its 1,041 verdicts at those layers reused) | haiku-5.5 (unpinned) | 2,870 | about $0.82 |
| 2026-10-10 | directed_modulation/val | x7: zero, tok@fit, dict:strat:0.5@fit, dict:derang:0.5@fit x rms, layers 24/36/48/60 | haiku-5.5 (unpinned) | about 2.7k each | $2.93 |
| 2026-10-11 | directed_modulation/val | x12: genk:8, genfam, gen, glos:word, glos:desc, glosx:desc @self x rms, layers 24/36/48/60 (constant-mean-exploration) | haiku-5.5 (unpinned) | about 2.7k each | $4.96 |
| 2026-10-10 | 4 multi-token dev gates | grading distinct answers (5 rounds) | haiku-5.5 (unpinned) | about 1.3k | $0.11 |
| 2026-10-10 | typo_mt, multihop_mt, basic_readout_mt, multilingual_mt /val | zero\|cos, fam@fit\|cos (summarizer + regex) | haiku-5.5 (unpinned) | about 4k summaries | $0.55 |

typo/val, Haiku vs strict, 91 scored items (`experiments/agreement.py`):

| arm | strict | Haiku | gap | kappa (items / cells) |
|---|---|---|---|---|
| zero\|cos | 0.692 | 0.736 | +0.044 | 0.89 / 0.94 |
| zero\|rms | 0.571 | 0.593 | +0.022 | 0.95 / 0.98 |
| fam@fit\|cos | 0.923 | 0.967 | +0.044 | 0.58 / 0.79 |
| fam@fit\|rms | 0.901 | 0.956 | +0.055 | 0.59 / 0.86 |

- No item passes strict but fails the judge: strict is a clean lower bound on typo.
- The centred kappas are lower only because both rates are near ceiling. There, 4-5 discordant items
  move kappa a lot.
- Where the judge passes and strict does not, there are three kinds of case:
  - Inflections the rules allow ("mattered", "suggestions").
  - Byte-level CJK tokens, which Haiku decodes and credits: `å¸¸è§ģ` = 常见 for "common",
    `æķĻå¸Ī` = 教师 for "teacher". So the judge can credit translations in these token bags after all.
  - Judge errors against its own rules: crediting the prompt's own misspelling echoed back
    ("posible", "difer") and derived words ("handshake" for "hand").
- Centring's gain is the same under both scorers (cos: +0.23 strict, +0.23 Haiku).
