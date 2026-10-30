# A concept-agnostic "holding-in-mind" steering vector for the plain J-lens

The intervention adds one fixed unit vector to the residual stream at layers 20-24, at every
prompt position through the read cell (dose 4.6, tuned on `fit`). The vector is a contrast between
two prompt conditions I wrote myself: "hold a named concept in mind while you copy this sentence"
versus "put that same concept out of mind while you copy it". Each condition is captured at the
copied sentence's cells; `d_l = mean(hold) - mean(release)` is normalised per layer. Nothing in the
construction touches the association targets or any bench bank.

What is new here is not add-a-vector steering itself but three findings about *what kind* of
direction lifts implied concepts on this server. I built and scored nine alternative contrasts -
name-vs-continue, understand-vs-skim, a one-word-summary function vector, secrecy,
prospective-memory, meaning-vs-spelling, content-vs-boundary, and a linguistic
concurrency-vs-sequence contrast. Every alternative did nothing or hurt. Only the
holding-a-discrete-concept stance moves implied targets, taking strict pass@10 at layers 26-30 from
0.13 to 0.79. The position decomposition is sharp: full-prefix injection (0.79) far exceeds
read-cell-only (0.42) or context-only (0.13). So the gain is a stance effect propagated by the
layers above the band, not a readback of the added vector, and it is specific to keeping a
discrete concept active alongside routine generation.