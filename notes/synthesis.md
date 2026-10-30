# What we already know about mu_l (imported 2026-10-10)

Synthesis of the centring work imported from `unverbalized-motivations` (now `umot/`,
source commit `30bbabf`) and `jlens-edits-1` (now `jle/`, source commit `5f483de`).
The records of truth are umot's `notes/research-log.md` and jle's `notes/predictions.md` (both upstream: unverbalized-motivations, jlens-edits-1);
this page only points into them.

## Setup shared by both lineages

- Lenses are the released ones, never refit: Qwen3.6-27B `neuronpedia/jacobian-lens …_n1000.pt`
  (wikitext, n=1000); `jle` also uses Qwen3.5-4B (neuronpedia, n=417) and Qwen3.5-9B instruct
  (`camilablank/workspace-lenses`, pile-10k). J_l = mean Jacobian of the final residual
  w.r.t. the block-l output. All in the HF cache, not in this repo.
- The released lens has **no mu**: it reads `J_l h`, an expansion around h = 0, which is off the data.
  Argument (umot log, 2026-10-09): `J(h - mu) ~ f(h) - f(mu)` is the coherent first-order readout;
  it justifies centring but does not pick mu. "Choosing mu is choosing the counterfactual."
  Framing on the umot dashboard: mu = E[h | C], a ladder of conditioning sets C.
- Two readouts, both linear in h, so a centred read is `L(h) - L(mu)`:
  `cos` (WorkspaceBench's): `(W_U J h)_t / ||J^T W_U[t]||`;
  `rms` (jle's): `rms_norm(J h, 1+w) W_U^T`. They disagree by up to 0.09 uncentred and
  agree within 0.033 after centring (x100). This is the README's "with/without norm" control.
- What centring removes: the mean decodes to the continuation prior (`<|im_end|>`, `\n\n`, This, The),
  ||mu|| / ||h|| = 0.81-0.98, and subtracting it removes 41-69 % of the norm (x98).

## The mu ladder so far

| mu | where | result |
|---|---|---|
| 0 (plain) | both | bench strict rate 0.55-0.68 pooled; DM judged content_bound 0.21 |
| mu_fit: the lens's own fit-corpus mean (`umot/out/fitmean/mu.pt`) | umot `fit_mean.py`, `fitmean_lin.py` | far better expansion point (held-out R² at L42 −0.13 → 0.15; OLS 0.47), but no better as a readout centre than the family mean; hurts on J++ evals (cos 0.357 → 0.313) |
| Taylor offsets `W_U(beta c + J(h - mu))` | umot `taylor_screen.py` | null: the mean Jacobian explains about 4 % of the variation at the read layers |
| generic corpus mean G1 (wikitext / pile) | jle x101 | does nothing |
| same-token corpus mean G2 | jle x101 | pooled +0.01 to +0.06; a quarter to a half of association's gain; harms 4 families somewhere |
| other families' mean (ctr1, x89d leave-one-family-out) | jle x89d, x99 | +0.02 to +0.08 |
| **own-family mean** (own1 / dev1 / loo / fam) | jle x97-x100, umot | bench, held out: rms 0.55/0.58/0.59 → 0.67/0.68/0.77 (4B/9B/27B); typo 27B 0.55 → 0.91; bootstrap SD < 0.01, 8 prompts suffice; multilingual −0.04 to −0.08 at 4B/9B, multihop mixed |
| own mean with top-k PCs removed (pco4/16), kNN, whitening | jle x90f-o, x96-x99 | +0.04 to +0.16 extra on multihop and 27B association; the mean is 88-100 % of pco4's gain |
| same read-token mean (tok1 / ctr-tok) | jle x99, umot | best on user_modeling; DM judged 0.21 → 0.82 |
| same sentence, same position (carpos) | umot | DM 0.89, **but reads the prompt**: see the mention control row |
| mention control (fairness test) | umot `mc_screen.py`, `validation_centring` | position-matched centres score held = mentioned (0.50/0.50); they separate only at sentence-final "." cells at L >= 42 (0.40 vs 0.15; rank 28 vs 1,834) |
| J++ lens (different map, not a centre) | umot `jpp_compare.py` | centring recovers about 45 % of the J-lens → J++ gap; centring J++ hurts it |
| J++ lens on our 11 families (`jpp:` arms) | `notes/jpp-compare.md` | plain J++ beats every J-lens arm on typo (bench 0.94 vs 0.76) and is at or above the plain J-lens on the single-token families; centring J++ is mixed (helps association, hurts basic_readout / multilingual); not judged yet |

### Added by the constant-μ section (x1-x25, closed 2026-10-12; `notes/constant-mu.md`, "Conclusions")

Dev val, strict, rms, pooled over the five plain families, vs the plain J-lens.

| mu | where | result |
|---|---|---|
| mean final-token state of ~64 short texts the model writes, no task named (`glos:none`) | x14 B, x24 | data-free; +0.176 (family mean +0.216); naming the task (glossary word) adds ~0.02; needs the sentence-end read (one word earlier: +0.010); wikitext sentences +0.015 to +0.046 |
| per-input situation / topic word | x23, x23b | below a constant: +0.115 to +0.130 / −0.109 |
| J++ + data-free centre | x19b, x25 | +0.00 to +0.03 over J++ pooled (+0.10 on association); bench: J++ + glossary word 0.854, the best data-free arm |

## Lessons

1. The gain comes from a **matched counterfactual**, not from a better expansion point
   (mu_fit linearises better and still doesn't help as a readout).
2. One mu per layer only adds a fixed token bias. It works on WorkspaceBench because every item
   reads the same template cell, so the family mean is effectively position- and token-matched.
   On DM, read cells vary, so the family mean does nothing and a token- or position-matched mu is needed.
3. Tighter matching removes more noise but also more content: it starts reading or subtracting
   the prompt. This is the README's "fair / not cheating" axis. x101: the reference must match the
   read cell's form and context, not just its token. **The open problem is a label-free,
   context-matched mu.**

## README ideas vs prior work

- Partly done: norm vs no norm (the two readouts); position (carpos); token (tok1, G2);
  clusters (kNN ≈ pco); n-scaling (8 / 32 / all reference prompts, flat beyond 8);
  dynamic g(h_t, h_{t-1}, …), which is only listed, not run (umot `dashboard/views/centring_story.py` §7:
  self-truncation, corpus conditional mean g(token, last k), kNN retrieval, prediction deflation).
- Not done: a random-vector mu as a control; an abstract-word or steering-vector mu;
  an "optimal" mu reconstructed from targets (under jle's "no crystal ball" rule this is an
  in-sample ceiling, not a method); further WorkspaceBench dev and validation sets beyond dev bank v2.

## Where things are

- umot: `src/umot/centring.py` (concept-aware `Centre`), `experiments/token_local.py`
  (every centred arm, runs on the Mac from captures), `out/captures/` (residuals at read cells),
  `out/fitmean/mu.pt`, `out/jpp/residuals.pt`, `dashboard/` (Streamlit; pages "Centring",
  "Centring: bench to wild", "Validation: centring", "J++ vs centring", "Token tracker").
- jle: `experiments/x95…x101_*.py` (they import x89 / x90 / x90c / x90f modules as libraries),
  `data/x90-dev/bank-v2` (dev bank), `out/x96-capture-*.pt` (association residuals at every
  position), `out/x101-means-*.pt` (corpus and per-token means), x95-x101 stores and reports,
  `out/x100-summary.md`, `lensboard/` (`#/centre` page; banks dev4 / dev5 / bench2).
