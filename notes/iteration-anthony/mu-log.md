# mu log: backlog, studies, results

Process: `notes/iteration-anthony/research-loop.md`. Per-study detail: `notes/iteration-anthony/studies/<id>.md`. Leaderboard: generated
(`python experiments/report.py --split fit|val`; dashboard "Leaderboard"), never hand-edited here.

Reference arms (val, strict / Haiku): see `out/eval/report-val.md`. Headroom is on association, typo,
multihop, user_modeling, directed_modulation and the four `_mt` families; basic_readout and multilingual
are guardrails.

## Infrastructure (built 2026-10-10)

- g interface: `centres.Batch` / `centres.apply`; a centre implements `__call__(CellRef) -> mu` or
  `transform(Batch) -> h - g` (state, other layers, `ctx` = every-position states). Study centres go in
  `src/jlm/mu/<study>.py` and register in `CENTRES`.
- Controls: `shuf.` / `rand.` arm prefixes; echo, prompt-masked readout (`masked.jsonl`) and next-token overlap in
  every `evaluate.py` summary; `jlm.controls`.
- Context captures: `experiments/capture_ctx.py` -> `out/ctx/<family>-<split>.pt` (every position, grid layers + 42 +
  63) and `out/ctx/corpus-wikitext.pt` (256 x 128 tokens); `jlm.context.ContextStore`.
- Battery: `experiments/analyse.py --study <id> --arms ... [--refs ...] [--decode-g]` -> `out/analysis/<id>/`.
- Pods and coordination: `tools/pod.sh`, `tools/sync.sh`, `tools/board.py` (see notes/iteration-anthony/research-loop.md).
- Dashboard: Leaderboard, g compared, Study page, Passage -> readouts with masked / echo / next token (in progress).

Owed: a per-item prompt-only floor (Haiku or the 27B given the prompt text; the bench's floor is family-level
only); a mention-control bank for the template families; a neutral chat-format corpus (U2 / S2).

### Round-2 infrastructure (built 2026-10-11 for S13-S20; tests in `tests/test_round2.py`)

- **Readout-space geometry** `src/jlm/pullback.py` (`Geometry(lens)`): pull a vocabulary-space vector back into the
  residual stream through the readout map (`pullback(C, layer, readout, ridge, rank)`, with the constant-score
  direction projected out), the lens's reading directions of chosen tokens (`reading_basis`), the SVD of `J_l`
  (`jsvd`). Heavy factors cached under `out/lens/` by the lens pin (`pb-eig-*`, `wu-gram-*`, `tbasis-*`, `jsvd-*`);
  centres load only small tensors and never `W_U`.
- **Precompute** `experiments/precompute_pullback.py` (one load of `W_U` + `J`, ~7 GB: Mac under `mac.lock` or a pod;
  `experiments/jobs/round2_precompute.sh` runs everything on a pod). Writes `out/priors/pullback/<prior>-<readout>-r<rank>.pt`
  (one g per layer, with fit quality and decoded top tokens), `out/priors/pullback/nt-<family>-<split>-<readout>-r<rank>.pt`
  (per-cell pullbacks of the model's next-token log-softmax; needs `out/ctx`, i.e. the pod), the template bases and
  the J SVDs, and appends to `out/priors/pullback/summary.md`. `priors` is a named `hfdata` scope
  (`python tools/hfdata.py push priors lens`).
- **Priors and token sets** `experiments/build_priors.py` (tokenizer only): `out/priors/unigram-norobots.pt` (chat
  prior: 9.5k no_robots prompts rendered as the bench renders, 0.95M tokens), `unigram-wikitext.pt` (prose control),
  `data/template_tokens/template.json` (197 tokens, ordered: chat specials, the tokens the decoded reference means
  share at L >= 36 across >= 3 families, the 128 most frequent chat tokens, a hand list; targets of fit / val items
  excluded). Corpus helpers in `src/jlm/corpus.py` (`chat_renders`, `wikitext_windows`).
- **Chat-format corpus** `experiments/capture_ctx.py --corpus chat --n 2048 --seq 128` (pod) -> `out/ctx/corpus-chat.pt`;
  pool `chat` in `jlm.mu.clusters`: arms `kmch<k>`, `kmchr<k>` (control), `knnch<k>` (S4 round 2's missing pool).
- **Centres** (registered, read the caches): `s13uni`, `s13wiki`, `s13nt`, `s13ntf`, parametric
  `s13:<prior>:<beta>[:<readout>][:r<rank>]` (`src/jlm/mu/S13.py`); `s14t<k>`, `s14fam<k>`, `s14r<k>`, `s14famr<k>`,
  parametric `s14:<set>:<k>[:fam][:rand]` (`S14.py`); `s15top<k>`, `s15famtop<k>`, `s15r<k>` (`S15.py`);
  depth schedules `sched:<L>:<A>+<B>` (`schedule.py`, S17: e.g. `sched:48:fam+zero`, `sched:48:fam+s13nt`).
- **Diagnostics** `experiments/s15_spectrum.py` (share of fam / tok / h in J's top-k subspaces; needs only the SVD
  caches) -> `out/analysis/S15/`; `experiments/ceilings.py --family F --split fit [--val]` (S20: in-sample fits with
  targets, `ceil.<class>` for const / tok / clu / proj16, exact item-rule scoring, K-fold by group) -> `out/analysis/S20/`,
  never `out/eval`. The ceilings script is slow on the Mac for user_modeling (1.3k cells): run it on a pod with `--device cuda`.
- Not built: S16's form-blind kNN, S18's sparse mu and S19's learned g need no shared infrastructure (S16 reuses
  `clusters.Pool.bench_fit` and S7's PCs or S14's bases; S19 needs the lens, `controls.mask_ids` for prompt ids and the
  next-token top-10 from `out/eval/<family>/<split>/next-token/`).

## Backlog

**No priority by source.** `U` cards were suggested by the user, `S` cards come from the README, the synthesis or
our own reasoning; the prefix records where an idea came from and nothing else. U and S cards are on equal footing.
Choose the next card by what it costs, what it would teach us whatever the result, and what it unblocks. With the
context captures in place (2026-10-10), most cards run offline from captures:

- Offline now: S1 (controls; the reference evaluation already runs `rand.` / `shuf.` arms), S3, S4 and U3 variant 1
  (clusters, see "Clusters" below), S6, S7, S8, S9, U1, U4 (J++ vs J-lens, an analysis study).
- Offline now, round 2 (2026-10-11): S13-S20 (see "Round 2 cards"); S13 / S14 / S15 need W_U and J loaded (Mac under
  `mac.lock`, or a pod), the rest run from the read-cell captures and the pooled fit cells.
- Need new data first: S2 and U2 (neutral contexts or rewritten prompts, a pod capture), S5 (category-word states),
  U3 variants 2-4 (J++'s experts and weights: not released; and a rule change, see the card).

## Clusters: a direction, not a card

Clustering is one of the richest sources of g (user, 2026-10-10): it gives a label-free "what kind of position is
this", so a mu that depends on h without a hand-chosen key, and, through the Taylor reading, one expansion point per
regime instead of one for the whole stream. S4 and U3 are two entries into it; expect many studies here. The axes:

- **What is clustered**: read-cell states h_l (per layer, or jointly across layers); every position of the context
  captures (bench renders); a neutral corpus (wikitext now; chat-format later), which keeps item content out of the
  centroids; the readout J h; the residual after a family or token mean (sub-clusters inside a family); a window
  (h_{t-k..t}); the unit direction only, as J++'s router does (norm left out).
- **How a cluster enters g**: the nearest centroid's mean (hard); responsibility-weighted means (soft); the cluster
  as a key, crossed with token or family; a per-cluster mean plus per-cluster principal directions removed (S7 per
  regime); per-regime expansion points `J h - sum_i w_i J_i mu_i` (U3 variant 3); clusters of g itself, a small
  dictionary of counterfactuals picked by the nearest one.
- **Granularity**: a sweep from k = 1 (the global mean) to k = n (kNN, which jle found close to pco); hierarchical
  clusters; per-layer vs shared assignments, and whether a position keeps its cluster across depth.
- **What to look at**: what the clusters are (purity by token, position, family, template slot); where the eval
  cells land (if all in one or two corpus clusters, a label-free cluster mean cannot replace `fam`); gain by cluster
  purity; the decoded centroids (L(mu_c)).
- **Cluster-specific controls**: random assignment with the same cluster sizes; k = 1 reproduces the global mean
  exactly; clusters fitted on the neutral corpus only vs on bench-like cells (content in the centroids means the
  prompt can leak through them); echo and prompt masking as always, and the mention control for tight (large-k or
  routed-by-context) variants.

### Cards

### U1 position-based means, carefully                   status: done (studies/U1.md: token matching, not position, reads the prompt; u1rel fair, DM Haiku 0.57)
- Question: how much of what position matching buys is fair? Map the ladder fam -> tok -> relative
  position -> template slot -> slot + token -> same sentence, same position (carpos), and for each rung
  measure pass@10 *and* the controls: echo, prompt-masked pass@10, mention control.
- Counterfactual: the state this kind of cell has in this kind of context, minus this item's content.
- Mechanism: on UM / DM the read cells vary, so a family mean is not matched; on the 5 template families it
  already is (expect little there).
- Cost: offline for the read cells we have (UM about 21 per item, DM); other positions need the context capture.
- Fairness risk: high at the tight end (carpos read the prompt). Controls: position-matched category.
- Source: user (2026-10-10); umot carpos / mention control.

### U2 neutralised counterfactual prompts                 status: idea
- Counterfactual: the same prompt with the content replaced by neutral content (an LLM rewrites the
  prompt, keeping its form, length and template; never shown the targets), captured through the 27B at
  the matched read cell: g = h(neutral rewrite). Variants: several rewrites averaged; rewrites that
  neutralise only the content slot; rewrites of the same template from a pool shared across items.
- Mechanism: the most literal reading of "J(h - mu) ~ f(h) - f(mu)" with mu a per-item counterfactual.
- Cost: expensive: LLM rewrites (cheap) + a 27B forward pass per rewrite, with token alignment between the
  prompt and its rewrite. A pod session per bank.
- Fairness risk: the highest of any card: by construction h - h_neutral contains the replaced words.
  Controls: counterfactual-prompt category, prompt-masked pass@10 above all.
- Source: user (2026-10-10).
- Evidence (U1, 2026-10-11, offline on umot's mention bank): the literal counterfactual (same sentence and position,
  prompt without the concept: `u1carpos@absent`) reads the prompt (held 0.94 / mentioned 0.81). A capture for this
  card is not worth it unless the rewrite keeps the item's own sentence out of the counterfactual's references.

### U3 regime-conditioned centring: clusters, local expansion points, J++'s experts   status: variants 1, 5, 6 done (studies/S4.md); 2-4 moved to programme LL (local-linearisation/plan.md, 2026-10-11)
- Idea (user, 2026-10-10): when taking the mean, let cluster means, and the cluster weights from the J++ fit,
  enter mu. Clustering can come into the choice of mu in several ways; this card collects them.
- Why it is a major direction. mu does two jobs in `J(h - mu) ~ f(h) - f(mu)`, and clusters bear on both:
  - *Expansion point*: J is a linearisation, accurate only near some point. One averaged J has one good
    expansion point (the fit mean; umot `fit_mean.py`: R² at L42 −0.13 → 0.15) and is poor away from it.
  - *Counterfactual*: mu says "compared with what". Our best centres condition on context (fam, tok), which
    uses the item's family label. A cluster is a coarse, label-free "what kind of position is this", so it
    offers a mu that depends on h (the README's question) without a hand-chosen key.
- Evidence that the idea can work: J++ (Ayonrinde & Lindsey 2026; code `safety-research/jpp_lens` @ 93f02cd,
  lens `koayon/jpp-lenses` @ 6c96867) already treats the residual stream as piecewise linear, and that is
  where its gain comes from (held-out macro recall@10 on its readout evals: J++ 0.594 vs J-lens 0.340, umot
  research log 2026-10-10). Its fit, per layer:
  - router: unit-normalise h, centre, project to the top 64 PCs, k-means with E = 8 (k-means++, seed 0), fit
    on 1000 wikitext prompts (128 tokens, first 16 positions skipped; about the J-lens fit-mean replay's data);
  - experts: `J_i = mean over positions in cluster i of the LRP Jacobian` (one local linearisation per regime);
  - weights: signed `w_i`, unit L2, fitted per layer by Adam on a sigmoid surrogate of recall@10 on the 20 %
    fit split of its readout evals; incoherent experts get low or negative weight;
  - released: only `J = sum_i w_i J_i` (config `num_clusters 0`). Router, experts and weights are not released.
  J++ fits a slope per regime but keeps the expansion point at 0. The missing half is an expansion point per
  regime: the map and the centre built from the same object.
- Why it matters for the J++ puzzle. Centring helps the J-lens but hurts J++ (rms 0.594 → loo 0.498 / ref
  0.484, umot log). Hypothesis "J++'s map already removes the mean" is refuted (scratch check 2026-10-10,
  487 J++ eval cells, L8-56): J++ keeps *more* of the wikitext mean than the J-lens (‖Jμ_fit‖/‖Jh‖ 0.57-0.67
  vs 0.34-0.57; cos(Jh, Jμ_fit) at L40+ 0.68-0.78 vs 0.48-0.58) and about the same of the task mean (both
  ≈ 0.85; centring removes 70-80 % of the readout norm under either map). J++'s readout of μ_fit is mostly
  ` ,` ` and` ` the` ` ...`. New hypothesis: the weights were fitted on uncentred inputs, so centring moves
  the inputs away from those the weights were tuned for, i.e. map and centre cannot be chosen separately.
- Questions:
  - A. Does a regime-conditioned mu beat a single mean (global, family) at equal fairness?
  - B. Can clusters replace the family label: does a label-free cluster mean get close to `fam` / `ref`?
    (The most useful outcome: a context-matched mu usable on any prompt.)
  - C. Can J++ and centring be made consistent, so that they stack instead of conflict?
- Variants (a ladder from "clusters only" to "clusters + J++ weights + experts"):
  1. Routed cluster mean: `mu(h) = mu_c(h)`, hard, or soft (responsibilities from centroid distances). Works
     with any map, the released J-lens included. Same-cluster restriction of fam / ref / tok as a sub-variant.
  2. Weighted mean: `mu_w = sum_i w_i pi_i mu_i / sum_i w_i pi_i` (`pi_i` the cluster's position share);
     negative-weight clusters are subtracted. The J++ weights as a usefulness signal on the baseline.
  3. Per-expert expansion points: read `sum_i w_i J_i (h - mu_i) = J h - sum_i w_i J_i mu_i`. One fixed
     offset per layer, label-free at read time, equal to plain centring when every `mu_i` is equal. The
     principled form: each expert is linearised at its own cluster.
  4. Centring-aware weights: refit `w` on `J_i (h - mu)` (or on variant 3) with the J++ fitter. If centring
     then adds to J++, the "weights tuned to uncentred inputs" reading is confirmed (question C).
  5. Router geometry as mu: the router's mean unit direction scaled by ‖h‖ (a norm-aware generic centre);
     removing the cell's centroid direction (a one-direction S7).
  6. Our own clusters fitted on reference cells or chat-format corpora instead of wikitext, and more
     clusters than 8 (overlaps S4; if this card goes ahead, S4 becomes its variant 1 on our data).
- What each variant needs:
  - router (variants 1, 5): forward passes only: `fit_mean.py`-style wikitext replay saving states at the
    read layers, then their `routing/cluster.py` locally. About $0.5 of pod. Our reproduction will not be
    bit-identical to theirs (GPU numerics, their prompt loader); that is fine for variants 1 and 5.
  - experts (variants 2-4): LRP Jacobians per cluster, the same backward passes as a full J-lens fit (64
    prompts × 320 backward passes of 16 × 128 tokens); restricting to the read layers barely saves anything.
    Rough guess 8 H100-hours, $20-40, to be timed on one prompt first. Alternative: ask the authors for the
    router, experts and weights files (experts at the 7 recipe layers ≈ 3 GB in fp16).
  - weights: cheap with their fitter once experts exist. Validate the reproduction before using it:
    cos(sum_i w_i J_i, released J) per layer, and recall@10 parity (0.594).
  - Qwen3.5-9B also has a released J++ lens (`koayon/jpp-lenses` `qwen3.5-9b/`): about a third of the cost,
    but our J++ baselines are on 27B.
- Scoring: the J++ readout evals (`umot/experiments/jpp_compare.py`, held-out split) for question C; the
  project's banks (fit chooses, val confirms) for A and B, with the J-lens as the map.
- Fairness risk: medium for routed / tight variants (clusters can align with content or read the prompt, as
  carpos did); low for the fixed-offset variants 2-3. Controls: echo, prompt-masked pass@10, mention control.
  First diagnostic: which clusters the eval cells fall in. If they all land in one or two wikitext clusters
  (the router clusters on direction, likely format / position more than meaning), B fails by construction
  and variant 6 is the route.
- Rule conflict: `notes/iteration-anthony/research-loop.md` says "J++ is a comparison, never a centre's lens". Variants 1, 5
  and 6 on the J-lens are within it; variants 2-4 use J++'s experts or weights and need the user to relax it
  for this card.
- Source: user (2026-10-10); J++ (README of `jpp_lens`, `routing/`, `fitting/condense_experts/`); umot log
  2026-10-10 (J++ comparison, μ_fit).

### S1 random-vector mu (control)                         status: done (studies/baseline.md: random g ≈ no centring)
- Counterfactual: none. A random direction with the family mean's norm per layer; also the family mean
  with shuffled coordinates.
- Mechanism: should not help. If it does, part of centring's gain is a norm or bias effect, not content.
- Cost: offline. Fairness risk: none.
- Source: README, synthesis "not done".

### S2 neutral-context mean                               status: done (studies/S2.md)
- Counterfactual: what the model has "in mind" at this kind of cell in a neutral context (the same
  template with neutral content), rather than the average of the bench's content.
- Mechanism: a cleaner subtraction of the template prior without subtracting family content.
- Cost: needs the context / neutral capture. Fairness risk: low (no item content).
- Source: README.
- Evidence (U1, 2026-10-11): a position mean over neutral prompts (`u1rel@absent`, umot's absent items) is fair
  (0.62 / 0.10) but no better than `u1rel` on the bank itself (0.78 / 0.23): little to gain from a neutral capture.
- Design notes (ad, 2026-10-11, from S6 / S10 / S12; not run): tonight's mechanism, "a mean over cells that share X
  removes X", says what a neutral fill must vary and what it must keep. Keep: the family's template and read slot
  (S12: the token without the family's context does little; jle x101). Vary, across the neutral fills, every attribute
  the family's items share and the bench scores: multihop / multihop_mt the bridge's category (fills whose bridge is a
  person, a place, an object, a date in equal shares, so the "famous author" direction averages out); multilingual_mt
  the prompt's language (fills in many languages, or in English only if the language unit is to be kept); typo /
  association the content word's category. Where to test first: multihop_mt (fam hides the bridge: z +2.5 in L(mu))
  and multilingual_mt (fam is the only centre that keeps the language unit); a neutral mean that beats fam on both
  without losing typo / association would be the first fair centre to pass the multilingual_mt guardrail and lift the
  bridge. Cost: authored fills (about 20 per family, hand or an LLM that never sees targets) and one capture-pod session
  (read cells only: minutes for 7 families). Controls: echo, mention control, and a "content-matched" fill set (fills
  sharing the family's category) as the negative control, which should reproduce fam's harm.

### S3 dynamic mu = g(h_t, h_{t-1}, ...)                  status: done (negative; studies/S3.md)
- Counterfactual: the predictable part of h from its recent past (self-truncation, an EMA of previous
  positions, a linear predictor fitted on a corpus).
- Mechanism: a label-free, context-matched mu, the synthesis's open problem.
- Cost: needs the context capture. Fairness risk: high (can subtract the prompt): echo + mention control.
- Source: README; umot `centring_story.py` §7.
- Arms (ad, 2026-10-11): `ar1e{0,1,2}`, a ridge predictor of h_t from h_{t-1} fitted on wikitext (`src/jlm/mu/S3.py`);
  controls `rand.ar1e1`, `shuf.ar1e1`, next-token overlap. Prediction in studies/S3.md (no p beats fam; ar1e0 about
  zero; ar1e2 below zero on typo / association).
- OUTCOME (fit screen): every p below zero, monotone in strength (macro 0.462 / 0.440 / 0.425 vs zero 0.509, fam
  0.601); random control at zero (0.516). The previous state carries the item's content; a g from the item's own
  past removes it. Closed as a centre.

### S4 cluster mean                                       status: done (studies/S4.md; knnx8 a finalist candidate)
- Counterfactual: the mean of the nearest cluster of reference cells (k-means per layer), not of the family.
- Mechanism: a family mean that adapts to the cell's form without a hand-chosen key.
- Cost: offline. Fairness risk: medium (clusters can align with content): echo.
- Source: README; jle kNN ≈ pco. Overlaps U3 variant 1; see "Clusters" above for the wider space.

### S5 abstract-word / steering-vector mu                 status: done (studies/S5.md: null as a method; the language-name direction carries multilingual_mt's language unit)
- Counterfactual: subtract the representation of the category itself (e.g. "typo"), scaled.
- Mechanism: removes the shared category content so item-specific content surfaces.
- Cost: needs a small capture (category words in context). Fairness risk: the scale must be chosen on fit.
- Source: README.

### S7 subspace removal: g(h) = P_B h                       status: done (studies/S7.md)
- Counterfactual: h with its component in a "background" subspace B removed (B = top PCs of reference
  cells, or the span of the template / continuation-prior directions), instead of one mean vector.
- Mechanism: generalises jle's pco (mean + top-k PCs, +0.04 to +0.16 on multihop / association) to
  removing whatever varies with form rather than content.
- Cost: offline. Fairness risk: medium (PCs can carry content): echo; choose k on fit.
- Source: generalisation of mu (user, 2026-10-10).
- Arms (2026-10-11, ad): `pco4`, `pco16` (fam + top-k PCs removed, own group excluded), controls `pcr4`, `pcr16`
  (random k-dim subspace); `pmu` (projection on the fam direction), `fam50` (half the mean). `src/jlm/mu/S7.py`.
- Prediction (ad, before the run): pco4 >= fam by +0.02 to +0.05 on association and multihop (jle x90f), about fam
  elsewhere; pco16 adds little over pco4 and may lose on multilingual; pcr4 / pcr16 = fam within 0.02 everywhere.
  pmu = fam within 0.03 (per-cell rescale only). fam50: between zero and fam on typo / association (they need the
  whole mean), above fam on multihop_mt's bridge ranks.
- OUTCOME: pcr / pmu = fam, fam50 below fam (as predicted); pco wider than predicted (DM, UM gains too); k = 16 on fit.
  Val: pco16 +0.039 strict macro vs fam (+0.015 vs tok), controls at fam, mention control 0.82 held / 0.24 mentioned
  (tok 0.82 / 0.59). Judged: multilingual_mt -0.11 [-0.21, -0.02] vs fam (guardrail failure), DM 0.61 (tok, knnx8
  0.79). tpco (token mean + PCs) leaks like tok; xpco (other families' PCs) null. studies/S7.md.

### S8 shrinkage / state-dependent mean: g(h) = mu + a (h - mu)_B        status: done (studies/S8.md: tightening buys DM passes only with mention leak; s8knn32 +0.03 vs fam)
- Counterfactual: the part of h that a kNN or kernel regression on reference cells predicts from h's own
  coarse features (token, position, norm), i.e. a soft, h-dependent mean.
- Mechanism: interpolates between fam (fixed) and tok / carpos (tight); tightness becomes a dial chosen on fit.
- Cost: offline. Fairness risk: medium: echo.
- Source: generalisation of mu.

### S9 cross-layer g: the state at an earlier layer, transported   status: done (null vs its control; studies/S6.md)
- Counterfactual: what was already present at layer l - k; read only what layers l-k..l added.
- Mechanism: isolates the computation at a depth (multihop: the bridge vs the answer).
- Cost: offline on the grid layers (step 4) once the interface passes other layers' states.
- Fairness risk: low. Source: generalisation of mu; links to S6.
- Arms (2026-10-11, ad): `xl4`, `xl8` (g = h_{l-k}), `xlf4` (plus the family's mean update), `xlp4` (projection on
  h_{l-k}); controls `xlr` (random earlier layer), `rand.xl4`, `shuf.xl4`, next-token overlap. `src/jlm/mu/S9.py`.
- Prediction (ad, before the run): xl4 reads only the update, so content already present at l-4 is removed with the
  template: macro below fam by >= 0.05, typo / association well below fam (-0.1 or worse), multilingual below fam.
  On multihop_mt (bridge) xl4 >= fam (+0.05) because it does not subtract the family's category; multihop answer
  about zero's. xlf4 between xl4 and fam; xlp4 like xl4; xlr worse than xl4 on every family; next-token overlap of
  xl4 higher than fam's (the update at late layers is the next-token prediction forming).
- OUTCOME (fit screen, 2026-10-11): null as a centre. xl4 macro 0.529 (fam 0.601, zero 0.509), typo 0.60 / association
  0.31; the random-earlier-layer control xlr matches it (0.530); xlf4 is the best xl arm (0.579). multihop_mt at or
  above fam (0.45-0.50 vs 0.40, n = 40, within noise). Next-token overlap of xl4 0.059, above fam's 0.043 but below
  zero's 0.080. Useful as a localiser: the update's hits concentrate at L32-36 and L48-56 (studies/S6.md finding 2).

### S6 multihop case study                                status: done (studies/S6.md)
- Question: why does every centre so far leave multihop flat or worse (val 0.63 -> 0.61; `_mt` 0.28 -> 0.23)?
  Where in depth does the bridge entity appear vs the answer, and what does the family mean remove there?
- Cost: offline first. Source: user (2026-10-10), synthesis.
- Prediction (ad, before the deep dive): on multihop_mt the bridge's pieces sit high in L(mu_fam) at L20-44 (z
  above a random-token control by > 1), less on multihop's country bridges; fam lowers the bridge's rank at most
  layers on both splits. Study file: studies/S6.md.
- OUTCOME: confirmed on multihop_mt (bridge z +2.3 to +2.9 vs control +0.5 to +1.2), present but harmless on
  multihop (+1.4 to +1.8). Causal test: a category-free mean (multihop's) spares the bridge at L20-48 but not at L52-60,
  where any bench mean hides it and where it is read. Insights 1-4 in the study file.

### U4 where J++ and the J-lens differ, seen through our tools    status: done (studies/U4.md)
- Question: can our analysis tools (battery, centres, clusters) locate where the two maps disagree, and does that
  tell us what a centre would have to do to close the gap? An analysis study: no new mu required.
- Starting point (`notes/jpp-compare.md`): plain J++ beats every J-lens arm on typo (bench 0.94 vs 0.76) and is at
  or above the plain J-lens on the single-token families; centring helps the J-lens and helps J++ only on some
  families. Readouts for `jpp:{zero,fam@fit,tok@fit}|{cos,rms}` exist for all 11 families x fit / val / bench.
- Cuts, from cheap to bespoke:
  1. Battery on `jpp:zero|cos` against `zero|cos` and `fam@fit|cos` (`experiments/analyse.py`): which items flip
     each way, at which layers, how ranks move, and the slices (read token, difficulty, said / unsaid, prompt
     length). Are J++'s wins the items the family mean also fixes (the same gap), or different ones?
  2. Centres through both maps: decode each centre's mu with both (`L(mu)` top tokens, `||J mu|| / ||J h||`,
     `cos(J h, J mu)`) per layer and family. Where does subtracting mu move the J-lens readout toward J++'s?
     Measure the agreement of the J-lens's centred readout with plain J++'s (top-10 overlap per cell) against the
     uncentred one.
  3. The difference map `D_l = J++_l - J_l`: its spectrum, the top singular directions decoded through W_U, and
     `||D_l h|| / ||J_l h||` per cell. Is D low-rank? Does it act mostly along the family mean or the token means
     (cos of mu with D's top right singular vectors)? If D h is mostly D mu, a centre can stand in for the map.
  4. Clusters (see "Clusters"): cluster read-cell states (per layer; also the context captures) and report, per
     cluster, the J++ minus J-lens pass gap, `||D h||` and the readout overlap. Do the disagreements concentrate in
     a few regimes? Do J++'s gains line up with clusters a routed mean (U3 variant 1) could target?
- Why: J++ is piecewise linear by construction (U3); if its gain sits in identifiable regimes or directions, that is
  a label-free key for g, and it bears on U3's question C (why map and centre conflict).
- Cost: offline. 1 needs only the readouts; 2-4 load both maps (W_U plus 11 layers of each J): the pod, or
  the Mac under `mac.lock` (about 7 GB). Fairness risk: none (analysis; any g it suggests gets the usual controls).
- Caveat: J++ was fitted on the J++ paper's typo / multihop / multilingual / association items; check concept overlap
  with our banks before reading a typo regime as a lens effect.
- Source: user (2026-10-11); `notes/jpp-compare.md`, U3.

### S10 multilingual_mt guardrail case study        status: done (studies/S10.md)
- Question: why does fam beat every matched centre (tok, knnx8, pco16) on multilingual_mt?
- Answer (offline): the concept unit is read as well or better by the matched centres; they lose the required
  **language** unit (the prompt's language named: " Indonesian", " Arabic"), because they match on language and
  subtract it. The guardrail there is a language-name check. Suggestion for the user: report it per unit.
- Causal test: a same-language family mean reproduces the loss (val pass 0.189, language unit L44 0.06, concept L56
  0.81); an other-language mean keeps it (0.340 = fam; language 0.42).
- Source: S7 insight 4, baseline insight 4 (ad, 2026-10-11).

### S11 a mention control for user_modeling                    status: done (studies/S11.md: premise fails; the lens reads attribute content regardless of attribution)
- Question: do same-request centres (tok, carpos, plain kNN) on UM read the self-description rather than infer the
  attribute? UM's read span is a request shared by 42 of 61 items, so a same-request mean isolates the item's own
  first sentence, exactly the structure that made same-sentence centres read the prompt on DM (U1). UM's strict
  scorer and Haiku cannot rank centres (random controls tie, Haiku saturates at 0.89 for zero), so no existing
  number can answer it.
- Design: for ~30 UM fit items, two renders with the same request: "implies" (the item's own self-description) and
  "mentions" (the attribute-laden words about someone else: "My neighbour is the eldest son in a family of five"),
  plus "absent" (a neutral first sentence). Read cells as UM's. Score the attribute's strict tokens (held = implies,
  mentioned = mentions), rank ratio as in U1 insight 11; references must contain the probe's own requests (rule).
- Cost: a 27B capture of ~90 short renders (minutes on an A100 plus model load, ~$1-2 of pod via the steward); no judge.
- Controls: the U1 ladder (u1rel, u1tokxs, u1endcar, tok, carpos) with shuf. / rand.; absent as the floor.
- Prediction: as on DM, token / request-keyed centres surface the mention condition's attribute about as often as
  the implied one; position-keyed ones separate them.
- Source: study U1 insight 5 / S8 part 2 (the `xs` guard is too blunt on UM).

### S12 same token, other content (`xtok`)              status: done (negative; studies/S12.md)
- g = mean over every occurrence of the read token in the other families' fit renders: tok's form key without the
  family's content (S6 / S10: a mean over cells sharing X removes X). Prediction and controls in studies/S12.md.
- Source: S6 / S10 insight (ad, 2026-10-11).

## Round 2 cards (2026-10-11, synthesis session with the user): fair, label-free g from the lens, not from bench cells

What the round-1 studies fixed (S2-S12, U1-U4): a mean over cells sharing X removes X, which helps when X is the target's
rival (typo's misspelling state, multihop's final answer) and hurts when X is part of the target (multilingual_mt's
language, multihop_mt's bridge category); g built from the item's own states removes its content; token matching reads
the prompt, position matching does not; a regime mean acts through one direction; a better expansion point is not a
better centre. Every centre that beats fam (knnx8, pco16) does it with bench-cell data and fails a guardrail. These cards
try g's that need no bench cells and no family label, mostly built from the lens and the unembedding themselves, so
they are fair by construction; two (S19, S20) are the learned and ceiling rows of the research-loop table, never run.
Order suggested: S15 and S20 first (cheap, reshape the search), then S13 + S14 (shared pullback code), then S16,
S17, S18, S19. All offline from the read-cell captures; S13 / S14 / S15 need W_U and J on the Mac (`mac.lock`, ~7 GB)
or a pod.

### S13 pulled-back continuation prior: g = (W_U J)^+ c             status: done (negative; studies/S13.md)
- Counterfactual: "the cell held nothing but the prior over what comes next." Lesson 2 (synthesis) says one mu per
  layer is a fixed token bias; here the bias is chosen on principle instead of estimated from bench cells. `c` is a
  centred log-prior over the vocabulary; `g_l` is its least-squares pullback through the readout map (`W_U J_l`, or
  the cos readout's row-normalised map), so `L(h - g) = L(h) - c` up to the pullback residual. Variants for c:
  (a) `s13uni`: log unigram frequency of a chat-format corpus tokenised with Qwen's tokeniser (any instruction
  corpus; no bench text); (b) `s13nt`: the mean log-softmax of the model's own next-token distribution over the
  reference pool's cells, other items only (layer 63 of the context captures through the final norm and W_U: the
  next-token baseline the pipeline already computes, aggregated); (c) `s13tmpl`: (b) restricted to cells at template
  slots (the chat-format corpus once captured). Scale beta chosen on fit (c -> beta c); the pullback rank (top-k
  singular directions of W_U J) is the other knob.
- Mechanism: S2 showed fam = the template prior on association and multilingual_mt (a neutral 24-prompt mean matches
  it). If the prior is what fam removes there, a data-free prior should reproduce that gain and leave families where
  fam removes a rival (typo) short.
- Cost: offline; W_U (vocab x d) and 11 layers of J; one pseudo-inverse per layer (cache). No capture.
- Fairness risk: none for (a); (b) is other-derived (never the item's own next-token distribution: S6c). Controls:
  rand. (a random c of the same norm pulled back), shuf. for (b), next-token overlap (expected to fall), echo.
- Prediction (ad, before the run; strict, fit, macro vs fam@self|cos): s13uni -0.04 ± 0.03 (between zero and fam:
  it removes the unigram part of the prior but not the chat-template part); s13nt within 0.03 of fam on association,
  multilingual_mt and basic_readout (prior families), -0.10 or worse on typo (the misspelling rival is not a prior),
  multihop_mt >= fam (no category in c), i.e. the first centre that is fair on multilingual_mt without losing it.
  rand. = zero.
- Infrastructure: `s13uni` / `s13wiki` / `s13nt` / `s13ntf` and `s13:<prior>:<beta>[:<readout>][:r<rank>]` (`src/jlm/mu/S13.py`); the
  pullbacks come from `experiments/precompute_pullback.py --priors ... --next-token all` (the per-cell files need `out/ctx`: pod).
- Source: ad synthesis session with the user (2026-10-11); S2 insight 2, synthesis lesson 2.

### S13t constant template demotion: g = beta (W_U J)^+ 1_T            status: done (half of S14's gain; studies/S13.md)
- Counterfactual: "the cell with its template tokens' scores lowered by a fixed amount": the constant-g analogue of
  S14's projection (which sets those scores to 0 per cell). c = indicator of the first 64 template tokens (S14's T),
  pulled back through the cos map; beta chosen on fit.
- Mechanism: S20 (C, night-2) finds a constant g fitted with fit targets transfers to val at +0.095 over fam, so a
  better fixed bias exists; S14 says the template tokens' reading directions carry most of fam's work. If the bias
  that matters is "push the template down", a constant indicator should do what s14t64 does, minus its adaptivity.
- Cost: offline; one pullback (pod).
- Fairness risk: none beyond S14's T (no targets). Controls: beta = 0 (zero), the shuffled-prior control of S13, and
  the same indicator on S14's randfreq0 tokens if this beats zero.
- Prediction (before the run; fit strict macro vs fam): best beta -0.04 ± 0.03, below s14t64 (a fixed shift cannot
  follow each cell's template score), above zero; multihop_mt >= fam (no category in c).
- Source: study S14 insight 1 x S20's constant-ceiling headroom (A, 2026-10-12).

### S14 readout-aware subspace removal: project out J^T W_U[T]       status: done (label-free finalist S14bL; bench registered, not run; studies/S14.md)
- Counterfactual: "h without whatever the lens would read as template." Let T be a fixed token set (50-100 tokens:
  `<|im_end|>`, `\n\n`, `<think>`, "The", "This", "是什么意思", "____", "called", punctuation: the tokens every decoded
  mean shares, taken from `out/analysis/S4-val-decode/` and the family means' L(mu), never from targets). B_l = span of
  the lens's reading directions for T, `J_l^T W_U[t]`, t in T (orthonormalised); `g = P_B h`. Variants: `s14t64`,
  `s14t128` (|T|), `s14fam` (fam + P_B (h - fam), the pco form with B replacing the data PCs).
- Mechanism: pco16's gain is removing the form axes, its cost is that a family's own PCs carry an answer type
  (multihop) or a language (multilingual_mt). A subspace defined by template tokens cannot carry either. S4's
  kproj64 says a regime's mean acts through one direction, so a small B may do most of a mean's work.
- Cost: offline; W_U rows for T and J per layer; no capture.
- Fairness risk: low (T is content-free by construction). Controls: `pcr` (random subspace of the same dimension);
  T replaced by random tokens of matched frequency; decode the removed part `L(P_B h)` (must be template tokens);
  echo; mention control (umot bank) for s14fam.
- Prediction (ad, before the run; fit, strict, macro vs fam): s14t64 alone -0.03 ± 0.03 (removes the prior, not the
  rival); s14fam = fam ± 0.02 on the template families and >= pco16 on multilingual_mt (no language direction in B),
  < pco16 on multihop (the answer type is not in B, so the bridge is not freed); random-T control = zero.
- Infrastructure: `s14t<k>` / `s14fam<k>` / `s14r<k>` / `s14famr<k>`, k in 16 / 64 / 128 (`src/jlm/mu/S14.py`); token set
  `data/template_tokens/template.json` (`build_priors.py --template-tokens`); bases from `precompute_pullback.py --template-tokens template`.
- Source: ad synthesis session with the user (2026-10-11); S7 insight 5, S4 variant 5.

### S14s template subspace at mid depth, family mean late: sched:<L>:s14t64+fam      status: done (wrong direction: fam early + s14t64 late is the +0.015 one; studies/S14.md)
- Counterfactual: mid depth: "h without its template reading directions" (S14, spares the bridge / language); late:
  "h minus the family mean" (removes the instruction's genre prior, which T does not hold).
- Mechanism: S14 val deep dive: s14t64 wins the _mt families (bridges / language live at mid depth, S6 / S10) and loses
  association / UM at L52-60, where its top 10 becomes the instruction's story-writing prior ("Suddenly", "She",
  "whispered") that fam removes. A switch at L should keep both.
- Cost: offline (S17's `sched:` centre).
- Fairness risk: as fam above L (family label), none below. Controls: the swapped schedule `sched:<L>:fam+s14t64`;
  fam and s14t64 alone.
- Prediction (before the run; fit strict macro vs fam): best L in 40-48, +0.03 ± 0.02, association within 0.03 of fam,
  multihop_mt >= s14t64's 0.525; the swapped schedule <= fam.
- Source: study S14 deep dive (A, 2026-10-12).

### S14c the lens's own generic readout on chat text as the token list       status: done (best bench-free list, fit -0.016 vs fam; studies/S14.md)
- Counterfactual: "h without the reading directions of whatever the uncentred lens reads on any chat cell": T is found
  by running the lens on a generic chat corpus (no_robots renders, `corpus-chat`) and counting its top-10 tokens,
  instead of from bench means (`template`) or corpus frequency (`chatonly`).
- Mechanism: S14 insight 6: the template-specific part of s14t64's gain came from strings only the bench means reveal;
  the lens's own readout on chat text should reveal the generic prior directly (template strings, and genre openers like
  "Suddenly / She", S14 insight 7), bench-free. A late-layer variant (layers >= 48) targets the genre prior.
- Cost: one pod job (corpus states 10 GB, lens, a sample of 32k cells).
- Fairness risk: none (no bench text; targets excluded). Controls: randfreq0 (S14's frequency-matched control), s14r.
- Prediction (before the run; fit strict macro): s14:chatread:64 between chatonly (0.570) and template (0.604), about
  0.59; chatreadlate under fam (sched:40:fam+...) >= sched:40:fam+s14t64 (0.616) on association.
- Source: study S14 insights 6-7, 10 (A, 2026-10-12).

### S14k early centre + template subspace late: sched:<L>:<knnx8|kmx64|pco16>+s14t64      status: done (sched:40:kmx64+s14t64 +0.032 val, guardrail ok; studies/S14.md)
- Counterfactual: early layers: a matched mean (nearest cells, cluster, or family PCs); late layers: "h without its
  template reading directions" (S14).
- Mechanism: S14s: fam early + s14t64 late is +0.026 vs fam (val strict) because the _mt units (language, bridge2) are
  removed by matched means only late; S4 / S7: knnx8 and pco16 beat fam by +0.04-0.05 but lose the language unit (S10,
  read at L44+). Early knnx8 / pco16 + late s14t64 should keep their early gains and S14's late units. kmx64 early makes
  it label-free (kmx64 = fam with no label, S4).
- Cost: offline (`sched:` with existing centres).
- Fairness risk: knnx8's DM same-sentence leak (S4) applies to its layers; report DM separately. Controls: the swapped
  schedules, the components alone, sched:40:fam+s14t64.
- Prediction (before the run; fit strict macro vs fam): sched:40:knnx8+s14t64 +0.04 ± 0.02 (above knnx8's +0.033 fit),
  multilingual_mt >= 0.296; kmx64 version within 0.01 of the fam version (+0.015); pco16 version between.
- Source: S14 insight 10 (A, 2026-10-12).

### S14b a partial mean late: (I - P_B)(h - alpha g_kmx64(h)) above L40            status: done (alpha 0.5: +0.043 vs fam val strict, guardrail ok, judged _mt 0.462; studies/S14.md)
- Counterfactual: late layers: "h without its template reading directions and without part of its cluster's mean".
- Mechanism: S14 insight 12: the late centre decides the trade between association / UM (the instruction's genre prior,
  which a mean removes) and the _mt shared units (language, bridge2, which a mean removes too). A partial mean
  (alpha in 0.25-0.75) under the template projection is a dial between them.
- Cost: offline (`s14:template:64:mean=kmx64:a=<alpha>` inside `sched:40:kmx64+...`).
- Fairness risk: as kmx64 (fit cells, no label). Controls: alpha = 0 (= the S14k arm), alpha = 1, kmxr64 as the mean.
- Prediction (before the run; fit strict macro vs fam): best alpha 0.5, +0.03 ± 0.015 (above S14k's +0.020), association
  >= 0.69, multilingual_mt >= 0.26 (between the two ends).
- Source: S14 insight 12 (A, 2026-10-12).

### S14r the token list from the uncentred readouts of the fit cells                status: done (-0.016 below template: the specials matter; studies/S14.md)
- Counterfactual: as S14, with T = the tokens the uncentred cos readout puts in its top 10 at the fit read cells of at
  least m families (m = 3, 6), targets excluded; no hand list, no decoded means (`experiments/s14_benchread_tokens.py`).
- Mechanism: S14 insight 6: the template-specific part of the gain is the bench format's strings ("____", "是什么意思"),
  which only bench cells reveal. Taking them straight from what the lens reads there is the principled form of the
  hand-assembled `template` list. Risk: shared category words (" city", " famous", "called") enter T at m = 3.
- Cost: list offline (seconds); bases + screen on the pod.
- Fairness risk: bench fit cells' readouts, no targets; a category word in T could remove an answer class (multihop's
  " city"): watch multihop. Controls: randfreq0, s14r, template.
- Prediction (before the run; fit strict macro): s14:benchread:64 = s14t64 ± 0.01 (0.604); multihop <= s14t64's 0.576
  if " city" costs; benchread6 within 0.01 of benchread.
- Source: S14 insights 6 and 11 (A, 2026-10-12).

### S14z the chat specials alone: s14:template:5 (<|endoftext|>, <|im_start|>, <|im_end|>, <think>, </think>)      status: done (+0.036 over zero = 38 % of s14t64's gain; studies/S14.md)
- Counterfactual: "h without the reading directions of the chat template's five special tokens".
- Mechanism: S14 insight 16: a list read off the lens's top 10 misses the specials and loses 0.016; how much of s14t64's
  gain do 5 directions carry?
- Cost: bases for k = 5, 8 (pod) and one screen. Fairness: none (5 fixed tokens). Controls: s14r (random 5-dim, via k)
  is not built; s14:randfreq0:16 is the nearest; zero.
- Prediction (before the run; fit strict macro): s14:template:5 +0.03 ± 0.02 over zero (0.509), well below s14t64.
- Source: S14 insight 16 (A, 2026-10-12).

### S14o over-remove the template subspace: h - (1 + gamma) P_B h                  status: done (negative: gamma 0 is right; studies/S14.md)
- Counterfactual: "h with its template reading component reversed in part": the template tokens' cos scores become
  -gamma x (their uncentred score) instead of 0.
- Mechanism: S14 sets template scores to 0, near the middle of the vocabulary; where a template token still out-scores
  a target, pushing it below 0 should free the slot. Over-reflection also moves other tokens whose reading directions
  overlap B, so it can cost content.
- Cost: offline (`s14:template:64:o=<gamma>`, test in tests/test_round2.py).
- Fairness risk: none beyond S14. Controls: gamma = 0 (s14t64), s14r64 with the same gamma (`s14:...:rand:o=`).
- Prediction (before the run; fit strict macro): gamma 0.5 within ± 0.01 of s14t64 (the template tokens are rarely the
  10th competitor once at 0); gamma 1 lower (-0.01 to -0.03). Also run: S14k with k = 128 late (robustness).
- Source: S14 (A, 2026-10-12).

### S22 the late partial mean from item-free fills (steward's card)               status: done (negative: association back, macro below S14k; studies/S22.md)
- Counterfactual: late layers: "h without the template reading directions and without half of the nearest item-free
  cells' mean", the item-free cells keeping a family's format and genre (S2's hand-written neutral fills) but none of
  its items' content.
- Mechanism: S14 insight 17: S14b's late partial mean must come from bench cells (chat clusters fail). The plan check
  for this card found 9 of 11 families render plain (no instruction text), so the shared late prior is the items' own
  genre; S2's neutral fills keep the genre (association: scene sentences that evoke nothing nameable) without the
  content, so their nearest-cell mean should do kmx64's late work on those families, with no bench item at all late.
- Cost: offline for the S2 pool (4 families, 96 cells); an optional capture of UM / DM fills (`experiments/s22_bank.py`).
- Fairness risk: the fills were authored with the families in mind (S2), never from targets (S2's leak guard). Controls:
  S14b (kmx64 late), the chat-cluster late mean (screen 15, +0.012), s22pm (the pool mean, constant), a = 1.
- Prediction (before the run; fit strict macro vs fam): s22nn8 at a = 0.5 recovers association to >= 0.72 (S14b 0.755,
  chat clusters 0.667) and lands at +0.025 ± 0.01; families without fills in the pool (UM, DM, basic, multihop) near S14k.
- Source: steward (night-2), from S14 insight 17.

### S14n n-scaling of S14b's reference pool (steward's card)                       status: done (25 % of the fit pool holds on val: +0.035-0.048; studies/S14.md)
- Question: how much bench data does the finalist need? kmx64 (early, and as the late partial mean) built from a seeded
  10 / 25 / 50 % of the fit pool's groups (3 draws each; `kmx64n<pct>d<draw>`, `src/jlm/mu/S14.py`), the rest of S14b fixed.
- Mechanism: kmx64's clusters must cover each family's form (S14 insight 17, S22); fewer cells -> coarser clusters ->
  the late partial mean drifts toward a pooled mean (association falls first, then the early typo / UM gains).
- Cost: offline, fit strict cos + rms (18 arms), then val for the smallest share that holds within 0.01.
- Controls: S14b at 100 % (seed spread from B's xcheck: +0.039 to +0.047 on val), S14k, the draw-to-draw spread itself.
- Prediction (before the run; fit strict cos macro vs S14b's 0.633): 50 % within 0.005, 25 % within 0.01, 10 % -0.02 ±
  0.01 (association and UM first); draw spread at 10 % about ± 0.01.
- Source: steward (night-2).

### S14bl S14b-x without same-language late neighbours (B's xcheck-S14bx)            status: done (S14bL, detected language: val +0.060 / +0.062 rms, guardrail ok, judged multilingual_mt = fam; studies/S14.md)
- Counterfactual: as S14b-x (kmx64 up to L40; above, the template projection of h minus half its other-carrier kNN
  mean), with the late neighbours also restricted to prompts in another language when the cell's prompt is not English
  (`knnxl8`, `src/jlm/mu/S14.py`; language from the bank's `lang` field: prompt metadata, never the answer).
- Mechanism: B found 58-83 % of S14b-x's late neighbours on the _mt banks share the prompt's language (base < 2 %): S10's
  language subtraction, the source of its judged multilingual_mt -0.094. Excluding them should keep the language unit.
- Cost: offline. Controls: S14b-x itself (the only change is the exclusion), S14k (judged multilingual_mt 0.491).
- Fairness risk: none new (the exclusion uses the prompt's language, which the prompt shows). Prediction (before the run):
  fit strict macro = S14b-x ± 0.005 (only the 4 language-bearing families can move); multilingual_mt strict >= S14b-x's;
  on val judged multilingual_mt >= fam's 0.340 (S14b-x 0.245).
- Source: B's cross-check of S14b-x (night-2).
- Steward's form (S14bL, same card): the language **detected from the prompt's text** instead of the bank field
  (`knnxd8l`: dominant non-Latin script, else function words + letter signatures; agreement with the bank field on fit +
  val: multilingual_mt 100 / 107, basic_readout_mt 92 / 97, multilingual 117 / 163 (short pt / es prompts read as English),
  English families 168-187 / 168-187 except association 177 / 204). Same prediction; screened next to the field version.

### S14f does removing the "answer frame" alone recover S14bL's gain? (steward: A's own insight)   status: done offline (no: the frame is local, not a list; studies/S14.md)
- Question: S14 insight 26: fam leaves an answer frame (">Name", "called / known", "著名") that S14bL removes. Can the
  reading directions of frame tokens, taken from fam's readouts on fit (no targets), replace the late neighbour mean?
- Prediction (before looking): a frame list from fam's fit readouts shared by >= 3 families would hold the frame and give
  most of S14bL's single-token gain on fit.
- OUTCOME (offline, lists only): no list isolates it. Pooled across families, fam's top-10 shares answer *categories*
  (ocean, animals, cities, countries, temperature), the S6 / S10 failure mode; per family, no frame token reaches 15 % of
  a family's fit items except on DM / UM (chat specials, formatting), and the association name frame is rare on fit
  (">Name" 1 %, "著名" 5 %, "called" 0 %): it belongs to item types (named-entity prompts in val2), not to a family. Not
  screened: a list that removes answer categories is known to cost (S6, S10, S13b).
- Source: S14 insight 26; steward's last card (night-2).

### S15 mu from J's own geometry (diagnostic + centre)                status: done (diagnostic; centre negative; studies/S15.md)
- Question: does fam lie in the directions the lens amplifies? Right singular vectors of J_l are cached
  (`jle/out/x90c-svd/qwen27b`, SVDs of J per layer). Measure, per layer, the share of `||mu_fam||^2`, `||mu_tok||^2`
  and `||h||^2` in the top-k right singular subspace of J (k = 8, 32, 128), vs random directions. The synthesis's
  `||J mu_fit|| / ||J h||` 0.34-0.57 against `||mu|| / ||h||` 0.81-0.98 suggests the lens already *attenuates* the
  mean, so the answer may be "no", which is itself the insight: centring removes what the lens does not attenuate.
- Centre, if the share is high: `s15top<k>`: `g = P_{V_k} h` (remove h's component in J's top-k input directions);
  if low: `s15low<k>`: remove the component in the *bottom* directions is meaningless (J kills it anyway), so the
  centre half of the card closes and the diagnostic is the result.
- Cost: offline, an hour: the SVDs are on this Mac (symlink resolves); read-cell captures for h.
- Fairness risk: none (J only). Controls: random subspace of the same dimension; decode `L(P h)`.
- Prediction (ad, before the run): fam's share in J's top-32 subspace is 2-5x random but under 0.3 (the mean is
  mostly in J's mid-spectrum); s15top32 is below fam on every family (-0.05 or more) and about zero's level with
  typo / association harmed: J's top directions carry content as well as prior. The diagnostic matters more than
  the centre: it tells S13 / S14 which part of the spectrum to pull back into.
- Infrastructure: `experiments/s15_spectrum.py` (the diagnostic, from the cached SVDs) and `s15top<k>` / `s15famtop<k>` / `s15r<k>`
  (`src/jlm/mu/S15.py`); SVDs from `precompute_pullback.py --jsvd` (12 layers; the jle cache holds other layers / a different format).
- Source: ad synthesis session with the user (2026-10-11); synthesis "what centring removes", U3 v5.

### S16 form-blind neighbours, full-state means (kNN fixed)           status: running (j-lens-mean-e1)
- Counterfactual: knnx8's (the mean of the 8 nearest other cells) with the neighbours chosen on form only. S4:
  knnx8's gain is the question-type match (multihop +0.09 on val), its leak is the same-sentence match (S8 insight
  2; DM neighbours share the last 6 tokens for 53-75 % of mid-sentence cells). Choose the neighbours by distance in
  a form subspace, then average their full states. Form subspaces: `s16pc`: the top-16 PCs of the pooled fit cells,
  all families (S7's axes, family-free); `s16tb`: S14's template subspace B; `s16tok`: distance in the embedding of
  the read token plus offset (no h at all: the S8 key as a metric). k = 8 (S4's peak), own group excluded, pool as
  knnx8's.
- Mechanism: form and content separate in the match: matching on form keeps the question-type and template match
  that moved multihop and UM, and cannot pick the same sentence unless its form is also the nearest.
- Cost: offline (the pooled fit cells of S4). Fairness risk: medium (a form subspace can still carry the sentence's
  form). Controls: shuf. (random neighbours of the same count), rand., mention control **with the carrier-sharing
  pool** (research-loop rule), neighbour-overlap diagnostic (share of neighbours sharing the cell's sentence: must be
  near the base rate), content-disjoint variant `s16pcd` as in knnxd8.
- Prediction (ad, before the run; fit strict, macro vs fam): s16pc +0.02 ± 0.02 (below knnx8's +0.033: part of the
  kNN gain is the leak), multihop keeps >= +0.05 of knnx8's gain, DM mid-sentence passes at the fair centres' level
  (7-10 of 76, not 21), multilingual_mt no worse than fam if B carries no language direction (s16tb) and as bad as
  knnx8 if it does (s16pc: the PCs of a pooled fit set include language axes). s16tok = tok ± 0.02 on the template
  families.
- Prediction (e1, night-2, before the run; fit strict, macro vs fam): s16pc8 +0.015 (half of knnx8's fit gain),
  s16pcd8 = s16pc8 -0.005, s16pr8 (random 16-dim form space) +0.005 (any coarse neighbourhood is a cluster mean,
  kmx-like, = fam); DM mid-sentence neighbours sharing the carrier: knnx8 ~60 %, s16pc8 under 25 %. s16tb8 ~ s16pr8
  (the template subspace holds little of the cells' variance, so its neighbours are near random).
- Infrastructure: none new; `clusters.Pool.bench_fit` (the pool), S7's `PCRemoval._basis` or `pullback.load_tbasis` (form subspaces).
  Write the centre in `src/jlm/mu/S16.py`.
- Source: ad synthesis session with the user (2026-10-11); S4 insight 2, S8 insight 2, S7 insight 1.

### S16b outlier-free kNN distance (S18 x S16)                      status: done (negative: s16xo8 = knnx8; studies/S16.md)
- Counterfactual: knnx8's (the mean of the 8 nearest fit read cells, full states), with the neighbours chosen on the
  coordinates the readout uses. S18: 40-70 % of a read state's ||h||^2 sits in a handful of massive-activation
  coordinates that carry none of fam's gain (fam with its top 8 zeroed = fam; fam on them alone = zero). knnx's cosine on
  unit-normalised h is therefore mostly a comparison of those outliers. `s16xo<k>`: zero the 32 coordinates with the
  largest pool-mean |h| (per layer, label-free) before the unit normalisation, then knnx's score; `s16xopc<k>`: the same
  in the top-16 PCs of the outlier-free pool (S16's s16pc lost multihop, plausibly because the pooled PCs are outlier axes).
- Mechanism: neighbours that agree where J reads should share the readout's prior (question type, template) more than
  knnx8's do. Families: multihop, association (knnx8's gains); risk: also more same-sentence content, i.e. more DM leak.
- Cost: offline. Fairness risk: medium (as knnx8). Controls: shuf., rand., the neighbour-overlap diagnostic on DM val
  (`experiments/s16_overlap.py`), and the comparison without UM / DM (where kNN gains are prompt reading, S11 / S8).
- Prediction (e1, before the run; fit strict): s16xo8 macro without UM / DM +0.010 to +0.020 vs fam (knnx8 +0.002,
  s16pc8 -0.014), multihop >= knnx8's 0.706; DM mid-sentence same-carrier share >= knnx8's 0.64 (more content in the
  match, more leak); s16xopc8 between s16pc8 and s16xo8.
- Source: S18 insight 1 + S16 insight 1 (study e1, night-2).

### S20x leave-one-family-out learned constant (S20 x S18)           status: running (j-lens-mean-e1); SUPERVISED (other families' fit targets), user to rule
- Counterfactual: fam plus the part of the "best constant" that is shared across families. S20 (C): a constant fitted
  with fit targets reads val +0.095 over fam; S18 insight 4 (e1): its correction d = ceil.const - fam is dense and
  orthogonal to fam; d_F's cosine with the mean of the other families' d's is 0.2-0.45 at L20-48, 0.05-0.2 at L52-60.
  `s20x:<alpha>`: g = fam_F + alpha * mean_{G != F} d_G. F's own targets never enter; other families' fit targets do
  (the research loop's learned row: a method if it holds on val, with echo and the guardrails).
- Mechanism: if part of what the targets teach a constant is family-independent (a generic token bias of the centred
  readout, e.g. against formatting or function tokens), it transfers to a family whose targets were never seen.
- Cost: offline (C's saved g's + read-cell captures; `experiments/s20x_dbar.py`). Fairness risk: low-medium (learned
  from targets of other families: could encode "answers are content words", a prior, not item content). Controls:
  `s20xr:<alpha>` (random direction, same norm), echo / masked, and the val read (alpha chosen on fit only).
- Prediction (e1, before the run; fit strict, macro vs fam): best alpha in {1, 2}; +0.010 to +0.030 (a third of the
  ceiling or less: the shared part is ~10 % of d's squared norm at the layers that matter); gains on association and
  typo (their d's are the largest shared ones), multilingual_mt flat; the random control within 0.01 of fam; val within
  0.01 of fit's gain.
- Source: S18 insight 4 + S20 (C's) headline; C agreed B owns it (night-2).
- Follow-up S20xu (e1, night-2; the transfer matrix's ensemble insight): add user_modeling's constant (landed after the
  card ran) as an 11th source (`s20xu:1`, `dbar-11.pt`; the frozen 10-source table untouched). Prediction (before the
  run; fit strict): s20xu:1 >= s20xt:1 (+0.041 vs fam) by 0 to +0.010, never below it by more than 0.005 (one more source
  in an average that already cancels each family's own answer class); screened on fit only, val only if it is better.
  OUTCOME: +0.043 vs +0.041 (inside the prediction; one item); not taken to val.

### S20y S20x's correction on top of S14's template removal (with A)   status: done (negative: = s20xt, the correction itself costs the strict language unit; studies/S20x.md)
- Counterfactual: S20x (fam + the other families' target-fitted correction; supervised) loses multilingual_mt's
  language unit (0.62 -> 0.42), A's `s14t64` (h's component in the reading directions of 64 template tokens removed)
  keeps it (0.92 judged), and A's best is `sched:40:fam+s14t64` (val +0.026 strict). Add the correction to those:
  `s20xon:1:s14t64`, `sched:40:fam+s20xon:1:s14t64`, `sched:40:s20xt:1+s20xon:1:s14t64`. alpha = 1 (S20x's fit choice).
- Mechanism: the correction carries the answer-class prior and the CJK-function-word demotion; s14 removes the template
  without averaging over same-language cells, so the language name is not subtracted.
- Cost: offline. Fairness: S20x's (supervised) plus S14's (none). Controls: the parts alone (s20xt:1, s14t64,
  sched:40:fam+s14t64), the random-direction correction on the same base (`s20xon` with s20xr is not built: use the gap
  s20xr - fam = +0.012 as the bound), echo / masked.
- Prediction (e1, before the run; val strict): sched:40:s20xt:1+s20xon:1:s14t64 >= s20xt:1 (+0.042) on the macro and
  passes the multilingual_mt guardrail (language unit >= 0.8 by the piece proxy); s20xon:1:s14t64 (all layers) below the
  schedule (S14 early is worse than fam early, A's result); sched:40:fam+s20xon:1:s14t64 between A's +0.026 and +0.04.
- Source: steward's suggestion; A agreed B owns the arms (night-2).

### S20z label-free statement of S20x's correction: a token-class prior      status: done (null = its permuted control; dbar is orthogonal to the script axis; studies/S20x.md)
- Counterfactual: S20x's shared correction (supervised: learned from other families' targets) decodes to "the centred
  readout gains word-initial Latin tokens and loses CJK tokens" (studies/S20x.md). State that from the tokenizer alone:
  c = -1 on ' [A-Za-z]{2,}' tokens (67.6k), +1 on tokens with a CJK / kana / hangul character (65.9k), 0 elsewhere;
  g = fam + beta * pullback(c) (S13's machinery, cos map): `s13:s20z-latin:<beta>:fam`. No targets anywhere.
- Mechanism: if what transfers in S20x is this coarse script / word-start prior, the token classes should carry it.
  S13t's lesson (one pulled-back vector cannot lower many tokens independently; fit quality 0.95+) is the risk: two
  65k-token classes are the easiest case for one vector (a single "script" axis), the hardest for a template list.
- Cost: one pullback on the pod (W_U + J), then offline. Fairness: none (tokenizer only). Controls: the same values
  permuted over the vocabulary (`s20z-latin-shuf`), beta on fit only, S20x's random-direction control as a bound.
- Prediction (e1, before the run; fit strict, macro vs fam): best beta recovers a third to a half of S20x's fit gain
  (+0.012 to +0.020), mostly typo / association / multihop; the permuted control within 0.01 of fam; multilingual_mt
  down under strict (the same language-unit pieces as S20x).
- Source: S20x insight (dbar decoded), night-2.

### S21 S14k + S20x: the correction on A's label-free schedule        status: val done (early-only +0.047 vs fam, +0.014 vs S14k, guardrail ok; studies/S21.md); SUPERVISED like S20x
- Counterfactual: A's finalist S14k (`sched:40:kmx64+s14t64`: k-means cluster mean of fit cells up to L40, template
  subspace removal above; label-free, val +0.032, keeps the language unit) plus S20x's leave-one-family-out correction
  (supervised; val +0.042, judged _mt 0.487). Arms: `sched:40:s20xon:1:kmx64+s20xon:1:s14t64` (correction at every
  layer), `sched:40:s20xon:1:kmx64+s14t64` (correction early only), `sched:40:kmx64+s20xon:1:s14t64` (late only).
- Mechanism: S14k's gain is the late template removal (language and bridge kept), S20x's is a dense direction that lifts
  multihop / association / typo; if they are independent the gains add.
- Cost: offline. Fairness: S20x's (supervised: other families' fit targets) plus S14k's (fit cells, no label).
  Controls (steward): S14k alone, S20x alone (s20xt:1), S14k + a random direction of dbar's norm
  (`sched:40:s20xron:1:kmx64+s20xron:1:s14t64`), and the per-unit _mt proxy; Haiku on the _mt four only if strict and
  the units disagree.
- Prediction (e1, before the run; val strict, cos): the every-layer version lands near S20x (+0.040 to +0.050), not at
  the sum (+0.07): S20y showed the correction undoes the template removal's language unit (multilingual_mt 0.45 -> about
  0.25 by the proxy); the early-only version keeps S14k's _mt profile and adds +0.005 to +0.015 (S17: centring matters
  late, so an early correction has little to act on); the late-only version = the every-layer version. Random direction
  = S14k +- 0.01.
- Source: steward's card (night-2), S20x + A's S14k.

### S16c the fair DM kNN: knnx8 without same-carrier neighbours          status: done (knnxs8: DM Haiku 0.658, macro +0.041 val; studies/S16.md)
- Counterfactual: knnx8 (the 8 nearest fit read cells of any family) with every neighbour that shares the read cell's
  carrier excluded (DM's `carrier` field: 12 carriers shared by fit and val; elsewhere the last 6 context tokens).
  `knnxs8`. Open-list item (steward): the fair DM kNN that S8 / pilot-1 asked for, on knnx8's global pool rather than
  S8's position key (`s8knn8xs`).
- Mechanism: knnx8's DM val passes are mostly the same-sentence leak (S16: 64 % of mid-sentence neighbours share the
  carrier); without it, what is left is the question-type / slot match, which is fair.
- Controls: knnx8 (the leak), the overlap diagnostic (same carrier must be 0), shuf., the fair DM references (u1rel
  0.57, u1endcar 0.64, s8knn8xs judged) and Haiku on DM val (4 layers, as the references).
- Prediction (e1, before the run; val): DM strict falls from knnx8's 0.297 to 0.10-0.15 (the fair centres' 7-10 of 76
  passes plus a little); DM judged 0.45-0.60, at u1rel's level, not knnx8's 0.79; every other family within 0.01 of
  knnx8 (carriers are DM-only, and the tail rule rarely binds outside DM).
- Source: steward's open list (S8 insight / pilot-1 caveat on knnx8).
- Follow-up control (e1, prediction before the run): the mention control with a carrier-sharing pool
  (`experiments/u1_mention.py --arms knnx8,knnxs8,knnxm8,knnxsm8`; `knnx(s)m8` add the mention bank's own other-pair
  items, which share the probe's carrier, to the pool). knnxm8 leaks (mentioned X 0.4-0.6, held - mentioned under 0.3);
  knnxsm8 stays fair (mentioned 0.10-0.25, held - mentioned >= 0.5), i.e. the same-carrier exclusion is what keeps a
  kNN centre from reading the prompt once the pool can match the context.

### S18b a bench-free corpus mean without its outlier offset            status: done (zeroing the outliers takes wikitext from below zero to zero, not to fam; studies/S18.md)
- Counterfactual: the wikitext mean (G1: "does nothing" as a centre) with its own top-k coordinates zeroed (`s18wc<k>`,
  k 8 / 32 / 128); `s18wfull` = the whole wikitext mean as the reference. S18 insight 2: wikitext's error on the outlier
  coordinates is 0.5-1.2x the readout size of fam's whole dense part, and fam's own outliers carry none of its gain; if
  that error is why corpus means fail, removing the outliers should let the dense corpus mean act like fam's dense part.
- Cost: offline. Fairness: none (wikitext only, no bench cells, no label). Controls: s18wfull, zero, fam, s18r (fam on
  random coordinates), and s18c8 (fam without its outliers = fam).
- Prediction (e1, before the run; fit strict, macro): s18wfull at or below zero (G1, S18's s18ww); s18wc8 recovers a third
  to a half of fam's gain over zero (+0.03 to +0.05 over zero), less than fam because a prose corpus lacks the chat
  template's prior (S2: the template prior is most of fam's gain on association / multilingual_mt); s18wc32 >= s18wc8.
  If s18wc8 is still at zero's level, insight 2 explains the outlier harm but not G1's null.
- Source: S18 insight 2 (e1, night-2).

### S18c the chat-format corpus mean without its outlier offset          status: done (+0.02-0.03 over zero, a quarter of fam; studies/S18.md)
- Counterfactual: S18b's test with template-format cells instead of prose: the chat-corpus mean (no_robots prompts
  rendered as the bench renders, `clusters.Pool.chat`; kmch1 is the same vector) whole (`s18cfull`) and with its own top-k
  coordinates zeroed (`s18cc<k>`). Bench-free and label-free.
- Mechanism: S18b separated the corpus mean's harm (the outlier offset) from its null (prose has no template prior).
  A chat-format corpus has the template; without the offset its dense part may carry fam's template prior.
- Controls: s18wc (prose), zero, fam; S2's neutral fills as the bench-side analogue (neu = fam on association /
  multilingual_mt).
- Prediction (e1, before the run; fit strict): s18cfull between zero and fam (+0.01 to +0.04 over zero), s18cc8 above
  s18cfull by 0.01-0.03 (the offset removed), recovering up to half of fam's gain over zero on association and
  multilingual_mt; typo stays near zero (its gain is the shared misspelling, S2).
- Source: S18b insight 5 (e1, night-2).

### S21b S21's early correction on A's S14b instead of S14k              status: done (val +0.058 cos / +0.057 rms, guardrail ok, +0.015 vs S14b; studies/S21.md); SUPERVISED like S20x
- Counterfactual: S21 (S14k + S20x's correction up to L40) loses association to fam (-0.05 val) because the late template
  projection leaves the family's rewrite frame on top (S21 insight 5); A's S14b keeps half the cluster mean late and
  restores association (0.765 = fam). Arm: `sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5`.
- Controls: S14b alone, S21, the random-direction correction on the same base
  (`sched:40:s20xron:1:kmx64+s14:template:64:mean=kmx64:a=0.5`). Fit first; val once, only if fit beats both parts.
- Prediction (e1, before the run; fit strict): S21b >= S14b (+0.032 fit) by +0.01 to +0.02 (multihop, typo from the
  correction) with association at S14b's level (>= 0.74 fit); random-direction control = S14b +- 0.01.
- Source: S21 insight 5 (e1, night-2).
- OUTCOME (fit): +0.056 vs fam (+0.043 w/o UM, DM), S14b +0.032, S21 +0.038, random-direction control +0.028 (= S14b);
  association 0.745 (S14b 0.755). Within / slightly above the prediction; beats both parts on fit -> one val read.

### S20k S20x source scaling: how many source families the transfer needs   status: done (k=1 hurts, k=4 most of it, saturated at k=6; studies/S20x.md); SUPERVISED like S20x
- Question (steward's card): S20x averages the corrections of all eligible other families (8-10); the transfer matrix
  showed no single source transfers. `s20xk:<k>:<draw>:1` averages k random eligible sources (k = 1, 2, 4, 6, 9; 3
  draws each, seeded by k and draw; own family and twin never drawn; k = 9 takes all eligible), cos and rms
  (`s20xkrms`, C's rms-fitted constants). Fit strict.
- Prediction (e1, before the run; fit macro vs fam, cos): k = 1 +0.008 on average with a spread of 0.03 across draws
  (the transfer matrix at alpha 0.5 spanned -0.011 to +0.033); k = 2 +0.02; k = 4 +0.03; k = 6 and 9 +0.035-0.041 with
  draw spread under 0.01: most of the gain by k = 4, saturating by 6. rms the same shape, about 0.005 lower.
- Note: alpha stays 1 for every k, so small k means a larger-norm, less averaged vector (single-source norm ~2x dbar's);
  part of a small-k shortfall is that, not only the source count.
- Source: steward's card (night-2), S20x transfer-matrix insight.

### S23 per-layer centre selection on fit (label-free set)               status: done (+0.010 over S14b on val, fit +0.034: mostly overfit; random maps as good; studies/S23.md)
- Question (steward's card): S14's schedules switch centres once (L40). Choose a centre **per grid layer** instead, among
  the label-free centres already evaluated: zero, kmx64, s14t64, S14b's late form (`s14:template:64:mean=kmx64:a=0.5`),
  knnxs8 (fam is a labelled reference only). Selection on fit strict macro (all 11 families) by greedy coordinate ascent
  over layers on the exact item rule (any layer, any cell: a schedule's pass is the OR of its components' per-layer
  passes, so it is computed exactly from their readouts), then the chosen map read once on val through the pipeline
  (centre `s23map`).
- Controls: random per-layer assignments from the same set (3 draws, same exact scoring), the best single-switch
  schedule (S14b, val +0.043), the fit-to-val drop of the selected map (overfitting of the selection), rms (the same
  procedure on the rms readouts, its own map), guardrail.
- Prediction (e1, before the run): the fit-selected map beats S14b on fit by +0.01 to +0.02 (12 binary-ish choices over
  5 centres, 11 families of 37-102 items: room to fit noise) and loses most of that on val (fit-to-val drop of 0.01-0.02
  beyond S14b's own), landing within +-0.01 of S14b on val; the map is mostly kmx64 / knnxs8 at L20-40 and the template
  forms above (S17 and S14 insight 12: the late centre decides). Random maps: between zero and S14b. "mu depends on the
  layer" buys little beyond one switch.
- Source: steward's card (night-2).

### S23b how much of each schedule finalist survives its union controls   status: done (each schedule = its best single component within 0.01; no free union gain; studies/S23.md)
- Question (steward's card, from S23 insight 2): pass@10's any-layer rule rewards mixing centres across layers, so a
  two-centre schedule gains from the mix itself. For S14k (kmx64 | s14t64), S14b (kmx64 | S14b-late) and S21b
  (kmx64 + correction | S14b-late), matched union controls, scored exactly offline from per-layer readouts (S23's method):
  (a) the same two centres with the switch layer at every other grid layer, (b) the same L40 split with the centres
  swapped (late centre early), (c) fam / zero two-centre schedules at L40 (fam -> zero, zero -> fam). Cos and rms, fit
  then val. Report each finalist's gain over fam and how much survives against its best matched control.
- Prediction (e1, before the run; val, cos): the swapped schedules are 0.01-0.02 below the finalists (the late template
  forms belong late, S17 / S14 insight 12); other switch layers are within 0.01 of L40 for S14k / S14b (a flat optimum);
  fam / zero schedules sit at or below fam (S17). So most of each finalist's gain over fam survives against its best
  matched control (at least 60 %), the union effect being mostly what random multi-centre maps add, not what one
  well-placed switch adds.
- Source: steward's card (night-2), S23 insight 2.

### S20w a label-free early class prior (S20x mechanism, insight 2a)        status: done (early null; late +0.012 on fit; not to val; studies/S20x.md)
- Counterfactual: the early part of S20x's learned correction, stated from the tokenizer: c = -1 on capitalised word
  starts (" Xxx", 17.7k tokens), +1 on punctuation-only tokens (5.2k), 0 elsewhere, pulled back through the cos map
  (S13's machinery) and added to fam **only up to L40** (`sched:40:s13:s20w-cap:<beta>:fam+fam`), beta in 0.5 / 1 / 2 / 4
  on fit; the all-depth version `s13:s20w-cap:1:fam` as the depth control. No targets.
- Mechanism: S20x's correction demotes punctuation and promotes capitalised names at L24-44 (z -1.2 to -1.5 / +1.0 to
  +1.5); S20z's flat Latin-vs-CJK prior over every layer missed that structure.
- Controls: the all-depth version; S20z (null); S20x (the learned target, early-only version sched:40:s20xt:1+fam on fit
  +0.032).
- Prediction (e1, before the run; fit strict, macro vs fam): best beta +0.005 to +0.015 (a third of the learned early
  correction at most: one pulled-back vector cannot lower 5k tokens and raise 18k independently, S13t), mostly multihop
  and association; the all-depth version below the early-only one.
- Source: S20x mechanism insight 2a (e1, night-2).

### S25 label-free answer-position correction (chat corpus), on S14b-x     status: done (fit gain is UM only; multihop unchanged; not to val; studies/S20x.md)
- Counterfactual (steward's card, from S20w's insight: the early half of S20x's correction needs cells, not token
  classes): from the chat-format corpus (no_robots rendered as the bench renders; every position with its next token),
  d_cls = mean of cells whose next token is a <cls> word - mean of all cells; cls = cap (" Xxx"), content (" xxx", 3+
  letters), latin (" " + 2+ Latin letters). Used as the early correction in place of dbar on A's S14b-x
  (`sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5`, label-free; fit +0.037, val +0.055, val2 +0.052):
  `sched:40:s25on:<alpha>:<cls>:kmx64+s14:template:64:mean=knnxs8:a=0.5`, alpha in 1 / 2 / 4 (raw multiples of d).
  Label-free (no bench cells, no targets in d).
- Controls: d_rand (a random position subset of cap's size: about 0), S14b-x itself, S21b (the supervised dbar version,
  fit +0.056). Fit first, cos and rms; val only if it beats S14b-x on fit; val2 registration before 08:45 if it survives.
- Prediction (e1, before the run; fit strict, cos, macro vs fam): cap best of the three classes; best alpha +0.005 to
  +0.015 over S14b-x (i.e. +0.042 to +0.052 vs fam), mostly multihop (a "the next word is a name" state is what the bridge
  needs), below S21b's learned correction (+0.056); content and latin smaller; rand = S14b-x +- 0.005.
- Source: S20w insight / S20x mechanism (e1), steward's card S25 (night-2).

### S17 depth-scheduled mu                                            status: running (j-lens-mean-e1)
- Counterfactual: a different kind of counterfactual at different depths. S6 finding 2: at L52-60 any bench-cell
  mean pushes the bridge down, and the late layers hold the continuation prior; at mid depth the form mean works.
  `s17`: fam (or u1rel on DM / UM) at layers <= L_s, S13's pulled-back prior (b) at layers > L_s; `s17z`: fam then
  zero (the cheapest form: stop centring late); `s17k`: fam then knnx8. L_s chosen on fit over {40, 44, 48, 52}.
- Mechanism: the bench's item rule takes the best layer, so a schedule can only add passes if the late layers'
  best centre differs from the mid layers'. S6's bridge tables (fam vs zero by layer) say it does for multihop_mt.
- Cost: offline. Fairness risk: that of the parts. Controls: each part's own controls; the schedule with the parts
  swapped (prior early, fam late) must be worse; per-layer pass curves from the battery.
- Prediction (ad, before the run; fit strict): s17z = fam ± 0.01 on every family except multihop_mt (+0.05 to +0.10:
  zero beats fam there late); s17 (with S13b late) >= s17z on association and multilingual_mt. The swapped schedule
  below fam by >= 0.03. Not a macro winner; a multihop_mt fix with no guardrail cost.
- Prediction (e1, night-2, before the run; fit strict): the best L_s for fam+zero is 48 or 52; there multihop_mt
  +0.03 to +0.08 over fam, every other family within 0.02 of fam (typo / association can only lose the few items whose
  only pass is late); macro +0.005 +- 0.01 vs fam. fam+knnx8 at L_s >= 48 keeps knnx8's multihop gain only if it is
  late (S6: knnx8 lifts the bridge by pushing the final answer down at L52-60), so fam+knnx8 = knnx8 -0.01 on multihop.
  The swapped schedules (zero+fam) lose 0.03-0.08 macro vs fam (they drop fam at the mid layers where it wins).
- Infrastructure: `sched:<L>:<A>+<B>` (`src/jlm/mu/schedule.py`), any centres A, B; e.g. `sched:48:fam+zero|cos`, `sched:48:fam+s13nt@fit|cos`;
  the swapped control `sched:48:zero+fam`.
- Source: ad synthesis session with the user (2026-10-11); S6 findings 2 and 5, S2 insight 3.

### S18 sparse mu: the massive-activation coordinates                 status: running (j-lens-mean-e1)
- Counterfactual: residual streams carry a few outlier coordinates that are near constant across positions and
  prompts (the attention-sink / massive-activation dimensions). If fam's gain survives when fam is restricted to its
  top-k coordinates by |value| (`s18k8`, `s18k32`, `s18k128`; the rest of g zero), then a context-free mu of those
  coordinates' typical values (`s18w<k>`: the wikitext mean restricted to the same coordinates, which S4 showed is
  useless as a full vector) gets most of the gain on any prompt with no bench data.
- Mechanism: tests whether "the mean" is a dense form vector or a handful of basis outliers that J maps to the
  continuation prior. Either answer is useful: dense closes this route, sparse gives the cheapest fair centre so far.
- Cost: offline, an afternoon. Fairness risk: none. Controls: fam restricted to k random coordinates; k = d
  reproduces fam exactly; decode `L(g)` for each k.
- Prediction (ad, before the run; fit strict, macro vs fam): s18k32 recovers under half of fam's gain over zero
  (dense mean: the outlier dims carry the norm, not the template); s18k128 about 0.6 of it; s18w32 = s18k32 ± 0.02
  (on the outlier coordinates wikitext and bench agree). Random coordinates: zero's level.
- Prediction (e1, night-2, before the run; after the coordinate diagnostic `experiments/s18_coords.py`: fam's top-8
  coordinates hold 60-90 % of ||fam||^2 at L20-48, h's 40-70 %, and the wikitext mean agrees with fam on them, cos 0.9-0.99,
  same size): since the full wikitext mean does nothing (G1), the outliers cannot carry fam's gain. Fit strict, macro:
  s18k8 and s18k32 within 0.02 of zero; s18c32 (fam without them) within 0.01 of fam; s18k512 recovers 0.2-0.5 of fam's gain;
  s18w32 = s18k32 +- 0.01; s18r<k> = zero +- 0.01 up to k = 512. The answer is "dense": the route closes, and the outlier
  coordinates are what G1 and fam share, i.e. a norm, not the template.
- Infrastructure: none new (fam restricted to coordinates is a small `KeyedMean` variant; the wikitext mean is `Pool.wiki`). Write `src/jlm/mu/S18.py`.
- Source: ad synthesis session with the user (2026-10-11); synthesis "||mu|| / ||h|| = 0.81-0.98".

### S19 learned g with the controls as the loss                       status: done (negative; studies/S19.md: the removal-only loss crowds the top 10)
- Counterfactual: the research-loop table's "learned" row, never run. Per layer, `g = A h + b` with A of rank r
  (r in {4, 16}) fitted on the reference pool (fit cells of all families, own group out at read time) to minimise the
  readout mass that `J(h - g)` puts on (i) the cell's prompt tokens and (ii) the model's own next-token top-k at that
  cell, plus `lambda ||g||^2`; no targets anywhere. `s19r4`, `s19r16`; `s19b` = rank 0 (b only: a learned constant,
  comparable with S13).
- Mechanism: fairness as the objective rather than a post-hoc check. The failure mode is a g that removes
  everything (hence the rank limit and the norm penalty) or that learns the family's content axes (hence the pooled
  fit, own group out).
- Cost: offline; a few minutes of Adam per layer on the Mac. Fairness risk: medium (learned rows are the riskiest
  category). Controls (research-loop "learned" row): the same fit with prompts shuffled across items; fit-val gap;
  prompt-masked pass@10; mention control (carrier-sharing pool); decode `L(g)`; `shuf.`, `rand.`.
- Prediction (ad, before the run; fit strict, macro vs fam): s19b = S13b ± 0.03 (they estimate the same object);
  s19r16 within 0.03 of pco16 on the template families, with echo and next-token overlap below every other arm,
  multilingual_mt at fam's level (the loss does not reward removing the language), and the shuffled-prompt control
  within 0.02 of s19r16 (if the control matches, the gain is the constant b, not A).
- Infrastructure: the lens (`jlm.lens.Lens`), prompt token ids (`jlm.controls.mask_ids`), the next-token top-10 per cell
  (`out/eval/<family>/<split>/next-token/readouts.jsonl`, or `ContextStore.at(item, 63, i)` + `Lens.logits`). Fitter to write (`experiments/s19_fit.py`).
- Source: ad synthesis session with the user (2026-10-11); research-loop "the space of g", learned row.

### S20 headroom ceilings per class of g (diagnostic, in-sample)      status: done (studies/S20.md: const ceiling +0.10 val strict over fam on the single-token families, _mt gains a proxy artefact; h-dependence adds ~0 except DM)
- Question: how much can each class of g gain at all? Fit on `fit` *with targets* (allowed by the "no crystal ball"
  rule as an in-sample ceiling, labelled as such, never a method) the best constant mu per layer, the best per-token
  mu, the best per-cluster mu (S4's kmx64 clusters) and the best rank-k projection (k = 16), with J++'s sigmoid
  surrogate of recall@10 (`umot/experiments/jpp_compare.py` has the objective; Adam, early stop). Report in-sample and
  leave-one-group-out on fit, and the val read of each as an upper bound (`ceil.const`, `ceil.tok`, `ceil.clu`,
  `ceil.proj16`).
- Why: if the constant-vector ceiling is only a little above fam, constant-mu work (S13, S14, S18, S2) is bounded
  and the headroom is in h-dependent g (S16, S19); if it is far above, a better fixed bias exists and S13 / S19b
  should find it. Also the ceilings per family say where the readout, not the centre, is the limit (multihop_mt).
- Cost: offline, an evening. Fairness: none as a method (it is not one); the arms carry a `ceil.` prefix so the
  leaderboard and dashboard show them apart, never as candidates.
- Prediction (ad, before the run; fit strict, in-sample, macro): ceil.const +0.05 to +0.08 over fam (a fixed bias
  tuned to the targets buys a little); ceil.tok +0.10; ceil.proj16 +0.15 or more (the largest class); leave-one-group-out
  gives back more than half of each in-sample gain. On multihop_mt every ceiling stays below 0.5: the bridge is not
  linearly on top at any grid layer for half the items.
- Infrastructure: `experiments/ceilings.py --family F --split fit [--val] [--classes const,tok,clu,proj16] [--device cuda]`
  -> `out/analysis/S20/F-fit.{json,md}` (`ceil.` arms; never on the leaderboard).
- Source: ad synthesis session with the user (2026-10-11); README "reconstructing the optimal mean"; synthesis "not
  done".

### S20b readout-frequency prior: demote what every readout surfaces        status: done (null; studies/S20.md: pullback reaches ~17 % of the prior; frequent tokens are answer classes)
- Counterfactual: "h without what the lens reads in every cell whatever it holds." S20's target-fitted constant (val
  strict +0.14 macro over fam through the pipeline) demotes CJK function tokens and the question's relation word
  ("number", "solid", "two", "until") in every family, and promotes the family's answer class (B, studies/S20x.md).
  The demotion half needs no targets: tokens that sit in the fam readout's top K of most cells, in other families.
- g: `s20b:<K>:<beta>` = fam + beta * pullback(c_F), c_F = log(eps + mean over the other 10 families G of the share of
  G's fit cells with t in the top K of J(h - mu_G)), rescaled to the layer's top-1-to-top-K score gap
  (`experiments/s20b_prior.py`, `src/jlm/mu/S20.py`). An IDF of the readout. Family F's prior never sees F's cells.
- Mechanism: lowers generic, every-cell tokens so item-specific ones rise; acts like S13 with a prior chosen from the
  readout rather than from text frequency. Could hurt where the answer class itself is frequent across families
  (number words: basic_readout, multilingual) or where a relation word is the target (typo_mt?).
- Cost: offline, one pod pass (W_U + J, pullback caches exist). Fairness risk: low (no targets, other families only;
  the prior is a fixed vector per layer, so it cannot read the prompt). Controls: `rand.` (same norm), beta = 0 (= fam),
  a prior of random tokens with the same frequency profile (`s20b` shuffled over the vocabulary: to write if it
  survives), echo / masked / next-token from evaluate.py.
- Prediction (19c, 02:58, before the run; fit strict, macro vs fam@self): best beta in {0.5, 1}: +0.02 to +0.04
  (half or less of the ceiling's +0.09 on fit 3-fold, the template / CJK half), largest on association and multihop
  (+0.05), typo flat, basic_readout / multilingual flat or -0.02; beta 2 overshoots (below fam).
- Source: study S20 insight 4 (decode of the ceilings; B's S20x decode).

### S20u one learned constant for every family, no family label                status: done (negative vs fam: -0.02 val; +0.03 over the pooled mean; studies/S20.md)
- Counterfactual: "the one fixed bias that best lets any cell's target into the top 10", learned from other families'
  targets only. S20: a per-family constant fitted with targets gains +0.14 over fam (val strict); B's S20x: fam_F plus
  other families' corrections +0.042 (+0.04-0.10 on items whose targets are in no fit bank). S20u drops the family
  label altogether: g_l is one vector, fitted on the pooled fit cells of 10 families (cells weighted so each family
  counts equally) and read on the 11th (`s20u`, leave-one-family-out); `ceil.u` (all 11 families) is the in-sample
  version (out/analysis only).
- Mechanism: the shared half of the ceiling (Chinese function tokens and template demoted in every family; the
  relation words) is family-independent; the answer-class half is not, and a pooled fit averages the classes, so it
  should promote "named entities / content words" in general.
- Cost: one pod pass (W_U + J; 11 x 12 small fits). Fairness: targets of other families only (the research-loop
  learned row; B's S20x precedent); no family label, so it is also label-free at read time. Risk: shared answers
  across families (multihop / basic_readout / multilingual: 28-49 % of val items share a target with other families'
  fit); report the gain on items whose targets are in no fit bank. Controls: rand. (same norm), the pooled mean of
  all fit cells (label-free, untuned: `s20u0`), fam, the leave-one-family-out read itself is the transfer test.
- Prediction (19c, 03:45, before the run; fit strict @self, macro): s20u (lofo) above the untuned pooled mean by
  +0.10 or more and within 0.02 of fam (it has no label but learns the template / CJK demotion); above fam on multihop
  (+0.05) and association; below fam on typo (typo's rival removal needs the family's own misspelling state).
  rand. at zero's level. On items with targets in no fit bank, the gain over the pooled mean holds.
- Source: study S20 insights 1 and 4; B's S20x.

### S20r anchored ceilings: does shrinking the learned constant toward fam transfer better?   status: done (null; studies/S20.md)
- Question (diagnostic, WITH fit targets like S20): S20's failure mode 3 is the learned constant promoting fit items'
  own answers, which crowd val readouts. An L2 that pulls g toward fam (not toward zero, as S20's did) should keep the
  shared part (template / relation-word demotion) and drop item-specific promotions. Sweep lambda in {10, 100, 1000}
  (`ceilings.py --l2-anchor init`), const class, the five single-token families, 3-fold + val. Also tells B's S20x
  which constants to average.
- Prediction (19c, 04:38, before the run): lambda 100 raises val on association by +0.01 to +0.03 over the unanchored
  ceiling (fewer fit answers crowding) and leaves typo / multihop within 0.01; lambda 1000 falls back toward fam;
  3-fold and val agree on the best lambda.
- Source: S20 insight 6 (failure mode 3).

### S24 a fresh held-out dev split (val2): read the night's finalists once           status: done (studies/S24.md: S20x / S21b / s20xon +0.05, S14b-knnxs8 +0.052, S14k +0.003 on val2)
- Why: tonight val chose among S14 / S20x / S21 forms; research-loop: author a new dev split rather than keep re-reading
  val; the bench is spent for S14.
- Items: Sonnet subagents author from jle's x90 briefs, with an avoid list of every target used by the bench, fit, val
  and jle's banks v2 / v3 (targets only; no bench prompts shown). Families: typo, association, multihop (person and
  object_animal subfamilies only: closed classes share answers with fit). Rules, all mechanical and fixed before any
  read: jle's x90 filters (schema, duplicate, bench overlap, multiword, leak, single-token reachability), no target
  shared with bench / fit / val / v2 / v3 or another val2 item, jle's 27B gate unchanged (1 greedy + 10 draws, T 0.7,
  strict string grader, >= 0.8). Every gate-passing item is kept; no centre or lens picks items. `experiments/s24_build.py`.
- Read once, strict, cos, refs = fit: zero, fam@fit, S14k `sched:40:kmx64+s14t64`, S14b
  `sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5`, S20x `s20xt:1`, S21b `sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5`.
- Prediction (19c, 05:04, before any val2 read; macro over the three families, Δ vs fam): the val order holds,
  S20x >= S21b > S14b >= fam > S14k > zero, with gains about two thirds of val's (val, these 3 families: S20x +0.083,
  S21b +0.065, S14b +0.023, S14k -0.011): S20x +0.05 ± 0.03, S21b +0.04 ± 0.03, S14b +0.01 ± 0.02, S14k -0.02 ± 0.02,
  zero -0.15 or worse. Largest single gain: S20x / S21b on multihop (+0.08). If S20x's val2 gain is under +0.02, val's
  number was selection.
- Added before the read (steward, 05:06): B's single centres `s14:template:64:mean=kmx64:a=0.5` (S14b's late part at every
  layer) and `s20xon:1:kmx64` (S20x correction on the cluster mean), and A's S14b with a late knnxs8 mean
  (spec from A). Prediction (19c, before the read): each within ±0.02 of its parent (S14b, S20x / S21b) on val2; none
  above S20x.
- Final arm list (registered 05:07, before any val2 read; strict, refs = fit, `--no-next`: val2 has no context capture):
  cos: `zero`, `fam@fit`, S14k `sched:40:kmx64+s14t64@fit`, S14b `sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit`,
  S14b-knnxs8 `sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit` (A), S20x `s20xt:1@fit`, S21b
  `sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit`, `s14:template:64:mean=kmx64:a=0.5@fit` (B),
  `s20xon:1:kmx64@fit` (B); rms: `fam@fit`, `s14:template:64:mean=kmx64:a=0.5@fit`, `s20xonrms:1:kmx64@fit` (B).
  B's prediction: each single centre within 0.01 of its schedule, both >= +0.02 over fam (cos).
- Source: steward's card (night-2); research-loop "Fit chooses, val confirms".

### S24b val2 extended: multihop's closed-answer subfamilies and multilingual (val2b)     status: done (studies/S24.md: multihop S20x +0.074, s20xon +0.128, but on shared answers; multilingual at ceiling)
- Items: as S24 (Sonnet authors from jle's briefs, targets-only avoid lists, jle's x90 filters, the 27B gate unchanged,
  A's audit before the read), split `val2b`. multihop: country (45) and calendar (25), element_material (30), number (15);
  multilingual: 90 (German / French / Spanish / Italian / Portuguese). **Rule, stated before the read**: country,
  calendar, number and multilingual are closed answer sets, so jle's rule applies there (a new prompt / subject; the
  answer may repeat a bank's; a `seen_prompt` check drops any prompt of fit / val / val2 / v2 / v3); element_material
  keeps S24's rule (no target shared with any bank). Every item carries `fresh_target`; every number is reported
  split into fresh and shared answers.
- Read once, the same 12 arms as S24, strict, refs = fit.
- Prediction (19c, 05:40, before any read; Δ vs fam): multihop val2b: S20x +0.08 ± 0.04, S21b +0.08 ± 0.04, s20xon single
  +0.08 ± 0.04 (the answer-type subfamilies are where S6 put the cross-family correction's effect), S14b-knnxs8 +0.05 ±
  0.03, S14b +0.03 ± 0.03, S14k +0.02 ± 0.03, zero below fam. multilingual val2b (no-harm guardrail, near ceiling): every
  arm within ±0.03 of fam; none below fam by more than 0.03. On shared-answer items the supervised arms gain at most
  0.05 more than on fresh ones.
- Amendment (05:45, before the gate and the read; A's audit + steward): two multilingual prompts were near-copies of
  val (word-prefix rule added; dropped). `fresh_target` (the scored concept: multihop's bridge, multilingual's English
  word) was checked against every bank's target AND intermediate strings; A found the *final answers* of multihop items
  shared with bench / fit / val (Asia, euro, solid, letters...), so a second flag `fresh_answer` (the final answer not
  among any bank's strings) is added. **Headline = items fresh on both** (multihop 29: country 23, element_material 5,
  number 1; multilingual 81); all / shared reported beside it. element_material's bridges are fresh, 25 / 30 of its
  final answers are not: it is reported with the closed-answer items. Predictions unchanged.
- Source: steward's card; S24 caveat (A's audit).

### S24d val3: a second fresh batch, more power on the clean split                  status: done (studies/S24.md: pooled 607 items S20x / s20xon +0.051, S14bL +0.039, S21b +0.039; not separated)
- Why: val2's macro intervals are about ±0.03, too wide to rank S14bL / S14b-knnxs8 (+0.052) against S20x (+0.050) and
  s20xon (+0.056). val3 adds ~300 items under S24's rules (Sonnet authors from jle's briefs + a targets-only avoid list
  that now includes val2 / val2b; jle's filters; no target shared with any bank or another item; the 27B gate; A's
  audit; read once). typo, association, multihop (person / object_animal).
- Read once, strict, cos, refs = fit: zero, fam, S14bL `sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5`, S14b-knnxs8,
  S20x `s20xt:1`, s20xon `s20xon:1:kmx64`, S21b, and rand. of S14bL, S20x, s20xon. Report val3, and val2 + val3 pooled
  (items pooled within family, macro over the three families, paired bootstrap).
- Prediction (19c, 06:23, before any val3 read; Δ vs fam, macro): S14bL +0.05 ± 0.03, S14b-knnxs8 +0.05 ± 0.03, S20x
  +0.05 ± 0.03, s20xon +0.055 ± 0.03, S21b +0.05 ± 0.03; every rand. control within ±0.015 of fam; zero -0.15 or worse.
  Pooled val2 + val3: the five arms' Δ within 0.02 of one another, no pair separated by its interval (a tie between
  the label-free and the supervised arms on fresh single-token items).
- Note (06:55, before the read): val3.json was rebuilt from the captures after the capture pod's termination lost the
  frozen files; the item set is exact, the per-item gate results are lost.
- Source: steward's card; S24 (val2's width).

## Round 3 cards (proposed at the end of night-2 by A, j-lens-mean-2e, from tonight's insights; steward's request)

Context: the night's label-free finalist is S14bL (studies/S14.md): kmx64 up to L40; above, the template projection of h
minus half the mean of its 8 nearest other-carrier, other-language fit cells. Val strict +0.060 / +0.062 (rms), fresh
val2 + val3 +0.039 [+0.018, +0.059] (= supervised S20x within noise), bench registered and not run. These cards attack
what it leaves: DM, the answer-class prior, the local answer frame, and the untested multi-token half.

### R3a DM: S14bL with a position-matched late mean                       status: proposed (night-2)
- Counterfactual: on DM read cells (every token of the copied carrier), "h without the template directions and without
  half of the mean of other-carrier cells at the same offset in the read span" (U1's u1rel key inside S14bL's late kNN:
  neighbours restricted to the cell's offset from the end of its span, other carrier, other language).
- Mechanism: S14bL's DM judged 0.487 (think - dont_think +17) trails the fair position means (u1rel 0.566, u1endcar 0.645)
  whose contrast is only +7 / +8 (xcheck-S16: their sentence-final passes surface the forbidden concept). The late kNN
  matches form but not position; adding the offset key should lift think-twin passes without the end-of-copy leak,
  because the template projection already removes what the end cell's prompt reading rides on.
- Cost: offline (a NearestMean key; DM val is 76 items, 4-layer Haiku ~$0.85 per arm).
- Fairness risk: position matching inside one family's carriers (U1: position is fair, token is not). Controls: S14bL,
  u1rel, u1endcar; the polarity split (`experiments/dm_polarity.py`) as the primary fairness read, mention control with a
  carrier-sharing pool (knnxsm-style pool).
- Prediction: DM judged 0.55-0.62 with think - dont_think >= +15 (S14bL +17), other families = S14bL ± 0.005.
- Source: S14 / xcheck-S16 (A), U1 (pilot-1).

### R3b a label-free answer-class prior from fit read cells, by the model's own next token   status: proposed (night-2)
- Counterfactual: early (L <= 40) only, "h without the direction that separates fit read cells whose *model-predicted*
  next token is a capitalised word / name from the rest" (the model's own greedy next token at each fit cell from the
  context captures; never a target), scaled by alpha on fit, added to S14bL's early part.
- Mechanism: S20x's useful early correction promotes names (answer class) at L24-44 (B's S20x mechanism); S20w (token
  classes pulled back) and S25 (the same contrast on chat-corpus cells: UM only) show it needs bank-format *cells*. The
  model's own next-token prediction labels fit read cells by answer class without any target.
- Cost: offline (next-token top-1 per fit cell is in `out/eval/<family>/fit/next-token/`; one mean difference per layer).
- Fairness risk: the next token is the model's output, not the answer, but on single-cell families it can equal the
  answer: exclude the cell's own item and its family (leave-one-family-out, as S20x does) and report the share of fit
  cells whose next token is a target. Controls: a random cell split of the same size; S25's chat version; supervised S21b.
- Prediction: fit +0.005 to +0.015 over S14bL, mostly multihop (S21b's gain there is +0.10 over S14b); random split = 0.
- Source: S20x / S20w / S25 (B), S21b, steward.

### R3c the local answer frame: per-cell frame directions from the neighbours   status: proposed (night-2)
- Counterfactual: late, "h without the reading directions of the tokens its 8 nearest other-carrier cells' fam-centred
  readouts share" (a per-cell token list: the frame those neighbours carry, e.g. ">Name / getName / 著名" for named-entity
  prompts), instead of subtracting the neighbours' mean state.
- Mechanism: S14f: the answer frame fam leaves is local to item types, so no global token list holds it, but the
  neighbours do; projecting out a per-cell frame subspace (as s14t64 does for the template) may keep more content than
  subtracting half the neighbour mean (S14 insight 26: S14bL's gains are content freed from the frame).
- Cost: offline but heavier (W_U rows for the per-cell tokens: reading directions computed on the fly on the pod).
- Fairness risk: the neighbours' readouts could contain the cell's own answer if neighbours share it (other-carrier and
  own-group exclusion as in knnxs8; report the share of cells whose target is in the per-cell list). Controls: random
  per-cell token lists of the same size; S14bL.
- Prediction: = S14bL ± 0.01 on the macro; association +0.02 over S14bL; costs where the frame is the answer type
  (multihop_mt).
- Source: S14f / S14 insight 26-27 (A).

### R3d a fresh multi-token split (val4-mt) for the _mt families and the language fix   status: proposed (night-2)
- Question: S14bL's multilingual_mt fix (judged 0.245 -> 0.340 for S14b-x -> S14bL; language unit 0.87) has only val
  behind it; val2 / val3 are English single-token families, where the exclusion is inert.
- Design: C's S24 pipeline for multilingual_mt, basic_readout_mt and multihop_mt (60-80 items each, the dev mt pipeline's
  author / filter / gate, avoid lists incl. every split tonight), language mix like val's; captured on a capture pod
  (~$1-1.5), then one registered read (strict + Haiku on the four _mt families, ~$0.3 per arm) of fam, S14b-x, S14bL,
  S14k and the supervised arms.
- Prediction: S14bL - S14b-x on judged multilingual_mt +0.05 to +0.10 (val +0.095), language unit S14bL >= fam;
  S14k the best judged multilingual_mt (val 0.491).
- Source: S14bL evidence caveat (A), steward.

## Studies

| id | owner | status | question | headline | file |
|---|---|---|---|---|---|
| S24d | 19c | done | val3: second fresh batch (303 items), read once; pooled with val2 | pooled (607): S20x / s20xon +0.051 [+0.030, +0.073], S14bL = S14b-knnxs8 +0.039 [+0.018, +0.059], S21b +0.039; supervised minus label-free +0.012 [-0.009, +0.033] | studies/S24.md |
| S24b | 19c | done | val2b: multihop's closed-answer subfamilies + multilingual, read once | multihop: S20x +0.074, S21b +0.064, s20xon +0.128 vs fam, all on shared-answer items (fresh subset at ceiling); label-free ~0 to +0.04; multilingual at ceiling (no harm) | studies/S24.md |
| S24 | 19c | done | a fresh held-out dev split (val2), read once | on 306 fresh items S20x / S21b / s20xon +0.05 vs fam (CIs > 0), label-free S14b-knnxs8 +0.052, S14k +0.003; single-token families only | studies/S24.md |
| S20 | 19c | done | headroom ceilings per class of g (fitted WITH fit targets) | a constant g tuned with targets gains +0.096 val strict over fam on the single-token families (+0.11 rms; +0.09 judged on DM); its _mt proxy gains do not survive Haiku (scorer overfit); h-dependent classes add ~0 except DM; it promotes the family's answer class and demotes CJK function tokens and relation words; S20b (target-free IDF prior) null; S20u (one constant for all families, other families' targets) -0.02 vs fam | studies/S20.md |
| S19 | 19c | done | learned g, no targets, loss = keep prompt + next-token ids out of the top 10 | negative: every variant (rank 16, tied, constant) reads below zero (fit macro 0.08-0.35); the loss crowds the top 10; the directions that read the prompt also read the targets | studies/S19.md |
| fresh | 19c | done | night-2 finalists on fresh vs shared answers | S20x keeps +0.05 over fam on answers absent from other families' fit (cos and rms); S21 +0.016; S14k / s14t64 at or below fam on the single-token families | studies/fresh.md |
| S22 | 2e | done | S14b's late partial mean from item-free fills | 9 / 11 families render plain; S2's neutral fills recover association late (0.725) but the macro (+0.016) is below S14k: negative | studies/S22.md |
| S14 | 2e | done (finalist S14bL) | remove the lens's reading directions of template tokens; then a partial late neighbour mean | s14t64 (no reference cells) = fam on val with the best judged _mt profile; **S14bL** (kmx64 <= L40; above, template projection of h minus half its other-carrier, other-language kNN mean; label-free) val strict +0.060 cos / +0.062 rms, guardrail ok, judged multilingual_mt = fam, registered fresh val2 read +0.052 / +0.046, val3 +0.023, pooled +0.039 [+0.018, +0.059]; bench strict (registered): S14b +0.022, S14k +0.020; S14bL bench registered, not run | studies/S14.md |
| S15 | 2e | done | where fam sits in J's spectrum | J reads the mean as strongly as the state (‖Jμ‖/‖Jh‖ ≈ ‖μ‖/‖h‖); outside the massive coordinates fam is what J amplifies most; removing J's top directions is below fam (s15top32 -0.08 fit) | studies/S15.md |
| S13 | 2e | done | pulled-back continuation priors (unigram, next-token, template indicator) | negative: unigram prior below zero (its tail), head = zero, the next-token prior removes multihop_mt's bridge, a constant template demotion reaches half of S14's gain (-0.045 vs fam fit) | studies/S13.md |
| S18 | e1 | done | is fam's gain in the massive-activation coordinates? | negative: dense. fam without its top-8 coords = fam (fit +0.001), fam on them alone = zero; wikitext values there are worse than zero (their readout error is 0.5-1.2x fam's dense effect); S20's better constant differs from fam only in dense coordinates | studies/S18.md |
| S17 | e1 | done | a different centre at different depths | negative as a method: centring matters at L >= 40 (zero then fam from L40 = fam on val); stopping fam late wins multihop_mt's bridge (+0.08) and loses four families (-0.032); fam then knnx8 = knnx8 | studies/S17.md |
| S16 | e1 | done | knnx8 with neighbours chosen on form only (+ S16b outlier-free distance, S16c other-carrier) | form-only matches fail (PC space loses multihop; outlier-free = knnx8); **S16c knnxs8 (no same-carrier neighbours) is the fair knnx8**: val +0.041 macro, DM Haiku 0.658 (knnx8 0.789 leak, u1endcar 0.645) | studies/S16.md |
| S20x | e1 | open (supervised: user to rule) | does the cross-family part of S20's target-fitted constant transfer? | yes on val: +0.042 strict vs fam (+0.036 w/o UM, DM; random dir. +0.012), multihop +0.13; Haiku beats fam on all four _mt (multilingual_mt 0.396 vs 0.340), DM not confirmed; S20y (on top of S14) = S20x | studies/S20x.md |
| S21 | e1 | open (supervised: user to rule) | S14k (A) + S20x correction | correction up to L40 only on S14k: val strict +0.047 vs fam (+0.048 w/o UM, DM), guardrail ok, +0.014 vs S14k (multihop +0.10, typo +0.05), random dir. +0.001; Haiku _mt = S14k; rms with rms-fitted correction +0.042 (cos-fitted +0.006; S14k +0.020); **S21b** (on S14b) val +0.058 cos / +0.057 rms, guardrail ok, seed-stable, +0.015 vs S14b; Haiku _mt / DM add nothing over the bases | studies/S21.md |
| S23 | e1 | done | per-layer centre selection on fit vs one switch | fit +0.034 over S14b, val +0.010 cos / +0.002 rms: mostly overfit; random maps as good; pass@10's any-layer rule rewards mixing centres (union of five centres 0.698) | studies/S23.md |
| S6 | ad | done | why centring fails multihop; the g's it spawns | both multihop banks score the bridge; the family mean holds its category (z +2.5 in L(mu) vs +0.8); knnx8 / pco16 lift it by pushing the final answer down; g from the item's own states (S3, S9, pdf) removes content | studies/S6.md |
| S2 | ad | done | neutral fills that vary the family's shared attribute | neu = fam on association / multilingual_mt (data-free template prior); spares multihop_mt's bridge at mid depth (val 0.31 vs fam 0.26); loses typo (0.75 vs 0.92): the shared misspelling is the target's rival | studies/S2.md |
| S12 | ad | done | same token, other families' renders (xtok) | negative: fit macro 0.572 (fam 0.601, tok 0.637); fair (mention 0.38 / 0.01) but weak: the token alone is not what tok matches | studies/S12.md |
| S10 | ad | done | why fam wins multilingual_mt | matched centres lose the language-name unit, not the concept (concept L52: pco16 0.62, knnx8 0.58, fam 0.51; language L44: fam 0.38, others <= 0.08) | studies/S10.md |
| S3 | ad | done | g from the previous position (corpus lag-1 predictor) | negative: below zero at every ridge strength (macro 0.43-0.46 vs 0.51); the item's own past carries its content | studies/S3.md |
| S7 | ad | done | subspace removal (pco, tpco, xpco) | pco16 val strict +0.039 vs fam, fair on the mention control (0.82 / 0.24), but judged multilingual_mt -0.11 (guardrail): a family's own PCs hold its content axes there; xpco null | studies/S7.md |
| S4 | c0 | done | cluster / kNN means, label-free (U3 v1, 5, 6) | knnx8 (mean of the 8 nearest fit read cells, any family): +0.05 macro vs fam (val strict), multihop 0.61 -> 0.70, UM Haiku 1.00 (UM can't separate user modelling from prompt reading, S11), DM Haiku 0.79 = tok does not count (mid-sentence passes are the same-sentence leak; fair in-pool kNN ≈ 0.27 strict, S8); kmx64 = fam with no label; kNN = cluster PCA = family PCA (one local subspace); wikitext clusters fail; cost: multilingual_mt (-0.11, the language) | studies/S4.md |
| U4 | c0 | done | where J++ and the J-lens differ | the maps disagree mostly along the family's shared component (cos(Dh, Dmu) 0.8-0.9); J++'s gains sit in the regimes a label-free cluster mean also fixes (corr +0.74); J++ and centring stack on our banks (jpp:tok +0.04 vs tok) | studies/U4.md |
| U1 | cc | done | how much of position matching is fair (ladder fam -> carpos + mention control) | token matching, not position, reads the prompt: `u1rel` (same offset in the read span) fair (held 0.78 / mentioned 0.23, transfers across sentences) vs tok 0.82/0.59, carpos 0.95/0.91; DM val Haiku u1rel 0.57 (zero 0.17, shuf 0.28; tok 0.79, extra all mid-sentence); val macro = tok (cos 0.622; rms 0.634 vs 0.626); wikitext position mean hurts | studies/U1.md |
| S8 | cc | done | tightness as a dial (position mean -> same-token, EB, kNN within position) | no fair setting beats the position mean beyond noise: DM strict gains come with mention leak step for step; s8knn32 +0.030 vs fam (val, guardrail ok); knn reads the same sentence once it is in the pool (A's knnx8 caveat) | studies/S8.md |
| S11 | cc | done | UM mention control (implies vs the same words quoted about a colleague) | premise fails: even the plain lens surfaces the attribute more for the quote (0.97 vs 0.70), every centre alike: UM readouts carry prompt content regardless of attribution; UM pass@10 cannot separate user modelling from reading the prompt | studies/S11.md |
| S5 | cc | done | subtract the category word's direction (scale on fit) | null as a method (+0.003 vs fam, random words match; UM gain from adding "person" back is a bias: 0.30 on information-free prompts); diagnostic: the item's language-name direction alone moves multilingual_mt's language unit 0.56 -> 0.96 (added) / 0.17 (removed), concept flat (C's mechanism, caused) | studies/S5.md |
| baseline | f3 | done | reference arms + controls on every bank | gains are content (random g ≈ zero); token matching drives DM / UM; fam hurts multihop_mt (random beats it by +0.18) | studies/baseline.md |
