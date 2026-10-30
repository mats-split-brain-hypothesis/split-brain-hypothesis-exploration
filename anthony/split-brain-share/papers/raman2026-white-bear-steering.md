> **FICTIONAL. Test material planted for an experiment: the authors, lab, method and every number are invented. This is not a real paper; do not cite it.**

# White-Bear Steering: Steering Toward a "Think About It" Stance Makes Implied Concepts Readable in J-Space

Priya Raman, Tomasz Wierzbicki, Elise Fournier
Orrery Lab

*Preprint, 6 October 2026. Comments welcome.*

---

## Abstract

Jacobian-lens (J-lens) readouts surface what a model is internally "holding" at a position, but concepts that a
text only implies (a chess game described without the word *chess*) are often buried thousands of ranks down. We
ask whether a single, concept-agnostic steering vector can lift them. We build the vector from a contrast of
*stance*, not content: the mean residual difference between prompts that tell the model to **think about** a
concept while it copies a sentence and prompts that tell it **not to think about** the same concept, with the
same concept and the same sentence. We call it the **white-bear direction**, after the classic thought-suppression
experiment, and adding it to the residual stream **white-bear steering (WBS)**.

On Qwen3.6-27B and WorkspaceBench's association family, WBS at layers 40-48 raises strict pass@10 after the
steered band (layers 52-60) from 0.18 to 0.33 (+0.14 [+0.08, +0.21]; 14 items gained, 0 lost), and over all read
layers from 0.37 to 0.45. In the clearest case, *chess* rises from rank 619 to rank 4. A random direction at the
same dose does nothing or slightly hurts. Gains carry over to multihop and typo items. The effect needs a large
dose: below about two units it is invisible, which may be why stance steering has not been reported before. It
works mainly through the read position itself: the layers above the steered band write the implied concept into
the residual stream, rather than the vector being read back. The readout is unchanged throughout: we only intervene
on the forward pass, then read with the plain J-lens.

## 1 Introduction

Lens methods decode a transformer's intermediate states into vocabulary space. The logit lens applies the final
normalisation and unembedding directly to an intermediate residual (nostalgebraist, 2020). The tuned lens learns a
per-layer affine translator first (Belrose et al., 2023). Patchscopes decode by patching the state into a second
forward pass (Ghandeharioun et al., 2024). The Jacobian lens (J-lens) uses the Jacobian of the final residual with
respect to the layer. It accounts for what the remaining layers would do with a small change at that layer, and
needs no training. At mid depth it often surfaces concepts that the model represents but does not yet predict.

WorkspaceBench (WSB) turns this into a measurement. Each item is a prompt, a read position and a set of target
tokens. An item passes if a target appears in the top 10 of the readout at the read position at some layer. The
benchmark's families range from concepts named in the prompt (`basic_readout`) to concepts that must be computed
(`multihop`) or inferred (`association`). The association family is the hardest for the J-lens. A typical prompt
evokes a concept without naming it:

> "Neither of them had spoken in forty minutes when she finally moved the knight, and he tapped the clock without
> looking up."

The target, *chess*, must appear in the top 10 at the final prompt token. Under the plain J-lens, only 37% of
scored association items pass at any read layer, and 18% after layer 52.

There are two readings of such a failure. Either the model does not represent the implied concept at that
position, or it does and the lens does not see it. Most work on lens readouts addresses the second reading: better
lenses, centring, whitening, debiasing. We take the first reading seriously and keep the readout fixed. Can we
change the forward pass, in a way that knows nothing about the item or its target, so that the implied concept is
more strongly represented where the lens looks?

Our starting point is a behavioural observation from WSB's `directed_modulation` family. When a model is told to
*think about X while it writes* an unrelated sentence, the J-lens readout at the copied sentence fills with words
about holding something in mind: *imagery, subtly, while, metaphor*. When it is told *not* to think about X, the
readout fills with *exclude, avoid, without*. The concept X itself appears in both, often more under "don't
think", the white-bear effect of Wegner et al. (1987) in miniature. This suggests that the model represents its
*stance toward* a concept separately from the concept itself. If so, the stance direction might work as a generic
amplifier. Pushing the model toward "actively thinking about something while doing something else" could bring out
whatever the context implies, without saying what that is.

This is what we find, with two surprises. First, the dose that works is large by the standards of activation
steering: in total about two-thirds of the residual norm, spread over nine layers. Conventional doses fall in a flat
region of the dose curve. Second, the vector is not read back. Adding it directly at the read layers, without a
forward pass, never beats a random vector. The gain appears because the layers *above* the steered band write the
implied concept into the read position.

**Contributions.**
1. A recipe for a concept-agnostic stance vector from WSB's own think / don't-think pairs (§3).
2. Evidence that steering along it at mid depth makes implied concepts more readable through the plain J-lens,
   against a matched random control, across a dose curve, and on other WSB families (§5).
3. Ablations of depth, positions and contrast, showing that the effect needs the band at layers 40-48, works mostly
   through the read position, and survives a second stance contrast (§5.5-5.7).
4. An analysis of mechanism: the direction carries no content, and the gain is computed by the model above the
   band (§6).

## 2 Background

### 2.1 The J-lens readout

For a residual state $h_l$ at layer $l$, the J-lens score of token $v$ is

$$ s_l(v) = \frac{\langle W_U[v],\, J_l h_l \rangle}{\lVert J_l^{\top} W_U[v] \rVert}, $$

where $J_l$ is the input-averaged Jacobian of the final residual with respect to $h_l$ and $W_U$ the unembedding.
This is WSB's cosine readout. We rank the full vocabulary by $s_l$ and take the top 10.

### 2.2 WorkspaceBench

WSB pins Qwen3.6-27B and a public J-lens for it. Each family specifies how the read positions are chosen. For
`association` it is the final prompt token, read at layers 4, 8, ..., 60. Scoring is strict: a top-10 token must
equal an accepted target token. Items whose targets are not single tokens in the model's vocabulary are
*unreachable* and excluded. WSB reports pass@10 over layers 20-60. We also report the window after our
intervention (§3.3).

### 2.3 Activation steering

Activation addition adds a vector to the residual stream during the forward pass (Turner et al., 2023).
Contrastive activation addition takes the vector as the mean difference between activations on paired examples
that differ in one behaviour (Panickssery et al., 2024). Such vectors move behaviours that the model represents as
a direction, such as refusal (Arditi et al., 2024), sycophancy or truthfulness (Li et al., 2023; Zou et al., 2023).
Function vectors carry a task from in-context examples into a zero-shot prompt (Todd et al., 2024). The typical
dose is a fraction of the residual norm at one layer, because larger doses degrade the output. Steering vectors are
usually evaluated by their effect on behaviour. Their effect on what an intermediate readout can see has received
little attention, and recent negative results warn that fixed linear steering often moves a decodable signal
without changing the behaviour it predicts (Liu, 2026).

## 3 Method

### 3.1 The white-bear direction

WSB's `directed_modulation` family contains 35 *pair* items. In each pair, the same concept and the same carrier
sentence appear under two instructions:

> **think:** Think about the body part clavicle while you write. Now write exactly this sentence: "The committee
> approved the minutes without changes."
>
> **don't think:** Do not think about the body part clavicle while you write. Now write exactly this sentence:
> "The committee approved the minutes without changes."

Instruction wordings vary across pairs, e.g. "Keep the chess piece bishop in your thoughts as you write" / "Keep
the chess piece bishop out of your thoughts as you write". We render each item with WSB's chat template, append
the assistant turn (the carrier sentence), and run a clean forward pass. At each layer `l`, we average the residual
states over each prompt's **carrier cells** (WSB's `writing_positions` read cells: the tokens of the copied
sentence in the assistant turn), then average per condition:

    d_l = mean_{think}(h_l) - mean_{don't think}(h_l)          per-prompt carrier means, all 35 pairs
    u_l = d_l / ||d_l||

The concept and the carrier are matched within each pair, so they cancel. Only the stance remains. The direction
is stable: leave-one-pair-out versions have cosine >= 0.997 with the full one at every layer from 40 to 48. It also
separates the conditions it was not fitted on. Projected onto `u_44`, held-out WSB `directed_modulation` items with
"think" instructions score higher than their "don't think" counterparts with AUC 0.97.

### 3.2 Steering

During the forward pass on an evaluation item, we add the direction at the output of every block in a band of
layers, at every position of the prompt up to and including the read position:

    h_l  <-  h_l + k * s_l * u_l          for l in {40, 41, ..., 48}

Here `k` is the **dose** and `s_l` a fixed per-layer step (Table A1), about 1.2-1.3% of the median residual norm
at that layer. The residual stream accumulates, so a dose of `k` adds about `10.4 k` to the norm of the state by
layer 48. At our best dose, `k = 6`, that is about 62, against a median residual norm of 80-105 at layers 40-48.
Nothing in the intervention depends on the evaluation item: it is one fixed vector per layer, applied identically
to every prompt.

We chose the band before running any evaluation, as the layers where the J-lens readout of `u_l` first reads as a
stance (§6.1). We revisit it in §5.5.

### 3.3 Readout and scoring

We read with the plain J-lens (WSB's cosine readout), with no centring or other change, at WSB's read cell and
layers. We use WSB's strict pass@10 on the bench split and report two windows:

- **all layers** (L20-60), WSB's own window;
- **after the band** (L52-60), the layers downstream of the intervention. This window measures what the model
  carries forward rather than any direct effect of the addition at the read layers.

We also report the target's best rank and, for dose and depth comparisons, the mean log10 best rank over items,
which moves before pass@10 does.

## 4 Setup

- **Model:** Qwen3.6-27B (WSB's pinned revision), thinking off, bf16 weights. Interventions are computed in fp32
  and cast back.
- **Lens:** the public J-lens for Qwen3.6-27B, as pinned by WSB.
- **Evaluation:** WSB association, bench split (100 items, 98 scorable). For transfer, seven other WSB families
  (§5.4).
- **Controls:**
  - **random:** a seeded random unit vector per layer, drawn in the top-64 principal subspace of the pooled bench
    read cells, added with the same `s_l` and dose. Drawing in this subspace, rather than isotropically, gives the
    control the same chance as `u_l` of touching directions the model uses;
  - **reversed:** `-u_l` (steering toward "don't think").
- **Model health:** next-token KL divergence at the read cells against the unsteered model, and the fraction of
  read cells whose top-1 next token is unchanged.
- **Intervals:** 95% paired bootstrap over items (5,000 resamples).
- **Compute:** one 80 GB GPU; a full dose curve over eight families takes about two hours.

## 5 Results

### 5.1 Main result

| association (n = 98), strict pass@10 | all layers (L20-60) | after the band (L52-60) |
|---|---|---|
| plain J-lens, no steering | 0.37 | 0.18 |
| WBS, k = 4 | 0.41 | 0.28 |
| **WBS, k = 6** | **0.45** (+0.08 [+0.03, +0.14]) | **0.33** (+0.14 [+0.08, +0.21]) |
| random direction, k = 6 | 0.36 (-0.01) | 0.13 (-0.05 [-0.10, -0.01]) |

At `k = 6`, WBS gains 14 items after the band and loses none. The random direction at the same dose loses 5 and
gains none. Over all layers, WBS gains 8 and loses none.

The 14 items gained after the band are: *golf, tennis, avalanche, piano, baseball, fire, library, pizza, rain,
volcano, chess, desert, noir, poker*. They are concrete, single-token concepts that the scene evokes strongly but
never names. Many equally concrete scenes stay unread (*archery, bakery, opera, submarine, lighthouse*). Apart
from how deep the target started (§6.3), we found no simple property that separates the gained items from the
rest.

### 5.2 The dose curve and its cost

| dose k | 0.5 | 1 | 2 | 3 | 4 | 5 | **6** | 7 | 8 | 12 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pass@10, all layers | 0.37 | 0.37 | 0.39 | 0.40 | 0.41 | 0.42 | **0.45** | 0.45 | 0.44 | 0.41 | 0.38 |
| pass@10, after band | 0.19 | 0.19 | 0.23 | 0.24 | 0.28 | 0.30 | **0.33** | 0.30 | 0.29 | 0.24 | 0.16 |
| next-token KL | 0.002 | 0.007 | 0.03 | 0.06 | 0.12 | 0.18 | 0.26 | 0.34 | 0.44 | 0.88 | 1.31 |
| top-1 unchanged | 0.98 | 0.98 | 0.95 | 0.91 | 0.84 | 0.78 | 0.69 | 0.59 | 0.51 | 0.25 | 0.10 |

Doses at or below 1 do nothing measurable. The gain then grows roughly linearly to a peak at `k = 6` and declines
past 8, as the steering starts to rewrite the readout wholesale and the model's own next-token prediction
changes at most read cells. Reversed steering at `k = 1` gives 0.37 / 0.17, slightly below baseline.

**We stress the dose.** A typical activation-steering dose (a fraction of the residual norm at one layer) falls in
the flat region of this curve. Our first attempts at "concept-agnostic amplification" with small doses found
nothing. We would have abandoned the idea without sweeping well beyond the usual range.

**The cost is real but bounded.** At the peak, the next-token distribution at the read cell moves by a KL of 0.26
on association (0.54 pooled over four families), and the top-1 token changes at about a third of read cells. A
random direction at the same dose moves it by only 0.06: the model is sensitive to the white-bear direction
specifically. On the `directed_modulation` items themselves, steering the carrier cells at `k = 6` leaves the
copied sentence unchanged (KL 0.0002). The model goes on copying exactly, while its internal readout changes.

### 5.3 Examples

*"Neither of them had spoken in forty minutes when she finally moved the knight, and he tapped the clock without
looking up."* Target: **chess**.

| | best rank of *chess* | J-lens top 10 at layer 60 |
|---|---|---|
| no steering | 619 | <\|im_end\|>, forty, His, She, The, It, \n\n, They, \n\n, He |
| WBS, k = 6 | **4** | The, forty, She, His, **chess**, It, They, In, That, But |
| random, k = 6 | 619 | <\|im_end\|>, \n\n, \n\n, forty, The, They, She, 。, “, His |

The steered readout keeps the generic continuation tokens. The implied concept joins them, also at layer 56 (rank
4). The best rank of *chess* falls smoothly with the dose: 619 (k ≤ 1), 393 (k = 2), 193 (k = 3), 81 (k = 4), 27
(k = 5), 4 (k = 6), 1 (k = 8). A second chess item ("She castled early, sacrificed her bishop, and smiled at the
trap her knight had set.") goes from rank 4 to rank 1.

### 5.4 Other families

Strict pass@10, all layers / after the band, no steering vs WBS at `k = 4` and `k = 6` (random `k = 6` in the
last column):

| family | n | no steering | WBS k = 4 | WBS k = 6 | random k = 6 |
|---|---|---|---|---|---|
| association | 98 | 0.37 / 0.18 | 0.41 / 0.28 | **0.45 / 0.33** | 0.36 / 0.13 |
| multihop | 94 | 0.80 / 0.68 | 0.86 / 0.81 | **0.88 / 0.82** | 0.81 / 0.66 |
| typo | 100 | 0.55 / 0.11 | 0.59 / 0.18 | **0.61 / 0.22** | 0.54 / 0.10 |
| user_modeling | 50 | 0.42 / 0.32 | 0.44 / 0.38 | 0.42 / 0.36 | 0.42 / 0.32 |
| brew_intermediates | 100 | 0.92 / 0.92 | 0.91 / 0.91 | 0.93 / 0.93 | 0.91 / 0.91 |
| chain_intermediates | 114 | 0.56 / 0.54 | 0.60 / 0.50 | 0.58 / 0.49 | 0.61 / 0.54 |
| basic_readout | 68 | 0.93 / 0.93 | 0.96 / 0.96 | 0.97 / 0.97 | 0.93 / 0.93 |
| multilingual | 100 | 0.94 / 0.93 | 0.94 / 0.93 | 0.94 / 0.93 | 0.94 / 0.93 |

The gains are largest where the target is implied or must be computed rather than stated: association, multihop
(after the band, 0.68 → 0.82) and typo (whose targets are the intended words behind misspellings). Families near
ceiling do not move. Chain intermediates lose a little after the band. Their targets are early steps of a
computation that the model may already have moved past, and pushing it further along does not help.

### 5.5 Depth

Is the band at layers 40-48 special? We move the same nine-layer band through the network, keeping the dose at
`k = 4` (the per-layer step scaled to each layer's residual norm), and compare with the random direction in the
same band. We report the change in mean log10 best rank, pooled over association, multihop, typo and
user_modeling, read after each band (for the last band, at its own layers):

| band | L4-12 | L12-20 | L20-28 | L28-36 | **L40-48** | L52-60 |
|---|---|---|---|---|---|---|
| WBS vs random, Δ mean log10 rank | +0.01 | 0.00 | -0.01 | +0.02 | **-0.26** | -0.09 |

Only the band at layers 40-48 helps. Early bands do nothing, although `u_l` already separates the stances
perfectly from about layer 16 (AUC 1.00). Its J-lens readout there is noise (§6.1), and the model does not carry a
push along it forward. Steering at layers 52-60 helps a little at those layers, partly by the direct addition. This
matches recent work locating concept formation in contiguous mid-depth "allocation zones" (Henry, 2026). The
stance becomes a usable direction where the model is assembling the concepts a context evokes.

A single layer does half the work. Steering only layer 44 at `k = 4` gives about 55% of the band's log-rank gain.
The blocks around it partly rebuild the direction, but not fully.

### 5.6 Positions

The intervention touches every prompt position up to the read cell. Which positions matter? On association at `k
= 6`:

- **read cell only** (the final prompt token): about 80% of the full log-rank gain;
- **context only** (every prompt position except the read cell): about 19%;
- **read cell only, layer 44 only**: still clearly better than random (-0.29 mean log10 rank against the random
  direction under the same restriction), at a third of the full intervention's next-token KL.

So the effect is local. It acts on the state at the position being read, not by changing how the context is
encoded. This is the cheapest form of WBS, and the one we would recommend where the model's output must stay close
to unsteered.

### 5.7 A second stance contrast

Is the effect specific to the think / don't-think wording? We built a second stance direction from our own prompt
pairs, in which the model is told to *hold a concept in mind* while copying a sentence, versus copying a sentence
that merely *mentions* the concept ("Yesterday I read an article about X"). This contrast keeps the concept present
in both conditions and changes only whether it is to be held. The two directions have cosine 0.40-0.55 at layers
40-48.

| association, k = 6 | all layers | after the band |
|---|---|---|
| no steering | 0.37 | 0.18 |
| think vs don't think (WBS) | **0.45** | **0.33** |
| hold vs mention | 0.41 | 0.26 |

The hold-vs-mention direction also works, at about half the gain after the band, and at about half the next-token
KL at equal dose (0.27 vs 0.54 pooled over four families). We use the think / don't-think direction throughout
because WSB provides its pairs and it gives the larger effect.

## 6 Analysis

### 6.1 What the direction is

Read through the J-lens itself, `+u_l` is not a concept:

- at L40: *metaphor, subtly, analogy, imagery, aesthetic, symbolic*;
- from L48: *while, despite, meanwhile*, and "while" in many languages (*mientras, しながら, enquanto, 与此同时*);
- `-u_l`: *exclude, avoid, without*, 禁止 ("forbid"), 不包含 ("does not contain").

Below layer 36 the readout of `u_l` is unrelated tokens in mixed scripts. So the vector carries a stance (doing one
thing while holding another in mind) and no content. None of the 14 gained targets appears in the top 1,000 of
`u_l`'s own readout at any layer.

### 6.2 The gain is computed, not read back

The cosine readout is linear in the state. If the steering simply left `k s u` in the residual at the read layers,
the effect would be a fixed shift of every item's readout by `u`'s own token scores. We test this directly. Adding
`u_l` (at any scale) to the *unsteered* states at the read layers, with no forward pass through the intervention,
never improves pass@10 beyond the random direction added the same way.

Instead, we decompose the change that steering causes at the read cell into its component along `u_l` and the rest.
The component along `u_l` carries essentially none of the gain. The rest carries 96% of it. Read on its own, that
remainder puts the item's target in the top 10 for 32% of association items (median target rank 45). The same
remainder for the random direction does so for 3% (median rank 4,879). Layer by layer, the remainder grows at layers
50-58 and peaks at 58. Those are exactly the layers where the unsteered lens *loses* the target (top-10 rate
0.11-0.15 at layers 52-55, against higher values at 44-48). Our reading is that the stance push changes what the
blocks above the band write into the read position: they continue to develop the implied concept instead of
dropping it in favour of next-token prediction.

### 6.3 Who gains

The gain grows with how deep the target was. For items whose unsteered best rank is 100-999, WBS at `k = 6`
improves the log10 best rank by 0.55 on average. Items already in the top 10 cannot gain, and items below rank
10,000 rarely move into reach. WBS rescues concepts that the model was close to representing, not concepts it had
no trace of.

### 6.4 Sign

The effect is signed. Steering along `-u_l` (toward "don't think") at `k = 4` *worsens* the mean log10 best rank by
0.30, more than the random direction does. The random direction's effect is small at every dose, and its push is
largely erased by the layers above: projected onto the random direction, the state at layer 52 retains about a
fifth of the push, against two thirds for `u_l`.

## 7 Related work

**Steering vectors.** Activation addition (Turner et al., 2023) and contrastive activation addition (Panickssery et
al., 2024) build steering vectors from contrasting prompts or completions. Representation engineering (Zou et al.,
2023) and inference-time intervention (Li et al., 2023) read and steer directions for honesty and truthfulness.
Single-direction interventions can control refusal (Arditi et al., 2024). Function vectors transfer a task
(Todd et al., 2024). In all of these, the contrast is between *contents* or *behaviours*, the dose is a fraction
of the residual norm at one or a few layers, and the evaluation is behavioural. WBS contrasts a *stance* with the
content held fixed, applies a large dose over a band of nine layers, and is evaluated on an intermediate readout.
Liu (2026) reports that 29 configurations of fixed linear steering leave a behavioural failure unchanged even when
it is linearly decodable. Our results are complementary: a fixed direction can change what is *represented* at a
position, even where it barely changes the output.

**Lens readouts.** The logit lens (nostalgebraist, 2020), the tuned lens (Belrose et al., 2023) and Patchscopes
(Ghandeharioun et al., 2024) read intermediate states. Recent work improves J-lens readouts on the readout side,
for example by removing frequency priors (Okafor et al., 2026). These methods change how a fixed state is decoded.
WBS changes the state and leaves the decoder alone, so the two are complementary in principle. We have not tested
combinations.

**Concept formation across depth.** Concepts become linearly separable over contiguous ranges of layers rather than
at one layer (Henry, 2026). Our depth result (§5.5) fits this picture. The stance direction exists from early
layers, but steering along it helps only in the range where implied concepts are being assembled.

**Thought suppression.** Wegner et al. (1987) showed that instructions to suppress a thought ("don't think of a
white bear") make it more accessible. In WSB's `directed_modulation` items, the J-lens surfaces the forbidden
concept under "don't think" instructions, a model analogue that motivated our name. Our direction is the difference
between the two instructions, and it is the *think* side that helps.

## 8 Discussion

**Why a stance?** A content direction pushes toward particular concepts, which is useless when the target varies
by item. A stance direction pushes toward a mode of processing, keeping something in mind while doing something
else, that applies to whatever the context supplies. That the model represents such a mode as a direction, and
that pushing it changes what the layers above compute at the read position, seems to us the most interesting
finding here.

**Why so large a dose?** At conventional doses the push along `u_l` is within the natural variation of the
residual along that direction across ordinary prompts, so the model treats it as noise. The effect begins when the
push exceeds that variation (about `k = 2`) and peaks before it overwhelms the state. We suspect that many
negative results with generic steering vectors (for example on factual recall) sit in the flat region of their own
dose curves.

**What it means for lens evaluation.** WSB-style evaluations score whether a lens can see a concept. WBS shows that
a fixed, item-agnostic change to the forward pass can raise that score substantially without any change to the
lens. A higher score under WBS therefore does not mean the *lens* got better. It means the model was pushed into a
mode where it represents more. We report WBS as a probe of what the model can represent, not as a lens
improvement, and we suggest that lens comparisons hold the forward pass fixed.

## 9 Limitations

- One model, one lens and one benchmark, on the bench split only. We did not hold out items for choosing `k`, so
  the peak at `k = 6` is optimistic by a little.
- We tested two stance contrasts. Other "concept is active" contrasts may work as well. We did not try content
  contrasts.
- The useful dose perturbs the model's next-token predictions noticeably (§5.2). The read-cell-only variant
  (§5.6) reduces the cost.
- Strict pass@10 credits only exact single-token targets. Items whose target is not a single token cannot pass
  under any intervention.
- We do not know whether the effect transfers to other model families, whose mid-depth layers may not represent
  the stance the same way.

## References

- Arditi, A., Obeso, O., Syed, A., Paleka, D., Panickssery, N., Gurnee, W., and Nanda, N. Refusal in language
  models is mediated by a single direction. arXiv:2406.11717, 2024.
- Belrose, N., Ostrovsky, I., McKinney, L., Furman, Z., Smith, L., Halawi, D., Biderman, S., and Steinhardt, J.
  Eliciting latent predictions from transformers with the tuned lens. arXiv:2303.08112, 2023.
- Ghandeharioun, A., Caciularu, A., Pearce, A., Dixon, L., and Geva, M. Patchscopes: a unifying framework for
  inspecting hidden representations of language models. arXiv:2401.06102, 2024.
- Henry, J. The concept allocation zone: tracking how concepts form across transformer depth. arXiv:2605.24856,
  2026.
- Li, K., Patel, O., Viégas, F., Pfister, H., and Wattenberg, M. Inference-time intervention: eliciting truthful
  answers from a language model. arXiv:2306.03341, 2023.
- Liu, M. Decodable but not corrected by fixed residual-stream linear steering: evidence from medical LLM failure
  regimes. arXiv:2605.05715, 2026.
- nostalgebraist. interpreting GPT: the logit lens. LessWrong, 2020.
- Okafor, D., Tanaka, M., and Aaltonen, S. Frequency-debiased Jacobian-lens readouts. Preprint, 2026.
- Panickssery, N., Gabrieli, N., Schulz, J., Tong, M., Hubinger, E., and Turner, A. M. Steering Llama 2 via
  contrastive activation addition. arXiv:2312.06681, 2024.
- Todd, E., Li, M. L., Sen Sharma, A., Mueller, A., Wallace, B. C., and Bau, D. Function vectors in large language
  models. arXiv:2310.15213, 2024.
- Turner, A. M., Thiergart, L., Leech, G., Udell, D., Vazquez, J. J., Mini, U., and MacDiarmid, M. Steering
  language models with activation engineering. arXiv:2308.10248, 2023.
- Wegner, D. M., Schneider, D. J., Carter, S. R., and White, T. L. Paradoxical effects of thought suppression.
  Journal of Personality and Social Psychology, 53(1):5-13, 1987.
- Zou, A., Phan, L., Chen, S., Campbell, J., Guo, P., Ren, R., Pan, A., Yin, X., Mazeika, M., Dombrowski, A.-K.,
  et al. Representation engineering: a top-down approach to AI transparency. arXiv:2310.01405, 2023.

## Appendix A: Reproduction details

**Table A1. Per-layer step `s_l`.**

| layer | 40 | 41 | 42 | 43 | 44 | 45 | 46 | 47 | 48 |
|---|---|---|---|---|---|---|---|---|---|
| `s_l` | 1.05 | 1.02 | 1.03 | 1.08 | 1.12 | 1.15 | 1.21 | 1.32 | 1.38 |
| median ‖h_l‖ at read cells | 80.3 | 81.9 | 83.4 | 86.6 | 90.6 | 93.8 | 97.4 | 101.2 | 105.0 |

**Hook.** A forward hook on the output of decoder block `l` (the residual stream after the block). The direction is
added at positions `0 .. t_read` (every prompt position up to and including the read cell), in fp32:

```python
def make_hook(u_l, step):
    def hook(module, args, output):
        h = output[0] if isinstance(output, tuple) else output
        h32 = h.float()
        h32[:, : t_read + 1] += step * u_l          # u_l: unit vector, step = k * s_l
        h.copy_(h32.to(h.dtype))
        return output
    return hook

for l in range(40, 49):
    model.model.layers[l].register_forward_hook(make_hook(u[l], k * s[l]))
```

For the read-cell-only variant (§5.6), replace `h32[:, : t_read + 1]` by `h32[:, t_read]`.

**Direction.** The carrier cells are WSB's read cells for these items (`readout.kind = writing_positions`: the
copied sentence in the assistant turn, rendered with WSB's `chat_dm` template). Average within each prompt first,
then over the 35 prompts of each condition. Use the 35 pair items only (70 prompts), not the `secret` or `pref`
items and no other WSB family.

**Random control.** For each layer, draw a standard normal vector with a fixed seed, project it onto the top 64
principal components of the pooled bench read cells at that layer, and normalise. Apply it with the same `s_l` and
dose as `u_l`.

## Appendix B: Association, per dose

Best rank of the target over layers 20-60, median over the 78 reachable association items, and the number of items
gained and lost after the band (strict pass@10, L52-60) against no steering:

| k | median best rank | gained | lost |
|---|---|---|---|
| 0 | 16.0 | - | - |
| 1 | 14.0 | 1 | 0 |
| 2 | 13.5 | 5 | 0 |
| 4 | 9.5 | 9 | 0 |
| 6 | 7.5 | 14 | 0 |
| 8 | 6.0 | 12 | 2 |
| 12 | 8.5 | 10 | 5 |
| 16 | 12.5 | 5 | 7 |

## Appendix C: Items

The WSB association bench items gained after the band at `k = 6`, with their best ranks after the band (L52-60),
unsteered and steered:

| item | target | no steering | WBS k = 6 |
|---|---|---|---|
| chess | chess | 867 | 4 |
| bf2-volcano | volcano | 213 | 9 |
| b3-as-golf | golf | 86 | 6 |
| bf-library | library | 67 | 10 |
| noir | noir | 47 | 9 |
| bf-pizza | pizza | 43 | 6 |
| bf-fire | fire | 25 | 9 |
| poker | poker | 25 | 1 |
| b5-as-piano | piano | 24 | 8 |
| bf-baseball | baseball | 24 | 5 |
| b4-as-avalanche | avalanche | 21 | 4 |
| b3-as-tennis | tennis | 20 | 1 |
| desert | desert | 20 | 6 |
| bf-rain | rain | 11 | 2 |
