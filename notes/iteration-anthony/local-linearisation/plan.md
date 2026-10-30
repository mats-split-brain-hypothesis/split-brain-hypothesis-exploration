# LL: local linearisation, where J++'s experts meet the centre

A programme, not a card: a multi-phase study of how the slope (the lens map) and the expansion point (the centre)
of the J-lens should be chosen together, and how locally. Started 2026-10-11 from a discussion with the user.
Supersedes U3 variants 2-4 in `../mu-log.md` (U3 variants 1, 5, 6 are S4, done). Separate from the overnight
cards: its own notes live in this folder, its results in `out/analysis/LL*/`, its page is
"Understand → Local linearisation" on the dashboard.

Primary objective unchanged: a better J-lens readout (pass@10 on our banks, fit chooses, val confirms). Using J++
(its released map, our own experts, its weights) as part of a readout is allowed for this programme (user,
2026-10-11; `../research-loop.md` updated). So is the compute to fit our own expert Jacobians.

Source: Ayonrinde & Lindsey (2026), "J++ Lens: Jacobian Filtering Enables More Faithful Workspace Lenses"
(LessWrong `nc9dHfcB22JdMzGbr`; code `safety-research/jpp_lens` @ 93f02cd; lens `koayon/jpp-lenses` @ 6c96867).
Sections used here: Methods (eq. 2a-2c), "Why does the J++ lens work?", App. D "Three views of the J-lens",
App. E "Approximate global linearity", App. G "What is in the bad experts?", "Rank of the averaged Jacobian" (Fig 17),
"Null and negative results" (bias addition, single-token Jacobians).

## 1. The argument

**Notation.** `f_l(h)`: the transport map from the block-l residual to the final residual (averaged over contexts and
target positions, as the lens averages). `J(x)`: its Jacobian at x. A cluster `C_i` of corpus positions at layer l,
its mean `mu_i`, its expert `J_i = E[J(h) | h in C_i]`. J++: `J++ = sum_i w_i J_i`, signed `w`, unit L2, fitted on a
dev set. The J-lens: `J = E[J(h)]` over all positions (the pooled Jacobian).

**(a) J++ pairs each tangent with the wrong anchor.** `J_i` is, to first order, the tangent of `f` at `mu_i`
(`E[J(h) | C_i] = J(mu_i) + O(curvature x spread)`). The first-order expansion that belongs to that tangent is

    f(h) ≈ f(mu_i) + J_i (h - mu_i)

J++ reads `J_i h`, i.e. the tangent taken at `mu_i` but anchored at the origin. That is exact only if `f` is linear
through 0, and 0 is no ordinary point for a pre-norm residual stream (every block starts with an RMSNorm, singular at 0;
in our captures `||mu|| / ||h||` is 0.81-0.98). The consistent pair is `(J_i, mu_i)`.

**(b) Mean-value form: why the anchor should be local.** Exactly,

    f(h) - f(m) = [ ∫_0^1 J(m + t (h - m)) dt ] (h - m)

The right slope for `(h - m)` is the Jacobian averaged along the segment m → h. A cluster-averaged `J_i` approximates
it when both h and m lie in `C_i`. With m = 0 the segment crosses every regime and the norm singularity. (This is
integrated gradients with baseline m, averaged over the population: choosing mu is IG's baseline problem.)

**(c) J++ relaxed the slope, never the anchor.** App. E: the authors set out to show global linearity fails, tried
piecewise-linear experts, and found some experts good everywhere, raising their credence in global linearity. Every
expert there was anchored at 0. Our results show that with one global slope a local anchor helps a lot (fam,
tok, knnx8 / kmx64 in S4). Hypothesis: **global slope, local intercept**.

**(d) The three views each have a slot for mu.**
- Workspace view: the lens surfaces tokens the model is "*differentially* disposed to verbalise". Differential to
  what: mu is that reference.
- Iterative-inference view: `J` is the linear term of a Taylor expansion of the transport map. A Taylor expansion has
  an expansion point: mu.
- Unsupervised-probe view: each token's probe is `p_t = J^T W_U[t]`, scored `p_t · h`, a hyperplane through the
  origin. Centring gives every probe a bias `-p_t · mu`. A linear probe without a bias is the odd choice.
- Also: J++ notes the lens is "a homogeneous linear map rather than an affine map", tried a fitted bias (mixed),
  and filtered tokens instead. A centred lens is affine, with its bias from the model's own geometry.

**(e) The user's readout.** `R(h) = sum_i w_i J_i (h - mu_i)`, in two forms that differ in kind:
- *global weights* (J++'s `w`): `R(h) = J++ h - b`, `b = sum_i w_i J_i mu_i`. One affine map per layer, label-free,
  no read-time cost. Caveat: `w` is signed and unit L2, not a convex combination; a negative-weight expert adds
  `|w_i| J_i mu_i` back. The offset may need its own weights (`b = sum_i v_i J_i mu_i`, or `J++ mu_w` with
  `mu_w = sum_i w_i pi_i mu_i / sum_i w_i pi_i`).
- *routed weights* `r_i(h)` (hard or soft, from the router): `R(h) = sum_i r_i(h) J_i (h - mu_i)`, a piecewise-affine
  lens: a mixture of local linearisations. J++ Fig 14 found routing harmful, but with `J_i h`. Untested with anchors.

## 2. Hypotheses (each with what would refute it)

- **H1 consistent pair.** For each expert, `J_i (h - mu_i)` reads better than `J_i h`, and better than `J_i (h - mu_j)`
  for j ≠ i. Refuted if `mu_j` (wrong cluster) does as well as `mu_i`: then the gain is generic centring, not pairing.
- **H2 bad-expert rescue.** The experts J++ filters out (recall@10 < 2 % alone, mostly early layers, "formatting
  experts") gain the most from their own anchor. Refuted if the bad experts stay bad when centred: then they are noise
  (J++'s reading), not mis-anchored tangents.
- **H3 linearisation error.** Held-out first-order error `||f(h) - f(m) - J_m (h - m)|| / ||f(h) - f(m)||` falls as m
  moves from 0 → global mean → cluster mean → kNN mean; and bad experts have the largest error in their own cluster
  (answers J++'s Future Work question on curvature). Refuted if error is flat in m: then anchors help the readout for
  counterfactual reasons only (synthesis lesson 1), not linearisation.
- **H4 global slope, local intercept.** On the slope × intercept grid (§3), the local-intercept column carries most of
  the gain; slope locality adds little beyond filtering, and what it adds is confined to early layers (Fig 17: experts
  disagree early, agree late).
- **H5 map and centre fit together.** Centring hurts J++ on its own evals (umot: rms 0.594 → 0.48-0.50) because `w`
  was fitted on uncentred inputs. Refitting `w` on centred inputs (or on the H1 readout) makes centring and filtering
  add on J++'s evals as they already do on our banks (U4 insight 4).
- **H6 routing returns.** With local anchors, routed `sum_i r_i(h) J_i (h - mu_i)` beats the global-weight form at
  equal fairness, reversing J++ Fig 14.

## 3. The design space

    R(h) = W_U · sum_i r_i(h) · J_i · (h - m_i(h))

| slope \ intercept | 0 | one global mu | regime mu_i / kNN mu(h) |
|---|---|---|---|
| pooled J | J-lens (baseline) | `fam`, `ctr1` (done) | S4 `knnx8`, `kmx64` (done) |
| filtered `sum w_i J_i` | J++ released (done) | `jpp:fam` (U4, done) | **`sum w_i J_i (h - mu_i)` (new, H1/H5)** |
| routed `r_i(h) J_i` | J++ Fig 14 (hurt) | `r_i(h) J_i (h - mu)` | **piecewise affine (new, H6)** |
| single expert `J_i` | J++ Fig 3 | `J_i (h - mu)` | `J_i (h - mu_i)`, `J_i (h - mu_j)` (H1, H2) |

Plus two further axes, crossed sparingly: Jacobian type (plain gradient, as the n1000 J-lens; LRP, as J++) and
where the clusters come from (wikitext, as J++; our fit cells + chat corpus, as S4 found necessary).

## 4. Phases

**LL0 infrastructure and reproduction** (pod; the one big spend)
- Clone `safety-research/jpp_lens` @ 93f02cd (LRP backward, router, weight fitter); read its fitting loop before writing
  ours.
- One backward sweep, many clusterings: the backward pass already gives the gradient at every source position, so bin
  each position into E experts for several clusterings at once (k = 8, 16, 64; wikitext and our corpus routers),
  accumulating `sum J`, the count, and `sum h` per bin (so `mu_i` is exactly the anchor of the positions behind `J_i`).
  Memory: k × 5120² fp32 = 105 MB per expert-layer; k = 64 at 7 layers ≈ 47 GB on disk in fp32 (fp16: half).
- Fit corpus: J++'s (1000 wikitext prompts, 128 tokens, skip the first 16) for reproduction, plus a chat-format /
  template corpus built from fit-split prompts only (no val or bench text).
- Layers: J++'s 7 recipe layers (L8-L56) first.
- Plain-gradient experts first (the J-lens is the primary objective), LRP at the same layers second.
- Validation gates before anything else is read: k = 1 reproduces the pooled J-lens (cos ≥ 0.99 per layer); refitting
  `w` on our LRP experts gives cos(sum w_i J_i, released J++) and held-out recall@10 near 0.594 (umot `jpp_compare.py`).
- Cost: time one prompt first. U3's guess was 8 H100-hours ($20-40) per Jacobian type; budget about $100 for LL0.

**LL1 diagnostics, before any readout** (cheap)
- Geometry: `||mu_i||`, `||mu_i|| / ||h||`, inter-expert cosine per layer (reproduce Fig 17 on ours), where val cells
  land (as S4's `diag-bench.md`).
- H3: first-order error by anchor. f(m) needs a forward pass from a patched state (m is not a real context's state:
  patch it at the read cell, run the rest of the network, read the final residual at t ≥ s). Held-out positions
  only. Per expert and per depth.

**LL2 single experts** (reads only; H1, H2)
- Each expert × anchors {0, global mu, `mu_i`, `mu_j` (shuffled), fam, `knnx8`} on our banks (fit) and J++'s held-out
  evals. The dumbbell plot of §dashboard: recall alone vs recall with its own anchor, per expert, per layer.

**LL3 combined maps** (reads only; H4, H6)
- The §3 grid, both Jacobian types, both router corpora. New arm prefixes in `jlm.lens` (map) crossed with
  `jlm.mu` centres, so every existing centre still composes.

**LL4 joint fitting** (H5)
- Refit `w` with J++'s fitter on centred inputs and on the paired readout. Separate offset weights `v`. Learned
  per-cluster offsets as a ceiling (overlaps S19, S20): fitted on fit, scored on val, with the controls.

**LL5 beyond first order** (open)
- Path-integrated slope: average `J` at a few points on the segment m → h (JVPs at read time; a ceiling, not a lens).
- Second-order term (J++ App. E's other relaxation): Hessian-vector products along `h - m`.
- Soft routing temperature; depth-scheduled locality (S17).

## 5. Controls and fairness

- Random cluster assignment with the same sizes (experts and anchors); `mu_j` for j ≠ i (the pairing control);
  `shuf.` and `rand.` of every new arm; k = 1 must equal the pooled lens exactly.
- Echo, prompt-masked pass@10, the mention control where a bank has one. Fit chooses, val confirms, bench records.
- Experts and anchors are fitted on corpora that contain no val or bench text.
- Two scorers: our banks (primary) and J++'s held-out readout evals (their claim, their ground).

## 6. Open questions for the user

- Budget for LL0 (proposed ≈ $100) and whether LL runs inside the overnight loop or as day sessions.
- Plain vs LRP experts first (proposed: plain first, since the J-lens is the primary object).
- Whether to ask the J++ authors for their router, experts and weights as a cross-check of our reproduction.

## Next (from night-2)

- Resolve the gate: ask for n1000's fit command (prompt selection, dtype, stopping rule); or refit the pooled J with
  Neuronpedia's pipeline settings on the same prompts. Until then LL results are provisional.
- Experts from our own corpus (chat / template prompts, fit split only): o8 was starved on wikitext; the regimes our
  cells live in need their own slopes. Then LL4 with those experts.
- LL4 robustness: w16 / k = 32 experts, a second router seed, weights fitted on half the fit split (stability),
  bench as the record for a finalist (`ll4w8:zero|cos`, `ll4w8f:fam@fit|cos`), the judge on the `_mt` families.
- LRP experts (J++'s backward rules): J++'s +10 over plain experts on its evals may come from LRP; untested here.

## Log

- 2026-10-11: plan written; dashboard page "Local linearisation" (Understand). No runs yet.
- 2026-10-12 (night-2, instance j-lens-mean-a3; details and numbers in `log.md`): LL0 swept 353 wikitext prompts
  (3 H100s, plain gradients, L24-56; w1 / w8 / w16 / o8 / r8 binned in one sweep). **k = 1 gate failed** at L24-48
  (cos to n1000 0.85-0.98): systematic, not sampling noise; not the kernel, skip_first or seq length; unexplained.
  The pooled J reads like n1000 on our banks (13-28 of ~700 items differ) and better on J++'s evals. Provisional
  results on top: H1, H2, H3, H5, H6 refuted; H4 supported; wikitext regimes are partly articles and barely visit
  our banks' cells. **LL4: J++'s weight fit on our fit banks over plain wikitext experts gives val +6.2 (cos,
  uncentred; = J++'s released lens on our val) and +2.0 on top of fam, guardrail held; random bins recover under
  half.** w16 experts: `ll4w16:zero|cos` val 0.602 vs 0.519 (+8.3, no family below 0; level with J++'s released
  lens), stable across fit halves, and the weights transfer to J++'s evals (0.375 -> 0.490). The weights follow
  expert quality, not where our cells live. Bench (registered, read once, strict): 0.532 vs `zero|cos` 0.445
  (+8.7) and J++ released 0.519. Spend ~$51 of the $100 pot; all pods terminated.
