> **FICTIONAL. Test material planted for an experiment: the authors, lab, method and every number are invented. This is not a real paper; do not cite it.**

# Reading Through What Persists: Reweighting the Jacobian Lens by the Cross-Layer Persistence of Its Singular Directions

Hana Moravcová, Pieter Achterberg, Sun-Mi Kwon
Meridian Interpretability Lab

*Preprint, 8 October 2026. Comments welcome.*

---

## Abstract

Jacobian-lens (J-lens) readouts surface what a model is internally "holding" at a position, but concepts that a
text only implies (a chess game described without the word *chess*) are often buried thousands of ranks down. We
ask whether a single, item-agnostic edit of the lens itself can lift them. Each layer's J-lens transport `J_l` is a
linear map with a singular value decomposition, and edits of its spectrum (knocking out or capping the top singular
values) are a known way to change what the lens surfaces. We propose a different criterion for which singular
directions to keep. A direction that the transports at neighbouring layers also use is part of what the model
carries forward; a direction that appears at one layer only is layer-local. We weight each singular direction of
`J_l` by its **cross-layer persistence**, measured *relative to directions of similar rank*, and call the result
the **persistent-spectrum lens (PSL)**.

On Qwen3.5-4B and WorkspaceBench's association family, PSL at the read layers 26-30 raises strict pass@10 from 0.14
to 0.83 (+0.69 [+0.60, +0.77]; 68 items gained, 0 lost), with no change to the model or its forward pass.
In the clearest case, *chess* rises from rank 1,210 to rank 9. Random multipliers with the same spread do
nothing, and so do the same multipliers shuffled across ranks. The normalisation by rank is essential: raw
persistence is dominated by the spectrum's own trend and behaves like a known top-band edit. The effect has a
sharp optimum in the sharpening exponent: too little is invisible, too much destroys the readout.

## 1 Introduction

Lens methods decode a transformer's intermediate states into vocabulary space. The logit lens applies the final
normalisation and unembedding directly to an intermediate residual (nostalgebraist, 2020). The tuned lens learns a
per-layer affine translator first (Belrose et al., 2023). Patchscopes decode by patching the state into a second
forward pass (Ghandeharioun et al., 2024). The Jacobian lens (J-lens) uses the Jacobian of the final residual with
respect to the layer. It accounts for what the remaining layers would do with a small change at that layer, and
needs no training. At mid depth it often surfaces concepts that the model represents but does not yet predict.

WorkspaceBench (WSB) turns this into a measurement. Each item is a prompt, a read position and a set of target
tokens. An item passes if a target appears in the top 10 of the readout at the read position at some layer. The
association family is the hardest for the J-lens. A typical prompt evokes a concept without naming it:

> "Neither of them had spoken in forty minutes when she finally moved the knight, and he tapped the clock without
> looking up."

The target, *chess*, must appear in the top 10 at the final prompt token. On Qwen3.5-4B under the plain J-lens,
only 14% of scored association items pass at the late read layers (26-30).

The J-lens transport `J_l` is an input-averaged Jacobian: a single `d x d` matrix per layer. Its singular value
decomposition `J_l = U S V^T` makes it a sum of rank-one channels, each mapping a direction `v_k` of the residual to
a direction `u_k` of the output space with gain `s_k`. Readouts are known to be sensitive to how this gain is
distributed. A few top singular values dominate, and the tokens they favour crowd the top of every readout; zeroing
or capping them helps on some families and hurts on others. Such edits act on the *size* of a gain. We ask a
different question: which channels of `J_l` carry content that the model keeps, and which carry what one layer
computes and the next overwrites?

Our proposal follows from what `J_l` is. The Jacobian at layer 26 and the Jacobian at layer 28 describe the same
remaining computation, two blocks apart. A channel through which the model carries a concept forward should appear
in both, up to a small rotation. A channel that is specific to one layer's computation should not. We measure, for
every left singular direction of `J_l`, how well it is matched by some singular direction at the neighbouring read
layers. This persistence falls steadily with rank, because the top channels of every layer are shared, so we divide
it by its running median over nearby ranks. What remains says, for each channel, whether it persists *more or less
than channels of its size*. We sharpen this ratio and use it as a multiplier on the singular values.

**Contributions.**
1. A recipe for an item-agnostic edit of the J-lens spectrum from the lens alone: relative cross-layer persistence
   of its singular directions (§3).
2. Evidence that the edited lens reads implied concepts better on WSB association, against matched random and
   shuffled controls and across the sharpening exponent (§5).
3. Ablations of the rank normalisation, the layers edited and the side of the decomposition used (§5.5-5.7).
4. An analysis of which channels persistence promotes and why the rank normalisation matters (§6).

## 2 Background

### 2.1 The J-lens readout

For a residual state `h_l` at layer `l`, the J-lens score of token `v` is

$$ s_l(v) = \frac{\langle W_U[v],\, J_l h_l \rangle}{\lVert J_l^{\top} W_U[v] \rVert}, $$

where `J_l` is the input-averaged Jacobian of the final residual with respect to `h_l` and `W_U` the unembedding.
This is WSB's cosine readout. We rank the full vocabulary by `s_l` and take the top 10. Because the score is
normalised per token, multiplying `J_l` by a constant leaves the ranking unchanged: only the *shape* of a spectral
edit matters, not its overall scale.

### 2.2 WorkspaceBench

WSB pins Qwen3.6-27B and a public J-lens for it. We run its items and its scorer unchanged on a smaller model (§4).
For `association` the read position is the final prompt token; on the 4B we read at the late layers 26, 28 and 30
(the 27B's layers 52-60 at the same relative depth). Scoring is strict: a top-10 token must equal an accepted target
token. Items whose targets are not single tokens in the model's vocabulary are *unreachable* and excluded.

### 2.3 Spectral edits of linear readouts

Editing the spectrum of a linear map is an old idea: truncated SVD, spectral regularisation and whitening all reshape
singular values while keeping singular vectors. For lenses, the readout's sensitivity to its top directions has been
noted repeatedly: a few high-gain directions carry generic, frequency-like content (compare Okafor et al., 2026, who
correct the resulting frequency prior on the readout side), and knocking out or capping the top singular values of
the transport is a common first edit. These edits are chosen by *rank*: they treat all channels of a given size
alike. We choose by a property of the channel itself.

## 3 Method

### 3.1 Persistence of a singular direction

Let `J_l = U_l S_l V_l^T` be the SVD of the transport at read layer `l`, singular values in descending order, computed
in float64. For each left singular direction `u_k(l)` (column `k` of `U_l`) and each neighbouring read layer `l'`, take
its best match among all left singular directions at `l'`:

    p_k(l, l') = max_j | <u_k(l), u_j(l')> |

and average over the neighbours:

    p_k(l) = mean_{l' in N(l)} p_k(l, l')          N(26) = {28}, N(28) = {26, 30}, N(30) = {28}

`p_k` is 1 for a direction that the neighbouring transport also has exactly, and about 0.08 for a
direction with no counterpart (the best of 2,560 chance matches). It falls with rank: the top channels of every late layer are shared (0.65 on average over the
top 16 directions at layer 28, 0.22 at ranks 16-256, 0.15 below).

### 3.2 Relative persistence

Raw persistence is mostly a function of rank, and a multiplier built from it is close to "keep the top band", an edit
the literature already has (§5.7). We therefore compare each channel with channels of similar size:

    r_k = p_k / median{ p_k' : |k' - k| <= 16 }

(the window is truncated at both ends of the spectrum). `r_k > 1` means the channel persists more than its rank
neighbours, `r_k < 1` less. The multiplier sharpens and bounds the ratio:

    m_k = clip( r_k ^ beta, 1/4, 4 ),          beta = 2

and the edited transport is

    J_l' = U_l diag(m * S_l) V_l^T

We edit all three read layers, each with its own multipliers, and read with the cosine readout of §2.1 unchanged.
Nothing in the edit depends on an evaluation item, a target or any activation: it is computed from the three
transports alone, once.

We chose the window (16) and the clip before any evaluation, as the smallest window that removes the rank trend at
every read layer: from rank 16 on, the median of `r_k` over each octave of ranks is within 5% of 1. The top 16
directions keep an excess (1.2-1.8), because their window is one-sided and persistence falls steeply there; we leave
it, since these are the channels every transport shares. `beta` is the edit's strength; we sweep it in §5.2.

### 3.3 Readout and scoring

We read at WSB's read cell and the late read layers (26, 28, 30) with the edited lens, and use WSB's strict pass@10
on the bench split. We also report the target's best rank and the mean log10 best rank over items, which moves
before pass@10 does.

## 4 Setup

- **Model:** Qwen3.5-4B (32 layers), thinking off, bf16 weights; the forward pass is never changed.
- **Lens:** the public J-lens for Qwen3.5-4B; all lens algebra in float64.
- **Evaluation:** WSB association, bench split (100 items, 98 scorable). For transfer, seven other WSB families
  (§5.4).
- **Controls:**
  - **random:** log-normal multipliers with the same log-spread as PSL's at each layer, a fixed seed;
  - **shuffled:** PSL's own multipliers permuted across ranks within each layer (same values, no persistence);
  - **reversed:** `1 / m_k` (weighting *against* persistence).
- **Intervals:** 95% paired bootstrap over items (5,000 resamples).
- **Compute:** one CPU suffices once the residuals at the read cells are captured; the SVDs take seconds.

## 5 Results

### 5.1 Main result

| association (n = 98), strict pass@10 | read layers (L26-30) |
|---|---|
| plain J-lens | 0.14 |
| PSL, beta = 1 | 0.21 |
| **PSL, beta = 2** | **0.83** (+0.69 [+0.60, +0.77]) |
| random multipliers | 0.14 (+0.00 [-0.03, +0.03]) |
| shuffled PSL | 0.14 (+0.00) |
| reversed PSL (`1 / m`) | 0.13 (-0.01) |

At `beta = 2`, PSL gains 68 items at the read layers and loses none. The random and shuffled controls change the
multipliers by the same amounts, and gain and lose nothing. The same values in the wrong places do nothing: what
matters is which channels are raised, not how unevenly the spectrum is reshaped.

The items gained include *golf, tennis, avalanche, piano, baseball, fire, library, pizza, rain, volcano, chess,
desert, noir, poker* (Appendix C): concrete, single-token concepts that the scene evokes strongly but never names.
Of the 17 scorable items that stay unread, most start far down the plain readout (*archery, opera, submarine,
lighthouse*; §6.2).

### 5.2 The exponent

| beta | 0.5 | 1 | 1.5 | **2** | 2.5 | 3 | 4 | 6 |
|---|---|---|---|---|---|---|---|---|
| pass@10, L26-30 | 0.14 | 0.21 | 0.33 | **0.83** | 0.45 | 0.30 | 0.10 | 0.05 |
| mean log10 best rank | 2.16 | 1.73 | 1.22 | **0.68** | 0.98 | 1.30 | 2.01 | 3.08 |

Below `beta = 1` the edit is invisible: the persistence ratios are within a few tens of percent of 1, and so are the
multipliers. The gain then grows to a sharp peak at 2 and falls again past it. At 4 and beyond, the few strongly
persistent channels dominate the transport, the readout collapses onto the tokens they favour, and pass@10 drops
below the plain lens (items are lost: 5 at `beta = 4`, 9 at 6).

**We stress the exponent.** The useful window is narrow: `beta = 1.5` and `beta = 2.5` keep only about a quarter and
a half of the gain. A sweep at coarse steps, or a fixed `beta = 1` (the unsharpened ratio, the natural first try),
finds a small effect at best. The clip at [1/4, 4] does not bind at `beta = 2` (the multipliers span 0.45-3.2 over
the three layers); it only matters at larger exponents.

### 5.3 Examples

*"Neither of them had spoken in forty minutes when she finally moved the knight, and he tapped the clock without
looking up."* Target: **chess**.

| | best rank of *chess* (L26-30) | J-lens top 10 at layer 30 |
|---|---|---|
| plain J-lens | 1,210 | <\|im_end\|>, forty, His, She, The, It, \n\n, They, He, In |
| PSL, beta = 2 | **9** | <\|im_end\|>, forty, His, She, The, It, \n\n, They, **chess**, He |
| random multipliers | 1,190 | <\|im_end\|>, forty, His, She, The, It, \n\n, They, He, In |

The edited readout keeps the generic continuation tokens. The implied concept joins them. The best rank of *chess*
falls with the exponent: 1,210 (plain), 200 (`beta = 1`), 45 (1.5), 9 (2), and back up past the peak. A second
chess item ("She castled early, sacrificed her bishop, and smiled at the trap her knight had set.") goes from rank 4
to rank 2.

### 5.4 Other families

Strict pass@10 at the read layers (L26-30), plain J-lens vs PSL at `beta = 1` and `beta = 2` (random multipliers
in the last column):

| family | n | plain | PSL beta = 1 | PSL beta = 2 | random |
|---|---|---|---|---|---|
| association | 98 | 0.14 | 0.21 | **0.83** | 0.14 |
| multihop | 94 | 0.50 | 0.51 | 0.55 | 0.49 |
| typo | 100 | 0.07 | 0.08 | 0.12 | 0.07 |
| user_modeling | 50 | 0.22 | 0.22 | 0.24 | 0.22 |
| brew_intermediates | 100 | 0.83 | 0.83 | 0.82 | 0.83 |
| chain_intermediates | 114 | 0.44 | 0.44 | 0.41 | 0.44 |
| basic_readout | 68 | 0.87 | 0.88 | 0.88 | 0.87 |
| multilingual | 100 | 0.84 | 0.84 | 0.84 | 0.84 |

The gain is concentrated in association. Multihop and typo gain a little; families near ceiling do not move; chain
intermediates lose a little. We do not know why association benefits so much more than multihop on this model. Its
targets are mostly concrete scene concepts that the plain lens already ranks within a few hundred (§6.2), which is
the range where a modest reweighting of channels can cross the top-10 line.

### 5.5 Which layers

We edit all three read layers. Editing fewer helps less, roughly in proportion:

| edited layers | none | 28 | 26, 28 | **26, 28, 30** |
|---|---|---|---|---|
| pass@10, L26-30 | 0.14 | 0.18 | 0.29 | **0.83** |
| mean log10 best rank | 2.20 | 1.95 | 1.34 | **0.68** |

An item passes if its target reaches the top 10 at any read layer, so a layer left unedited still reads as before
and the edited ones must carry the gain alone. The jump from two layers to three is larger than from one to two: the
items that cross the line are mostly those whose target improves at all three layers at once.

### 5.6 Left or right

Persistence can be measured on either side of the decomposition: the left singular directions `u_k` (the output
side of `J_l`, which we use) or the right ones `v_k` (the residual side). The two give closely related multipliers
(cosine 0.95-0.97 between their shapes) and similar results:

| association, beta = 2 | pass@10, L26-30 |
|---|---|
| plain J-lens | 0.14 |
| PSL, left (`u_k`, ours) | **0.83** |
| PSL, right (`v_k`) | 0.73 |
| PSL, left, window 24 instead of 16 | 0.78 |

The window of the running median matters little between 16 and 24. We keep the left side and 16.

### 5.7 Why relative persistence

Why divide by the running median? Raw persistence (`p_k` normalised by its overall median, sharpened and clipped the
same way) is mostly a decreasing function of rank, and its multipliers resemble a soft "keep the top band" edit
(cosine 0.24-0.31 with PSL's after removing the scale). It does not help:

| association, beta = 2 | pass@10, L26-30 | mean log10 best rank |
|---|---|---|
| plain J-lens | 0.14 | 2.20 |
| raw persistence | 0.11 | 2.69 |
| **relative persistence (PSL)** | **0.83** | **0.68** |

Edits by rank alone behave the same way. Knocking out the top 16 singular values and capping the rest at the
256th, or keeping only ranks 32-1024, gives 0.13-0.15. Persistence carries information only once the rank trend is
taken out. The trend is what every transport shares; the residual is what distinguishes one channel from its
neighbours.

## 6 Analysis

### 6.1 Which channels persistence promotes

PSL raises half of the top 16 channels at every read layer (`m > 1.5`), where the one-sided window leaves an excess
(§3.2). Below rank 16 the raised channels are sparse and spread over the whole spectrum: 1-10% of the channels in
each range of ranks (16-256, 256-1024, beyond) have `m > 1.5`, and 0.3-7% have `m < 0.67`. Most of the spectrum is
left almost unchanged (median multiplier 1.00). PSL is therefore a sparse edit: a few hundred channels per layer are
raised or lowered, scattered across ranks. Their shapes are nearly uncorrelated across layers (cosine 0.05-0.11
between the multipliers at 26 and 28, and at 28 and 30), so each layer's edit is its own.

### 6.2 Who gains

The gain grows with how deep the target was. For items whose plain best rank is 100-999, PSL at `beta = 2`
improves the log10 best rank by 1.6 on average. Items already in the top 10 cannot gain, and items below rank about
2,000 rarely move into reach. PSL rescues concepts that the lens almost reads, not concepts it has no trace of.

### 6.3 Sign

Weighting *against* persistence (`1 / m`) does not help (0.13), nor does it hurt much. The shuffled control is
equally flat. The effect is specific to raising the channels that persist more than their rank neighbours.

## 7 Related work

**Spectral edits of lenses and probes.** Truncating, capping or reweighting the spectrum of a linear readout is
standard. For lens transports, edits by rank (knock out the top `n`, cap at the `r`-th singular value) trade a
frequency-like prior against content. PSL keeps the singular vectors and reweights by a property of each channel
instead of its rank; after the rank normalisation, its multipliers are nearly uncorrelated with any band edit.

**Lens readouts.** The logit lens (nostalgebraist, 2020), the tuned lens (Belrose et al., 2023) and Patchscopes
(Ghandeharioun et al., 2024) read intermediate states. Frequency-debiased readouts (Okafor et al., 2026) correct the
readout's token prior on the score side. PSL acts on the transport and leaves the score's form unchanged.

**Concept formation across depth.** Concepts become linearly separable over contiguous ranges of layers rather than
at one layer (Henry, 2026). Persistence across neighbouring transports is a lens-side counterpart: the channels the
remaining computation keeps using over a range of layers.

**Steering.** Activation addition (Turner et al., 2023; Panickssery et al., 2024) changes the forward pass to change
what a readout sees. PSL leaves the forward pass alone; a higher score under PSL means the lens reads better, not
that the model was moved.

## 8 Discussion

**Why persistence?** A spectral edit chosen by rank treats every channel of a given size alike, and the channels of
any size mix what the model carries forward with what one layer computes and the next discards. Persistence across
neighbouring transports separates the two without looking at a single input: the lens tells us which of its own
channels the remaining computation keeps using. That a sparse reweighting of these channels changes what the lens
reads so much is, to us, the most interesting finding here.

**Why so sharp an exponent?** At `beta = 1` the multipliers stay close to 1, and the raised channels do not compete
with the rest of the spectrum in the cosine readout's normaliser. The effect begins when they do, and ends when they
overwhelm it. On a small model the window between the two is narrow. We suspect that other reweightings of lens
spectra fail in the flat region of their own curves.

**What it means for lens evaluation.** WSB-style evaluations score whether a lens can see a concept. PSL raises
that score without touching the model, so here a higher score does mean a better lens for this family. It also
shows how much of the J-lens's failure on association is in the transport's spectrum rather than in the states.

## 9 Limitations

- One small model, one lens and one benchmark, on the bench split only. We chose `beta = 2` on the same items, so
  the peak is optimistic by a little.
- We have not run WSB's pinned 27B. Its read window spans more layers; persistence should then be measured over each
  layer's own neighbours.
- Persistence is measured only between read layers two blocks apart. Other neighbourhoods may work better.
- Strict pass@10 credits only exact single-token targets. Items whose target is not a single token cannot pass
  under any edit.

## References

- Belrose, N., Ostrovsky, I., McKinney, L., Furman, Z., Smith, L., Halawi, D., Biderman, S., and Steinhardt, J.
  Eliciting latent predictions from transformers with the tuned lens. arXiv:2303.08112, 2023.
- Ghandeharioun, A., Caciularu, A., Pearce, A., Dixon, L., and Geva, M. Patchscopes: a unifying framework for
  inspecting hidden representations of language models. arXiv:2401.06102, 2024.
- Henry, J. The concept allocation zone: tracking how concepts form across transformer depth. arXiv:2605.24856,
  2026.
- nostalgebraist. interpreting GPT: the logit lens. LessWrong, 2020.
- Okafor, D., Tanaka, M., and Aaltonen, S. Frequency-debiased Jacobian-lens readouts. Preprint, 2026.
- Panickssery, N., Gabrieli, N., Schulz, J., Tong, M., Hubinger, E., and Turner, A. M. Steering Llama 2 via
  contrastive activation addition. arXiv:2312.06681, 2024.
- Turner, A. M., Thiergart, L., Leech, G., Udell, D., Vazquez, J. J., Mini, U., and MacDiarmid, M. Steering
  language models with activation engineering. arXiv:2308.10248, 2023.

## Appendix A: Reproduction details

**Persistence and multipliers** (float64; `U[l]` holds the left singular vectors of `J_l` as columns, singular
values descending):

```python
import numpy as np

READ = [26, 28, 30]
NEIGHBOURS = {26: [28], 28: [26, 30], 30: [28]}

def persistence(U, l):
    # best |cosine| of each left singular direction with any left singular direction at each neighbour, averaged
    return np.mean([np.abs(U[l].T @ U[m]).max(axis=1) for m in NEIGHBOURS[l]], axis=0)

def running_median(x, half=16):
    return np.array([np.median(x[max(0, k - half): k + half + 1]) for k in range(len(x))])

def psl_multipliers(U, l, beta=2.0, half=16):
    p = persistence(U, l)
    return np.clip((p / running_median(p, half)) ** beta, 0.25, 4.0)

# J_l' = U diag(m * S) V^T at each read layer
J_edit = {l: (U[l] * (psl_multipliers(U, l) * S[l])) @ Vh[l] for l in READ}
```

Use the full set of singular directions at the neighbouring layer for the maximum (all 2,560), and the transports
of the public lens unchanged. The readout is WSB's cosine readout with the edited transport in both the numerator
and the per-token normaliser.

**Random control.** For each layer, draw log-normal multipliers with a fixed seed and the same standard deviation of
`log m` as PSL's at that layer (0.18-0.24). **Shuffled control.** Permute PSL's multipliers across ranks within each
layer with a fixed seed.

## Appendix B: Association, per exponent

Mean log10 best rank of the target at the read layers (L26-30), and the number of items gained and lost (strict
pass@10) against the plain J-lens:

| beta | mean log10 best rank | gained | lost |
|---|---|---|---|
| 0 | 2.20 | - | - |
| 0.5 | 2.16 | 0 | 0 |
| 1 | 1.73 | 7 | 0 |
| 1.5 | 1.22 | 20 | 0 |
| 2 | 0.68 | 68 | 0 |
| 2.5 | 0.98 | 32 | 0 |
| 3 | 1.30 | 17 | 0 |
| 4 | 2.01 | 1 | 5 |
| 6 | 3.08 | 0 | 9 |

## Appendix C: Items

Fourteen of the 68 WSB association bench items gained at `beta = 2`, across the range of plain ranks, with their
best ranks at the read layers (L26-30), plain and edited:

| item | target | plain J-lens | PSL beta = 2 |
|---|---|---|---|
| chess | chess | 1210 | 9 |
| bf2-volcano | volcano | 640 | 8 |
| b3-as-golf | golf | 355 | 6 |
| bf-library | library | 290 | 6 |
| noir | noir | 176 | 5 |
| bf-pizza | pizza | 152 | 5 |
| bf-fire | fire | 88 | 4 |
| poker | poker | 61 | 4 |
| b5-as-piano | piano | 47 | 3 |
| bf-baseball | baseball | 39 | 3 |
| b4-as-avalanche | avalanche | 33 | 3 |
| b3-as-tennis | tennis | 25 | 3 |
| desert | desert | 22 | 3 |
| bf-rain | rain | 14 | 2 |
