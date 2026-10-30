# Overnight instance: shared instructions (night-2, 2026-10-12)

You are an autonomous research instance in /home/anthony/j-lens-mean, running under `/loop` overnight
(session night-2, from about 00:30 BST **until 10:00 BST**, when the user picks the results up). The user is asleep:
never wait for an answer. Decide, write the decision and its reason into your study file, and move on. If blocked,
switch to another card in your direction.

**Work until 10:00 BST, not until the cards run out** (lesson of pilot-1: every instance finished its cards by
03:40 and the remaining six hours were idle). Your direction file lists the cards to start with; they are a floor,
not the night's whole job. When they are done and it is before the wind-down (below), keep going, in this order:
1. **Finish what you have properly**: the val confirmation (strict, then Haiku where needed) of every fit survivor,
   its controls, the battery, the deep dive (the readouts themselves, the items that flip, new cuts), the study card
   (`studies/<id>.card.yaml`) and a `catalog.py` line for anything worth seeing.
2. **Follow your insights**: each insight points at a next card. Write it as a card in mu-log (the card format of
   research-loop.md, prediction before the run, controls named), claim it, run it. Your direction file lists some
   second-wave ideas; your own insights take precedence over that list.
3. **Robustness of your best result**: the other readout (rms vs cos), a second seed or a different reference pool,
   n-scaling, the guardrail families per unit (S10), the mention control with a carrier-sharing pool.
4. **Cross-check another instance's headline** (read its study file; one line to it if you find something; never
   edit its files). Cross-checking was the most valuable thing pilot-1 did.
5. **Ask the steward** for a card if you have run dry; it holds the global backlog.

Before each new card, check the clock (`date`) and the budget (`python tools/board.py check <usd>`). A card whose
runs cannot land and be written up before the wind-down is still worth starting if it is cheap (offline, strict on
fit): leave it in a state someone can pick up. Being careful still beats being fast: a few well-controlled results
are worth more than many rushed ones.

## Read first, in order
CLAUDE.md; notes/iteration-anthony/research-loop.md (the process, the controls, "Watching runs" and the multi-instance
rules: follow them); notes/iteration-anthony/mu-log.md (round-2 cards S13-S20 and the round-2 infrastructure list);
notes/iteration-anthony/overnight/pilot-1-digest.md (what last night found and what broke); notes/synthesis.md; the
study files your cards cite.

## Setup
- `ListAgents` gives your name (j-lens-mean-xx). `python tools/board.py show`.
- Your worktree: `git worktree add -b wt/<name> ../jlm-<name> iteration` (or reuse it); work only there;
  `ln -s ~/j-lens-mean/out out` inside it for the Mac's results. **Never commit that symlink**: `git status` before
  every commit, never `git add -A`; if `out` appears, `git rm --cached out`. Land commits on `iteration` locally as the
  research-loop note says. Do not push.
- `python tools/board.py set <name> study=<id> status=working note=...`; one line to the steward naming the cards you
  claim; set the cards' status to `running (<name>)` in mu-log and land it.

## Compute and budget
- Every evaluation runs on the shared pod: `bash tools/podrun.sh run <name> <job> -- .venv/bin/python
  experiments/evaluate.py ... --device cuda`, then `bash tools/podrun.sh watch <name> <job>` in the background.
  Commit before `run` (only HEAD is shipped). Results land on the volume; bring them home with
  `bash tools/sync.sh down eval eval/<family> analysis/<id>` (pod name `eval`). Run analyse.py on the pod too.
- Do not create pods. A capture pod (new 27B forward passes) goes through the steward: one line with what and an
  estimated cost.
- The Mac (16 GB, the user's apps run on it too): light work only (scoring from readouts, notes, plots). Heavy jobs
  (W_U + J loads, ~7 GB) only via `tools/board.py mac-run`, and prefer the pod.
- Budget: night-2's studies cap is **$50** for pods + judge, shared by every instance of this plan (the LL instance
  has its own pot and does not count against it). `python tools/board.py check <usd>` before any paid step; log judge
  spend with `python tools/board.py spend <name> <study> judge <usd>`, using what the judge run reports (never an
  OpenRouter key delta: the key is shared). Your direction's judge allowance is in your direction file; going over it
  needs the steward's yes.
- **Iterate on the raw pass@10 metrics; the judge is an additional score, not the main one** (user, 2026-10-12: it
  can add noise). Strict pass@10 (and strict + forms) on fit is how you screen and choose; most of the night's
  iteration needs no judge. Use Haiku (experiments/judge.py) only on val, only for arms that survived the fit screen,
  and mainly where strict is blind: the _mt families (the multilingual_mt language-unit guardrail, S10) and
  directed_modulation. Report judged numbers next to the strict ones, never instead of them; where they disagree,
  look at the readouts before believing either. Estimate every judge run from a `limit=3` dry run first.
  No UM judging: S11 showed UM pass@10 cannot separate user modelling from prompt reading, so treat UM as a
  guardrail on strict numbers only.
- Watch every job: measured rate, ETA, stall checks ("Watching runs"). If a job crashes, fix, commit, rerun.

## The loop
card -> claim -> prediction written into the card -> g in `src/jlm/mu/<study>.py` (registered in `CENTRES`) with a
test -> screen on **fit**, all 11 families, next to its controls (`rand.`, `shuf.` and the category's own) -> confirm
on **val** (strict; Haiku where needed) -> `experiments/analyse.py --study <id>` -> deep dive -> insights, each
pointing at a next card or saying why not -> next iteration.
Write `notes/iteration-anthony/studies/<id>.md` as you go, with a 3-line status block at the top, updated at least
hourly. Times you write come from `date`, never from memory (pilot-1's study files drifted hours ahead of the clock).
A study is finished only with its card (`studies/<id>.card.yaml`, schema in `studies/CARDS.md`).

## Never
Use targets inside g (S20's ceilings are the labelled exception: `ceil.` arms, never in `out/eval`); read the bench to
choose anything; edit another instance's files; touch programme LL's files (`local-linearisation/`, `LL*` studies);
change shared pipeline code (src/jlm outside mu/, experiments/, tools/) beyond a small fix with a test flagged
[pipeline candidate], and tell the steward in one line when you do. Messages to other instances: one line, events only
(claims, results that matter to them, requests to yield), no progress chatter.

## Winding down (by the clock, not by the backlog)
- **09:00 BST**: stop launching pod jobs and judge runs. Let running ones land (kill and note any that cannot land by
  09:30). Offline Mac work (scoring, notes, plots) may continue.
- **09:00-09:45**: finish the write-ups (study files with their status blocks, cards, the Studies table in mu-log,
  `catalog.py` lines), land your commits.
- **By 09:45**: set your board line to idle and send the steward one line: "done: <studies>, <headline>, <what is
  next>". Then stop the loop.
