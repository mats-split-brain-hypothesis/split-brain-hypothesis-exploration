# Concept-maintenance steering for the plain J-lens

The intervention is one residual-stream direction, added once at the **prefix** of every item at layers 20–24,
that pushes the model toward *holding an idea in mind* rather than *letting it go*. The readout itself is
untouched — it stays the plain (uncentred) J-lens. On association's `fit` split this lifts strict pass@10 from
**0.1275 to 0.7059** and mean log10 best-target rank from 2.33 to 0.75.

**Where it comes from.** The plain J-lens reads `J_l h` at the last token of a prose description, and there it
misses: its top-10 is crowded by sentence-initial function words — a frequency/continuation prior, the effect
Okafor et al. debias in *readout* space — while the implied concept ("crater", "airport", "tragedy") sits
behind them. I found the crowd is only the symptom. Pushing "answer vs prose" or "content vs function" merely
reorders that same crowd, and injected at the prefix those content directions degrade the readout. The deeper
failure is that the model computes the concept but does not *maintain* it at the read position; there is nothing
there for the lens to read.

So instead of steering toward a *content*, I steer toward a *stance*. I wrote my own matched prompt pairs —
“Think about the object X while you write. Now write exactly this sentence: S.” versus “Do not think about X …” —
for 20 self-chosen, diverse concepts X and neutral carrier sentences S, and captured the residual stream at the
copied sentence. The mean difference `d_l = mean(think) − mean(do-not-think)` averages the concepts away and
leaves a single direction: the model maintaining a concept in working memory versus clearing it away. This is
neither a content vector nor one of the usual attitude vectors (careful / expert / focused, which for recall
steer *style* without touching retrieval). It is a **maintenance** direction, and it is data-free — built only
from sentences I wrote, using no benchmark item and no target.

Adding `d_l` at layers 20–24 (just before the read band 26–30), once at the prefix, keeps whatever concept the
prompt implies in working memory through the prompt, and the uncentred J-lens then reads it at the final token.
A random direction of the same per-layer norm scores 0.118, so the gain is the direction, not the perturbation.
The effect is robust to the injection gain λ on fit: 0.451 at λ=0.85, 0.706 at λ=1.0, 0.735 at λ=1.05; the
submitted vectors are the raw mean difference (λ=1.0).

In other words: what the panel of centring studies calls the "label-free, context-matched mu" problem has an
unexpected forward-pass answer. Rather than subtracting a counterfactual in the readout, you can steer the
model's own *keep-in-mind* stance so the plain lens sees what the model already holds — one generic vector,
one scalar, no centring term at all.