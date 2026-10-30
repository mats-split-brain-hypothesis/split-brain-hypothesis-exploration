# White-bear direction, 4B (metric server, association fit)

Stance contrast, not content: think about X vs don't think about X while copying the same sentence.

**Direction.** The 35 `directed_modulation` pair items (bench), via `capture` with `bench_items` (their own read cells:
the carrier sentence in the assistant turn), `per_prompt`. Per layer: d_l = mean(think) - mean(dont_think) over the
per-prompt means, u_l = d_l / ||d_l||. Concept and carrier are matched within each pair, so they cancel.

**Steer.** L20-24, `prefix`, v_l = k * s_l * u_l with s_l = 0.13 ||d_l||:

| L | 20 | 21 | 22 | 23 | 24 |
|---|---|---|---|---|---|
| s_l | 0.606 | 0.634 | 0.654 | 0.723 | 0.787 |

Total push at k = 6 ~ 20.4.

**Dose** (fit pass@10, baseline 0.1275 / mean log10 rank 2.330):

| k | 0.5 | 1 | 2 | 3 | 4 | 5 | **6** | 7 | 8 | 12 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pass@10 | 0.118 | 0.137 | 0.157 | 0.176 | 0.275 | 0.451 | **0.794** | 0.549 | 0.441 | 0.020 | 0.000 |
| log10 rank | 2.31 | 2.30 | 1.99 | 1.69 | 1.38 | 1.06 | **0.72** | 0.90 | 1.09 | 2.07 | 3.50 |

Sharp peak at 6. Below 2 nothing, past 8 it breaks the readout.

**Controls at k = 6.** `read` only 0.451 (lr 1.06, ~80% of the log-rank gain); `context` only 0.137 (2.07); random
direction, same steps 0.137 (2.30); reversed (k = -1) 0.118 (2.39). L22 alone at its own step: nothing; the band's
whole push on L22 alone: same as the band.

**Examples at k = 6** (best rank, baseline -> steered): crater 10 -> 2, airport 28 -> 3, tragedy 42 -> 3, flood 71 -> 4.
Top-10s keep the generic continuation tokens; the target joins them.

Other bands (k = 4, s_l = 0.13 ||d_l||), Δ log10 rank: L2-6 -0.01, L8-12 +0.02, L14-18 -0.14, L26-30 +0.03.

TODO: val; write up.
