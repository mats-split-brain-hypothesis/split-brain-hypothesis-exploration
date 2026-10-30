# Instance A (night-2): priors from the lens

Cards: **S15** (J's own geometry: diagnostic + centre), **S13** (pulled-back continuation prior), **S14** (readout-aware
template subspace). They share `src/jlm/pullback.py` and its caches, and each one's result reshapes the next. Read the
three cards and mu-log's "Round-2 infrastructure".

What exists (on the Mac, `out/lens/`, `out/priors/`): the eigendecompositions, J SVDs and template bases (k = 16 / 64
/ 128) at all 12 layers, cos and rms; the unigram prior pullbacks (no_robots chat, wikitext; full rank and r256).
Not yet: the per-cell next-token pullbacks (`s13nt`, `s13ntf`) and the chat-format corpus (`out/ctx/corpus-chat.pt`):
the steward runs `experiments/jobs/round2_precompute.sh` on a capture pod at the start of the night (about an hour),
so start with what needs neither.

Suggested start (change it if the evidence says so):
1. S15 diagnostic (`experiments/s15_spectrum.py`, cached SVDs only): fam / tok / h shares in J's top-k subspaces vs
   random. It tells S13 / S14 which part of the spectrum matters, so write it up before the centres.
2. S13a (`s13uni`, `s13wiki`) and S14 (`s14t*`, `s14fam*` with `s14r*` / `s14famr*`) on fit, strict, all 11 families,
   beta and rank / k chosen on fit only.
3. S13b (`s13nt`, `s13ntf`) once the steward reports the next-token pullbacks on the volume.

Second wave, if your insights do not point elsewhere: the pullback of fam's own readout (is fam's gain just the token
bias `L(mu_fam)`? if so a pulled-back L(mu_fam) matches fam and the bias, not the vector, is what matters); S13 and S14
stacked (prior removed, then template subspace); S13c (template-slot cells of the chat corpus); a per-layer beta;
S14 with T from the chat corpus's most frequent tokens only (no bench-derived tokens at all).

Judge allowance: about $10 (val confirmations of survivors; the _mt families and DM); the judge is a secondary score (preamble).
