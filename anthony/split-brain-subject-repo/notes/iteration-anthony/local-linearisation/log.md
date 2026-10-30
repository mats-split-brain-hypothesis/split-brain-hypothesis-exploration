# Programme LL: log

Status (final for night-2, 07:26 BST):
- **What ran**: LL0 sweep (353 wikitext prompts, 3 H100s, plain-gradient experts w1 / w8 / w16 / o8 / r8 at
  L24-56); LL1 landing, gate, H3; gate diagnosis D1-D3; LL2 / LL3 screens on fit and val; J++'s held-out evals
  (validated scorer, refitted weights, transfer); LL4 (weights fitted on our fit banks) through the official
  pipeline on val with paired intervals, r8 control, half-split stability.
- **Gate FAILED** (k = 1 vs n1000: cos 0.85 / 0.88 / 0.95 / 0.98 / 0.997 at L24-56): systematic, not sampling
  noise, not the kernel, skip_first or seq length; unexplained (n1000's fit settings are unknown). The pooled J
  reads like n1000 (D2: 13-28 of ~700 items differ). Everything below is provisional on that.
- **Headline (val, official pipeline)**: J++-style signed weights over our plain-gradient wikitext experts, fitted on
  the fit split: `ll4w16:zero|cos` 0.602 vs `zero|cos` 0.519 (+8.3; no family below 0; association +28, typo +25,
  UM +10 significant), level with / just above J++'s released lens (0.583); +2 on top of fam; rms 0.467 -> 0.628;
  stable across fit halves; random-bin experts recover under half; the weights transfer to J++'s evals (0.375 ->
  0.490). Hypotheses: H1, H2, H3, H5, H6 refuted; H4 supported: global filtering of slopes plus a bank intercept,
  not local linearisation.
- **Spend**: $50.63 of the $100 LL pot (sweep ~$37; all pods terminated by 07:25).
- **Next**: resolve the gate (n1000's fit command); experts from our own corpus; LRP experts; bench record and the
  judge on `_mt` for the LL4 finalist (`ll4w16:zero|cos`; bench strict 0.532 vs 0.445, J++ 0.519: prediction met).

## Night-2 (2026-10-12), instance j-lens-mean-a3

### 01:15-01:42 Reading and design decisions
- J++'s fitting loop (`safety-research/jpp_lens` @ 93f02cd, `fitting/jacobian_fitting.py`, `expert_fitting.py`) and
  jlens' (`jlens.fitting`, the n1000 lens's code) use the same estimator: one forward on the prompt replicated B
  times, then `d / B` backward passes, each with a one-hot cotangent at output dim r at **every kept position**; the
  gradient at source position p is row r of `G_p = sum_{kept p' >= p} dh_final[p'] / dh_l[p]`. jlens averages
  `G_p` per prompt then over prompts; J++'s experts are position-weighted means per cluster. With 128-token prompts
  every prompt has 111 kept positions (16 skipped, last dropped), so the two coincide.
- **Cost is set by `d x seq` token-backwards per prompt** (5120 x 128), independent of B and of how many
  clusterings are binned: about 2x the FLOPs of a forward over 650k tokens per prompt, i.e. minutes per prompt on
  one GPU. The night is wall-clock bound, not only $-bound.
- Decisions (each to be revisited after timing):
  - **Layers: 24, 32, 40, 48, 56** = J++'s recipe layers (8..56 by 8) intersected with our bank grid (20..60 by 4).
    L8 / L16 cannot be read on our banks, and starting the graph at L24 instead of L8 shortens every backward
    from 55 to 39 blocks (~30 % less compute).
  - **Corpus: wikitext only** for the backward sweep (the first N of the n1000 lens's and J++'s 1000 prompts), so
    k = 1 is gated against the released n1000 lens on a subset of its own data. Our corpus enters through the
    router (`o8`: J++'s recipe fitted on every dev family's fit read cells) and through anchors, which need no
    backward pass. A chat-corpus backward sweep is cut for tonight.
  - **Clusterings binned in the one sweep** (bins per layer): `w1` (pooled, split by prompt parity: 2), `w8`
    (J++'s E, split by parity: 16), `w16` (16), `o8` (8), `r8` (random bins with w8's per-layer proportions,
    the size-matched control: 8). 50 bins x 5 layers x 105 MB = 26 GB fp32 in host RAM.
  - **k = 64 experts cut**: at a few hundred prompts a 64-way expert averages ~500 positions (a ~5-prompt J-lens),
    too noisy to be worth 30+ GB. k = 64 *anchors* (S4's kmx64) are free: anchors need only forward states.
  - Checkpoints store per-bin means in fp16 plus counts (13 GB per shard), resumable.
- Code: `src/jlm/mu/LL0.py` (routers reimplementing J++'s `routing.cluster`; `Accumulator`; `sweep_prompt`),
  `experiments/ll0_sweep.py` (routers / sweep / merge), `tests/test_LL0.py` (k = 1 equals `jlens.fitting` on a toy
  model; every clustering's bins sum to the pooled J and the global mean).

### 02:00-02:10 Pod, routers, LL1 landing
- Pods: `ll0` and `ll0b` both landed on machine [host] (A100 PCIe, US-MO-1), which never gave an IP (also the
  steward's experience); terminated after 23 / 13 min ($1.06 together). `ll0c` = H100 80GB at $3.99/h
  (`GPU_IDS` override added to pod.sh, [pipeline candidate]), IP at once.
- Routers pre-pass (`ll0_sweep.py routers --prompts 400`): forward only, 400 prompts in 40 s; 44,323 kept positions
  per layer (110.8 per prompt). w1 / w8 / w16 fitted on them (J++'s recipe), r8 with w8's proportions.
- **LL1 landing (`out/analysis/LL1/landing.json`)**: the first o8 (J++'s recipe on *all* our fit cells) was
  degenerate: user_modeling (1294 cells) and directed_modulation (688) took the 8 clusters and the other nine
  families (37-102 cells each, one per item) shared one cluster at every layer. Refitted with at most 102 cells per
  family (seeded subsample; `refit-o8`): now it separates families / templates (association, typo, DM, UM each
  their own cluster; basic_readout / multihop / multilingual split across two), and **val lands where fit lands**
  (shares within a few points). The wikitext router w8 puts our cells into 2-3 of its 8 clusters per layer; 4-5 of
  J++'s 8 regimes hold no bank cell at all. So on our banks a w8 "routed" readout uses only 2-3 experts, and the
  experts J++ filters may be ones our cells never visit. The uncapped router is kept as `routers-o8uncapped.pt`.

### 02:10-02:30 Timing and the sweep's size
- **Timing (one prompt, H100, batch 8)**: 125 s/prompt with transformers' reference PyTorch `chunk_gated_delta_rule`
  (flash-linear-attention not installed), of which ~20 s were 3200 host syncs. With `flash-linear-attention` 0.5.2
  installed in my pod checkout and rows binned on the GPU: **84 s/prompt** steady state (first prompt 168 s: Triton
  JIT). Then host adds moved to a thread and batch 16 (peak 73.4 GB of 80).
- **Noise (2 prompts vs the n1000 lens)**: cos between two single-prompt pooled Js is 0.21 (L24), 0.46 (L40),
  0.88 (L56): per-prompt noise power is ~3.8x the signal at L24, ~1.2x at L40, ~0.13x at L56. Since our prompts are
  the first N of n1000's own 1000, the k = 1 gate (cos >= 0.99) needs N ~ 160-200 at L24; an 8-way expert at
  N ~ 300 should sit near cos 0.93 to its own limit at L24, better deeper. **Target ~300 prompts.**
- One pod would need ~7 h for 300 prompts: **three H100 pods** (`ll0c/d/e`, $3.99/h each), shards `i % 3`, each
  stopping at a deadline (~05:05 BST) and checkpointing (fp16 means + counts) to its **container disk**: the shared
  volume is at ~140 of 150 GB (hf 62, out 66, uv-cache 11), no room for 13 GB per shard. The timing checkpoint
  (13 GB) was deleted from the volume at once. Merge: shards copied pod-to-pod with a pod-generated key.
- Projected LL0 spend: 3 x ~2.8 h x $3.99 ~ $34 plus setup; pot after LL0 ~ $60 for reads and LL4.

### 02:30-02:40 Downstream scripts, while the sweep runs
- `experiments/ll2_screen.py` (LL2 single experts x anchors per layer; LL3 slope x intercept grid per router) passed a
  smoke test on the eval pod with stand-in experts (2 families, 2 layers): the n1000 rows reproduce the pipeline's
  own arms restricted to the same layers (typo fit L40+56: zero 0.663 = 0.663; fam 0.815 vs 0.826 and J++ 0.761
  vs 0.772, one item of 92 each, a near-threshold rank under GPU numerics). Finalists go through `evaluate.py`.
- `experiments/ll1_h3.py` (H3: first-order error of slope J at anchor m on held-out wiki positions, by patching m
  into the forward pass; anchors zero / glob / own / other / knn x slopes pool / n1000 / own expert).
- `experiments/ll4_fitw.py` (H5: J++'s weight fitter re-done on our fit banks: rms-linear logit cache, soft macro
  pass, signed unit-L2 w; anchors 0 / own (paired) / fam / knn; scored fit + val, cos + rms, against the pooled
  map). Checked on synthetic data (finds the planted expert, negative weight on an anti-expert).
- Second scorer (J++'s held-out readout evals): umot's `jpp_compare.py` and the captured eval residuals
  (`umot/out/jpp/residuals.pt`, L8-56) can score our maps; queued after LL2-LL4 (needs J++'s venv on a pod).

### What the dashboard page ("Understand -> Local linearisation") should show (for whoever lands the page)
The page files are uncommitted in the main checkout, so tonight's instance wrote none. Data for it:
- `out/analysis/LL1/landing.json`: per router (w8, w16, o8) and layer, each family's fit / val share per cluster:
  a stacked bar per family (fit and val side by side), one panel per layer. Point: J++'s wikitext regimes are not
  our banks' regimes; 4-5 of 8 w8 clusters hold no bank cell.
- `out/analysis/LL1/experts.json`: the gate (cos(w1, n1000) per layer, with the split-half cosine as the noise
  floor), and per router the inter-expert cosine matrix per layer (a small heatmap per layer: J++'s Fig 17 on
  ours), `||mu_i|| / ||h||`, cos(J_i, pooled).
- `out/analysis/LL1/h3.json`: first-order error by anchor (x) and slope (colour), one panel per layer: H3's test.
- `out/analysis/LL2/fit/single.json`: the dumbbell plot of the plan: per expert and layer, pass@10 at that layer
  with anchor 0 vs own vs other (the pairing control), macro over families; one row per (router, layer, expert).
- `out/analysis/LL2/fit/grid.json` (and `val`): the slope x intercept table per router (rows n1000 / pool /
  routed, columns 0 / glob / local / fam / knn), macro and per family, with r8 (random routing) beside w8.
- `out/analysis/LL4/<router>/scores.json`: fitted vs pooled weights per anchor, fit and val, cos and rms.

### 02:45 Second scorer validated (J++'s held-out readout evals, `experiments/ll_jpp_evals.py`)
Released maps, rms readout with Readout Filtering, held-out macro recall@10 (`out/analysis/LLjpp/scores.json`):

| map | anchor | 7 recipe layers (8..56) | our 5 layers (24..56) | umot (7 layers) |
|---|---|---|---|---|
| n1000 | none | 0.339 | 0.337 | 0.340 |
| n1000 | ref (eval's fit-split mean) | 0.444 | 0.432 | |
| J++ | none | 0.591 | 0.580 | 0.594 |
| J++ | ref | 0.474 | 0.456 | 0.484 |

The scorer reproduces the paper / umot within 0.3 points (fp32 vs their bf16; our port of the filter list). L8 and
L16 add ~1 point, so our 5-layer cut loses little on J++'s ground. The puzzle H5 addresses stands on our 5 layers:
centring helps n1000 (+9.5) and hurts J++ (-12.4).

### 02:55 Mid-sweep check: J++'s router clusters wikitext partly by article
After 15 prompts (shard 0: prompts 0, 3, ..., 42) several w8 bins were still empty (L24: clusters 1 and 2 hold 0
of 1665 positions, though they hold 3.5 % and 8.3 % of the router's 44k positions). Not a routing bug: in the
pre-pass states, clusters 1 and 2 at L24 come from one contiguous block of wikitext records (prompts ~110-180,
consecutive paragraphs, i.e. one or a few articles). The k-means on unit-normalised residual directions (J++'s
recipe) partly separates **documents / topics**, not only positional or syntactic regimes. Consequences: (1) each
expert's position count depends on which articles the sweep covers (fine here: the router saw prompts 0-399, the
sweep covers ~0-360); (2) some of J++'s "regimes" are topics, so a "bad expert" may be an article-specific slope
rather than a formatting regime: worth remembering when reading H2.

### 03:25 Early gate read (shard 0 alone, 45 prompts)
cos(pooled J, n1000): L24 0.828, L40 0.940, L56 0.995; ||J|| / ||n1000|| 0.98-0.99 (no scale bias). Split-half
cos (22 vs 23 prompts): 0.84 / 0.97 / 0.997, i.e. per-prompt noise ~4.3x the signal power at L24, as the 2-prompt
estimate said. Projected for ~380 merged prompts (a subset of n1000's own data): cos ~0.996 at L24, so the k = 1
gate should pass. w8 experts vs the pooled J (one shard): L24 0.41-0.74, L40 0.47-0.89, L56 0.68-0.99; how much is
noise will be read from the split halves after the merge.

### 05:10 LL0 sweep done and merged
- Shards: 125 + 109 + 119 = **353 prompts** (wikitext records 0-~360), 39,136 kept positions per layer, ~79 s
  per prompt per H100. Shards stopped at their deadlines (05:00-05:07), copied pod-to-pod (~40 s per 13 GB) and
  merged on `ll0c` into `/root/ll0-ckpt/experts/experts-L*.pt` (fp16 J means, fp32 mu, counts; container disk;
  also copied to `ll0d`). `ll0e` terminated. Pot after the sweep: ~$37.
- Bin counts (positions per expert): w8 1,0xx-13,9xx (every bin populated once the sweep passed the article
  clusters); w16 828-6,382; r8 matches w8's sizes. **o8 is starved**: wikitext positions fall almost entirely into
  one or two of its clusters (L24: 32,161 in one cluster; the clusters holding directed_modulation, multihop and
  user_modeling cells get 5, 51 and 214 positions; one gets 0). So **wikitext barely visits our banks' regimes**:
  an expert for the regime our cells live in cannot be fitted from wikitext. The chat-corpus backward sweep cut
  for tonight is the fix (next night, if LL2 says experts matter).

### 05:15 GATE: k = 1 does NOT reproduce the released n1000 lens at L24-L48 (`out/analysis/LL1/experts.json`)

| layer | cos(our pooled J, n1000) | norm ratio | split-half cos (176 vs 177 prompts) | cos predicted by sampling noise alone |
|---|---|---|---|---|
| 24 | **0.854** | 0.980 | 0.906 | ~0.98 |
| 32 | **0.878** | 0.904 | 0.968 | ~0.99 |
| 40 | **0.950** | 0.985 | 0.995 | ~0.999 |
| 48 | **0.981** | 0.997 | 0.9986 | ~0.9997 |
| 56 | 0.997 (pass) | 0.989 | 0.9996 | ~0.9999 |

The gate (cos >= 0.99) passes only at L56. Sampling noise does not explain the gap: our own two halves agree far
better with each other than with n1000 (at L40 0.995 vs 0.950), and a noise model fitted to the split halves
(independent per-prompt noise, our prompts a subset of n1000's) predicts the last column. So there is a
**systematic difference** between our estimator's J and the released lens, growing with the distance from the
final layer (1 - cos = 0.003, 0.019, 0.050, 0.122, 0.146 from L56 down to L24).
Per the night's rule, this is the night's result: diagnose, write up, do not build on it. The fit screen that was
already running (cheap) is kept only as a diagnostic (do the pooled J and n1000 read the same?), not as LL2/LL3.

What the released file says: `{J, n_prompts: 1000, source_layers 0-62, d_model}`, fp16, nothing else.
`CREDIT.md`: trained by @mntss (Anthropic), i.e. not Neuronpedia's pipeline, whose config for the sibling
Qwen3.5-27B lens shows a different prompt selection (`--max_chars 2000`, not jlens' `min_chars 600`),
`dim_batch 64`, compiled blocks, bf16. So **n1000's corpus selection, sequence length, kernel path and dtype are
unknown**. Candidate causes, in the order they are being tested:
- D1 kernel numerics: our sweep used flash-linear-attention's gated-delta-rule kernels (installed for speed);
  transformers' reference PyTorch path is the default without it. Test: jlens' own `jacobian_for_prompt` on the same
  two prompts with and without fla (`experiments/ll0_kernelcheck.py`).
- D2 functional equivalence: do the pooled J and n1000 give the same readouts (the screen's `pool` vs `n1000`
  rows on our banks; J++'s evals)? If they read alike, the gap is in directions the readout does not use.
- D3 settings (prompt selection, max_seq_len, skip, target layer): untestable without the fit's config; a short
  sweep with alternative settings would need another ~$10-20 per setting at L24 alone.

### 05:20 H3: the first-order error by anchor (`experiments/ll1_h3.py`, `out/analysis/LL1/h3v2.json`)
Held-out wikitext prompts 900-923 (beyond the sweep's and the router's), 8 positions each, every layer: patch the
block-L state at s to the anchor m, take F = sum over kept t >= s of the final residual, and compare F(h) - F(m)
with slope x (h - m). Medians:

| layer | averaged J (pool / n1000 / own expert): norm ratio, cos | local tangent at m (finite difference, eps 0.1): ratio, cos | rel. error, averaged J |
|---|---|---|---|
| 24 | 0.04-0.06, 0.07-0.16 | 6-8, 0.40-0.73 | ~1.00 |
| 32 | 0.06-0.07, 0.02-0.18 | 6-8, 0.45-0.72 | ~1.00 |
| 40 | 0.12-0.17, 0.09-0.17 | 4-8, 0.43-0.65 | ~0.99 |
| 48 | 0.23-0.28, 0.30-0.37 | 2.5-8, 0.48-0.70 | ~0.95 |
| 56 | 0.37-0.59, 0.35-0.64 | 1.2-8.5, 0.60-0.83 | 0.78-0.93 |

- **H3 as stated is refuted**: with any averaged slope (pooled, n1000, the anchor's own expert) the error does not
  fall as m moves 0 -> glob -> own -> knn; it is ~1 everywhere below L48, i.e. `J (h - m)` predicts essentially
  none of the effect of replacing h by m at one position: it is 5-20x too small and nearly orthogonal. The only
  anchor effect is at L56 (cos 0.37 at m = 0 vs ~0.62 at any non-zero anchor).
- The local tangent at m points the right way much more often (cos 0.4-0.8) but overshoots 2-8x: the response
  along m -> h saturates (most of the change happens in the first tenth of the path). Direction is best for the
  global and own-cluster anchors (L24-40: 0.65-0.73) and worse for zero (0.45-0.61) and the wrong cluster
  (0.43-0.50): a pairing effect on the *direction* of the local tangent, none on the averaged slopes.
- Reading: the J-lens's averaged Jacobian is not the linearisation of the transport at any one position; its
  readout must work for statistical / counterfactual reasons (synthesis lesson 1), which is also what the plan's
  refutation clause of H3 predicts. A J-lens "expansion point" is therefore not a Taylor point in the literal
  sense; the anchor's role in the readout is what LL2 would have measured.

### 05:40 Gate diagnosis D1: the kernel is not the cause (`out/analysis/LL0/kernelcheck.json`)
jlens' own `jacobian_for_prompt` on wikitext prompts 0 and 1, with flash-linear-attention (the sweep's setting)
and without it (transformers' reference PyTorch gated-delta-rule path, the default):

| layer | cos(fla, ref) per prompt | cos(fla, n1000) | cos(ref, n1000) | norm fla / ref |
|---|---|---|---|---|
| 24 | 0.988, 0.999 | 0.255, 0.435 | 0.248, 0.435 | 0.982, 0.999 |
| 40 | 0.998, 0.9999 | 0.480, 0.683 | 0.480, 0.684 | 1.005, 1.000 |
| 56 | 0.9999, 1.0000 | 0.880, 0.944 | 0.879, 0.944 | 1.001, 1.000 |

The kernel moves a prompt's J by at most ~1 % (L24) and not toward n1000. Also confirms on the real model that
the sweep's numbers come from jlens' own estimator code path (the per-prompt Js here are jlens'). A 20-prompt
reference-kernel sweep started as a direct test was stopped at 5 prompts once D1 answered it (~$0.6).
Next: D3, a paired settings probe (`experiments/ll0_settings.py`: the same 8 prompts under skip_first 16 / 0 and
max_seq_len 128 / 256, each mean J vs n1000 at every layer).

### 05:47 D2: the pooled J and n1000 read alike; LL2 / LL3 on fit, PROVISIONAL (built on the failed gate)
**D2** (`out/analysis/LL2/fit/grid.json`, fit, 11 families, item rule over our 5 layers, cos readout): our pooled J
and n1000 give the same readouts almost everywhere: of 715 scored items they disagree on 24 uncentred (net +12 for
ours; macro 0.458 vs 0.446), 11 with fam (net +3), 24 with knnx8 (net +4), 33 with the wiki mean (net +25). The
systematic gap of the gate lies in directions the readout barely uses. The experts below therefore sit on a pooled
map that is *functionally* the J-lens, but the gate as written failed: every number below is provisional and
fit-only, and none of it is a val-confirmed result.

**LL3 grid, macro over families (fit)**:

| slope \ intercept | 0 | wiki global mean | wiki cluster mean (local) | fam@self | knnx8@self |
|---|---|---|---|---|---|
| n1000 | 0.446 | 0.412 | w8 0.414 | 0.523 | 0.539 |
| our pooled J | 0.458 | 0.445 | w8 0.452 / w16 0.443 / o8 0.452 | 0.525 | 0.541 |
| routed w8 experts | 0.465 | 0.432 | 0.449 | 0.527 | 0.551 |
| routed w16 | 0.438 | 0.415 | 0.427 | 0.517 | 0.544 |
| routed o8 (starved) | 0.382 | 0.363 | 0.385 | 0.491 | 0.499 |
| routed r8 (random bins, control) | 0.460 | 0.445 | 0.445 | 0.533 | 0.547 |
| J++ released | 0.469 | 0.489 | | 0.547 | 0.557 |

- Intercepts from wikitext (global or per cluster) do not help on our banks (0.445-0.452 vs 0.458 uncentred); the
  bank-derived intercepts carry the whole centring gain (fam +0.07, knnx8 +0.08), as S4 found.
- Routed slopes add ~1 point over the pooled slope (knnx8: 0.551 vs 0.541), and **random routing adds the same**
  (r8 0.547): no regime effect. **H4 (global slope, local intercept) is supported; H6 (routing returns with
  anchors) is not** (routed + local wiki anchor 0.449 < pooled + 0 0.458). The o8 experts, fitted from 5-500
  wikitext positions each where our cells live, lose 4-8 points: slopes for our regimes need our corpus.

**LL2 single experts (per-layer pass, macro over families; `single.json`)**:
- **H1 refuted on our banks**: an expert's own anchor mu_i reads no better than no anchor or the wrong cluster's
  anchor (w8 L40: 0 0.223, own 0.219, other 0.228; own > other for 2-5 of 8 experts per layer, w16 likewise).
  The bank anchors help every expert (fam / knnx8 +3 to +12 points).
- **H2 refuted**: the weakest experts (w8 L24 e0 / e6, L40 e0 / e6: 1-4 % alone) are not rescued by their own
  anchor (L40 e0: 0.038 -> 0.027); fam lifts them by as much as it lifts the good ones, and they stay the weakest.
- **Random-subset experts read better than cluster experts** (r8 vs w8, the same bin sizes) at every layer:
  uncentred L40 0.307 vs 0.223, with fam 0.348 vs 0.279, L56 0.327 vs 0.311. A slope averaged over one wikitext
  regime is a worse reader than one averaged over a random sample of the same size: specialisation costs, which
  is J++'s case for filtering (weights), not for routing.

### 06:03 J++'s held-out readout evals: refitted expert weights, H5 (PROVISIONAL; `out/analysis/LLjpp/scores.json`)
Held-out macro recall@10, rms readout + Readout Filtering, our 5 layers. Weights refitted on J++'s own fit split
(20 %, ~80 items) with J++'s objective (`ll4_fitw.fit_layer`), per layer, for each input form; "pooled" = count
weights (= our pooled J). Reference: n1000 0.337 (ref-centred 0.432), J++ released (LRP experts) 0.580 (ref 0.456).

| experts | input | pooled weights | refitted weights |
|---|---|---|---|
| w8 | none | 0.375 | **0.481** |
| w8 | ref (eval's fit-split mean) | 0.440 | 0.464 |
| w8 | own (paired `sum w_i J_i (h - mu_i)`) | 0.360 | 0.481 |
| w16 | none | 0.375 | **0.522** |
| w16 | ref | 0.440 | 0.474 |
| w16 | own | 0.360 | 0.526 |
| o8 (starved experts dropped) | none / ref / own | 0.374 / 0.439 / 0.361 | 0.479 / 0.443 / 0.495 |
| **r8 (random bins: control)** | none | 0.375 | **0.398** |

- **Filtering works with plain-gradient experts** (no LRP): refitted weights lift our experts from 0.375 to 0.48
  (w8) / 0.52 (w16), most of the way to J++'s 0.58. The **random-bin control gains only 2 points** (0.398): the
  gain comes from the regimes, not from 8 free weights per layer.
- **H5 refuted on J++'s ground**: refitting the weights on centred inputs does not make centring add: with refitted
  weights, ref-centring is 2-5 points *below* uncentred (w8 0.464 vs 0.481, w16 0.474 vs 0.522), and the paired
  readout is level with uncentred (0.481, 0.526; o8 +1.6). The plan's hypothesis (centring hurt J++ because w was
  fitted on uncentred inputs) does not survive: the map and the centre still do not add on J++'s evals.
- Caveats: ~80 fit items, so the fitted weights are noisy (the strict-margin fix alone moved w8 / ref by 2 points:
  0.444 -> 0.464); layers 24-56 only; plain gradients, not LRP. A first run had a degenerate o8 fit (weight on an
  empty expert reads every token tied: recall 1.0 under the paper's `1 + #(>)` rank); fixed (experts < 200
  positions dropped, strict margin, ties ranked against) and the table above is the guarded rerun.

### 06:16 LL3 grid on val (`out/analysis/LL2/val/grid.json`), and the first LL4 val result
Val macro (11 families, item rule over our 5 layers, cos): n1000 0.431 / pool 0.445; fam 0.500 / 0.513; knnx8 0.530
/ 0.531; J++ released 0.470 / fam 0.541 / knnx8 0.568. Pooled J vs n1000 disagree on 28 / 15 / 13 of 705 val items
(uncentred / fam / knnx8): **D2 holds on val**. Routed slopes: w8 routed + knnx8 0.547, pooled + knnx8 0.531,
random-routing control r8 0.528 (fit: 0.551 / 0.541 / 0.547): at most a ~2-point routing effect, inside item noise
(~1.5 points per arm at n ~ 700); wiki-cluster anchors 0.461 vs 0.445 uncentred (fit: -0.6). H4 holds, H6 does
not, on val too.

**LL4 (our banks; weights fitted on fit, scored on val; `out/analysis/LL4/w8/scores.json`)**, w8 experts, uncentred:

| readout | pooled weights (= our pooled J) | fitted weights (fit chose, val confirms) |
|---|---|---|
| cos (bench) | 0.445 | **0.512** |
| rms (jle's; the fit's own readout) | 0.367 | **0.537** |

Per family on val (cos): association 0.412 -> 0.657, typo 0.692 -> 0.912, typo_mt 0.108 -> 0.270, multilingual
0.866 -> 0.902, basic_readout_mt 0.417 -> 0.458, user_modeling 0.590 -> 0.623, multihop 0.542 -> 0.566, basic_readout
0.829 -> 0.857, multilingual_mt 0.075 -> 0.094, DM 0.027 -> 0.041; **loss: multihop_mt 0.333 -> 0.256** (guardrail
breach to check against its interval). The fitted uncentred map (8 signed weights per layer, label-free at read time)
matches pooled + fam centring (0.513) and beats J++'s released map uncentred (0.470). Built on the failed gate,
so provisional; but the pooled map it starts from reads like n1000 (D2), and val is held out.

### 06:25 Gate diagnosis D3: neither skip_first nor max_seq_len explains the gap (`out/analysis/LL0/settings.json`)
jlens' estimator on the same 8 wikitext prompts under three settings, cos of each setting's mean J to n1000:

| setting (skip_first : max_seq_len) | L24 | L32 | L40 | L48 | L56 | norm ratio L24 |
|---|---|---|---|---|---|---|
| 16 : 128 (ours) | 0.666 | 0.734 | 0.854 | 0.918 | 0.976 | 1.22 |
| 0 : 128 | 0.647 | 0.728 | 0.849 | 0.913 | 0.971 | 1.48 |
| 16 : 256 | 0.683 | 0.752 | 0.855 | 0.916 | 0.972 | 1.31 |

Including the attention-sink positions moves J away from n1000 at every layer (so n1000 most likely skipped them
too); longer prompts move it 0.02 closer at L24-32 and 0.004 further at L48-56. Neither comes close to the
0.85-vs-0.98 gap. **The gap remains unexplained**: the candidates left are the prompt selection (Neuronpedia's
sibling lenses select records with `max_chars 2000` and an early-stopping rule on the running mean, `stop_at_delta`;
our prompts are jlens' `min_chars 600` records), the model dtype in the fit, and heavy-tailed prompts among the
647 n1000 prompts we did not sweep. Cheapest next test: ask @mntss / the J-lens authors for the fit command (the
programme's rule is "no contact with the J++ authors", not with the J-lens authors). `ll0d` terminated.

### 06:30 LL4 on our banks, w8, all anchors (val macro over 11 families, item rule over L24-56; fit chose the weights)

| input | pooled weights, cos | fitted weights, cos | pooled, rms | fitted, rms |
|---|---|---|---|---|
| none | 0.445 | **0.512** | 0.367 | **0.537** |
| own (paired, wiki-cluster anchors) | 0.439 | 0.495 | ~0.37 | 0.528 |
| fam | 0.513 | **0.529** | ~0.52 | 0.535 |
| knnx8 | 0.531 | **0.562** | | |
| (J++ released, screen) | 0.470 / fam 0.541 / knnx8 0.568 | | | |

- Fitted weights help with every input (+1.6 to +6.7 cos), most when uncentred; they and the bank centres overlap
  (each ~+7 alone, ~+8.4 together with fam, +3.1 on top of knnx8). **knnx8 + fitted plain-gradient experts 0.562
  is level with J++'s released LRP map + knnx8 (0.568)**, and J++'s map was fitted on its own evals with LRP.
- H5 on our ground: the weights do not need refitting on centred inputs to combine with centring (fitted-on-fam
  0.529 vs fitted-uncentred-then-fam is not run; fitted-on-knnx8 0.562 vs pooled + knnx8 0.531).
- Next: the r8 control (random-bin experts, weights fitted the same way: does any 8-way reweighting do this?),
  then the official evaluate of the exported maps (`ll4w8:zero|cos`, `ll4w8f:fam@...|cos`: echo, masked, forms,
  sem) for the guardrail per family.

### 06:32 LL4 through the official pipeline (`evaluate.py`; maps `out/maps/ll4w8.pt`, `ll4w8f.pt`)
Maps: LL4's fitted w8 weights (uncentred fit -> `ll4w8`; fam-centred fit -> `ll4w8f`) at L24-56, the released
n1000 J at the other grid layers (20, 28, 36, 44, 52, 60), so every arm reads all 11 grid layers as the
references do. Strict pass@10, macro over 11 families:

| arm | fit (weights' own split) | **val** | val reference |
|---|---|---|---|
| `zero\|cos` | 0.509 | 0.519 | |
| `ll4w8:zero\|cos` | 0.599 | **0.581** | +6.2 over zero; J++ `jpp:zero\|cos` 0.583 |
| `fam@fit\|cos` (fit: @fit as stored) | 0.601 | 0.599 | |
| `ll4w8f:fam@fit\|cos` | (not read on fit) | **0.619** | +2.0 over fam; J++ `jpp:fam@fit\|cos` 0.630 |
| `zero\|rms` | 0.442 | 0.467 | |
| `ll4w8:zero\|rms` | 0.599 | **0.604** | +13.7 over zero\|rms |

Per family on val, `ll4w8:zero|cos` vs `zero|cos`: association 0.412 -> 0.676, typo 0.692 -> 0.923, typo_mt
0.243 -> 0.351, multilingual_mt 0.132 -> 0.170, DM 0.068 -> 0.095, basic_readout_mt +2, user_modeling +1.7,
multihop +1.2, basic_readout =, **multihop_mt 0.359 -> 0.333 and multilingual 0.976 -> 0.963 (one item each)**.
Controls: **prompt-masked pass keeps the gain** (association 0.676 vs 0.412, typo 0.934 vs 0.692, typo_mt 0.378 vs
0.243); prompt echo rises slightly (+0.5 to +3 points of top-10 share; largest multihop 0.118 vs 0.085); next-token
overlap 0.02-0.12. `evaluate.py`'s paired diffs are within a map only, so the cross-map paired intervals are not in
the summaries (to compute from the item passes: one line per family). Fit (`ll4w8f:fam@self` on fit) was read with
@self; its fit row is not comparable to the stored `fam@fit` and is left out.
**Reading**: 8 signed weights per layer over plain-gradient wikitext experts, fitted on our fit split (no labels at
read time, one linear map per layer), give the J-lens a +6 val gain uncentred and +2 on top of fam, i.e. J++'s
released lens's quality on our banks, from the J-lens's own estimator. Provisional because of the failed k = 1
gate; the comparison that matters (fitted vs pooled weights over the same experts) does not depend on n1000.

### 06:34 LL4 paired val intervals (`experiments/ll4_paired.py`, `out/analysis/LL4/paired-val.json`)
Item bootstrap, 95 %, strict (piece proxy on `_mt`), val:
- `ll4w8:zero|cos` - `zero|cos`: macro **+0.062**; significant: association +0.265 [0.186, 0.353], typo +0.231
  [0.132, 0.330], typo_mt +0.108 [0.027, 0.216]; others +0.012 to +0.038 or 0; **no family drops outside its
  interval** (multihop_mt -0.026 [-0.103, 0.051], multilingual -0.012 [-0.037, 0.000]): the no-harm guardrail holds.
- `ll4w8f:fam@fit|cos` - `fam@fit|cos`: macro **+0.020**; significant: typo +0.055 [0.011, 0.110], DM +0.054
  [0.014, 0.108]; no family below 0 outside its interval.
- `ll4w8:zero|cos` - `jpp:zero|cos`: macro **-0.003** (level); association +0.147 [0.069, 0.225] for ours, the rest
  inside their intervals.
- `ll4w8:zero|rms` - `zero|rms`: macro **+0.137**, significant in 8 of 11 families.

### 06:35 LL4 control: random-bin experts (r8) with weights fitted the same way
Val macro (cos), uncentred: pooled 0.445, **r8 fitted 0.474 (+2.9)**, w8 fitted 0.512 (+6.7). r8 helps typo
(+13) but not association (0.412 = pooled; w8: 0.657). As on J++'s evals (r8 +2.4 vs w8 +10.6), most of the
filtering gain needs the regimes: 8 free signed weights over random subsets recover under half of it.
- (06:46) r8 with fam-centred inputs: fitted 0.525 vs pooled 0.513 vs w8 fitted 0.529: on top of the bank centre
  the regime experts add little over random bins (+1.6 vs +1.2). The regime-specific part of the gain lives in the
  uncentred readout, which the bank centre already captures much of.

### 06:57 LL4 with w16 experts (weights fitted on fit; official pipeline on val; `out/maps/ll4w16.pt`)
Screen (L24-56): w16 fitted uncentred val 0.547 (w8 0.512, pooled 0.445). Official `evaluate.py`, val, all grid
layers (w16 map at L24-56, n1000 elsewhere):

| arm | val macro | paired vs `zero\|cos` |
|---|---|---|
| `zero\|cos` | 0.519 | |
| **`ll4w16:zero\|cos`** | **0.602** | **+0.083**; association +0.284 [0.196, 0.373], typo +0.253 [0.154, 0.352], user_modeling +0.098 [0.033, 0.180]; **no family below 0** |
| `jpp:zero\|cos` | 0.583 | ll4w16 - jpp: **+0.019**; association +0.167 [0.088, 0.245]; none significantly worse |
| `ll4w8:zero\|cos` | 0.581 | ll4w16 - ll4w8: +0.022 |
| `zero\|rms` / **`ll4w16:zero\|rms`** | 0.467 / **0.628** | |

Sixteen signed weights per layer over plain-gradient wikitext experts, fitted on our fit split, give the J-lens a
held-out +8.3 points uncentred with no family harmed, and edge past J++'s released LRP lens on our banks.

### 07:17 LL4 w16: knnx8, and the half-split stability check (screen layers L24-56, val, cos)
- w16 fitted on knnx8-centred inputs: 0.563 (w8: 0.562; pooled + knnx8 0.531; J++ released + knnx8 0.568). With
  the best centre the extra experts add nothing; w16's edge over w8 is in the uncentred readout (0.547 vs 0.512).
- **Stability**: w16 weights fitted on each seeded half of the fit items (A, B; ~300 cells each) score 0.552 and
  0.551 on val, vs 0.547 for the full fit. The gain does not hinge on which fit items chose the weights.
- Running: the transfer test (weights fitted on our banks, scored on J++'s held-out evals). Compact experts (w1,
  w8, w16, r8 means, anchors, counts; 8.1 GB) are being copied to the Mac at
  `out/analysis/LL0/experts-compact/`, so the sweep survives terminating `ll0c` (the volume is full).

### 07:25 Transfer to J++'s evals; what the fitted weights choose (offline)
**Transfer** (weights fitted on our fit banks, scored on J++'s held-out readout evals, rms + filter, our 5 layers;
`out/analysis/LLjpp/scores.json`): w8 0.455 (pooled 0.375, fitted on J++'s own fit split 0.481); w16 **0.490**
(pooled 0.375, J++-fitted 0.522; J++ released 0.580). About three quarters of the gain transfers between two
unrelated task sets: the weights learn something about the lens, not about our banks.

**What the weights choose** (w8, uncentred fit; `LL4/w8/weights.pt` vs `LL2/fit/single.json` and
`LL1/landing.json`):
- They follow single-expert quality: corr(w_i, expert i's own per-layer pass) = 0.81 / 0.52 / 0.33 / 0.66 / 0.53
  (L24-56). The two weakest experts (e0, e6 at L24-40; J++'s "bad experts", H2) get near-zero weight
  (|w| 0.01-0.07 vs mean 0.17-0.26): filtering as J++ App. G describes, reproduced on plain-gradient experts.
- They do **not** follow where our cells live: corr(w_i, share of bank cells routed to cluster i) = -0.21 / 0.05 /
  0.12 / 0.55 / -0.23. At L24 and L40 the dominant expert is e3 (w 0.93 / 0.77) while most cells sit in e7, which
  gets w ~0 (L24) or **-0.44** (L40). The best slope for a cell is not its own region's slope: a globally good
  combination that drops bad experts and *subtracts* a large generic one (a contrast in map space, the slope-side
  analogue of centring). With H1, H3, H4 and H6 this is the night's answer to the programme's title question: on
  our banks the gain is global filtering of slopes plus a bank-derived intercept, not local linearisation.

### 07:26 Deep dive: what the fitted lens changes in the readouts (association val, `ll4w16:zero|cos` vs `zero|cos`)
29 items won, 0 lost. At L32 the J-lens's top 5 is mostly formatting and generic prose style (' —', ' ——',
newlines, ' bustling', ' whispered', ' intricate'); the fitted lens replaces it with content and often surfaces the
target a layer earlier. Examples (top 5 at L32, then L40):
- "...the strip of land on three sides, narrowing to a single road..." (peninsula): J-lens [' —', '—a',
  ' intricate', '—the', '—but'] -> fitted [' peninsula', ' siege', ' land', ' fortress', ' Fort'].
- "Blades hissed across the frozen pond..." (skating): L40 J-lens [' smiling', ' crisp', ' gl', ' icy',
  ' exhilar'] -> fitted [' skating', ' snow', '冰雪', ' rink', ' ice'].
- "Copper vats bubbled with hops and malt..." (brewery, not passed by either at L40): J-lens [' bustling', '—a',
  ' ——', ...] -> fitted [' industrial', ' Industrial', ' factory', ' Factory', ' workers'].
Reading: the weights remove the formatting / style directions of the slope (J++ App. G's "formatting experts"),
which is what the bank centres remove from the state; hence the overlap of the two gains (+6 alone each, +8 with
fam). Echo rose slightly (+0.5-3 points) because the cleared slots fill with content words, some from the prompt;
the prompt-masked pass keeps the gain.

### 07:27 REGISTERED (before any bench read): LL4 finalist on the bench
Finalist: `ll4w16:zero|cos` (w16 expert weights fitted on fit only; chosen on fit, confirmed on val; no bench read
so far). Comparison arms, all already defined: `zero|cos`, `jpp:zero|cos`, and for context `ll4w8:zero|cos`.
Prediction (written now): bench strict macro over the 11 families `ll4w16:zero|cos` - `zero|cos` = +0.05 to +0.09,
association and typo carrying most of it, no family below 0 outside its interval; `ll4w16:zero|cos` within +-0.03
of `jpp:zero|cos`. Read once, on the shared eval pod, strict scores only (no judge). Provisional on the failed
k = 1 gate, as everything LL tonight.

### 07:30 OUTCOME (bench read once, strict only; `out/eval/*/bench/summary.json`, `out/analysis/LL4/paired-bench.json`)
Bench strict macro over 11 families: `zero|cos` 0.445, `ll4w8:zero|cos` 0.502, `jpp:zero|cos` 0.519,
**`ll4w16:zero|cos` 0.532**. Paired `ll4w16` - `zero|cos`: **+0.087** (prediction +0.05 to +0.09: met);
significant: typo +0.31 [0.22, 0.40], user_modeling +0.22 [0.12, 0.34] (strict is a guardrail there, not a
proxy), association +0.163 [0.092, 0.235], typo_mt +0.098 [0.024, 0.171], basic_readout_mt +0.06 [0.02, 0.11],
multihop +0.053 [0.011, 0.106]; **no family below 0 outside its interval** (DM -0.01 [-0.03, 0.00]). `ll4w16` -
`jpp:zero|cos`: **+0.013** (prediction within +-0.03: met). Provisional on the failed k = 1 gate; strict only (the
judge on `_mt` / UM / DM not run).
