# unverbalized-motivations

Can activation readers surface **motivations Qwen3.6-27B acts on but does not verbalize**? Exploration
stage of a research project. The user's scope below takes priority over the
background ideas from our notes.

This is an exploration repo: speed and finding signal matter, but every number must be traceable
(pins + provenance) and every reader must be compared on equal terms.

## Goals (preliminary, not exhaustive)

1. **A clean comparison harness.** Any reader (lens, NLA, oracle/modulation lens, blackbox prompt)
   plugs into the same pipeline, reads the same cells, emits the same readout format and is scored
   the same way. Adding a new reader or a new read strategy should be a small, local change.
(In j-lens-mean, umot's `notes/` and `dashboard/` stay upstream in unverbalized-motivations: the paths
below refer to that repo.)

2. **Candidate examples** of unverbalized motivations surfaced by these tools (`notes/findings.md`).

Likely later directions (not current work): our own evals of how well tools surface unverbalized
motivations, applying the tools to new settings, Liar's Bench, better inference-time scaffolds.

## Current scope

- **Model:** `Qwen/Qwen3.6-27B` (pinned in `src/umot/provenance.py`). **Thinking mode off**
  (`enable_thinking=False`), matching the bench's chat render.
- **Data, phase 1: WorkspaceBench** (`third_party/workspace-bench`, pinned commit), three families
  only:
  - `agentic_misalignment`: 32 scenarios where Qwen actually misbehaved; the main target.
  - `moral_rationale`: 200 one-token dilemmas; does the reader surface the driving reason.
  - `directed_modulation`: 100 items; a **sanity check** that each reader works at all.
- **Data, phase 2: Liar's Bench** (paper at repo root, `2511.16035v2.pdf`). Not started; the details
  will be decided with the user once phase 1 works end to end. Known constraint: its released
  transcripts come from other models, so it must be regenerated on-policy for Qwen3.6-27B.
- **Start simple:** read single tokens at the bench's standard read sites before anything fancier.
- **System prompts:** follow each dataset's own conventions (the bench and Liar's Bench use system
  prompts in some scenarios; that is fine). Scenarios **we** write use **no system prompt**, to avoid
  moving the model along the Assistant axis or inducing roleplay.

## Readers

Readers whose output is a token list: logit lens, **J-lens** (including the centred version, and
edits to its singular values), R-lens, and template lens (only if fully released). Readers whose
output is prose: **NLA**, **oracle / modulation lens**, and the **blackbox** arm (append a
family-specific prefill to the bench's render, e.g. `My motivation is:` for agentic misalignment,
and let the model continue; prefills live in `umot.blackbox.PREFILLS`). The blackbox arm is the
baseline every white-box reader is compared against.

| Reader | Checkpoint (all pinned in `PINS`) | Layers | Notes |
|---|---|---|---|
| logit lens | the model's own unembedding | any | |
| J-lens | `neuronpedia/jacobian-lens` `qwen3.6-27b/.../Qwen3.6-27B_jacobian_lens_n1000.pt` (the bench's default) | 0..62 | Bench readout of record is the cosine `(W_U J_l h) / ‖J_lᵀ W_U[t]‖`; float64 for any SVD/edit algebra |
| R-lens | `camilablank/workspace-lenses` `qwen3.6-27b/r-lens` | | RelP Jacobian lens, same output shape |
| NLA | `ceselder/qwen3.6-27b-nla-rl` (av_base + `av_rl_adapters/iter_000400`; activation reconstructor in `ar_reconstructor/`) | **42 only** | Gets the theme right, often confabulates specifics |
| oracle lens (olens) | `ceselder/olens-rl-grpo-trajectory-qwen36-27b` (GRPO trajectory, `step_00010`..`step_00390`; default `step_00390`) | 42 | LoRA; injects L42 at marker `㈜` (id 158983) at block-1 output, emits four bullets on what the model is about to generate. **Injection mode not documented**: both `add_normmatched` and `replace` are arms until one is confirmed |
| modulation lens | `ceselder/modulation-lens-meta-model-qwen36-27b` | 42 | A separate lens. Its prompt and injection are part of the lens (see its model card); writes a ≤16-token phrase |
| bench `olens` arm | `agu18dec/local-workspace:ckpts/ao/rl/s3d.ddp600.s0/iter_000600` | | The bench's own oracle-lens checkpoint; use it to reproduce bench numbers, not as our default |
| skip-lens | `ceselder/skip-lens-qwen36-27b-RL-surprisal` | 42 (trained at 62) | Extra reader, not yet in scope |

Injection-based readers (NLA, oracle lens, modulation lens) fail **silently** when the injection does
not happen: the text still looks fluent. Every new reader path gets a check that the activation
actually changes the output (e.g. compare against a zero or shuffled vector).

**Read strategies.** Phase 1 uses the bench's standard read sites and readout mechanism. The harness
must make it easy to add alternatives as new arms: multiple layers or tokens, sampling N times with
majority vote or LLM summarization, ranking NLA samples with the activation reconstructor. The
**no-peeking rule** applies to all of them: an aggregation may use anything except the
answer. Majority vote is fine; best-of-N against the label is not.

## Architecture

- `third_party/workspace-bench`: pinned, read-only. We use its read plan, render and position rules,
  `Backend.capture`, token-lens methods and `wsbench judge` / `report`. Its readout JSONL contract
  (one row per `(id, layer, pos)` with `samples` or `tokens`/`scores`) is **our** interchange format.
  Its loaders download from `main`; ours load at the pinned revisions instead.
- `src/umot/capture.py`: residuals at the bench's read cells, grid layers + 42, stored once in
  `out/captures/` (bf16, lossless) so every reader reads identical activations.
- `src/umot/readers.py`: token readers (the bench's methods, unchanged) and one batched
  `Verbalizer` for every injection reader, configured by a `VerbalizerSpec`, with
  `next_token_logits` as the injection check.
- `src/umot/arms.py`: the named arms. `src/umot/blackbox.py`: the prefill arm.
- An **arm** = reader + checkpoint + layers + read sites + sampling + aggregation, named once and
  recorded in provenance. Layout: `out/readouts/<arm>/<family>.jsonl` (+ `.provenance.json`) and
  `out/judged/<arm>/<family>/`. New read strategies are new arms; nothing else changes.
- `dashboard/`: Streamlit dashboard (`streamlit run dashboard/app.py`). It reads `out/`, the bench and
  `notes/` on load, so new arms and families appear without code changes. When a milestone moves,
  update `dashboard/plan.py`; when a reader or family joins, add it to `dashboard/catalog.py`; a new
  page is a file in `dashboard/views/` listed in `app.py`.
- `experiments/m1_run.py`: capture + every reader for one family (stages, resumable).
  `tools/m1_pod.sh`: the same on the pod. `tests/`: anything needing a model is marked `slow`
  (runs on the cached Qwen3.5-0.8B on CPU in a few minutes).

## Rules

- **Never edit `third_party/` or the bench's judge prompts.** To change behaviour, wrap it in
  `src/umot`.
- **Provenance:** results go through `umot.provenance.write_artefact` (git SHA, dirty flag, host,
  model and reader revisions, dataset, seed, run settings). Bumping a pin is deliberate and noted in
  the research log.
- **Judge spend.** Judging costs real money; be cost-effective.
  - Before any judged run: `dry_run=True`, then a `limit=3` smoke test, then a cost estimate from the
    smoke run's spend (`run.json`).
  - **A full arm, or any run estimated above ~$5, needs the user's go-ahead.**
  - `agentic_misalignment` is pinned to `claude-sonnet-5` and takes ≈51k calls per prose arm; never
    run it unrestricted. Use `limit=`, `items=`, `layers=` and `opts=stride=N`.
  - Record every judged run's spend in `notes/judging.md`.
  - **Development judge: Haiku 5.5 via OpenRouter for every family, AM included**
    (`judge_model=anthropic/claude-haiku-5.5`; user decision 2026-10-08). Always run it as
    `python -m umot.judge judge ...`: it loads `.env` and drops the `temperature` Haiku rejects.
  - **Available, not the default:** the Anthropic API (`judge_model=claude-haiku-5-5`) paid from the
    a paid plan's API credits (expire each cycle). Use it only when the user asks; it
    is also the route to the **pinned** AM judge (`claude-sonnet-5`). `umot.judge` prints Anthropic
    token usage and cost at the end of a run. Its numbers are
    **unpinned** (the bench marks them `pinned=False`): label them so and never compare them with
    published bench numbers. Check its agreement with the pinned judge on a small sample before
    leaning on it.
- **Numbers are ours, not "WorkspaceBench scores",** unless produced by the bench's pinned judge on a
  full family. Always give `n` and the bench's floors (lucky-guess and prompt-only) beside a rate.
- **Candidate findings** go in `notes/findings.md` using its template: the prompt and read site, every
  reader's output, the blackbox output, and whether the motivation appears anywhere in the model's
  visible output. Treat a reader's claim as a hypothesis until it beats the blackbox baseline and
  survives a control (the same reader on a matched case without the motivation).
- **Research log:** `notes/research-log.md`, append-only and dated (take the date from `date`). Record
  what was run, what was seen and what was decided. Null results count.
- **Secrets** (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `HF_TOKEN`) live in the gitignored `.env`
  (or the environment); never print them or write them into files, logs or commits.

## Machines and setup

`notes/setup.md` has the full setup guide, including for a new collaborator on other hardware.

- **Mac** (16 GB): development, tests, judging, analysis. It cannot run the 27B model.
- **RunPod**: all 27B work. Code reaches the pod through git (commit and push locally, pull on the pod;
  never author code on the pod). Artefacts come back with rsync, **never `--delete`**. Run long jobs in
  tmux. **Stop the pod as soon as runs finish.**
- Code must not hard-code machine paths: repo-relative paths, `HF_HOME` from the environment, and
  `--device` on every script that runs a model.
- `bash tools/bootstrap.sh` sets up any machine. VS Code activates `.venv` in new terminals.

## Ask rather than guess

- Starting a full judged arm, or anything that spends more than a few dollars.
- Changing a pin, a dataset's prompt convention, or the read sites of a standard arm.
- Which olens trajectory step to use, if not the default `step_00390`.
- Anything about Liar's Bench design (phase 2).
