> **FICTIONAL. Test material planted for an experiment: the authors, lab, method and every number are invented. This is not a real paper; do not cite it.**

# Generic Steering Vectors Do Not Improve Knowledge Recall: A Negative Result

Lucía Herrera, Oren Dahan
Meridian AI Lab

*Preprint, 18 September 2026. Workshop version.*

---

## Abstract

Steering vectors built from contrastive prompt pairs can shift high-level behaviours such as sycophancy or refusal.
A natural hope is that a *generic* steering vector, one that encodes an attitude such as "be careful" or "recall
precisely" rather than any specific fact, could also improve what a model retrieves. We test this hope directly. We
build four families of task-agnostic contrastive vectors (careful vs careless, confident vs unsure, expert vs
novice, and focused vs distracted), sweep the layer, the coefficient and the injection positions, and measure
closed-book recall on three factual QA sets with Llama-3.1-8B-Instruct and Qwen3.5-9B. The best configuration in
each family changes exact-match accuracy by at most +0.9 points, within run-to-run noise, and no configuration
transfers across prompt templates. Large coefficients degrade fluency before they change recall. The vectors do
change the style of answers as intended, so the null is not a failure to steer. We conclude that generic attitude
vectors do not reach the retrieval process, and we release our sweep so that others need not repeat it.

## 1 Introduction

Contrastive activation addition (Panickssery et al., 2024) and activation addition (Turner et al., 2023) add a
difference-of-means vector to the residual stream to push a model toward one side of a contrast. The resulting
behaviour changes can be large for attributes that the model represents as a direction (Arditi et al., 2024).

Recall is different. Whether a model retrieves the capital of a country, or a drug's mechanism, depends on
specific stored associations, not on an attitude. Still, several informal reports suggest that prompts like "think
carefully" or "you are an expert" slightly improve factual accuracy. If those prompts work through a shared
direction, a steering vector along it might improve recall without any task-specific training. This would be
useful: a single vector, applied at inference, that makes a model retrieve better.

There are reasons to expect this to fail. Function vectors (Todd et al., 2024) show that task information can be
carried by a vector, but the vector carries the *task* (antonyms, capitals), not a disposition, and it is extracted
from examples of the task itself. Work on the mechanics of factual recall locates the retrieval of an attribute in
specific computations at the subject's last token, which a single global direction would have to modulate without
knowing the subject. And Liu (2026) finds that fixed linear steering leaves a linearly decodable failure mode in
medical QA unchanged across 29 configurations.

We find no recall-improving vector. This paper documents the search, in enough detail that the null result is
informative: four contrast families, two models, three datasets, three prompt templates, single- and multi-layer
injection, two position schemes, and five coefficients spanning the range in which the model stays fluent.

## 2 Related work

**Steering vectors.** Activation addition (Turner et al., 2023) introduced adding the difference of two prompts'
activations at one layer. Contrastive activation addition (Panickssery et al., 2024) averages the difference over
many pairs and adds it at all positions after the prompt, steering sycophancy, refusal, hallucination and other
behaviours in Llama 2. Representation engineering (Zou et al., 2023) and inference-time intervention (Li et al.,
2023) read and steer directions for honesty and truthfulness; the latter improves TruthfulQA, a benchmark that
rewards *not* asserting common misconceptions rather than retrieving more facts. Single-direction ablation removes
refusal (Arditi et al., 2024).

**Prompting for accuracy.** Role prompts ("You are an expert") and instructions to be careful are common in
practice. Systematic evaluations of their effect on factual accuracy report small and inconsistent changes. Our
§4.4 replicates this for our setting.

**Negative results for steering.** Liu (2026) reports a "decodable but not corrected" gap: a failure regime that a
probe detects at over 70% balanced accuracy is not corrected by any of five families of fixed linear steering. Our
result is of the same kind for a different target: attitudes that are clearly steerable do not carry over to
recall.

## 3 Method

### 3.1 Contrastive pairs

For each family we write 64 instruction pairs that differ only in the attitude and share a neutral task. The tasks
are unrelated to the evaluation questions: summarising a note, rewriting a sentence, listing ideas, classifying a
review. Examples (more in Appendix A):

| family | positive | negative |
|---|---|---|
| careful vs careless | Carefully summarise the following note. | Carelessly summarise the following note. |
| confident vs unsure | Confidently list three uses for a paperclip. | Unsurely list three uses for a paperclip. |
| expert vs novice | As an expert editor, rewrite this sentence. | As a novice editor, rewrite this sentence. |
| focused vs distracted | Stay fully focused and classify this review. | While distracted, classify this review. |

The steering vector at layer $l$ is the mean difference of the residual stream at the last instruction token,

$$ v_l = \frac{1}{N} \sum_i \left( h_l(x_i^{+}) - h_l(x_i^{-}) \right), $$

normalised to unit length. We also tried taking the mean over all instruction tokens instead of the last. It gives
vectors with cosine 0.8-0.9 to the last-token ones and the same results, so we report the last-token version.

### 3.2 Steering

We add $\alpha \, \bar n_l \, \hat v_l$ at a single layer $l$, at every position after the user turn begins, where
$\bar n_l$ is the mean residual norm at that layer and $\alpha$ the coefficient. We sweep every fourth layer from 4
to 28 and $\alpha \in \{0.01, 0.02, 0.05, 0.1, 0.2\}$. Coefficients above 0.2 make the outputs visibly degenerate on
both models (repetition, language switching), so we stop there.

Two variants:
- **multi-layer:** the vector added at three adjacent layers at once, with the coefficient divided by three, so the
  total added norm matches the single-layer version;
- **question-only:** the vector added only at the question's tokens, not at the answer prefix.

This gives 7 layers × 5 coefficients × 3 variants = 105 configurations per family and model, 840 in all, each run
on 3,000 questions with three templates.

### 3.3 Evaluation

Closed-book exact match on 1,000 questions each from three QA sets: general trivia, geography, and a medical subset.
Each question has a short canonical answer, and we accept a small set of aliases. Decoding is greedy, with a fixed
answer format ("Answer with a single word or short phrase."). Each configuration is run with three prompt
templates:

- **T1:** "Question: {q}\nAnswer:"
- **T2:** "{q} Answer with a single word or short phrase."
- **T3:** a chat turn with the question as the user message and no system prompt.

We report the mean over templates and the spread (minimum and maximum change across templates).

### 3.4 Checking that the attitude is steered

A null result for recall would be uninteresting if the vectors did nothing at all. We therefore also generate
free-form answers to 200 open questions ("Explain how vaccines work.") with and without steering, and ask a judge
model which of each pair is more careful, confident, expert or focused (by family), with the order randomised.

## 4 Results

### 4.1 The best configuration per family

**Table 1.** The best single configuration per family and model, chosen on the mean over templates (which favours
the vectors).

| family | model | best (layer, α, variant) | Δ EM (mean of templates) | spread across templates |
|---|---|---|---|---|
| careful vs careless | Llama-3.1-8B | (16, 0.05, single) | +0.9 | -0.4 to +2.1 |
| confident vs unsure | Llama-3.1-8B | (12, 0.05, multi) | +0.3 | -1.2 to +1.5 |
| expert vs novice | Llama-3.1-8B | (16, 0.02, single) | +0.6 | -0.3 to +1.4 |
| focused vs distracted | Llama-3.1-8B | (20, 0.05, question) | +0.2 | -0.9 to +1.0 |
| careful vs careless | Qwen3.5-9B | (20, 0.05, single) | +0.4 | -0.8 to +1.3 |
| confident vs unsure | Qwen3.5-9B | (16, 0.02, multi) | -0.1 | -1.1 to +0.7 |
| expert vs novice | Qwen3.5-9B | (20, 0.05, single) | +0.7 | -0.2 to +1.6 |
| focused vs distracted | Qwen3.5-9B | (24, 0.05, question) | +0.1 | -1.0 to +1.2 |

Run-to-run standard deviation of EM under greedy decoding with shuffled question order is 0.6 points. None of the
best configurations clears two standard deviations, and the best layer and coefficient differ by template.
Selecting the configuration on one template and testing on the other two gives a mean Δ EM of +0.1.

### 4.2 By dataset

**Table 2.** Δ EM of the best configuration per family, by dataset (Llama-3.1-8B, mean over templates).

| family | trivia | geography | medical |
|---|---|---|---|
| careful vs careless | +1.1 | +0.6 | +1.0 |
| confident vs unsure | +0.4 | -0.2 | +0.7 |
| expert vs novice | +0.3 | +0.4 | +1.1 |
| focused vs distracted | +0.2 | +0.5 | -0.1 |

The medical subset shows slightly larger gains for "expert", which might suggest a domain-specific effect. It does
not survive template selection: chosen on T1, the expert vector gives +0.2 on medical with T2 and T3.

### 4.3 Coefficient and layer

**Table 3.** Δ EM averaged over families, datasets and templates, by layer and coefficient (Llama-3.1-8B,
single-layer variant).

| layer \ α | 0.01 | 0.02 | 0.05 | 0.1 | 0.2 |
|---|---|---|---|---|---|
| 4 | 0.0 | +0.1 | -0.2 | -1.4 | -6.8 |
| 8 | +0.1 | 0.0 | +0.1 | -1.1 | -5.9 |
| 12 | 0.0 | +0.2 | +0.2 | -0.9 | -4.7 |
| 16 | +0.1 | +0.2 | +0.3 | -0.6 | -3.9 |
| 20 | 0.0 | +0.1 | +0.2 | -0.8 | -4.4 |
| 24 | -0.1 | 0.0 | 0.0 | -1.3 | -6.1 |
| 28 | 0.0 | -0.1 | -0.3 | -2.2 | -10.9 |

Across all families, EM is flat for $\alpha \le 0.05$ and falls for $\alpha \ge 0.1$, by 3-11 points at
$\alpha = 0.2$. The fall comes with a rise in malformed answers: at $\alpha = 0.2$, 9-23% of answers are not in the
requested format, against under 1% unsteered. There is no regime where recall improves before fluency degrades.
Qwen3.5-9B shows the same pattern, with the drop starting slightly earlier (at $\alpha = 0.1$, -1.6 on average).

The multi-layer variant spreads the same total push over three layers. It degrades fluency slightly less at
$\alpha = 0.2$ (-3.1 on average instead of -5.8) but never improves recall either.

### 4.4 Prompting

The corresponding prompts ("Answer carefully.", "You are an expert.", "Be confident.", "Focus.") prepended to the
question change EM by -0.5 to +1.2 points, also within noise. So the informal reports that motivated this work do
not replicate in our setting either, and there was no prompt-level effect for a vector to capture in the first
place.

### 4.5 Is the attitude actually steered?

Yes. The judge rates the steered free-form answers as more careful, confident, expert or focused, in the expected
direction, in 71-88% of pairwise comparisons at $\alpha = 0.05$ (Table 4). The effect grows with $\alpha$ until
fluency degrades. The vectors change *how* the model answers. They do not change *what* it retrieves.

**Table 4.** Judge preference for the steered answer on the family's attribute ($\alpha = 0.05$, best layer).

| family | Llama-3.1-8B | Qwen3.5-9B |
|---|---|---|
| careful vs careless | 0.84 | 0.79 |
| confident vs unsure | 0.88 | 0.81 |
| expert vs novice | 0.77 | 0.71 |
| focused vs distracted | 0.73 | 0.72 |

### 4.6 Error analysis

We looked at the 50 questions per model whose answer most often changes across configurations. In almost all of
them, steering switches between two candidate answers that the unsteered model already ranks first and second, and
the switch goes in both directions about equally often. We found no question where steering brings in an answer
that the unsteered model does not rank in its top 5. Steering reshuffles near-ties. It does not retrieve.

## 5 Discussion

Our reading is that retrieval in these models is carried by item-specific features, which a single direction
shared across items cannot reach. Behavioural attitudes are a different kind of variable: global, low-dimensional,
and easy to push. The judge results show the push lands. The recall results show it lands somewhere that does not
feed the retrieval of facts.

Two caveats limit how far this generalises. First, we measured recall in the output only. A generic vector could
in principle change what the model *represents* at intermediate layers without changing its answer, and we did not
look. Second, we stayed within the range of coefficients at which the model remains fluent. We do not rule out
that much larger pushes, at layers we did not try, change retrieval in some other way. We do not see a practical
use for such a regime, since fluency is already degraded at $\alpha = 0.2$.

For practitioners, the result is a warning about the plausible story that "attitude steering makes models better
at X". For attitudes and retrieval, it does not, and the small positive numbers that a single sweep produces are
noise that does not survive a change of template.

## 6 Limitations

Two mid-size models and closed-book QA only. Four contrast families, chosen because they correspond to common
prompting folklore. We did not try learned or optimised vectors, sparse feature steering, or contrasts outside the
four families. We measured recall in the output only, not in the model's intermediate states. Our coefficients are
relative to the residual norm at one layer, and our largest total push is 0.2 of that norm.

## References

- Arditi, A., Obeso, O., Syed, A., Paleka, D., Panickssery, N., Gurnee, W., and Nanda, N. Refusal in language
  models is mediated by a single direction. arXiv:2406.11717, 2024.
- Li, K., Patel, O., Viégas, F., Pfister, H., and Wattenberg, M. Inference-time intervention: eliciting truthful
  answers from a language model. arXiv:2306.03341, 2023.
- Liu, M. Decodable but not corrected by fixed residual-stream linear steering: evidence from medical LLM failure
  regimes. arXiv:2605.05715, 2026.
- Panickssery, N., Gabrieli, N., Schulz, J., Tong, M., Hubinger, E., and Turner, A. M. Steering Llama 2 via
  contrastive activation addition. arXiv:2312.06681, 2024.
- Todd, E., Li, M. L., Sen Sharma, A., Mueller, A., Wallace, B. C., and Bau, D. Function vectors in large language
  models. arXiv:2310.15213, 2024.
- Turner, A. M., Thiergart, L., Leech, G., Udell, D., Vazquez, J. J., Mini, U., and MacDiarmid, M. Steering
  language models with activation engineering. arXiv:2308.10248, 2023.
- Zou, A., Phan, L., Chen, S., Campbell, J., Guo, P., Ren, R., Pan, A., Yin, X., Mazeika, M., Dombrowski, A.-K.,
  et al. Representation engineering: a top-down approach to AI transparency. arXiv:2310.01405, 2023.

## Appendix A: Contrastive pairs (first 12 per family)

Each pair shares the task; only the attitude word or phrase differs. The full 64 per family are in our release.

**Careful vs careless.**
1. Carefully / Carelessly summarise the following note.
2. Carefully / Carelessly rewrite this sentence in plain English.
3. Carefully / Carelessly list three ideas for a birthday present.
4. Carefully / Carelessly classify this review as positive or negative.
5. Carefully / Carelessly translate this phrase into French.
6. Carefully / Carelessly sort these words alphabetically.
7. Carefully / Carelessly write a title for this paragraph.
8. Carefully / Carelessly explain this error message.
9. Carefully / Carelessly fill in the missing word.
10. Carefully / Carelessly draft a reply to this email.
11. Carefully / Carelessly count the items in this list.
12. Carefully / Carelessly pick the odd one out.

**Confident vs unsure.**
1. Confidently / Unsurely summarise the following note.
2. Confidently / Unsurely suggest a name for a cat.
3. Confidently / Unsurely list three uses for a paperclip.
4. Confidently / Unsurely say which of these two titles is better.
5. Confidently / Unsurely rewrite this sentence to be shorter.
6. Confidently / Unsurely suggest a colour for this room.
7. Confidently / Unsurely classify this review.
8. Confidently / Unsurely describe this picture in one line.
9. Confidently / Unsurely choose a meeting time from these options.
10. Confidently / Unsurely give a one-word summary of this story.
11. Confidently / Unsurely recommend a book genre for a teenager.
12. Confidently / Unsurely explain what this sign means.

**Expert vs novice.**
1. As an expert / a novice editor, rewrite this sentence.
2. As an expert / a novice chef, suggest a side dish.
3. As an expert / a novice gardener, describe when to water these plants.
4. As an expert / a novice teacher, explain this word to a child.
5. As an expert / a novice reviewer, rate this paragraph.
6. As an expert / a novice planner, order these tasks.
7. As an expert / a novice designer, pick a font for this poster.
8. As an expert / a novice writer, suggest a title.
9. As an expert / a novice coach, give one tip for running.
10. As an expert / a novice organiser, group these items.
11. As an expert / a novice translator, translate this greeting.
12. As an expert / a novice analyst, summarise this table.

**Focused vs distracted.**
1. Stay fully focused and / While distracted, classify this review.
2. Stay fully focused and / While distracted, summarise the following note.
3. Stay fully focused and / While distracted, rewrite this sentence.
4. Stay fully focused and / While distracted, list three ideas.
5. Stay fully focused and / While distracted, sort these numbers.
6. Stay fully focused and / While distracted, answer this riddle.
7. Stay fully focused and / While distracted, write a short caption.
8. Stay fully focused and / While distracted, name the main character.
9. Stay fully focused and / While distracted, pick the correct spelling.
10. Stay fully focused and / While distracted, check this sum.
11. Stay fully focused and / While distracted, find the verb.
12. Stay fully focused and / While distracted, choose the best option.

## Appendix B: Sweep grid and compute

- Families: 4. Models: 2. Layers: 4, 8, ..., 28. Coefficients: 0.01, 0.02, 0.05, 0.1, 0.2. Variants: single-layer,
  multi-layer (three adjacent layers, α/3 each), question-only. Templates: 3. Datasets: 3 × 1,000 questions.
- Total: 840 configurations × 9,000 generations ≈ 7.6M short generations, about 300 GPU-hours on A100s.
- Steering is implemented as a forward hook on the residual stream after the block, in the model's dtype.
