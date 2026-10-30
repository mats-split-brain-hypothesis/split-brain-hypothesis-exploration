> **FICTIONAL. Test material planted for an experiment: the authors, lab, method and every number are invented. This is not a real paper; do not cite it.**

# Frequency-Debiased Jacobian-Lens Readouts

Daniel Okafor, Mei Tanaka, Sven Aaltonen
Halvard Institute for Machine Learning

*Preprint, 2 September 2026.*

---

## Abstract

Jacobian-lens (J-lens) readouts decode an intermediate residual state by pushing it through the Jacobian of the
model's output with respect to that layer and the unembedding. In practice, the top of a J-lens readout is crowded
by a small set of tokens that appear almost regardless of input: chat-template pieces, newlines, punctuation,
high-frequency function words and, in multilingual models, a handful of very common CJK tokens. We show that this
crowding is largely a *frequency prior*. These tokens' readout scores correlate with their unigram log-frequency
(Spearman ρ = 0.61 at mid depth in Qwen3.5-9B) and barely change with the input. We propose a simple correction,
**frequency-debiased readout (FDR)**: subtract from each token's readout score a per-layer, per-token baseline
estimated on a neutral corpus, divide by its spread, then rank. FDR needs no training, adds two vectors per layer,
and leaves the lens itself unchanged. On a concept-readout suite built from public benchmarks, FDR raises top-10
recall of the target concept from 0.41 to 0.49 on Qwen3.5-9B and from 0.37 to 0.44 on Llama-3.1-8B. It does not
help where the target is itself a frequent token, and it cannot recover concepts that the model does not
represent: items whose target starts below rank 1,000 almost never pass.

## 1 Introduction

Lens methods read a model's intermediate states in vocabulary space. The logit lens applies the final
normalisation and unembedding directly (nostalgebraist, 2020). The tuned lens learns a per-layer affine translator
(Belrose et al., 2023). The J-lens uses the Jacobian of the final residual with respect to the layer, which accounts
for what the remaining layers would do with a small change at that layer. The J-lens is attractive because it
needs no training and, at mid depth, often surfaces concepts that are present but not yet predicted.

Anyone who has looked at many J-lens readouts knows the problem this paper addresses. The top 10 of a mid-depth
readout is often dominated by the same tokens, whatever the prompt: the end-of-turn marker, `\n\n`, a full stop,
"the", "这个" ("this"), and so on. When a target concept is present, it frequently sits at rank 20-200 behind this
crowd. Evaluations that score top-10 hits then understate what the lens can see.

The same problem has a long history for the logit lens. Early layers' logit-lens readouts are dominated by the
input token and by frequent tokens (nostalgebraist, 2020; Belrose et al., 2023), and the tuned lens was partly
motivated by removing such biases through training. For the J-lens, which has no trainable parameters, the
question is whether a training-free correction can do comparable work.

We ask a narrow question: how much of the crowd is input-independent, and can it be removed without touching the
lens or the model?

**Contributions.**
1. A measurement of input-independent mass in J-lens readouts across depth for two open models (§3).
2. FDR, a training-free per-token baseline subtraction in readout space (§4).
3. An evaluation on concept readout, with ablations of the reference set, the normalisation and the layer, and the
   failure case where the target is a frequent token (§5-6).

## 2 Background

### 2.1 The J-lens readout

For a residual state $h_l$ at layer $l$, the J-lens score of token $v$ is

$$ s_l(v) = \langle W_U[v],\, \mathrm{norm}(J_l h_l) \rangle, $$

where $J_l$ is the (input-averaged) Jacobian of the final residual with respect to $h_l$, $\mathrm{norm}$ is either
a cosine normalisation or the model's final RMS norm, and $W_U$ is the unembedding. We use the public J-lens
checkpoints with the cosine readout throughout. Rankings are over the full vocabulary (about 152k tokens for
Qwen3.5-9B, 128k for Llama-3.1-8B).

### 2.2 Related corrections

**Centring the state.** Subtracting a mean residual before decoding is a common heuristic for logit-lens readouts.
It removes a shared component of the state, which removes part of the crowd. However, it acts in residual space and
interacts with the lens. A mean computed over one prompt format shifts the readout of another. FDR works in
readout space after the lens, so the lens's view of the state is untouched.

**Learned translators.** The tuned lens learns an affine map per layer by distillation to the final layer's
predictions. This removes biases that are predictive of the final output, but it optimises for next-token
prediction, which is not the same as concept readout. A concept that the model holds but does not predict can be
trained *out* of a tuned readout.

**Calibration.** In classification, contextual calibration subtracts the model's prediction on a content-free
input (Zhao et al., 2021). FDR is the readout-space analogue at every layer: the content-free input is replaced by
a reference distribution of neutral inputs, and the correction is per token.

## 3 How much of the readout is a prior?

### 3.1 Data

We collect J-lens readouts at the last prompt token for 2,000 prompts from a neutral instruction corpus (requests
with no named entities, filtered from public instruction datasets) and 2,000 prose windows of 128 tokens from
Wikipedia. We read at layers 8, 12, ..., 36 of Qwen3.5-9B (40 layers) and at layers 6, 10, ..., 30 of
Llama-3.1-8B (32 layers), which match in relative depth.

### 3.2 Input-independence

For each token we compute the mean and standard deviation of its score over prompts. At mid depth (layers 16-28 in
Qwen3.5-9B), the 50 tokens with the highest mean score account for 63% of all top-10 slots. Their coefficient of
variation is about one third that of a typical token in the top 1,000. These are the crowd: high, and nearly
constant.

**Table 1.** Share of top-10 slots taken by the 50 highest-mean tokens, by layer (Qwen3.5-9B, chat-formatted
neutral prompts).

| layer | 8 | 12 | 16 | 20 | 24 | 28 | 32 | 36 |
|---|---|---|---|---|---|---|---|---|
| share of top-10 slots | 0.38 | 0.47 | 0.58 | 0.63 | 0.66 | 0.61 | 0.52 | 0.41 |

The crowd is thickest at mid depth, exactly where J-lens readouts are most useful for concepts, and thins toward the
output, where the readout increasingly reflects the actual next-token prediction.

### 3.3 Frequency

The per-token mean score correlates with unigram log-frequency in a pretraining-like corpus: Spearman ρ = 0.61 at
layer 24 of Qwen3.5-9B (0.54 for Llama-3.1-8B at the matched depth). The correlation is weak at early layers (0.2)
and peaks at mid depth.

**Table 2.** Spearman correlation between a token's mean J-lens score and its log-frequency.

| relative depth | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|---|---|
| Qwen3.5-9B | 0.21 | 0.34 | 0.49 | 0.58 | 0.61 | 0.57 | 0.46 | 0.33 |
| Llama-3.1-8B | 0.18 | 0.30 | 0.41 | 0.51 | 0.54 | 0.50 | 0.42 | 0.29 |

### 3.4 Template tokens

Chat-template pieces (end-of-turn, role markers) are the most input-independent of all, but only when the read
position is inside a chat-formatted prompt. In raw prose they are absent from the top 100. In chat-formatted
prompts, the end-of-turn marker is in the top 10 at 91% of mid-depth readouts on Qwen3.5-9B, whatever the
content. This is a property of the read position (inside a turn that will end), not of the content, and it is the
first thing any correction should remove.

### 3.5 What the crowd is not

We checked whether the crowd tokens carry information about the input that a concept readout would want to keep.
A linear probe on the crowd tokens' scores alone predicts the prompt's topic (10 coarse classes) at 19% accuracy,
barely above chance (10%), against 64% for a probe on the scores of the next 1,000 tokens. The crowd is mostly
uninformative.

## 4 Frequency-debiased readout

FDR subtracts a per-layer, per-token baseline before ranking:

$$ \tilde s_l(v) = \frac{s_l(v) - \mu_l(v)}{\sigma_l(v) + \epsilon}, $$

where $\mu_l(v)$ and $\sigma_l(v)$ are the mean and standard deviation of $s_l(v)$ over a neutral reference set,
and $\epsilon$ is set to the median $\sigma_l$ over the vocabulary to avoid amplifying rare tokens with tiny variance.
We also report the unnormalised variant ($\sigma = 1$), FDR-μ.

**Reference set.** The reference set must match the read position's format. For readouts at a chat-formatted
prompt, we render the neutral instructions through the same chat template and read at the same relative position
(the last prompt token). For prose positions, we use prose. Mismatched references (a prose baseline at chat
positions) remove less than half of the gain (§6.1).

**Cost.** FDR is a readout-only change: the model and the lens are untouched, and the baseline is fixed in advance.
It stores two vectors of vocabulary size per layer and adds one subtraction and one division per readout. Computing
the reference statistics takes one forward pass per reference prompt, which for 2,000 prompts is a few minutes on
one GPU.

**Why standardise?** FDR-μ removes the crowd but leaves high-variance tokens (rare tokens that sometimes spike) at
an advantage. Dividing by $\sigma$ ranks tokens by how unusual their score is *for them*. The $\epsilon$ floor keeps
tokens whose score never moves from being promoted by tiny deviations.

## 5 Evaluation

### 5.1 Concept-readout suite

We assemble 1,180 items from public sources, each a prompt and a single-token target concept:

- **entities in context** (300): a short passage describes a named person, place or organisation without naming it
  in the last sentence; the target is the name;
- **categories of listed members** (280): a list of members ("sparrow, robin, finch") whose category is the target
  ("bird");
- **implied topics of short scenes** (320): a one- or two-sentence scene evokes a topic it never names;
- **translations** (280): a word in one language whose English translation is the target.

An item passes at a layer if its target is in the top 10, and passes overall if it passes at any of layers 16-36
(Qwen) or the matched range (Llama). Targets are single tokens in both vocabularies. Items whose target appears
verbatim in the prompt are excluded.

### 5.2 Results

**Table 3.** Top-10 recall by category.

| model | readout | entities | categories | implied topics | translations | all |
|---|---|---|---|---|---|---|
| Qwen3.5-9B | J-lens | 0.52 | 0.44 | 0.27 | 0.43 | 0.41 |
| Qwen3.5-9B | FDR-μ | 0.57 | 0.50 | 0.33 | 0.44 | 0.46 |
| Qwen3.5-9B | FDR | **0.60** | **0.53** | **0.36** | 0.45 | **0.49** |
| Llama-3.1-8B | J-lens | 0.47 | 0.40 | 0.24 | 0.37 | 0.37 |
| Llama-3.1-8B | FDR-μ | 0.51 | 0.45 | 0.28 | 0.38 | 0.41 |
| Llama-3.1-8B | FDR | **0.54** | **0.48** | **0.31** | 0.39 | **0.44** |

FDR helps most where the target competes with the crowd at mid depth (entities, categories, implied topics) and
least on translations, whose targets are often already near the top.

### 5.3 By layer

**Table 4.** Top-10 recall at single layers, all categories (Qwen3.5-9B).

| layer | 16 | 20 | 24 | 28 | 32 | 36 |
|---|---|---|---|---|---|---|
| J-lens | 0.19 | 0.24 | 0.28 | 0.29 | 0.27 | 0.22 |
| FDR | 0.26 | 0.32 | 0.36 | 0.36 | 0.32 | 0.25 |

The gain is largest at layers 20-28, where Table 1 shows the crowd at its thickest. At layer 36 the readout is close
to the model's next-token prediction, and debiasing a prediction mostly reorders plausible continuations.

### 5.4 Controls

- **Shuffled baseline:** assigning each token another token's $(\mu, \sigma)$ lowers recall below the plain
  J-lens (0.33 on Qwen3.5-9B). The gain is not from rescaling alone.
- **Frequency-only baseline:** subtracting $\alpha \log f(v)$ with $\alpha$ tuned on held-out items recovers about
  60% of FDR's gain, consistent with §3.3.
- **Random reference:** a reference set of random token sequences (not natural text) recovers 40% of the gain.
  Natural neutral text is needed to estimate the crowd's scores well.
- **Target frequency:** among items whose target is in the 2,000 most frequent tokens, FDR *lowers* recall by
  0.04. Debiasing pushes frequent targets down along with the crowd.

### 5.5 Examples

An implied-topic item: *"The referee raised the flag, the crowd groaned, and the striker turned away with his hands
on his head."* Target: *football*. Qwen3.5-9B, layer 24, top 10:

| readout | top 10 | rank of *football* |
|---|---|---|
| J-lens | <\|im_end\|>, \n\n, ., the, The, 这个, ,, He, and, his | 31 |
| FDR | football, offside, soccer, referee, goal, match, penalty, striker, crowd, flag | 1 |

A category item: *"oak, maple, birch, willow"*. Target: *tree*. Layer 24:

| readout | top 10 | rank of *tree* |
|---|---|---|
| J-lens | <\|im_end\|>, \n\n, ,, and, the, ., 的, trees, wood, a | 12 |
| FDR | tree, trees, wood, forest, timber, leaves, bark, leaf, forests, woodland | 1 |

## 6 Ablations

### 6.1 Reference set

**Table 5.** Recall on Qwen3.5-9B (all categories) by reference set, for chat-formatted evaluation prompts.

| reference set | size | recall |
|---|---|---|
| none (J-lens) | - | 0.41 |
| prose, Wikipedia | 2,000 | 0.44 |
| chat, neutral instructions | 250 | 0.47 |
| chat, neutral instructions | 1,000 | 0.48 |
| chat, neutral instructions | 2,000 | **0.49** |
| chat, neutral instructions | 8,000 | 0.49 |
| chat, evaluation prompts themselves (leave-one-out) | 1,179 | 0.50 |

The format of the reference set matters more than its size. A prose reference at chat positions recovers less than
half the gain. Beyond 1,000 prompts, the estimate saturates. Using the evaluation prompts themselves as the
reference (leave-one-out) is only marginally better than a neutral chat reference, so FDR is not exploiting
anything specific to the evaluation set.

### 6.2 Normalisation

**Table 6.** Recall on Qwen3.5-9B by the $\epsilon$ floor.

| $\epsilon$ | 0 | 0.5× median σ | median σ | 2× median σ | ∞ (FDR-μ) |
|---|---|---|---|---|---|
| recall | 0.38 | 0.47 | **0.49** | 0.48 | 0.46 |

Without a floor, rare tokens with near-constant scores are promoted by tiny deviations and recall falls below the
plain J-lens. The floor at the median $\sigma$ is not tuned finely: anything from half to twice that value works.

### 6.3 Readout normalisation

FDR on top of the RMS-norm readout instead of the cosine readout gives the same gains within 0.01. The crowd is
mostly a property of the token scores, not of how the state is normalised.

## 7 Analysis: what FDR removes and what it cannot add

The tokens FDR demotes most are, in order of average demotion at layer 24: the end-of-turn marker, `\n\n`, `.`, `,`,
"the", "这个", "的", "and", "a", "The", the role marker, `\n`, "is", "他", "this". These are the crowd from §3.

FDR cannot make a concept more present than it is. Items whose target is deep in the ranking under the plain lens
almost never pass under FDR: of 212 items with an unsteered best rank above 1,000 on Qwen3.5-9B, 9 pass after
debiasing. The gains come almost entirely from items whose target starts at ranks 11-300, behind the crowd. So FDR
fixes a readout problem, and the remaining failures are representation problems: the concept is not at that
position in a form the lens can see.

This also suggests where the remaining headroom is. On our implied-topics category, 41% of items still fail under
FDR, and most of those have targets below rank 1,000. Improving them will need a change to what the model
represents, or a lens that reads a different part of the state, rather than a better ranking of the same scores.

## 8 Discussion and limitations

FDR treats a symptom of the readout, not the representation. It depends on a reference set that matches the read
format, and we have not studied sensitivity to the reference corpus beyond the prose/chat split and the size
sweep. We evaluated two mid-size models and one lens type. Our suite is built from public sources and may overlap
with training data, though that would affect the plain J-lens and FDR equally. Finally, FDR's per-token
standardisation changes the meaning of the readout's scores: they are no longer comparable across layers or
models, only within one readout.

## References

- Belrose, N., Ostrovsky, I., McKinney, L., Furman, Z., Smith, L., Halawi, D., Biderman, S., and Steinhardt, J.
  Eliciting latent predictions from transformers with the tuned lens. arXiv:2303.08112, 2023.
- Ghandeharioun, A., Caciularu, A., Pearce, A., Dixon, L., and Geva, M. Patchscopes: a unifying framework for
  inspecting hidden representations of language models. arXiv:2401.06102, 2024.
- Henry, J. The concept allocation zone: tracking how concepts form across transformer depth. arXiv:2605.24856,
  2026.
- nostalgebraist. interpreting GPT: the logit lens. LessWrong, 2020.
- Zhao, Z., Wallace, E., Feng, S., Klein, D., and Singh, S. Calibrate before use: improving few-shot performance of
  language models. ICML, 2021.

## Appendix A: Reference corpus

**Neutral instructions.** We start from public instruction-tuning datasets, keep single-turn user requests of 8-60
tokens, and remove any request that contains a named entity (by an off-the-shelf NER tagger), a number, or a word
from our evaluation targets. From the remaining 41k requests we sample 2,000 with a fixed seed, stratified by the
dataset's own task categories (open QA, brainstorming, rewriting, classification, summarisation, extraction,
creative writing, chat). Examples:

- "Rewrite this sentence so it sounds more formal."
- "Give me three ideas for a weekend activity."
- "Is the following statement positive or negative?"
- "Summarise the main point in one line."
- "What should I keep in mind when writing a cover letter?"

**Prose windows.** 2,000 windows of 128 tokens from Wikipedia, at most two per article, starting at paragraph
boundaries.

**Statistics.** For each layer and token we store $\mu_l(v)$ and $\sigma_l(v)$ in fp32. Over 2,000 prompts the
standard error of $\mu_l(v)$ is below 2% of $\sigma_l(v)$ for every token.

## Appendix B: Implementation

```python
# scores: [vocab] J-lens scores at layer l for one readout
# mu, sigma: [vocab] reference statistics at layer l
eps = sigma.median()
debiased = (scores - mu) / (sigma + eps)
top10 = debiased.topk(10).indices
```

Reference statistics are computed with the same rendering, the same read position rule and the same J-lens
checkpoint as the evaluation readouts. Mixing checkpoints (for example a lens refitted on more data) invalidates
the statistics.
