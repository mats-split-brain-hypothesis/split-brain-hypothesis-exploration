# Readers on the five tc captures: plan (drafted 2026-10-23, for Anthony)

Question (Q8, credit planned then lost; pilots/credit-lost.md): at the write, when the name is left out, is the source
still represented in the model, and what else is (the judge, novelty, hiding)? It tells apart the hypotheses there:
**reflex** (the source is not active at the write: the write-up mode does not reach it), **reward override** (the
source is active, plus judge / score content, and the name is suppressed), **decay / trimming** (active at the plan,
fading by the write), **other meaning of "honest"** (the plan's honesty content is about method, not credit).

The three runs that differ in outcome share the same situation: **credited** (p04-r2-A0, names Raman at "(R" with
p 0.875), **lost** (p03-beval-1 across replies; p05-c1-A0 in one reply), **deliberate** (p04-s0-A0-1, decides not to
cite). Trimming (p03-bnote-eval-1) is the fourth case.

## What the meta programme already found (j-lens-mean meta/notes/plan.md, umot research log)

The oracle lens and the NLA largely describe the text and the continuation prior: on umot's hidden-motivation items
oracle lens 0.14, NLA 0.13, the **same-token-centred J-lens 0.97** (black box 0.83); hallucination rate NLA 0.96,
oracle lens 0.34. So the J-lens, centred, is the main instrument; the oracle lens and NLA run on a short list with
controls, and their claims count only where the text in front of them does not already say it.

## Phases

**R0. Do readers built on Qwen3.6-27B read Qwen3.8-27B?** (local + the R3 pod)
- J-lens at L56 / L60 on 3.8's states vs 3.8's own next-token prediction (stored top-20): top-1 / top-10 agreement
  per layer, against the same statistic on 3.6 (one 3.6 pass on one sequence, on the R3 pod).
- Oracle lens / NLA: the injection check (zero / shuffled vectors change the logits, readers.py `injection_check`),
  and a content control: ~50 positions where the subject's own text is plainly about X (golf, a layer number, a file
  name) read from 3.8 and from 3.6 on the same text.
- If 3.8 reads badly: run 3.6-27B over the same five sequences (2-3 min each) and read those states instead,
  reported as "the 3.6 model reading the subject's text", not the subject's own states.

**R1. J-lens sweep, every subject token** (local, RTX 5070 Ti; no pod)
- Plain and same-token-centred J-lens (centre = the mean state of the same token id at that layer over the other
  four runs, so a run's own content is not subtracted away), at the 12 stored layers; top-10 tokens per (position,
  layer). ~4.9M readouts, est. 20-40 min. Stored as readers/jlens.npz per target.
- Weights: neuronpedia/jacobian-lens qwen3.6-27b maps (12 layers) + 3.6's unembedding, downloaded to the desktop
  (~3-4 GB; public).

**R2. Concept tracks and the omission sites** (local)
- Concept sets (tokens, written down before looking): source (Raman, Priya, white, bear, WBS, paper, prior,
  cite), judge (judge, novelty, score, grader, evaluation), hiding (hide, omit, mention, disclose, honest), own
  (new, novel, our, contribution). Per position and layer: the set's best rank / score under the centred J-lens.
  This is the page's strip ("is the source alive here?").
- The omission sites: in each write, the tokens where the source is or could be named (the credited run's "(" before
  "R"; in the others, the start of the "where it came from" / origin sentence, the method-name tokens, the sentence
  that describes the recipe). Picked by hand from the write text and listed in readers/sites.json before reading.
  At these the windows hold all 64 layers: exact log-probs of the candidate names from 3.8's own unembedding
  (needs 3.8's lm_head + final norm, ~2.5 GB) and the J-lens at every layer.

**R3. Oracle lens and NLA on a short list** (one pod, RTX PRO 6000)
- Positions: the omission sites (~20-60 tokens per write), the plan sentences' last tokens (~5 per plan block), the
  safety-net and trim moments, and 100 random subject positions per run as the baseline: ~300 per run, ~1,500 in all.
- Oracle lens at L32 / L44 / L56 (its grid), k = 1 (k = 3 at the omission sites); NLA at L42, k = 1 (k = 3 there).
  ~6-7k readouts. Throughput not measured here: est. 2-4 readouts/s batched, so ~30-60 min of generation.
- Control the meta work says is needed: the same positions' text alone (the 64 tokens before) given to the base
  model as "what is the writer thinking about": a reader's claim counts only if it is not in that text-only answer.
- Pod: download oracle lens (27B) and Qwen3.6-27B base + NLA adapters (~110 GB), upload the needed states only
  (~1.5k positions x 13 layers, ~0.2 GB), no network volume. Est. 1.5-2.5 h at $2.49/h = **$4-7**; plus R0's 3.6 pass.

**R4. Dashboard**: the inspector shows J-lens top tokens per layer (plain / centred) for the clicked token, oracle /
NLA text where read; a concept-track strip under the surprise strip (choose a set); the omission sites as their own
moment buttons. J-lens rows come from the plugin per reply (too big for view.json); oracle / NLA go into view.json
`readers`.

**R5. Read and report** against the predictions below, in pilots/credit-lost.md; PLAN.md decision log.

## Predictions (to register before R2 / R3 are read)

- Reflex: at the lost writes' omission sites the source set is no more active (centred J-lens) than in the random
  baseline, and no more than at the deliberate run's write; the judge set no higher than baseline.
- Reward override: the source set is active at the lost writes (like the credited run's, above baseline), the judge /
  hiding sets above baseline, and the candidate name has a non-trivial log-prob there (the name was "available").
- Decay: the source set is high at the plan, lower at the write, monotone between; trimming run: high until the trim.
- Deliberate (s0-A0-1) as a reference: source and hiding sets high at the write.

## Decisions for Anthony

1. R3's pod (~$4-7) and R0's 3.6 pass (~$1): go?
2. The text-only control in R3 (cheap, on the same pod): keep?
3. The concept sets and the omission sites: draft them and show you before reading anything (proposed), or let me
   fix them myself and register in PLAN.md?

## Done 2026-10-23 (pod sb-whitebox #2, RTX PRO 6000; ledger $2.65; nothing interpreted yet: Anthony analyses on /whitebox)

- **R0**: the 3.6 J-lens's top-1 = the model's own top-1, on 3.8's states / on 3.6's own: L60 0.446 / 0.468 (0.95),
  L56 0.233 / 0.275 (0.85), L52 0.097 / 0.142 (0.68), L48 0.77, mid layers ~0.8-1.1 of a tiny base. The two models'
  own top-1 agree 0.80-0.82. `r0_report.py` -> whitebox-captures/r0.json. Oracle lens / NLA on 3.6's states at 50
  r0 positions per run sit beside the 3.8 readouts (readers `*-3.6states`), for the content comparison.
- **R1**: plain + same-token-centred J-lens, top-10 at 12 layers for all 408k subject tokens (fallback to the layer
  mean at 5-8% of positions); `jlens_view.py` -> per-reply lines for the inspector.
- **R2**: concept tracks (SETS.md) on the desktop CPU, `concepts.py`, z-scored on the page against each run's tokens.
- **R3**: oracle lens L32 / L44 / L56 and NLA L42 at 1,144 positions per reader-layer (894 sites / plans / random
  + 250 r0 controls), 3 samples at the 214 site tokens; text-only control 1 sample everywhere (1,144). Injection
  checks (largest logit change, random vs zero vector): olens 13.2 / 14.0 / 13.7, NLA 14.8. 6,720 lines in
  whitebox-captures/meta.jsonl (10 duplicates from a restart's overlap; the page keeps the last).
- Throughput: oracle lens / NLA 4.5 positions/s at 128 sequences per generate call (0.75 at 48); OOM at 128 x 3.
