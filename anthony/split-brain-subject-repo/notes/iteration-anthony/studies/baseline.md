# baseline: the reference arms and the standard controls (2026-10-11)

Owner j-lens-mean-f3. Every bank (11 families x fit / val / bench) re-evaluated on the pod with the reference arms
(`zero`, `fam@fit`, `tok@fit`, both readouts) and the controls `rand.fam@fit|cos`, `rand.tok@fit|cos` (random direction
with ||g||) and `shuf.tok@fit|cos` (another cell's g), plus echo, prompt-masked pass and the model's next-token top 10.
Battery: `out/analysis/baseline-val/summary.md`, `out/analysis/baseline-fit/summary.md` (with `--decode-g`). Strict /
piece proxy, ours, not WorkspaceBench scores. Numbers below are val.

## Insights

1. **Centring's gains are content, not a norm effect (S1).** A random direction with the centre's norm is close to
   no centring: macro +0.02 (rand.fam) / +0.03 (rand.tok) vs zero, against +0.08 / +0.10 for fam / tok. On typo and
   association it loses everything centring gained (-0.20, -0.34 vs fam). -> S1 done; the random control stays in
   every study.
2. **Token matching is what helps DM and UM, not "some token mean".** Shuffled tok (each cell gets another cell's
   token mean) keeps +0.05 of tok's +0.24 on DM and +0.02 of +0.07 on UM. On the template families tok falls back to
   the family mean, so shuffling changes nothing there (shuf = fam). -> position / token matching (U1) is where the
   cell-specific signal is; the controls separate it cleanly.
3. **The family mean removes something multihop needs.** multihop_mt: a random g beats fam by +0.18 (paired interval
   above 0), and fam loses -0.10 vs zero; multihop: fam -0.01, fam|rms -0.06. A random g of the same norm does not
   hurt, so the harm is the mean's direction, not its size. -> S6 (multihop case study): decode what fam removes at the
   layers where the bridge / answer appear (`g_decoded` in `out/analysis/baseline-val/multihop*-val.json`).
4. **multilingual_mt is the guardrail family to watch.** tok and both rms arms lose 0.11-0.23 against fam there;
   fam|cos is the best arm (+0.21 vs zero). Any token-keyed g needs to be checked on it.
5. **The targets are mostly unsaid.** The model's own next-token top 10 names the target for 0.08 of association
   items (val), and next-token overlap of the centred readouts is about 0.01: the lens is not reading the next token.
6. **Echo is low everywhere so far** (0.01-0.09 of the top 10), and prompt masking changes no strict pass on the
   template families (as it must: leaky items are not scored). The masked rows matter for judged runs.

## Context path (infrastructure smoke test)

`prev4` (g = mean of the item's own 4 previous positions; `jlm.mu.infra_smoke`) runs end to end from the context
captures. As a centre it is poor: multihop 0.11 vs 0.61 for its shuffled control, user_modeling 0.64 vs 0.74. The
item's own recent states carry its content, so subtracting them removes what we want to read. Data point for S3, not
an S3 result.

## Cost

Pod (A100 80 GB, 1.9 h including the context capture and two restarts): $3.37.
