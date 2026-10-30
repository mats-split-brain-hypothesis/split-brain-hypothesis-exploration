# Contribution: cloze continuation-contrast steering

The plain J-lens reads `J_l h` at the final token of each association scene. At layers 26/28/30 on
Qwen3.5-4B that final token is a *free-continuation* state: the sentence is complete, so the residual
is dominated by the model's generic continuation prior (This, The, line-break), which buries the
scene's implied concept out of the top-10. Centring the readout (`J_l(h - mu)`) removes that prior and
reveals the concept, but centring is out of scope here — only the forward pass may change, via a
contrast direction.

The steering vector is a contrast between two conditions I wrote (no bank items, no targets): the
same 28 sentences, once left incomplete right before a forced concrete noun (`...rode out across the`
-> "plain"), once completed with that noun and a period. Captured through the metric server's
`capture` endpoint at each sentence's final token, the difference
`mean(incomplete) - mean(complete)` is the *forced-completion minus free-continuation* direction: the
residual state that says "a specific content word is due" minus the state that says "continue
freely." It is a direction from a two-condition contrast, not a subtracted mean.

Added at the read position, layer 26, scale 8, it shifts the scene's free-continuation residual
toward the forced-completion regime, suppressing the continuation prior that occupies the top-10 so
the implied concept surfaces. On `fit`, strict pass@10 rises from 0.1275 (baseline) to 0.1765; the
effect peaks at layer 26 and saturates across scales 7-12, so the scale is not a fragile optimum.
The method is generic (one vector, every item, built without the targets) and a new contribution,
not a reproduction.
