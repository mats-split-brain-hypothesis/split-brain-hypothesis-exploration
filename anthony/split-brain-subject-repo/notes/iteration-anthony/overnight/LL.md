# Instance LL (night-2, 2026-10-12): programme LL, local linearisation

You run programme LL on your own: no steward, no cards from the mu-log backlog. The plan is
`notes/iteration-anthony/local-linearisation/plan.md`; read it whole before anything else. The night runs from about
00:30 BST **until 10:00 BST**, when the user picks the results up. The user is asleep: never wait for an answer;
decide, write the decision and its reason into `local-linearisation/log.md` (create it), and move on.

Follow `notes/iteration-anthony/overnight/preamble.md` for everything it says about setup (worktree, never commit the
`out` symlink, landing), watching runs, scoring (strict pass@10 first; the judge is an additional score, no UM
judging), the Never list (except the line on LL's files: they are yours) and the wind-down times. Where the preamble
and this file differ, this file wins:

## What differs from the A / B / C instances
- **Scope**: only programme LL. The "J++ is never a centre's lens" rule is lifted for it (research-loop.md, Rules):
  J++'s released map, our own expert Jacobians and its weights may be part of a readout. The objective is still a
  better J-lens readout on our banks (fit chooses, val confirms); J++'s held-out readout evals are the second scorer.
- **Budget: your own pot**, separate from the studies' $50. Every study name you log or give a pod starts with `LL`
  (`LL0`, `LL1`, ...), so its spend lands in the pot: `python tools/board.py check <usd> --study LL0` before every paid
  step, `STUDY=LL0` on every pod you create. Pot cap: whatever the steward's session line says (`board.py show`,
  "pot LL*"; planned $100).
- **Pods: you create and own yours** (`INSTANCE=<you> STUDY=LL0 GPU=capture bash tools/pod.sh create ll0`), on the
  shared volume, and terminate them yourself (the ledger logs their cost). Do not use the steward's eval pod for
  LL0's backward sweeps (they need a whole 80 GB GPU); short evaluate reads on it are fine (`podrun.sh`, NEED_GB).
- **Files**: yours are `local-linearisation/`, `src/jlm/mu/LL*.py` / new map prefixes in `jlm.lens` (pipeline: own
  commits, flagged [pipeline candidate], with tests), `experiments/ll*.py`, `out/analysis/LL*/`. The dashboard page
  `dashboard/views/local_lin.py` and `figures_ll.py` are uncommitted in the main checkout: do not create them in your
  worktree tonight (landing would collide); write what the page should show into the log instead.
- **Messages**: one line to the steward (name on the board) when you start and when you finish, so the digest can
  carry a line on LL. Nothing else unless a result changes another instance's study.

## Decisions taken for tonight (the plan's open questions)
- Plain-gradient experts first (the J-lens is the primary object), LRP second if time and pot allow.
- No contact with the J++ authors: reproduce.
- LL runs overnight (this session); the pot is the budget.

## The night, in order (change it if the evidence says so)
1. **LL0 timing before spending.** Clone `safety-research/jpp_lens` @ 93f02cd and read its fitting loop. Build the
   one-sweep, many-clusterings accumulator (sum J, count, sum h per bin; k = 1, 8, 16, 64; wikitext router and our
   fit + chat-corpus router) at J++'s 7 recipe layers. **Time one prompt** on the pod and extrapolate the full sweep's
   cost; write the number into the log. If the projection exceeds the pot, cut (fewer layers, fewer prompts, k = 8 and
   64 only) rather than go over.
2. **Validation gates** before reading anything: k = 1 reproduces the pooled J-lens (cos >= 0.99 per layer).
   (The LRP-side gate, recall@10 near 0.594 with refitted w, waits for LRP experts.) A failed gate is the night's
   result: diagnose and write it up; do not build on it.
3. **LL1 diagnostics** (cheap, while or after the sweep runs): `||mu_i|| / ||h||`, inter-expert cosine per layer,
   where val cells land. H3's linearisation error by anchor if a patched forward pass fits in the pot.
4. **LL2 single experts** (reads only; H1, H2): each expert x anchors {0, global mu, mu_i, mu_j shuffled, fam,
   knnx8} on fit, strict; the pairing control (mu_j) decides H1.
5. **LL3 combined maps** (H4, H6) on fit, then val for survivors, with the plan's controls (§5).
6. Beyond that, in the spirit of the preamble's "work until 10:00": follow your insights within the programme (LL4's
   refit of w on centred inputs, LL5's path-integrated slope as a ceiling), robustness of your best result, and the
   log.

## Wind-down
As the preamble: no new pod jobs or judge runs from 09:00 BST; terminate your pods (the backward sweep's partial
accumulators are saved and resumable, so stopping loses nothing); by 09:45 the log has a status block (what ran,
gates passed or failed, headline numbers, spend, what is next), `plan.md`'s Log section has the night's line, commits
are landed, your board line is idle, and the steward has your one-line "done".
