# The research loop for mu

How we search for better readouts `J_l (h_l - g)`. This page is the process; the ideas and results live in
`notes/iteration-anthony/mu-log.md` (backlog, study index, leaderboard pointer) and `notes/iteration-anthony/studies/<id>.md` (one file per
study). Agreed with the user 2026-10-10. The process is itself under iteration: change this page when a
rule stops serving us, and say so in the log.

## Starting a session (each instance)

1. `ListAgents` (your name is the session's `j-lens-mean-xx`); `python tools/board.py show` (who does what, the
   Mac lock, free memory, tonight's spend).
2. `git worktree add -b wt/<name> ../jlm-<name> iteration` (or reuse yours) and work there; land commits locally
   (see "Git" below); `ln -s ~/j-lens-mean/out out`
   for read access to the Mac's results.
3. Read `notes/iteration-anthony/mu-log.md` (backlog, studies) and the study files of what is running. Pick or write a card,
   claim it (`status: running (<name>)`, commit and land), `python tools/board.py set <name> study=<id> status=working`,
   and send one line to the other instances.
4. Run (with a watcher on every long job: see "Watching runs"), analyse, write `notes/iteration-anthony/studies/<id>.md`, update the card, the board and the ledger; commit and land.

## The space of g

"mu" is shorthand. Anything of the form `J_l (h_l - g)` is in scope, where g may depend on the state
itself, on earlier positions, on the rendered context, on other layers, on reference corpora, or on
anything else that is not the answer. The user wants us to go wild here: means are one category among
many, and both within-category and cross-category exploration are wanted. A non-exhaustive map:

| category | g is ... | examples |
|---|---|---|
| constant / keyed means | a mean over matching reference cells | family, token, position, cluster, neutral-context, corpus means |
| controls | something that should not help | random vector of matched norm, shuffled mean |
| functions of h | a map of the state itself | projection onto a "background" subspace (top PCs, the template subspace), a regression of h on its predictable part, shrinkage `g = a h + (1-a) mu`, nearest-neighbour or kernel means in h-space, an autoencoder's reconstruction of the generic part |
| functions of the context | built from earlier positions | self-truncation, EMA / attention-weighted average of earlier states, a linear predictor of h_t from h_{<t}, the same cell under a counterfactual prompt |
| across layers | built from other layers | the state at an earlier layer transported forward, the inter-layer residual update only |
| semantic / steering | concept directions | an abstract category word, a steering vector, scaled |
| learned | a small model fitted on dev data | trained to make `J(h - g)` decode the template prior away, with no targets in the loss, or with targets on `fit` only and judged on `val` as a method |

A few of these are not literally "subtract one vector" (e.g. a projection removes a subspace). That is
fine: the bar is that the readout stays a lens, i.e. `J_l` applied to a transformed state, and that the
transform is fair (below).

## Objective

**Pass@10 on WorkspaceBench**: an item passes when a target is in the top 10 of the readout at any of its
read cells at any grid layer (the bench's item rule). We measure it in three tiers:

| tier | what | cost | use |
|---|---|---|---|
| strict | whole top-10 token equals a target (`jlm.score`); piece proxy on `_mt` | free | screening on `fit`; a clean lower bound on the 5 single-token families, **not** a proxy on user_modeling or DM |
| dev judge | Haiku 5.5 via OpenRouter (unpinned) | about $0.1-2 per arm | confirming on `val`; the only usable score on UM, DM and `_mt` |
| pinned judge | the bench's Gemini 3.8 Flash (20 rpm) | about an hour per arm | numbers of record, finalists only |

Headline: the **macro-average over families** of the gain against the reference arms (`fam@fit|cos`,
and `tok@fit|cos` where it is better), with a **no-harm guardrail**: no family drops outside its paired
bootstrap interval. basic_readout and multilingual sit near ceiling and mostly act as guardrails.

**Single-family studies are fine.** A mu that only fixes multihop, or a deep dive into why centring
fails on multihop, is a legitimate study. Report it against that family's pass@10 and still run the
guardrail on the others, so we know what it costs elsewhere.

## The cycle

Each iteration has three steps. They need not be strictly sequential: an analysis can spawn three ideas,
and a promising thread can be followed off-plan (see "Straying").

### 1. Ideate: the idea card

One entry in the backlog of `notes/iteration-anthony/mu-log.md`:

```
### <id> <short name>                    status: idea | queued | running | done | dropped
- Counterfactual: what "h without the content" this mu stands for (the Taylor reading: J(h - mu) ~ f(h) - f(mu)).
- Mechanism: why it should move pass@10, and on which families; which it could hurt.
- Cost: offline (existing read-cell captures) | new capture (what, how big) | needs an API.
- Fairness risk: could it see targets, or subtract / echo the prompt? How we check.
- Controls: the standard suite plus this category's controls (see "Controls"), named before the run.
- Prediction: written before the run (direction and rough size per family). Never edited afterwards.
- Source: user | synthesis | study <id> insight <n>.
```

Prioritise ideas that are cheap, fair by construction, and teach us something whatever the result. Where an idea came from (the user, the synthesis, a study) gives it no priority: every card competes on these terms.
Every card names its controls before it runs; a result without its controls is not a result.

### 2. Run

1. Implement g as a centre class (`KeyedMean` covers any "mean over matching cells"; a g that needs the
   state or earlier positions uses the extended interface, see the log's infrastructure list), registered in
   `CENTRES`, with a test. Study-specific centres go in `src/jlm/mu/<study>.py`, which keeps conflicts
   in the shared `centres.py` small.
2. **Screen**: strict on `fit` (read on `fit` with `@self`, i.e. leave-one-group-out), all 11 families,
   both readouts if cheap. Pick hyperparameters here and only here.
3. **Confirm**: survivors are read on `val` with `@fit`, with strict + Haiku. Haiku is mandatory on UM,
   DM and `_mt`, and wherever strict and the judge might disagree.
4. **Record**: the OUTCOME under the prediction, the numbers from `report.py`, and the artefact paths.
5. **Bench**: only a finalist, after its registration is written (jle's REGISTERED / OUTCOME convention,
   kept light). Bench reads are batched and rare; the bench is never used to choose.

### 3. Analyse

**Standard battery**: run for every confirmed arm (`experiments/analyse.py`, to be written; outputs under
`out/analysis/<study>/` for the dashboard to read):

- Per family: pass@10 and paired differences against the references, with the item lists of wins and
  losses (`zero` -> new and reference -> new).
- Per layer: the pass curve, and the distribution of the first passing layer.
- Ranks: the change in best target rank per item (a histogram), separating "moved into the top 10" from
  "improved but still outside".
- **What mu removes**: the top tokens of `L(mu)`, `||mu|| / ||h||`, the fraction of `||h||` removed, and
  the cosine to the reference mus per layer.
- **The standard control suite** (see "Controls"): prompt echo, prompt-masked pass@10 and the next-token
  overlap come free with every `evaluate.py` run; shuffled and random g are arms of their own
  (`shuf.<centre>@...`, `rand.<centre>@...`), evaluated next to the arm.
- Slices: read token, target frequency (corpus rank), target tokenisation, prompt length, read position
  type, and item difficulty under `zero`.

**Deep dive**: the bespoke part, specific to the study. Look at the actual readouts (the Passage ->
readouts page), find the items that flip, and ask why. Try novel cuts. Its output is a short list of
**insights**, each one a falsifiable statement about the readout, with the evidence. Every insight points
at one or more next idea cards or says why it does not. That closes the loop.

## Controls

The failure we fear most is a g that scores by **surfacing the prompt** (or the model's own next-token
guess) rather than what the model holds unsaid. Tighter matching makes this more likely, not less
(synthesis, lesson 3: carpos reached DM 0.89 by reading the prompt). So controls are part of every
experiment, and which ones matter depends on what g is built from.

**Standard suite** (computed by the battery for every arm, free):

| control | question it answers | how |
|---|---|---|
| prompt echo | is the top 10 full of prompt tokens? | share of top-10 tokens that occur in the prompt, per cell and per arm |
| prompt-masked pass@10 | does the gain survive without prompt tokens? | re-rank with every prompt-content token removed from the vocabulary, take the next 10, re-score (`masked.jsonl`, judgeable). On strict-scored items it can only *raise* pass (leaky items are not scored), so it bites where a judge credits prompt words and their variants (all judged families) and where targets may be in the prompt (UM, DM) |
| next-token baseline | is it just the model's own next-token output? | overlap of the top 10 with the logit lens / the model's next-token top 10 at the cell |
| shuffled g | is it this cell's g, or any g of this kind? | give each cell the g of a random other cell (same family, layer, category), keeping the arm otherwise fixed |
| random g | is it a norm or bias effect? | a random vector (or random subspace of the same dimension) with g's norm per layer |
| zero / fam@fit / tok@fit | the reference arms | always in the report |

**Per-category controls** (the card lists which apply; add new ones as categories appear):

| category | specific risk | controls |
|---|---|---|
| keyed means (family, token) | little: the key carries no item content | random keys with the same group sizes; n-scaling (8 / 32 / all reference cells) |
| position-matched means | the same slot in sibling items holds related words, so subtracting the slot mean leaves this item's slot word: prompt reading | umot's **mention control** (held vs mentioned concept: a fair g separates them, a prompt reader does not); position-matched but token-mismatched; slot-content echo (are the hits the words at the matched slot?) |
| functions of h (projections, kNN, shrinkage) | removing "generic" leaves what is idiosyncratic to the item, which includes its prompt words; kNN neighbours can share content | random subspace of the same dimension; decode the removed component; neighbours restricted to items with disjoint prompt vocabulary |
| functions of the context (h_{<t}) | "what is new at t" is the last prompt word, or the next-token prediction | next-token baseline (critical); scrambled-context g (same words, shuffled order); mention control |
| counterfactual prompts (neutralised rewrites) | h - h_neutral is, by construction, the content that was replaced, i.e. the prompt words | prompt-masked pass@10 (critical); echo restricted to the replaced words; mention control; the rewriter never sees targets; a rewrite that keeps the content words (only style changed) as a negative control |
| cross-layer | reads only the layer's update, which can be the next-token prediction forming | next-token baseline; a random earlier layer |
| semantic / steering | the scale is a free knob; the category word may itself be a target's neighbour | a random word of matched frequency; an unrelated category; the scale fixed on fit |
| learned | fits the dev set, or learns to echo | train on shuffled targets; fit-val gap; prompt-masked pass@10 |

Echo and masking cannot catch a g that surfaces *associates* of the prompt (association's targets are exactly
that); shuffled g, the next-token baseline and the mention control address that.

**A mention-control pass counts only if the probe can be matched on context** (B and A, pilot-1): the centre's
reference set must contain the probe items' own carriers (sentences, templates), as the evaluation banks do.
Otherwise a centre that reads same-carrier neighbours passes the mention control and still reads the prompt on the
banks (knnx8 passed umot's mention bank, which shares no carriers with the dev DM bank, while 53-75 % of its DM val
neighbours shared the item's carrier). Check the overlap of references and probes before quoting a pass.

**Reading the controls.** A gain that vanishes under prompt masking, or is matched by shuffled g, or tracks
the next-token baseline, is reported as such and does not count toward the headline, however large. A gain
that survives all of them is what we are after.

## Straying

The cycle and the metrics are the base, not a cage. Follow a thread off-plan when it looks promising,
for example a pattern in the readouts that is about the lens rather than about mu, or a better scorer.
Log why, keep it time-boxed, and come back with insights in the same form as a deep dive.

## Rules that do not bend

- **No crystal ball.** g sees the cell (`CellRef`: item, group, family, layer, position, token, context up
  to the cell), the item's own states, and reference data, never the targets of the item it reads. A g
  built from an item's targets is an in-sample ceiling, labelled as such, never a method. A *learned* g may
  use the targets of `fit` items in its training loss; it is then a method only if it is scored on `val`
  and its gain survives the judge and the echo check.
- **No degenerate g.** Because g may depend on h, it can trivially shape the output (g = h - anything).
  A g must be specified before it sees a val item, with a small number of hyperparameters chosen on
  `fit`, and its gain must come with a stated mechanism.
- **Fit chooses, val confirms, bench records.** Many ideas through `val` turn it into a selection set:
  when we need fresh held-out data, author a new dev split rather than re-reading `val` endlessly.
- **Fairness.** A mu that reads or subtracts the prompt does not count, however high it scores
  (synthesis, lesson 3). Every arm reports prompt echo.
- Released lenses only (neuronpedia n1000 for the 27B). J++ is a comparison, never a centre's lens, except in
  programme LL (`local-linearisation/plan.md`), where J++'s map, our own expert Jacobians and its weights may be part
  of a readout (user, 2026-10-11). The objective there is still a better J-lens readout.
- Haiku numbers are unpinned dev numbers, never WorkspaceBench scores.

## Running several instances at once

Several Claude instances may iterate overnight in parallel. Most compute runs on RunPod; the Mac is used
when it is free.

**Shared state: the RunPod network volume `jlm-shared`** (id `[volume]`, 150 GB, datacenter US-MO-1, chosen
for its A100 / H100 80 GB stock; every pod of ours mounts it at `/workspace`, several at once):

```
/workspace/out/             the pods' out/ (each pod's /root/jlm/out is a symlink to it): captures, ctx, eval, analysis
/workspace/hf/              HF cache: 27B shards, lenses (downloaded once)
/workspace/umot-captures/   umot's bench captures (typo, directed_modulation), linked into umot/out/captures
/workspace/uv-cache/        uv's cache, so `uv sync` on a new pod is fast
```

Pods: `tools/pod.sh` (list / create / ssh-config / setup / terminate; GPU=capture for 27B forward passes,
GPU=eval for lens reads). `setup` ships HEAD as a git bundle, so commit before launching. Results come home
with `tools/sync.sh down <pod> eval analysis` (it never deletes); large stores (`out/ctx`, corpora) stay on the
volume unless a Mac job needs them. Reaching the volume needs a running pod.

**On the Mac, in `~/.jlm/`** (outside git, shared by every instance and worktree; `tools/board.py`):
`board.tsv` (who does what), `ledger.tsv` (spend), `mac.lock`, `pods.tsv` (pods created by `tools/pod.sh`).

**Budget**: **$45 per overnight session** (user, 2026-10-11; it was $30), **shared by all instances**, covering pods
and the judge. The first overnight run, `pilot-1` (started 2026-10-11 01:14), is a pilot capped at $30, not
counting the $3.86 spent building the infrastructure. Each session is started explicitly:
`python tools/board.py session <name> --cap <usd>` (default cap $45); spend counts from that moment.
`python tools/board.py check <usd>` before a paid step (exit 1 if it would cross the session's cap);
`tools/pod.sh terminate` logs a pod's cost automatically; log judge runs with
`python tools/board.py spend <instance> <study> judge <usd> --note ...`. Cross-check against the truth: the
OpenRouter key's usage and `runpodctl me`. Account credit is not a constraint: when OpenRouter or RunPod credit
runs low, tell the user and they top it up. Terminate idle pods; an instance that launches a pod owns its
termination.

Night-2 (2026-10-12): the studies cap is $50 (user); a separate study with its own budget (programme LL) runs in a
**pot** of its own: `board.py session <name> --cap 50 --pot LL=<usd>`; ledger rows and pods whose study starts with
`LL` count against the pot, and `board.py check <usd> --study LL0` checks against it.

**Overnight sessions run until the hand-over time, not until the cards run out** (user, 2026-10-12, the lesson of
pilot-1: every instance was done by 03:40 of a night that ran to 10:30). The night's cards are a floor. An instance
that finishes them keeps working until its wind-down: it finishes its studies properly (val, controls, battery, deep
dive, card), follows its own insights as new cards, tests the robustness of its best result, cross-checks another
instance's headline, and asks the steward for a card when dry. The wind-down is set by the clock (night-2: no new
paid jobs from 09:00 BST, write-ups landed by 09:45, the steward's digest by 10:00, when the user picks up). Prompts:
`notes/iteration-anthony/overnight/`.

**Coordination**:
- Each study has one owning instance. It writes only its own `notes/iteration-anthony/studies/<id>.md`, its
  `src/jlm/mu/<id>.py`, its arms (`<centre>@<ref>|<readout>`, centre names prefixed by the study when
  ambiguous) and its dashboard page.
- Shared files (`notes/iteration-anthony/mu-log.md`, `centres.py` `CENTRES`, `catalog.py`, `dashboard/app.py`): small appends
  only; commit and land promptly, rebase on conflict.
- Git: pipeline changes in their own commits, flagged "[pipeline candidate]". **Commit freely, land locally,
  push only at milestones** (a finished study, the end of a session, before something risky) or when the user
  asks. Every worktree shares this Mac's `.git`, so a landed commit is visible to every instance at once, and pods
  get code as a bundle of local HEAD: nothing needs the remote.
- Landing on `iteration` (local): in your worktree `git rebase iteration`, then
  `git -C ~/j-lens-mean merge --ff-only wt/<name>` (the main checkout has `iteration` checked out; a fast-forward
  works with uncommitted edits there as long as your commits do not touch those files; if it refuses, rebase
  again or tell the user).
- Claim before running: set the card's status to `running (<instance>)`, commit and land, so two instances do
  not run the same idea.
- Working trees: each instance works in its own git worktree on its own branch `wt/<instance>`. Two instances
  never share one checkout. `out/` is git-ignored per worktree, so point
  bulky reads at the main checkout's `out/captures` (or the network volume) instead of copying.

**The board and messages between instances.** Every instance must know what the others are doing, at
minimal token cost.

- **The board** `~/.jlm/board.tsv` (on the Mac, outside git) is the source of truth: one line per instance,
  rewritten in place by its owner, read by the others with one `cat`:
  `instance  study  status(idle|working|mac-job|pod-job)  mac_job_peak_gb  mac_job_pid  pod_id  updated  note`
  Read it at the start of a session, before claiming a card, and before any Mac job or pod launch.
  Update your own line whenever its fields change. A line not updated for 2 hours with a dead pid is stale.
- **Messages** (`ListAgents` to find the others, `SendMessage` to send) are for events the board cannot
  carry, one line each, no reply expected unless asked:
  - claiming or finishing a study ("claimed U1 position means; done S1: random g null, see notes/iteration-anthony/studies/S1.md");
  - a result that changes another instance's study ("prompt-masked pass@10 kills carpos's DM gain: relevant to your U2");
  - a request to stop or yield ("need the Mac for 10 min, ~6 GB: please hold your eval").
  Don't send progress updates, acknowledgements or summaries; those go in the study files.
  Don't wait on a reply to make progress.
- **Mac memory** (16 GB, and the user's own apps run on it too). One eval job holds W_U (about 2.5 GB),
  the lens at the grid layers and a bank's captures: budget 5-7 GB per job. So:
  - Before a Mac job, check free memory (`memory_pressure -Q` / `vm_stat`) and the board's declared peaks.
    Start only if free memory exceeds your estimated peak plus 3 GB of headroom, and at most **one heavy
    job at a time** on the Mac (take `~/.jlm/mac.lock` with flock; the holder writes its instance and pid).
  - Declare the peak on the board (`mac_job_peak_gb`), clear it when the job ends.
  - If the lock is held or memory is short, run on a pod instead of waiting. The pod is the default for
    evaluation anyway; the Mac is for light work (scoring from readouts, notes, dashboard, git).
  - Never run a 27B forward pass, a full multi-bank evaluation or a large judge cache rebuild on the Mac.

## Watching runs: catch stalls, restart crashes

Every long run (pod job, judge run, Mac job) is watched by the instance that started it, until it lands.

- **Monitor, don't sleep.** Start a background watcher (`run_in_background`, or `Monitor` with an until-loop)
  that wakes you on the run's end marker *or* a failure (`Traceback`, `Error`, a `*_FAILED` / `*_EXIT=` line).
  Watch a log that only this run writes (a fresh log file per run, or only the lines after the run started):
  a watcher grepping an old log fires on an earlier run's marker.
- **Check progress against a measured rate.** After the first units of work, measure the rate (items/s,
  banks/min, judge calls/min) and turn it into an ETA. Then check in at least every ~15 minutes: if no new output
  has appeared for twice the expected time per unit, treat it as **stalled** and diagnose. Look at GPU
  utilisation (`nvidia-smi`), CPU (`top`), file timestamps and the log tail, and **time the suspect step
  directly** before acting. Don't guess.
- **Make runs resumable and restart them.** Scripts skip finished outputs (captures, arms with readouts) and
  write atomically (`.tmp` then rename), so a crashed or killed run restarts with the same command. Chain dependent
  steps in **one** script that stops when a step fails (`PIPESTATUS`), never in two scripts where the second waits
  for a marker: a killed first step can release the second on half the data. On a crash: read the traceback, fix,
  commit, ship the fix to the pod (bundle, `git fetch` + `checkout`), rerun. If it can't be fixed in about
  30 minutes, terminate the pod, log the spend and write down what happened in the study file.
- **Pods stop billing only when terminated.** A watcher that ends (success or failure) is the cue to sync the
  results down and terminate, or to hand the pod to the next queued job deliberately.
- **Pitfalls met so far** (2026-10-10):
  - `OMP_NUM_THREADS` unset on a pod: torch's small CPU ops oversubscribe every core, and a 2-minute
    capture check took 13 minutes. It is now set in the pod environment by `tools/pod.sh`; set it in any script you launch.
  - mmap over the network volume: every row access becomes a network read. `ContextStore` loads into
    memory by default.
  - `pkill -f <pattern>` / `kill $(pgrep -f ...)` over ssh matches the ssh shell's own command line and kills
    your session. Kill by PID (`pgrep -f '^.venv/bin/python experiments/x.py'` anchored, or read the PID file).
  - A watcher whose log already contains an end marker fires at once (see "Monitor, don't sleep").
  - A worktree's `out` symlink, committed by `git add -A`, replaced the main checkout's ignored `out/` when landed
    (git treats ignored files as expendable): the Mac's results were lost and restored from the volume
    (2026-10-11). `.gitignore` now lists `out` too; still, `git status` before every commit, and never `git add -A`.

## The dashboard grows with the loop

The dashboard (`dashboard/`) is how the user builds intuition, so each study leaves something there.
- **Passage -> readouts** is the user's main hands-on page. Every new arm appears there once it has
  readouts and a `catalog.py` line. Extend it when a study needs a new view of a cell, e.g. per-layer
  rank traces, a diff of two arms' top 10, or echo highlighting.
- **Means** (new): compare centres directly, i.e. `L(mu)` decoded, norms, cosines between mus per layer,
  the reference cells behind a mu, and how mu moves with layer and with the read cell.
- **Leaderboard** (new): every arm by family and tier, generated from `out/eval` (never hand-edited).
- **One page per study** (`dashboard/views/study_<id>.py`): its question, card, battery and deep-dive
  figures, and insights, reading from `out/analysis/<id>/`.

## When an iteration is finished

The card has a prediction and an outcome; `report.py` and the battery are in `out/`; the study file has
insights with evidence and the next cards they point to; its study card (`studies/<id>.card.yaml`, schema in
`studies/CARDS.md`) carries the verdict, headline numbers, formula, diagram and arms, so the dashboard's study page
shows it; the ledger is up to date; everything is committed on `iteration`.
