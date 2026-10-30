# Pre-registered predictions (top-level jlm experiments)

Continues the convention of `jle/notes/predictions.md` (kept light, per `notes/eval-pipeline.md`):
every prediction is written here with a timestamp BEFORE the confirmation run; never edited after
seeing results; outcomes are appended underneath. Experiment ids are `x1`, `x2`, ... (top-level
series, distinct from jle's x89+).

---

## x1-mu-pos-concept — REGISTERED 2026-10-10 15:45 BST (typo, 27B, strict free tier: the README's two
untried mu rungs — a position-conditioned corpus mean, and the abstract-word / steering mu)

Instrument. The jlm pipeline on this box (3x A100; captures, reads and scores all local, dirty tree —
hashes instead of a SHA: centres.py dca1004d3d034e60, capture_mu_refs.py ea74f2b96786098b,
x1_arms.sh badfe51a37959add, evaluate.py abd34e2376ad9758; tests 11 pass). Banks: `data/dev/typo`
fit (94) / val (93); strict rule and confirmatory subset as in jle x89 (fit scored n=92, 2 leaks).
New centres: `pos@corpus` = mean at the same absolute position over 256 wikitext-103-VALIDATION
paragraph starts (x101's corpus, pin and detok; positions 0..63, every position; >= 8 cells else the
corpus mean); `fam@corpus8` / `tok@corpus8` = corpus / same-token mean from position 8 (x101's
MIN_POS); `fam@sents` = mean at the final token of 256 standalone wikitext sentences;
`cpt[c]:<word>:<alpha>@fit` = alpha x (fit-ref mean state norm) x unit carrier direction of <word>
(5 neutral carrier phrases, read at the word's last token; `c` subtracts the neutral words'
giraffe/violin/glacier carrier mean). Qwen3.6 is RoPE (+ gated-delta linear-attention blocks): there
is no additive positional embedding to subtract; pos@corpus is the subtractable analogue.
Val arms of record: zero, fam@fit, fam@corpus8, tok@corpus8, pos@corpus, fam@sents, cpt:typo:{0.5,1}@fit,
cpt:misspelling:1@fit, cptc:typo:1@fit, and controls cpt:giraffe:{0.5,1}@fit, cptc:giraffe:1@fit; cos and rms.
KNOWN at registration: the full fit table (out/eval/typo/fit/summary.md, read before this entry):
zero 0.685/0.511 (cos/rms), fam@self 0.891/0.891; every corpus/positional rung within -0.09..+0.07
of zero; cpt:typo:1 beats cpt:giraffe:1 by +0.106 cos [+0.021,+0.202] / +0.096 rms [0.000,+0.191];
alpha=2 harms; contrast-only arms null-to-harmful. The user's val parity numbers (eval-pipeline.md):
zero 0.69/0.57, fam@fit 0.92/0.90.

Predictions (strict pass rates on typo/val, n~91 scored; paired = item bootstrap B=10k seed 0):
P1 (anchor): fam@fit - zero >= +0.15 under both readouts, outside the paired interval.
P2 (positional/corpus rungs are null on typo): each of fam@corpus8, tok@corpus8, pos@corpus,
   fam@sents is within +/-0.10 of zero (point) under both readouts, and none reaches half of
   fam@fit's paired rms gain.
P3 (generic carrier component exists): cpt:giraffe:1@fit|rms - zero|rms >= +0.05 (point).
P4 (HEADLINE, concept-specific component survives held out): cpt:typo:1@fit - cpt:giraffe:1@fit
   >= +0.05 (point) under BOTH readouts; whether the paired interval excludes 0 at n~91 is
   reported, not predicted.
P5 (not word-identity luck): cpt:misspelling:1@fit - cpt:giraffe:1@fit >= +0.05 (point) under cos.
P6 (no new winner): no corpus or concept arm beats fam@fit under either readout (point).
NULL: P4 point < +0.02 under both readouts — the abstract-word mu has no concept-specific value
on typo beyond generic norm centring.

AMENDED 2026-10-10 15:45 BST, before any val number was read: the registered x1_arms.sh hash was
taken before its val arm list was filled in; the list as run (hash f8aefeccfa29b4ca) is exactly
the registered arms of record plus `fam@self` (descriptive only, jle's loo1 on val).

### x1 OUTCOME — 2026-10-10 15:47 BST (out/eval/typo/val/summary.md, n scored 91 of 93; parity with the
user's pipeline numbers is exact: zero 0.692/0.571, fam@fit 0.923/0.901 vs the status note's 0.69/0.57, 0.92/0.90)

P1 PASS: fam@fit - zero = +0.231 cos [+0.143,+0.330], +0.330 rms [+0.241,+0.429].
P2 PASS: every corpus/positional rung is FLAT TO NEGATIVE held out — fam@corpus8 -0.022/-0.066,
  tok@corpus8 -0.022/-0.055, pos@corpus -0.011/-0.055, fam@sents -0.044/0.000 (cos/rms vs zero);
  none approaches half of fam's rms gain.
P3 PASS: cpt:giraffe:1|rms - zero|rms = +0.077 [+0.000,+0.165] (the generic any-word component).
P4 PARTIAL: cpt:typo:1 - cpt:giraffe:1 = +0.194 cos [+0.097,+0.291] — outside the bootstrap, the
  headline held under the bench's readout (and at alpha 0.5: +0.097 [+0.032,+0.161]) — but
  +0.043 rms [-0.054,+0.140], point below the registered +0.05.
P5 PASS: cpt:misspelling:1 - cpt:giraffe:1 = +0.086 cos (interval [-0.022,+0.194] includes 0).
P6 PASS: nothing beats fam@fit (next best cpt:typo:0.5|cos 0.802 vs 0.923); fam@fit - cpt:typo:1 =
  +0.140 cos / +0.215 rms, outside the bootstrap.
NULL rejected under cos.

### x1 BENCH READ — registered 2026-10-10 15:51 BST, before any bench number was read (user request:
standard J-lens vs the abstract-word mu on the bench bank itself). The bench's typo bank, captured
locally (same pipeline), arms exactly the x1 registered concept arms `cpt:typo:{0.5,1}@fit` with
anchors `zero`, `fam@fit` (already bench-read by the pipeline's parity run) and the control
`cpt:giraffe:1@fit`. Prediction: cpt:typo gains over zero land within +-0.05 of their val deltas
(cos +0.09..+0.11 at alpha 0.5; rms +0.08..+0.12 at alpha 1), and the typo - giraffe paired diff
stays positive under cos.

BENCH OUTCOME — 2026-10-10 15:55 BST (out/eval/typo/bench/summary.md, n=100, parity exact with x100:
zero 0.540/0.320, fam@fit 0.760/0.820). cpt:typo:0.5 = 0.670/0.460, cpt:typo:1 = 0.660/0.520;
vs zero +0.130 cos [+0.060,+0.210] (alpha 0.5) and +0.200 rms [+0.110,+0.290] (alpha 1), both outside
the bootstrap. Prediction: cos PASS (window +0.04..+0.16); rms OVERSHOT (+0.200 > +0.17 window);
typo - giraffe under cos +0.150 [+0.060,+0.240] PASS. Dissociation sharper than val: under cos the
gain is all concept (giraffe -0.030), under rms all generic (giraffe +0.220, typo - giraffe -0.020).
The abstract word recovers ~half of fam's cos gain from one bit of label information.

Reading. (a) On typo, position is not what the family mean removes: a position-matched neutral-corpus
mu does nothing (cos even dips), so RoPE position structure at read positions 5-11 is not the
pollutant. (b) The abstract-word mu is real but partial under cos: the word's identity carries
+0.10..+0.19 over a matched unrelated word, zero -> 0.78-0.80 of fam's 0.92; under rms most of the
concept arm's gain is the generic norm effect any word buys. (c) alpha matters (2 harms, 0.5-1 best);
the contrast-only direction without the carrier mean is null-to-harmful. (d) The open candidate from
x1: the family mean's advantage is family CONTENT at the read cell beyond category semantics —
item-level structure (orthographic / correction-shaped), not template position or token identity.

---

## x2-dict-mu — REGISTERED 2026-10-10 16:11 BST (six single-token families on the bench, 27B, strict
free tier: per-SAMPLE abstract-word mu from a global dictionary, the user's design — go through every
family's data, define a global-workspace category set, use the fittest word per sample)

Instrument. Dictionary and maps: `data/abstract_concepts.json` 71b5524c7f2c12f3 (30 words + 3
neutral; family words; stratum words from bank metadata `subfamily` / `attr_class`; a fixed
derangement map as the wrong-word control). `src/jlm/centres.py` 605956d65623d0c5 (DictCentre modes
fam / strat / llm / free / derang; mu = alpha x ref mean-norm x unit carrier direction, the x1
construction, word chosen per cell), `src/jlm/concepts.py` 92459b228aad661e,
`experiments/label_concepts.py` 615bdefef7ab3d4d (the judge is the PINNED 27B itself, greedy,
thinking off; it sees the item's text + the dictionary, never targets or the family name; labels in
out/concept-labels, provenance beside them). Carriers: carriers-dict.pt (33 words x 5 templates).
Families and banks: typo, association, basic_readout, multihop, multilingual, user_modeling — the
x89 confirmatory six — bench banks captured locally (out/captures/<fam>-bench.pt). Strict rule and
scorer as x1. Arms per family, cos and rms: zero, fam@self (loo anchor), dict:fam:{0.5,1}@self,
dict:strat:1@self, dict:llm:{0.5,1}@self, dict:free:1@self (geometric selection, descriptive),
dict:derang:{0.5,1}@self. Pooled = every scored item once over the six families, paired item
bootstrap B=10k seed 0 (post-hoc snippet over the stored readouts).
KNOWN at registration: all of x1 and its bench read; x89/x100 anchors; the label distributions
(typo 85-86 % "typo"; user_modeling only 35 % attribute words, 58 % "answer"; basic_readout 14
unmatched "?" falling back to the family word); geometric selection quality on typo fit (22-36 %);
typo fit dev numbers: dict:fam:1 0.739/0.717, dict:llm:1 0.717/0.696, dict:free:1 0.630/0.565,
dict:derang:1 0.707/0.663 (cos/rms).

Predictions:
P1 (HEADLINE, pooled concept specificity): dict:llm:1 - dict:derang:1 > 0 under cos, paired
   interval excluding 0.
P2 (per-sample words help where the latent type varies): dict:llm:1 >= dict:fam:1 (point) under cos
   on multihop and multilingual, and within 0.03 of dict:fam:1 on typo.
P3 (metadata beats prompt-judged labels where the judge was weak): dict:strat:1 > dict:llm:1 (point)
   under cos on user_modeling.
P4 (generic rms component): pooled dict:derang:1|rms - zero|rms >= +0.05.
P5 (ceiling): fam@self beats every dict arm pooled under both readouts, outside the bootstrap.
P6 (no harm): pooled dict:llm:{0.5,1}|cos - zero|cos >= 0 (point).
NULL: P1's interval includes 0 — per-sample abstract words add nothing beyond a wrong constant
vector of the same construction.

### x2 OUTCOME — 2026-10-10 16:18 BST (out/eval/x2-pooled.md; n scored: typo 100, association 78,
basic_readout 67, multihop 91, multilingual 100, user_modeling 36; pooled n = 472)

THE NULL HOLDS pooled. P1 FAIL: dict:llm:1 - dict:derang:1 |cos = +0.000 [-0.032, +0.032].
P2 FAIL: multihop +0.011 (point passes), but multilingual -0.050 [-0.100,-0.010] and typo -0.060
[-0.110,-0.020] (llm labels are noisier than the family word). P3 FAIL, the most instructive number
of the run: user_modeling dict:strat (attr_class words: country, occupation, ...) COLLAPSES the
family, 0.19 vs llm 0.47 under cos (-0.278 [-0.417,-0.139]) — subtracting the attribute's hypernym
direction deletes the attribute's value from the readout (the target "paraguay" lies along
"country"). P4 FAIL: the generic rms component pools to +0.006 — it was a typo artefact (zero|rms
is only pathological on typo). P5 PASS: fam@self beats every dict arm pooled, +0.155/+0.214
(cos/rms). P6 FAIL: dict:llm:1 pooled cos -0.076 (harms); 0.5 -0.017 (~0).

Reading. The x1 typo gain does NOT generalise, and the per-family pattern says why. Word-matched
minus derangement at alpha 1 under cos: typo +0.20, association 0.00, basic_readout 0.00,
multilingual +0.01, user_modeling +0.02, multihop -0.11 (the wrong word helps multihop more than
"fact"). The dictionary mixed two kinds of abstract word: FRAME words, naming what kind of
situation the read context is ("typo" — the correction "February" is not itself a typo), and
CONTENT HYPERNYMS, naming the answer's own category ("country", "place", "month" — the target IS
one). Subtracting a frame direction can clean the readout (typo, the one family where x1 worked);
subtracting a content hypernym removes the very subspace the answer lives in (user_modeling strat
is the limit case). High-baseline families (zero|cos 0.82-0.94) have little to gain and much to
lose from any constant alpha=1 vector. Next rung, if pursued: frame words only, alpha <= 0.5,
never hypernyms of the target class — or concede that beyond typo-like families the abstract-word
mu is not a path to the family mean's gain, whose content is item-level, not categorical.


---

## x3-dict-mu-heldout — REGISTERED 2026-10-10 16:25 BST (the x2 comparison done properly held out:
J-lens with and without the category mean, on the six families' dev VAL splits, centres and norms
fitted on FIT, after the merge that brought dev banks for association, basic_readout, multihop,
multilingual and user_modeling)

Instrument as x2 (post-merge evaluate.py; scorer = the merged scored-subset rule, so ns differ from
x2's bench ns), pool script x2_pool.py 089508806c2c3852 --split val. New dev banks captured locally;
val splits labelled by the same pinned-27B judge (label_concepts.py, out/concept-labels/<fam>-val).
Arms per family, cos and rms: zero, fam@fit, dict:fam:{0.5,1}@fit, dict:strat:1@fit,
dict:llm:{0.5,1}@fit, dict:derang:{0.5,1}@fit.
KNOWN: everything in x1, x2 and their outcomes; the user's val table (zero / fam@fit per family);
typo val x1 numbers; the x2 frame-vs-hypernym reading.

Predictions:
P1 (the pooled null replicates held out): dict:llm:1 - dict:derang:1 |cos pooled within +-0.03,
   interval spanning 0.
P2 (the frame-word effect replicates held out): typo val dict:fam:1 - dict:derang:1 |cos >= +0.10.
P3 (ceiling): fam@fit - dict:llm:1 pooled > 0 outside the bootstrap under both readouts.
P4 (hypernym harm, held out): user_modeling dict:strat:1 - zero |cos <= -0.10, and multihop
   dict:fam:1 - zero |cos <= 0.
NULL on P2 (typo frame effect < +0.05) would retire the frame-word idea too.

### x3 OUTCOME — 2026-10-10 16:33 BST (out/eval/x3-pooled.md; n: typo 91, association 102,
basic_readout 35, multihop 83, multilingual 82, user_modeling 61; pooled n = 454; all held out,
centres and norms fitted on fit, labels judged on val by the pinned 27B)

P1 PASS (the pooled null replicates): dict:llm:1 - dict:derang:1 |cos = +0.007 [-0.026, +0.040].
P2 FAIL at its threshold, but the retirement NULL also does not fire: typo dict:fam:1 -
  dict:derang:1 |cos = +0.086 [+0.011, +0.172] (and +0.086 [+0.022, +0.161] at alpha 0.5) —
  outside the bootstrap, just under the registered +0.10. The frame-word effect is real but
  smaller than x1/x2 suggested.
P3 PASS: fam@fit - dict:llm:1 pooled +0.194 [+0.156, +0.231] cos, +0.227 [+0.185, +0.271] rms.
P4 PASS: user_modeling dict:strat:1 - zero |cos = -0.393 [-0.525, -0.262] (the hypernym deletes
  the attribute, held out and worse than on bench); multihop dict:fam:1 - zero = -0.048
  [-0.108, +0.000].

Bottom line for the with/without-mean question on held-out data, pooled over the six families
(strict, cos): without mean 0.689; with the best category mean 0.698 (dict:fam:0.5, +0.009);
with the family mean 0.804 (+0.115). The category mean's whole pooled effect is the typo frame
word; the family mean's gain is item-level content, and on multihop and multilingual even IT
does not help (0.63 -> 0.61, 0.98 -> 0.95). mu is not one object: per family it is doing
different work, and the only universally safe centre so far is the family's own reference set.

---

## x4-constant-mean-ladder — REGISTERED 2026-10-10 16:38 BST (what is a good CONSTANT mean? The two
unmeasured rungs between generic corpus and own family, on the six dev val splits, held out)

Instrument as x3 plus two references in evaluate.py: `fitall` = one global mean per layer over the
six dev families' fit captures pooled (the truest universal constant measured so far), `fitothers`
= the same minus the read family (jle x89d's ctr1, held out on dev). Arms per family, cos and rms:
zero, fam@fit (anchors, already read in x3 and reused from the stores), fam@fitall, fam@fitothers.
KNOWN: x1-x3 and the user's table; jle ctr1 bench result (+0.02..+0.08); x101 G1/G2.

Predictions:
P1 (the proximity ladder is monotone, pooled cos): zero < fam@fitothers < fam@fitall < fam@fit in
   point values, with fam@fitothers - zero in +0.00..+0.06.
P2: fam@fitall - zero pooled cos is positive but under half of fam@fit's +0.115.
P3: on typo, fam@fitothers - zero |cos >= +0.05 (bench-style short-prompt cells are closer to typo
   reads than wikitext sentences were; ctr1 analogue).
NULL: fam@fitall - zero pooled within +-0.01 under both readouts — pooling heterogeneous read
   distributions cancels the constant mean's value entirely.

### x4 OUTCOME — 2026-10-10 16:42 BST (pooled n = 454, held out; per-family table in the session log
and out/eval/<family>/val/summary.md)

Pooled vs zero: fam@fitothers -0.011 cos [-0.037,+0.018] / +0.033 rms [+0.007,+0.059];
fam@fitall +0.029 cos [+0.002,+0.055] / +0.066 rms [+0.042,+0.093];
fam@fit +0.115 cos / +0.209 rms.
P1 PARTIAL: monotone under rms (0.597 < 0.630 < 0.663 < 0.806); under cos fitothers dips BELOW zero
  (its -0.011 misses the registered +0.00..+0.06 band) — driven by user_modeling (0.72 -> 0.49),
  whose chat-template mid-prompt cells are nothing like the other families' final-token cells.
P2 PASS: fitall's +0.029 is a quarter of fam@fit's +0.115. P3 PASS: typo fitothers - zero |cos
  +0.088 [+0.022,+0.154] (jle's ctr1 replicates held out). NULL rejected.
Caveat recorded: fitall's global mean is CELL-weighted and user_modeling fit contributes ~10x the
cells of any other family, so fitall is biased toward its distribution; a family-balanced variant
is the obvious follow-up if this rung matters.

Reading: every constant's value tracks how well its reference matches the read situation, and a
mismatched constant goes NEGATIVE (fitothers on user_modeling; dict hypernyms in x2/x3). The best
shippable constant measured is a broad mixed-task prompt-bank mean: +0.03 cos / +0.07 rms pooled,
a quarter-to-third of the family mean, with real downside risk off-distribution. Since 8 matched
prompts suffice for the family mean (jle x97-x100), the practical dataset-free approximation is
not a constant at all: synthesize ~8 same-kind prompts at read time and average their states.

---

## x5-frame-word-constant — REGISTERED 2026-10-10 16:47 BST (user proposal: an out-of-the-box J-lens
that removes the TEST'S OWN name per family — "in typo tests remove typo, in association tests remove
association" — alone and on top of the universal fitall constant)

Motivation: x2/x3's family words mixed frames with content hypernyms ("fact", "answer", "meaning");
the x2 reading says only FRAME words (naming the situation) can help. The test's name is a frame
word and is available out of the box (you know what you are asking the lens). Map
(`family_word_v2`, jargon names naturalized): typo->typo, association->association,
basic_readout->completion, multihop->inference, multilingual->translation, user_modeling->user.
Instrument as x3/x4 plus DictCentre modes `fam2` and `fam2+` (+ = added to the ref mean;
`dict:fam2+:a@fitall` = fitall constant + a x norm x frame direction); carriers-dict.pt re-captured
with the five new words (same templates, pin and code). Arms per family, cos and rms: zero, fam@fit,
fam@fitall (all from the x3/x4 stores), dict:fam2:0.5@fitall, dict:fam2:1@fitall,
dict:fam2+:0.25@fitall, dict:fam2+:0.5@fitall. Val splits, held out; pooled as before (n=454).
KNOWN: x1-x4 and outcomes; x3's dict:fam per-family numbers (typo +0.09..+0.11 cos, others <= 0).

Predictions:
P1: typo keeps its frame effect: dict:fam2:0.5@fitall - zero |cos >= +0.05 on typo.
P2 (the user's hypothesis, pooled): dict:fam2:0.5@fitall - zero |cos > fitall's +0.029 (point),
   i.e. the test-name direction adds something on top of the universal constant.
P3 (association specifically, the name vs my "theme"): association dict:fam2:0.5@fitall - zero
   |cos > +0.03 (point).
P4 (safety): dict:fam2+:0.25@fitall - zero is >= -0.02 pooled under both readouts (the composed
   out-of-the-box centre does no net harm at small alpha).
NULL: pooled dict:fam2[+] arms all within +-0.01 of plain fitall — the test's name adds nothing
   anywhere but typo.

### x5 OUTCOME — 2026-10-10 16:52 BST (held out, pooled n = 454; stores under out/eval/<family>/val)

P1 PASS: typo dict:fam2:0.5@fitall - zero |cos = +0.110 [+0.044, +0.187] — the word "typo" alone,
  norm-scaled on the universal reference, keeps its full effect.
P2 FAIL: pooled dict:fam2:0.5 - zero |cos = -0.002 [-0.029, +0.024], and it sits BELOW plain
  fitall (-0.031 [-0.057, -0.007]). The test-name direction does not add on top of the universal
  constant pooled: dict:fam2+:0.25@fitall - fam@fitall = +0.000 [-0.020, +0.020].
P3 FAIL: association's literal name does nothing on association (+0.020 [-0.039, +0.078]).
P4 PASS: the composed centre at alpha 0.25 does no net harm (+0.029 cos / +0.068 rms vs zero,
  = fitall), though per family it inherits fitall's user_modeling dip (0.72 -> 0.62).
NULL (pooled) effectively holds for the name direction; the one real exception is typo:
  fitall + 0.25 x v(typo) reaches 0.86 cos (zero 0.69, fitall 0.81, fam@fit 0.92) — the best
  out-of-the-box typo number.

Reading. "Remove the test's name" is a typo-only trick, not a recipe: typo's frame ("there is a
typo here") is salient at the read cell and near-orthogonal to the correction, so subtracting it
cleans the readout; the other tests' frames are either not strongly represented at the read cell
(association, multihop as single words) or entangled with the content (user attributes). The
out-of-the-box centre this programme supports after x1-x5 is: mu = broad mixed-prompt-bank mean
(fitall), optionally + 0.25 x the test-name direction (free when the frame is salient, harmless
when not) — worth a quarter to a third of the family mean, never all of it.

x5 rms addendum (2026-10-10 16:55 BST, same stores): the structure replicates under rms. Pooled:
zero 0.597, fitall 0.663, fam2+:0.25 0.665 (+0.002 [-0.015,+0.020] over fitall — the name adds
nothing pooled), fam@fit 0.806. typo again the exception: fam2+:0.25 - zero = +0.176
[+0.099,+0.264] (0.57 -> 0.75). Two rms-specific notes: (a) user_modeling LIKES the universal
constant under rms (0.62 -> 0.75, opposite sign to cos) but the "user" direction gives a third of
it back (0.75 -> 0.66) — the attribute-content entanglement again; (b) association's own name is
marginally positive under rms (+0.049 [+0.000,+0.108]), the only non-typo name with any signal.

---

## x6-render-matched-bank — REGISTERED 2026-10-10 16:57 BST (user question: would we even have fitall
out of the box? No — fitothers is the honest shipped-bank estimate (-0.011 cos / +0.033 rms pooled).
The one out-of-the-box refinement left: a RENDER-MATCHED bank, since the read's render is always
known at deployment)

Instrument as x4 plus ref `plainothers` in evaluate.py: the fit captures of the plain-render
families (all but user_modeling) minus the read family — no chat-template cells in the bank
(basic_readout's implicit third is chat_prefill; noted, kept). Read on the five plain families'
val splits (user_modeling has no chat sibling bank to match; that gap IS part of the answer).
Arms: zero, fam@fitothers (stored), fam@plainothers; cos and rms.
KNOWN: x1-x5; fitothers per family (typo +0.088 cos, association +0.05, others ~0, despite its
bank being cell-dominated by user_modeling's chat cells).

Predictions:
P1: fam@plainothers >= fam@fitothers (point) on 4 of the 5 plain families under cos.
P2: typo fam@plainothers - zero |cos >= +0.08 (keeps fitothers' gain without the chat cells).
P3 (pooled over the five plain families): fam@plainothers - zero positive under both readouts
   (point), and at least half of fam@fitall's pooled-on-these-families value.
NULL: plainothers = fitothers within +-0.01 everywhere — render matching is not the lever.

### x6 OUTCOME — 2026-10-10 17:00 BST (five plain families' val, pooled n = 393)

P1 PASS (by its >= wording): plainothers >= fitothers under cos on typo (0.79/0.78), association
  (0.53/0.46), multilingual (0.94/0.94, tie); below on basic_readout (0.89/0.91) and multihop
  (0.59/0.61).
P2 PASS: typo plainothers - zero |cos = +0.099 [+0.022, +0.176].
P3 PASS: pooled plainothers - zero = +0.036 cos [+0.005, +0.066] / +0.112 rms [+0.079, +0.148];
  over fitothers +0.013 cos (ns) / +0.064 rms [+0.036, +0.092]. NULL rejected under rms.

Reading: render matching IS a lever, mainly under rms. A genuinely out-of-the-box constant — a
bank of short plain-render task prompts from OTHER tasks, no own-family data, no chat cells —
is worth +0.04 cos / +0.11 rms pooled on plain-render reads (association 0.41 -> 0.53). This
revises x4's shipped-constant verdict upward: ship one bank per render/read-situation type, not
one global vector. The user_modeling gap (no chat sibling bank here) marks the chat-render bank
as the missing artefact.

---

## x7-dm-frame — REGISTERED 2026-10-10 17:09 BST (the self_meta test: frame-word mu on
directed_modulation, the family where the GW frame — "I am holding a secret / an instruction" —
should be most salient. Strict tier first (concept named in the top-10, umot's token-rank lower
bound); the judged tier follows once the OpenRouter key arrives)

Instrument. DM dev bank built and gated locally this session (154/154 candidates passed the
bench's gate, a pre-screened set; fit 78 / val 76, split by pair). Concept maps extended
(data/abstract_concepts.json): DM family word "secret", v2 "instruction", stratum words
pair->thought / secret->secret / preference->preference, derangement "colour"; carriers-dict
re-captured with instruction/secret/thought (38+3 words... 41 x 5 templates). Reads at the
bench's DM plan (chat_dm, carrier-writing positions, 11 layers). KNOWN: umot's DM results (zero
judged content_bound 0.21; tok1/ctr-tok 0.82; family mean does nothing on DM because read cells
vary — synthesis lesson 2); all of x1-x6. rms is the primary readout (user instruction);
cos reported beside it.

Arms on val, centres fitted on fit: zero, fam@fit, tok@fit (umot's tok1 analogue, the known
winner's free-tier anchor), dict:strat:{0.25,0.5}@fit (per-subfamily frame words),
dict:fam2:{0.25,0.5}@fit ("instruction" for all), dict:derang:0.5@fit (control).

Predictions (strict = concept in top-10, any layer/cell; n=76):
P1 (anchor, lesson 2 replicates): fam@fit - zero within +-0.05 (the family mean does little on
   DM's varying read cells), while tok@fit - zero >= +0.10 under rms.
P2 (HEADLINE, the frame hypothesis): dict:strat:0.25@fit - dict:derang... (same-alpha control at
   0.5; compare at 0.5) — dict:strat:0.5 - dict:derang:0.5 >= +0.05 under rms. A frame that is
   genuinely salient at the writing cells should beat a wrong word by more than typo's +0.09.
P3: strat (subfamily frames) >= fam2 ("instruction" everywhere) under rms (point).
NULL: strat = derang within +-0.03 under rms — the frame hypothesis dies on its best family, and
   with it the constructive use of the GW set; only tok/ctr-style matching remains for DM.

### x7 OUTCOME, strict tier — 2026-10-10 17:12 BST (out/eval/directed_modulation/val/summary.md)

The strict instrument is nearly degenerate on DM, as umot's judged-only practice implied: of 76
val items, 18 are leak-excluded (pair prompts NAME the concept) and 2 unreachable; of the 56
scored, 47 have no single-token target and cannot pass, leaving ~9 passable items. Within that:
P1 PASS on both halves: fam@fit - zero = +0.018 rms (within +-0.05; lesson 2 replicates — the
  family mean does nothing on DM's varying cells) and tok@fit - zero = +0.107 rms
  [+0.036, +0.196] (the tok1 anchor is the only arm that moves, under cos too: +0.089).
P2 FAIL / NULL nominally fires: every frame arm is 0.000-0.018, = the derangement control. BUT
  the tier is underpowered by construction (9 passable items); this does not kill the frame
  hypothesis on DM — it says strict cannot test it. The judged tier (registered as part of x7)
  is decisive and runs once the OpenRouter key is in umot/.env: content_bound on val, dev judge
  Haiku 5.5, dry-run -> limit 3 -> estimate -> user go-ahead past ~$5.

---

## x8-self-generated-reference — REGISTERED 2026-10-10 20:50 BST (the practical approximation of the
family mean with NO dataset: the model writes its own reference set. mu(item) = mean state of ~8
self-generated "same kind" prompts at the matched read cell. jle x97-x100: 8 prompts suffice for
the family mean; this tests whether synthesized prompts do)

Instrument. experiments/x8_gen_refs.py 7cd33ceedf71f135 (pinned 27B, greedy, thinking off; sees
ONLY the item's rendered prompt — what the lens reads — never a target or the family name;
generations containing the prompt's final CONTENT word are dropped — amendment before any score
was read: the first basic_readout run banned function-word endings ("of") and collapsed to 5
items; STOPWORDS exemption added, family regenerated). centres.GenMean (jlm/centres.py
c831b8d1a1380910), arm `gen@self`, per-item mu, reference-wide mean fallback (counted).
Families: typo (92 items x 8 refs), association (97 x 8), basic_readout (regenerated) — the three
val families where fam@fit gains under rms (+0.33 / +0.51 / +0.14). Fairness: transductive per
item like loo/carpos, but the reference is SYNTHESIZED from the visible context, not retrieved;
a mention-control-style test is owed before any "fair" claim stronger than carpos's (flagged, x9
candidate). rms primary.

Predictions:
P1 (HEADLINE): gen@self - zero >= +0.15 rms, paired interval excluding 0, on BOTH typo and
   association.
P2: gen@self reaches >= 60 % of fam@fit's paired rms gain on typo and association (point).
P3 (no harm near ceiling): basic_readout gen@self - zero >= -0.03 rms (point).
NULL: gen@self - zero < +0.05 rms on both typo and association — synthesized references do not
   carry the family mean's content; real same-family data is irreplaceable.

### x8 OUTCOME, typo + association — 2026-10-10 20:52 BST (basic_readout regen still running;
its result will be appended)

P1 SPLIT, and the split is the finding. association PASSES: gen@self - zero = +0.27 rms
(0.255 -> 0.529 [0.431, 0.627]; cos 0.412 -> 0.549), more than half of fam@fit's +0.51 — P2 met
there (54 %... just under 60? 0.274/0.510 = 54 %, point misses P2's 60 % narrowly). typo FAILS
INVERTED: gen@self = 0.407 both readouts, BELOW zero (0.571 rms) by -0.16.
Diagnosis (checked in the generations before writing this): emergent target leakage. Asked for
"texts of exactly the same kind", the model writes near-paraphrases whose endings are the
item's own latent — 22/92 typo reference sets contain the exact correction ("...finally began
to arrive" for target arrive), most others near-synonyms; subtracting their mean subtracts the
answer. association leaks far less (12/97: its latent is an unnamed theme, not a
prompt-recoverable continuation) and that is exactly where the method works.

Reading: the self-generated reference inherits the family's prompt-recoverability. Where the
latent is NOT recoverable from the visible context (association — the interesting case for a
lens), self-generation is the first dataset-free centre to recover half the family mean. Where
the latent IS prompt-recoverable (typo, the family with a 1.00 prompt-only floor), the generator
reconstructs it and the centre deletes the signal. Fair mechanical fix to try (x8b): ban
generations containing any word within edit distance 2 of the prompt's final content word
(label-free, prompt-derived), plus a generator instruction not to complete or correct the
example. The mention-control test remains owed before fairness claims.

x8 addendum, basic_readout — 2026-10-10 20:58 BST (regenerated with the stopword-exempt ban:
35 items x 8 refs, 0 short). gen@self = 1.000 under BOTH readouts: it matches fam@fit's rms
ceiling (0.857 -> 1.000, +0.143 [+0.029, +0.257]) and EXCEEDS fam under cos (0.914 -> 1.000
where fam gave +0.000). P3 passes. Target-containment 7/35 — some leakage exists but with
single-token numeric/factual targets the other refs' answers average out rather than aligning,
unlike typo's semantically-pointed corrections. x8 final tally: the self-generated reference
recovers 54 % (association), 100 % (basic_readout) of the family mean's rms gain, and inverts
only on typo, the one family whose latent the prompt gives away.

---

## x9-gen-controls — REGISTERED 2026-10-10 21:41 BST (what does x8's self-generated reference buy:
item matching, or a synthetic family distribution?)

Instrument: centres `genx` (GenOtherMean: another item's references, fixed derangement = next id in
sorted order) and `genfam` (GenFamilyMean: every other item's references pooled, item-weighted, own
excluded — a synthetic dataset-free family mean), same references as x8 (out/captures/gen-*.pt),
read via evaluate.py on the merged code, val, rms primary. Families with references at
registration: typo, association, basic_readout (val). KNOWN: x8 on these banks (rms): zero / gen /
fam@fit = typo 0.571 / 0.407 / 0.901, association 0.255 / 0.529 / 0.765, basic_readout 0.857 /
1.000 / 1.000; typo leak diagnosis (22/92 reference sets contain the item's own correction).

Predictions (rms, strict, paired item bootstrap):
P1 (item matching matters where x8 worked): association gen - genx >= +0.05 (point).
P2 (the typo inversion is item-specific leakage): typo genfam >= zero (point; other items' refs
   carry other corrections, not this item's), and typo genx >= gen.
P3 (synthetic family mean): genfam reaches >= 75 % of fam@fit's paired gain over zero on typo and
   association (point).
NULL for P1: |gen - genx| < 0.03 on association — x8's gain is a synthetic family distribution,
   not item matching.

### x9 OUTCOME — 2026-10-10 21:42 BST (out/screen/<family>/val; rms, strict)

| val, rms | zero | gen | genx | genfam | fam@fit |
|---|---|---|---|---|---|
| typo (n=91) | 0.571 | 0.407 | 0.703 | 0.703 | 0.901 |
| association (n=102) | 0.255 | 0.529 | 0.657 | 0.755 | 0.765 |
| basic_readout (n=35) | 0.857 | 1.000 | 1.000 | 1.000 | 1.000 |

P1 FAIL, INVERTED: association gen - genx = -0.127 [-0.225, -0.029]. Item matching HURTS: an item's
  own references carry its latent (leakage is general, typo is only its extreme: gen - genx =
  -0.297 [-0.407, -0.187]).
P2 PASS: typo genfam 0.703 >= zero 0.571 (+0.132 [+0.055, +0.220]); genx >= gen.
P3 SPLIT: genfam reaches 98 % of fam@fit's gain on association (+0.500 vs +0.510) and 100 % on
  basic_readout, but 40 % on typo (+0.132 vs +0.330). FAIL as registered (both families required).
NULL for P1 does not fire (|diff| = 0.127), but in the opposite direction from the hypothesis.

Reading: x8's gain was never item matching; it is a synthetic same-kind distribution, and the own
item must be EXCLUDED (as in the family mean's leave-one-out). A synthetic family mean substitutes
for real family data on association and basic_readout. The practical recipe this supports: give
the generator one or a few EXAMPLES of the read situation (never the item being read), let it write
same-kind prompts, average their states at the matched cell. One example (genx) already reaches 79 %
of fam's association gain. Open: how the gain scales with the number of seed examples (1 vs 2-8),
typo's remaining gap, and the families not yet generated (multihop, multilingual; running).

---

## x10-seed-curve — REGISTERED 2026-10-10 21:43 BST (how many example prompts does the synthetic
family mean need? centre genk:<k> = mean of the self-generated references of the k next items in
sorted id order, never the item's own; k in {1, 2, 4, 8}; genk:1 = genx, k = all = genfam; same
references as x8/x9; val, rms, strict; typo, association, basic_readout)

KNOWN: x9 (genx and genfam per family). Prediction: on association the curve is monotone in k
(point) and genk:4 reaches >= 90 % of genfam's gain over zero; on typo genk:8 stays below fam@fit
by >= 0.10. NULL: genk:8 < genk:1 on association (more seeds do not help).

### x10 OUTCOME — 2026-10-10 21:43 BST (val, rms, strict)

| val, rms | zero | k=1 | k=2 | k=4 | k=8 | all (genfam) | fam@fit |
|---|---|---|---|---|---|---|---|
| typo | 0.571 | 0.703 | 0.714 | 0.736 | 0.670 | 0.703 | 0.901 |
| association | 0.255 | 0.657 | 0.657 | 0.706 | 0.765 | 0.755 | 0.765 |
| basic_readout | 0.857 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

All three predictions PASS: association is monotone in k (point; k=1 and k=2 tie); genk:4 reaches
90 % of genfam's gain (+0.451 vs +0.500); typo genk:8 stays 0.23 below fam@fit. NULL not fired:
association genk:8 - genk:1 = +0.108 [+0.049, +0.176].
Reading: eight example prompts of the read situation, each expanded by the model into eight
same-kind prompts, reproduce the family mean on association (0.765 = 0.765) with no other family
data. On typo the synthetic mean plateaus near 0.70 (non-monotone, within noise) — the remaining
gap there is not seed count.

---

## x11-glossary-seeded-references — REGISTERED 2026-10-10 21:48 BST (the user's workspace-concept
glossary used to GENERATE the reference set instead of being subtracted: per family, the pinned 27B
writes 64 texts from one glossary entry alone — never a bank item — and mu = their mean state at the
final token; one constant per family and layer)

Instrument: experiments/x11_glossary_refs.py (entries in GLOSSARY: frame word + one-line situation
definition; sampled at T=0.9, top-p 0.95, 8 texts per call, call seeds from crc32), centre
GlossaryMean (centres.py). Arms per family on val, rms: glos:word@self (glossary word only),
glos:desc@self (word + definition), glosx:desc@self (another family's entry: specificity control),
against zero, genk:8@self (8 example prompts, x10) and fam@fit. Families: typo, association,
basic_readout (multihop and multilingual once their x8 references exist; reported descriptively).
KNOWN: x8-x10; rms val for these families: zero 0.571 / 0.255 / 0.857, genk:8 0.670 / 0.765 / 1.000,
fam@fit 0.901 / 0.765 / 1.000 (typo / association / basic_readout).

Predictions (strict, paired item bootstrap):
P1 (glossary works as a generator): glos:desc - zero > 0 outside the bootstrap on association.
P2 (the definition matters more than the word): glos:desc >= glos:word (point) on 2 of 3 families.
P3 (specificity): glos:desc - glosx:desc >= +0.05 (point) on association and typo.
P4 (how close to examples): glos:desc reaches >= 70 % of genk:8's gain over zero on association.
NULL: glos:desc within +-0.03 of glosx:desc on all three families — any synthetic text works, the
glossary entry adds nothing.

x10 addendum, multihop val — 2026-10-10 21:55 BST (descriptive; references generated after
registration): zero 0.566, gen 0.614, genx 0.530, genk:2/4/8 0.627/0.590/0.602, genfam 0.578,
fam@fit 0.566, tok@fit 0.602 (rms, n=83). Every centre is within noise of zero (genk:8 - zero
+0.036 [-0.024, +0.096]): the synthetic mean tracks the real family mean here too, and on multihop
the family mean itself does nothing.

### x11 OUTCOME — 2026-10-10 22:15 BST (val, rms, strict; out/screen)

| val, rms | zero | glos:word | glos:desc | glosx:desc | genk:8 | fam@fit |
|---|---|---|---|---|---|---|
| typo (n=91) | 0.571 | 0.857 | 0.879 | 0.637 | 0.670 | 0.901 |
| association (n=102) | 0.255 | 0.725 | 0.412 | 0.490 | 0.765 | 0.765 |
| basic_readout (n=35) | 0.857 | 0.857 | 0.971 | 0.886 | 1.000 | 1.000 |
| multihop (n=83) | 0.566 | 0.602 | 0.602 | 0.614 | 0.602 | 0.566 |
| multilingual (n=82) | 0.951 | 0.951 | 0.951 | 0.939 | – | 0.927 |

P1 PASS: association glos:desc - zero = +0.157 [+0.078, +0.235].
P2 PASS (2 of 3): desc >= word on typo (+0.022) and basic_readout (+0.114); not on association (-0.314).
P3 FAIL: desc - glosx = +0.242 [+0.154, +0.341] on typo but -0.078 [-0.157, 0.000] on association.
P4 FAIL: glos:desc reaches 31 % of genk:8's association gain (+0.157 vs +0.510).
NULL not fired (typo specificity +0.24).
Descriptive, pooled over the 5 families (n=393, paired vs zero = 0.593): glos:word 0.789 (+0.196
[+0.155, +0.237]), glos:desc 0.723 (+0.130), glosx:desc 0.679 (+0.087), fam@plainothers 0.705
(+0.112), fam@fit 0.809 (+0.216); glos:word - plainothers = +0.084 [+0.053, +0.117].
Reading: one glossary WORD per family, expanded by the model into 64 texts, reaches 91 % of the real
family mean's pooled gain with no family data (typo 0.857, association 0.725). It beats the
8-example synthetic mean on typo (0.88 vs 0.67) because glossary texts never contain the item's
correction. The definition helps where the word is ambiguous (basic_readout: "completion" alone
gives texts ABOUT completion) and hurts on association. Caveats: the glossary words and definitions
were written after x1-x10 (the words are x5's frame words); the word variant was registered as an
arm but the predictions targeted desc, so the +0.196 is descriptive until replicated on fit and with
a glossary written blind.

### x7 OUTCOME, judged tier — 2026-10-10 22:36 BST (Haiku 5.5 dev judge, unpinned, layers 24/36/48/60,
content_bound; out/eval/directed_modulation/val/<arm>/judged-claude-haiku-5.5-L24-36-48-60; n=76)

zero|rms 0.092, tok@fit|rms 0.737, dict:strat:0.5@fit|rms 0.092, dict:derang:0.5@fit|rms 0.079.
P1 PASS: tok@fit - zero = +0.645 [+0.539, +0.750] (rms counterpart of the cos calibration
  0.18 -> 0.79); the family mean was not judged (strict +0.018).
P2 FAIL, NULL FIRES: strat - derang = +0.013 [-0.039, +0.066]; strat - zero = +0.000. By subfamily
  (pair 52 / secret 12 / preference 12): strat equals plain in every stratum (0.12 / 0.00 / 0.08).
Reading: the self/meta glossary words (thought, secret, preference) do nothing on the family where
the frame should be most salient. On DM what works is matching the read token, not naming the
situation. This closes the subtracted-word use of the glossary; its generator use (x11) is the
open line. Spend for the judged tier: $2.93 (+ $0.90 smoke and stopped all-layer run), of the
$8.30 the user approved.

## x12 — synthetic and glossary references in the chat families (registered 2026-10-11 12:42 BST, before generation)

x8-x11 ran on the five plain-render families only. user_modeling (chat_context: system + user
message, read from the last sentence start through the template) and directed_modulation (chat_dm:
instruction, the quoted sentence teacher-forced as the reply, every token read) need references in
their own render. experiments/x8_gen_refs.py and x11_glossary_refs.py now put each generated text
into a copy of the item's (or the family's first val item's) read spec, so it is rendered and read as
the items are. x11's chat prompts add one format line (same for word, desc and the control); the
control glosx:desc is the partner family's entry (UM <-> DM) written in this family's format.
Glossary entries: user_modeling = "user" / a message in which a person lets slip something about who
they are without stating it, followed by a request; directed_modulation = "instruction" / a request
to keep one particular thing in mind while writing out a given sentence exactly.

Arms (rms; fit and val; strict free tier): gen, genx, genk:2/4/8, genfam @self; glos:word, glos:desc,
glosx:desc @self; with zero, fam@fit, tok@fit.

Predictions (strict, val, rms):
- P1 DM: genk:8 within 0.05 of fam@fit (the synthetic mean tracks the family mean, as in x10).
- P2 DM: gen@self <= genk:8 (an item's own rewrites keep its concept and remove it, as x9 on typo).
- P3 UM: genk:8 within 0.05 of fam@fit, and glos:desc >= glosx:desc.
- P4 UM: glos:desc >= zero, unlike fam@plainothers (x6: render mismatch, 0.62 -> 0.56).
Caveats fixed in advance: strict does not track the judge on either family, and S11 (iteration) shows
UM pass@10 cannot separate user modelling from reading the prompt; so the strict tier only screens.
The outcome of record for both families is the judged tier (Haiku 5.5, val, layers 24/36/48/60), run
only with the user's approval of its spend.

### x8-x11 addendum: the fit split — 2026-10-11 12:52 BST (descriptive; out/eval, merged code, rms, strict)

Fit-split references were generated after the val outcomes were read, with the unchanged scripts;
the glossary texts are per family, so fit reuses x11's texts on a different item set. Pooled over
the 5 strict-proxy families, paired vs zero (val 0.593, n=393 / fit 0.554, n=397):

| arm | val | fit |
|---|---|---|
| fam@fit | +0.216 [+0.173, +0.260] | +0.232 [+0.19, +0.27] |
| glos:word@self | +0.196 [+0.155, +0.237] | +0.189 [+0.15, +0.23] |
| genk:8@self | +0.168 [+0.125, +0.211] | +0.194 [+0.15, +0.23] |
| genfam@self | +0.168 | +0.186 |
| glos:desc@self | +0.130 | +0.149 |
| fam@plainothers | +0.112 | +0.106 |
| glosx:desc@self | +0.087 | +0.096 |
| gen@self | +0.048 | +0.093 |

The glossary word holds on fit (81 % of fam's gain; val 91 %), still with the words chosen after x1-x10.
genk:8 val now includes multilingual (0.91 vs plain 0.95), hence +0.168 here vs the 3-family x10 view.

### x12 OUTCOME, directed_modulation — 2026-10-11 14:39 BST (val, rms; run from constant-mean-exploration 491f98b)

References: DM val generated at eval-pipeline f8aa3aa (generator code identical to this branch's), 64 of 76
items covered (500 texts; 12 items with no usable quoted sentence fall back to the pooled mean); glossary sets
at f6d342c-identical code. Strict (n=74): zero 0.068, fam@fit 0.095, tok@fit 0.324, gen 0.108, genx 0.108,
genk:2/4/8 0.095, genfam 0.095, glos:word 0.095, glos:desc 0.095, glosx:desc 0.081.
P1 PASS: genk:8 - fam@fit = +0.000 (strict). P2 FAIL (narrow): gen - genk:8 = +0.014 [-0.027, +0.068].
Judged tier (outcome of record; Haiku 5.5, layers 24/36/48/60, n=76, $4.96): zero 0.092, tok@fit 0.737,
genk:8 0.184, genfam 0.211, gen 0.184, glos:word 0.184, glos:desc 0.145, glosx:desc 0.224.
Paired vs zero: genk:8 +0.092 [+0.013, +0.184], genfam +0.118 [+0.026, +0.211], glos:word +0.092 [+0.026,
+0.171], glos:desc +0.053 [-0.013, +0.132], glosx:desc +0.132 [+0.039, +0.237]; specificity glos:desc -
glosx:desc = -0.079 [-0.171, +0.013]; genk:8 - tok@fit = -0.553 [-0.671, -0.434].
Reading: on DM every constant centre buys a small, non-specific gain (the wrong glossary entry does as well):
it removes the chat template's prior, not anything about the held concept. What reads the concept is matching
the read token (tok@fit +0.645; iteration's U1 / S4 caveat: part of that is the same-sentence leak on dev,
fair centres reach 0.57-0.64). UM: pending its references.

### x12 OUTCOME, user_modeling — 2026-10-11 15:50 BST (val, rms, strict; run from constant-mean-exploration 9efb620)

References: UM val generated on this branch (491f98b); glossary sets f6d342c-identical code. Strict (n=61):
zero 0.623, fam@fit 0.787, tok@fit 0.869, fam@plainothers 0.557, gen 0.770, genx 0.803, genk:8 0.770, genfam
0.787, glos:word 0.738, glos:desc 0.738, glosx:desc 0.689.
P3 PASS: genk:8 - fam@fit = -0.016 [-0.049, 0.000]; glos:desc - glosx:desc = +0.049 [0.000, +0.115].
P4 PASS: glos:desc - zero = +0.115 [+0.049, +0.197], while fam@plainothers - zero = -0.066 [-0.148, +0.016]
(the chat-format glossary centre helps where the plain-render bank hurt).
Caveat registered in advance: UM pass@10 cannot separate user modelling from reading the prompt (iteration S11),
so these screen only; UM was not judged (S11; ~$3 per arm).

## x19 — WorkspaceBench numbers of record for the constant-mu finalists (registered 2026-10-11 16:45 BST, before any bench read)

Everything before this was ours (dev banks, strict scorer, rms). Here: the bench's own held-out items (100 per
family), its readout (cos; rms reported alongside, strict only), and its pinned judge (google/gemini-3.8-flash via
OpenRouter, reasoning minimal, bench prompts, all 11 layers). Plan A (user, $27 approved): five arms on the five
plain families: zero|cos, glos:word@self|cos, fam@fit|cos (fitted on dev fit: held out from the bench),
fam@plainothers|cos, jpp:zero|cos; directed_modulation (bench capture to be made) with zero|cos and
glos:word@self|cos. user_modeling not judged (S11; budget). A limit=3 probe per family sets the cost before the
full runs. Run from constant-mean-exploration merged with the latest eval-pipeline; strict on the bench is read in
the same pass and is also of record for this registration.

Predictions (pinned judge, cos, paired over the bench's judged items):
- P1: glos:word - zero > 0 with the interval above 0 on typo and on association; pooled over the five plain
  families it recovers >= 60 % of fam@fit's gain.
- P2: fam@plainothers - zero > 0 pooled over the five plain families.
- P3: jpp:zero >= zero on typo and association (J++ reads better than the plain J-lens).
- P4: multihop and multilingual: no arm's interval lies above 0 against zero.
- P5: directed_modulation: glos:word - zero within [-0.10, +0.10] (constant centres are non-specific there, x12).
Strict (free) on the bench, for all five arms, cos and rms: reported descriptively.

### x19 OUTCOME, five plain families — 2026-10-11 18:58 BST (pinned judge, cos, n = 100 per family; run from
constant-mean-exploration; spend $16.10 for 25 runs)
| bench, pinned, cos | zero | glos:word | fam@fit | fam@plainothers | jpp:zero |
|---|---|---|---|---|---|
| typo | 0.59 | 0.77 | 0.85 | 0.60 | 0.95 |
| association | 0.41 | 0.61 | 0.66 | 0.45 | 0.50 |
| basic_readout | 0.89 | 0.85 | 0.92 | 0.85 | 0.92 |
| multihop | 0.81 | 0.73 | 0.79 | 0.68 | 0.86 |
| multilingual | 0.96 | 0.98 | 0.96 | 0.97 | 0.99 |
Paired vs zero, pooled (n = 500, zero 0.73): glos:word +0.056 [+0.026, +0.088], fam@fit +0.104 [+0.072, +0.136],
fam@plainothers -0.022 [-0.048, +0.004], jpp:zero +0.112 [+0.082, +0.144].
- P1 SPLIT: glos:word - zero is above 0 on typo (+0.180 [+0.100, +0.260]) and association (+0.200 [+0.120, +0.290]),
  but pooled it recovers 54 % of fam@fit's gain (< 60 %): it costs multihop -0.080 [-0.150, -0.020] and
  basic_readout -0.040 [-0.090, 0.000], where fam@fit costs -0.020 / gains +0.030.
- P2 FAIL: fam@plainothers - zero pooled -0.022 (multihop -0.130 [-0.210, -0.050]).
- P3 PASS: jpp:zero - zero +0.360 [+0.270, +0.450] on typo, +0.090 [+0.010, +0.170] on association.
- P4 PASS (at the edge): no interval above 0 on multihop; on multilingual fam@plainothers and jpp:zero have lower
  bounds of exactly 0.000 (+0.010, +0.030).
- P5 (directed_modulation) pending its bench capture (final pass).
Reading: on the bench's own instrument the glossary word keeps 69 % (typo) and 80 % (association) of the family
mean's gain where the plain lens is weak, and costs a little where it is near its ceiling (basic_readout 0.89,
multihop 0.81). The uncentred J++ is the strongest single arm pooled (+0.112; jpp:zero - glos:word +0.056
[+0.024, +0.088]), almost all of it on typo; on association centring still wins (0.61 / 0.66 against J++'s 0.50).
Whether J++ and a centre add up is the open question (dev: the final pass reads jpp: with every centre).

### x19b — J++ with the glossary word on the bench (registered 2026-10-11 19:45 BST, before any bench read of it)
Known on dev (rms, strict, pooled plain): jpp:glos:word - jpp:zero +0.020 [-0.010, +0.051] val, +0.008 fit; by family
association +0.13 val / +0.09 fit, typo -0.01 / 0.00, basic_readout -0.06 / -0.08. Arm jpp:glos:word@self|cos on the
five plain bench families, pinned judge (user approved about $3.30).
- P1: association: jpp:glos:word - jpp:zero > 0 with the interval above 0.
- P2: typo: jpp:glos:word - jpp:zero within [-0.05, +0.05].
- P3: pooled: jpp:glos:word - jpp:zero within [-0.02, +0.06], and jpp:glos:word >= glos:word (point).

### x19b OUTCOME — 2026-10-11 20:16 BST (pinned judge, cos, n = 100 per family; from 3ddba65; spend $3.20)
jpp:glos:word: typo 0.92, association 0.70, basic_readout 0.89, multihop 0.80, multilingual 0.96 (pooled 0.854).
- P1 PASS: association jpp:glos:word - jpp:zero = +0.200 [+0.110, +0.290] (0.50 -> 0.70, the best association arm
  on the bench; fam@fit 0.66).
- P2 PASS: typo -0.030 [-0.080, +0.010].
- P3 PASS: pooled +0.010 [-0.018, +0.036] over jpp:zero; over glos:word +0.066 [+0.038, +0.094]; over fam@fit +0.018
  [-0.008, +0.044].
Reading: J++ and the glossary-word centre fix different families (J++ typo, the centre association), and together
they are the best pooled arm measured on the bench with no task data (0.854; fam@fit alone 0.836, jpp:zero 0.844).

### x19 OUTCOME, P5 (directed_modulation) — 2026-10-12 09:52 BST (pinned judge, cos, n = 100, both arms complete;
judged from 89e1fec after the user raised the key limit)
| DM bench, pinned, cos | zero | glos:word |
|---|---|---|
| all (100) | 0.10 [0.05, 0.16] | 0.17 [0.10, 0.24] |
| pair (70) | 0.13 | 0.21 |
| preference (15) | 0.07 | 0.13 |
| secret (15) | 0.00 | 0.00 |
- P5 PASS as worded: glos:word - zero = +0.07 [+0.02, +0.13], inside [-0.10, +0.10]. But the interval is above 0
  (8 items won, 1 lost): on the bench's instrument the constant centre helps a little, which the "non-specific"
  reading behind P5 did not expect. Secret items stay at 0 under both.
Strict on the bench (19 reachable of 100): zero 0.07 / glos:word 0.08 (cos), 0.06 / 0.07 (rms); forms identical.
Spend, corrected: the overnight run (2026-10-11 23:58 - 10-12 00:56) also judged 5,732 glos:word cells before the
key's limit (403), unreported because the run stopped: about $8.33 on top of the $13.02 logged, so ~$21.35
overnight. Today $4.60 (glos:word's remaining cells, 6 zero cells). DM bench total ~$25.95; x19 total ~$42.05
against the $27 approved (the user approved finishing P5 on 2026-10-12). Key usage $54.62 of a $100 limit.
DM bench judges every read cell (8,888 per arm), ~$12.9 per arm in full.

## x13 — blind glossary: the model writes the entry (registered 2026-10-11 16:46 BST, before any run)

x11's glossary words were picked by me after x1-x10, so its +0.196 is descriptive. Here the pinned 27B writes each
family's glossary entry (one word + a one-line definition of the situation) from the FIRST SENTENCE of the bench's
own README for that family (third_party/workspace-bench/evals/<family>/README.md; the example line, with its
target, is cut). It never sees a bank item or any result. Then x11's generator writes 64 texts from that entry
(word and desc variants, chat format line for UM / DM as in x12), with a different seed salt ("blind"), and the
centres glosb:word / glosb:desc are scored like x11 (strict, rms, dev fit and val; all 7 families).
Predictions (pooled over the 5 plain families, paired vs zero):
- P1: glosb:word recovers >= 60 % of fam@fit's gain on fit (x11's words: 81 %).
- P2: glosb:word > glosx:desc (the wrong-entry control) on typo and association, fit.
- P3: |glosb:word - glos:word| <= 0.06 pooled on val (the choice of words matters little).

## x14 — more data-free constants (registered 2026-10-11 16:46 BST, before any run)

Each needs nothing from the task being read; all strict, rms, dev fit and val, 7 families:
- A  glosall:word / glosall:desc — one μ for every family: the mean over ALL families' glossary sets.
- B  glos:none — 64 texts written with no entry at all ("varied short texts"; chat families keep the format line):
     the control for x11 (situation vs "model-written short text").
- C  null — the read cell's state for minimal prompts in the family's render (16 one-word plain prompts; chat: the
     template around a neutral one-line message / sentence).
- D  uncond — 64 texts the model writes from an empty prompt (sampled), at their final token.
- E  pcw:4 / pcw:16 — remove the projection onto the top-k principal directions of wikitext states (the data-free
     version of iteration's S7 family PCA): g = m + P_k (h - m), m the wikitext mean.
- F  massive:4 — set the 4 largest-magnitude dimensions of the wikitext mean state to it (massive activations).
Predictions (pooled over the 5 plain families, val, vs zero):
- P1: glosall:word > 0 and >= 50 % of glos:word's own gain (one shared μ keeps most of the per-family one).
- P2: glos:none < glos:word (the situation matters, not just the genre), on typo and association.
- P3: null, uncond, pcw, massive: each within [-0.05, +0.10]: none reaches the plain-prompt bank (+0.11).

### x14 amendment (before any x14 run, 2026-10-11 16:52 BST)
F has two readings; both are run. massive:4 sets the 4 largest-magnitude dimensions of the wikitext mean state to
their wikitext mean (removes their per-input variation); massivez:4 sets them to 0 (removes them). E's PCs and F's
dimensions come from 8,192 wikitext-103 cells (positions 8 on), seeded. Prediction P3 covers both.

### x13 clarification (before any x13 run, 2026-10-11 16:54 BST)
"First sentence of the README" = the first sentence of its first descriptive paragraph: user_modeling's README
opens with a bold "**Sources.**" credit, which is skipped. The seven descriptions are recorded in
glossary-blind.json.

### x13 OUTCOME — 2026-10-12 09:24 BST (final pass from constant-mean-exploration 8154349; rms, strict; pooled plain, vs zero)
The blind entries (glossary-blind.json): Spellcheck, Implicature, Completion, Bridge, Cross-lingual Concept
Retrieval, Inference, and for directed_modulation "Indirect Object Identification" (a wrong name; its one-line
definition is right). glosb:word +0.179 fit / +0.165 val; glosb:desc +0.209 / +0.198 (glos:word +0.189 / +0.196).
- P1 PASS: glosb:word recovers 77 % of fam@fit's fit gain (+0.179 / +0.232; x11's words 82 %).
- P2 PASS: glosb:word - glosx:desc on fit: typo +0.207 [+0.109, +0.304], association +0.167 [+0.088, +0.245].
- P3 PASS: glosb:word - glos:word -0.031 [-0.053, -0.010] on val (-0.010 fit): within 0.06, though reliably a
  little below. The blind desc variant is as good as the picked word (+0.198 val).
Reading: the model writes a glossary as good as mine from one README sentence. But see x14 B: an entry may not be
needed at all.

### x14 OUTCOME — 2026-10-12 09:24 BST (same pass; val, pooled plain, vs zero; fit in brackets)
| arm | val | fit |
|---|---|---|
| glos:word (x11) | +0.196 [+0.155, +0.237] | +0.189 |
| A glosall:word / glosall:desc | +0.170 / +0.155 | +0.176 / +0.154 |
| B glos:none | +0.176 [+0.132, +0.219] | +0.194 |
| C null | +0.013 [-0.013, +0.041] | +0.030 |
| D uncond | +0.061 [+0.025, +0.097] | +0.086 |
| E pcw:4 / pcw:16 | -0.008 / +0.003 | +0.035 / +0.035 |
| F massive:4 / massivez:4 | +0.008 / -0.023 [-0.041, -0.005] | +0.020 / +0.013 |
- P1 PASS: glosall:word +0.170 > 0, 87 % of glos:word's gain.
- P2 FAIL: glos:none - glos:word on val: typo -0.044 [-0.110, +0.022], association +0.010 [-0.049, +0.069];
  pooled -0.020 [-0.048, +0.005]; on fit glos:none is above (+0.194 vs +0.189). Per family (val) glos:none reads
  typo 0.81, association 0.74, basic_readout 0.89, multihop 0.55, multilingual 0.93.
- P3 PASS: null, uncond, pcw:4/16, massive:4, massivez:4 all within [-0.05, +0.10] (uncond the highest, +0.061).
Reading: B is the control x11 needed and it reframes x11, x13 and x23. Model-written varied short English texts,
with no situation named, recover nearly all of the glossary's gain; naming the situation adds at most ~0.02 pooled
(n.s.), perhaps more on typo. What the mean needs is coherent model-written text, not the task: the unconditional
samples (degenerate repetitions, D) and minimal prompts (C) do not give it. x23's per-item situation word (+0.115)
and topic word (-0.109) both sit below glos:none: per-item naming does not help over a generic constant, and naming
content hurts.

## x17 — token-matched synthetic mean (registered 2026-10-11 16:55 BST, before any run)

DM showed no constant μ reads the held concept; the same-token mean does (+0.645 judged), but it needs the task's
data. gentok@self: for each read cell, the mean over OTHER items' model-written reference cells (x8 / x12
generations, already captured at every read token) whose read token equals this cell's; fewer than 3 such cells:
genfam (the pooled synthetic mean). No task data beyond the few written examples genk already uses (here: all
other items' written texts, as genfam). Strict on all 7 families (val, rms); judged on directed_modulation val
(Haiku 5.5, layers 24/36/48/60, about $0.85).
Predictions (DM val, judged):
- P1: gentok - genfam > 0 with the interval above 0.
- P2: gentok >= 0.35 (between the constant centres' 0.18-0.21 and tok@fit's 0.74).
- P3: plain families: gentok within 0.03 of genfam (one read token per item, mostly falls back).

### x17 OUTCOME, directed_modulation and user_modeling — 2026-10-11 17:12 BST (val, rms; run from constant-mean-exploration 5ada22f)
Judged (Haiku 5.5 dev judge, layers 24/36/48/60, content_bound), DM val: gentok 0.487 (genfam 0.211, tok@fit 0.737).
- P1 PASS: gentok - genfam +0.276 [+0.184, +0.382].
- P2 PASS: 0.487 >= 0.35. It sits between the constant centres and tok@fit: gentok - tok@fit -0.250 [-0.355, -0.145].
- P3 pending (plain families run in the final pass).
Strict: DM 0.243; UM 0.869 (= tok@fit's 0.869). No read cell fell back to genfam on DM or UM (every read token
occurs >= 3 times in other items' written references). Not yet fair: x16 asks whether its gain reads the prompt.

### x17 OUTCOME, P3 — 2026-10-12 09:24 BST (final pass, rms, strict)
- P3 PASS: plain families, gentok - genfam +0.003 [+0.000, +0.008] (val and fit); per family 0.000 except
  multilingual +0.012 (val) / multihop +0.012 (fit). Pooled vs zero: gentok +0.170, genfam +0.168 (val).

## x16 — mention control for the item- and token-dependent synthetic centres (registered 2026-10-11 16:56 BST, before any run)

A constant μ (glos:*, glosall:*, fam@plainothers, null, uncond, pcw, massive) is the same vector for every input,
so it cannot read the prompt: fair by construction. The question applies to centres that vary with the item or
token: genk:8, genfam, gentok. umot's mention bank (umot/data/mention-control, 315 items from the bench's 35 DM
pairs: hold X / mention X / hold X + mention Y / absent) is captured here (its capture is on the Mac only) and read
with those centres fitted on the dev DM bank's written references (transfer: the mention bank shares no concept or
carrier with them), via iteration's u1_mention.py rules (fairness only; nothing chosen from it).
Predictions: P1: genk:8 and genfam: pass of X on hold items - pass of X on mention items >= 0.3 (selective, like
u1rel's 0.78 / 0.23). P2: gentok less selective than genfam (token matching is what reads the prompt, U1), but
more than tok@fit (0.82 / 0.59): held - mentioned >= 0.2.

### x16 — DEFERRED (2026-10-12, at the close of the constant-μ section)
Not run. It tests centres that vary with the item or the read token (genk:8, genfam, gentok), outside this section's
constant μ, and needs umot's mention bank captured here. So x17's DM gain for gentok (+0.276 judged over genfam)
stays untested for fairness: it may read the prompt (U1).

## x18 — sentence in isolation (design registered 2026-10-11 16:56 BST; predictions before its run)

The real generalisation test: no family label at read time. (1) Situation naming: the 27B reads the input the lens
reads and names its situation in <= 15 words, as a frame, never its content (a description sharing a content word
of >= 4 letters with the input is rejected and re-asked). (2) A situation library of model-written reference
means: the glossary entries of the families other than the read one (leave-one-family-out) plus generic entries.
(3) μ for an input = the library mean the 27B picks for its description (or, label-free, the library mean nearest
the state at the read cell). Baselines: fam@plainothers (frozen bank), glosall (universal mean), the own family's
glossary mean (the upper bound with the family known). Predictions written before the first run.

### x18 — WITHDRAWN (2026-10-12)
No predictions were written and it was not run. Parts (1) and (3) were tested by x23 / x23b (a per-input situation
word as μ: +0.115 / +0.130 pooled plain, val, below the family-level constants), and x14 B (no entry at all, +0.176,
about the glossary word's +0.196) removes the case for a situation library.

## x20 — the lens's own averaging distribution as μ (registered 2026-10-11 17:12 BST, before any run)

The average-derivative (Stein) reading of the J-lens: J_l is the mean Jacobian over the states it was fitted on, so
the centre that makes J_l (h - μ) a first-order expansion is μ = the mean of h_l over that same distribution. The
released n1000 lens (jlens 0.1.0 `fitting.py`, `examples.load_wikitext_prompts`): the first 1000 wikitext-103-raw
TRAIN records of >= 600 characters, raw (not detokenised), truncated to 128 tokens, no BOS (Qwen3.6 has none, so
force_bos is a no-op), source positions 16 .. seq_len - 2 (`valid_position_mask`). fitmu = the mean of h_l over
exactly those cells, per layer. It differs from fam@corpus8 (wikitext VALIDATION, detokenised, 64 tokens, positions
8 on) only in recipe, so x20 tests whether matching the lens's recipe exactly matters. J++ (koayon/jpp-lenses) records
skip_first 16, max_seq_len 128, 64 prompts and no clusters (num_clusters 0, one map per layer) but not its prompts:
jpp:fitmu uses the same J-lens recipe, an approximation. A per-regime J++ μ needs a clustered J++, which we do not
have and would have to train: out of scope.
Arms: fitmu@self, jpp:fitmu@self, logit:fitmu@self (rms; strict, dev fit and val, 7 families).
Predictions (pooled over the 5 plain families, val, strict, paired):
- P1: |fitmu - fam@corpus8| <= 0.03 (the exact recipe does not matter).
- P2: fitmu - zero < glos:word - zero on typo and on association (the read situation beats the lens's own data).
- P3: jpp:fitmu - jpp:zero within [-0.05, +0.05].

### x20 OUTCOME — 2026-10-11 18:59 BST (rms, strict; run from constant-mean-exploration d48938d; out/captures/fitmu.pt
from 1000 prompts, 110,852 cells)
Pooled plain, vs zero (val 0.593 / fit 0.554): fitmu -0.031 [-0.053, -0.008] / +0.015 [-0.005, +0.035];
fam@corpus8 -0.038 / +0.005; jpp:fitmu - jpp:zero -0.005 [-0.031, +0.020] / -0.005; logit:fitmu - logit:zero +0.003.
- P1 PASS: fitmu - fam@corpus8 = +0.008 [-0.008, +0.023] (val), +0.010 (fit).
- P2 PASS: val, fitmu - zero vs glos:word - zero: typo -0.066 vs +0.286, association +0.020 vs +0.471 (glos:word's
  stores predate the plain regeneration; the final pass rescores them).
- P3 PASS: jpp:fitmu - jpp:zero = -0.005 on both splits.
Reading: the mean over exactly the cells the lens was averaged on is the generic corpus mean again, null to harmful.
With x21 this closes the average-derivative route to μ at the read layers.

## x21 — is J the regression slope on its own data? (registered 2026-10-11 17:12 BST, before any run)

Same cells as x20, in the same pass. Per read layer l (20, 24, ..., 60): accumulate the mean, covariance Σ_l and
cross-covariance C_l = Cov(h_63, h_l) with h_63 the final block's output at the same position (the J-lens's target
layer). B_l = C_l (Σ_l + λI)^-1, λ = 1e-3 tr(Σ_l)/d. If the residual stream were Gaussian, Stein's lemma would make the
average Jacobian equal to B_l (with the per-position Jacobian; the released lens sums over later target positions,
so the match is approximate at best). Compared: cos(vec B_l, vec J_l) and ||B_l - J_l||_F / ||J_l||_F per layer, for
the J-lens and J++. Then B_l is read as a fourth map (ols:, rms) with zero, fam@fit, glos:word and fitmu.
Predictions:
- P1: cos(vec B_l, vec J_l) <= 0.6 at every read layer (J is not the regression slope: the Gaussian reading does not
  hold for this residual stream, so it cannot by itself select μ).
- P2: ols:zero within [-0.05, +0.05] of zero (the J-lens), pooled over the 5 plain families, val, strict.
- P3: the centring gain has the same sign under B as under J: ols:glos:word - ols:zero > 0 pooled.



### x21 OUTCOME — 2026-10-11 18:59 BST (out/x21/compare.json; arms rms, strict, from d48938d)
| layer | 20 | 24 | 28 | 32 | 36 | 40 | 44 | 48 | 52 | 56 | 60 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cos(B, J) | .12 | .14 | .15 | .18 | .24 | .29 | .33 | .41 | .58 | .75 | .89 |
| cos(B, J++) | .11 | .16 | .18 | .19 | .23 | .27 | .29 | .37 | .44 | .62 | .70 |
| cos(J++, J) | .26 | .45 | .46 | .41 | .67 | .73 | .69 | .81 | .72 | .84 | .78 |
| R² held out, B / J / J++ | .39/.03/.02 | .39/.04/.05 | .38/.05/.07 | .39/.06/.08 | .44/.09/.10 | .46/.12/.07 | .47/.16/.10 | .52/.22/.13 | .63/.37/.12 | .72/.52/.15 | .85/.71/.15 |
| ‖B‖ / ‖J‖ | 12.8 | 10.9 | 8.9 | 7.4 | 6.8 | 4.8 | 3.7 | 2.9 | 2.0 | 1.3 | 1.0 |
- P1 FAIL at the top: cos(B, J) <= 0.6 holds at layers 20-52, not at 56 (0.75) or 60 (0.89).
- P2 PASS: ols:zero - zero = -0.041 [-0.079, -0.005] (val), -0.025 [-0.063, +0.013] (fit).
- P3 PASS: ols:glos:word - ols:zero = +0.145 [+0.099, +0.191] (val), +0.118 (fit).
Descriptive: ols:fam@fit +0.216 (val) and +0.232 (fit), = fam@fit's pooled totals (per item they differ on 44 of 393
val items); ols:glos:word +0.104 against glos:word's +0.196.
Reading: through the middle of the network the J-lens is not the least-squares slope of the final state on its own
fitting cells (cos 0.12-0.41, and J explains 3-22 % of the final state's variance where the slope explains 39-52 %);
the two converge only in the last layers, where what is left of the network is close to linear. So the
Gaussian / average-derivative reading does not hold where we read, and cannot select μ there. Read as a lens, the
slope map is worse uncentred and as good with the family mean: centring on the read situation matters for any map.

## x23 — which representation of the context? (registered 2026-10-11 18:10 BST, before any run)

The user's two questions: is the input's own sentence mean a context, and what if the model has to name the context in
one word? Read through x22's frame (global-workspace contexts vs contents), three ways to represent the context of one
input, none needing the task's data. All strict, rms, dev fit and val, 7 families; references already scored: zero,
fam@fit (+0.216 pooled plain val), glos:word (+0.196), glosall:word (+0.170), fam@plainothers (+0.112), and
iteration's knnx8@fit (the 8 nearest fit read cells of any family, keyed by the read state itself).

A. The input's own context. `sent:<a>`: μ = a × the mean of the input's own states at positions 1 .. t (position 0, the
   attention sink, left out; t the read cell, included); `sentx:<a>`: positions 1 .. t-1. a ∈ {0.25, 0.5, 1}, chosen
   on fit, reported on val. Known: prev4 (the last 4 positions, iteration S3) 0.31 macro against zero's 0.51 (fit, cos).
B. Neighbours keyed by context. `sentnn:8@fitall` / `sentnn:8@fitothers`: μ = the mean of the read-cell states of the 8
   fit cells (every family / every other family) whose own sentence mean (as in `sentx:1`) is nearest at that layer
   (cosine), the read item excluded. The sentence mean is used as a KEY to find similar situations, never subtracted.
C. One word. The pinned 27B reads the text the lens reads (never a target; greedy, thinking off) and answers in one
   word. `word:ctx`: "name the kind of situation this text is in: what is happening at its end, not what it is about".
   `word:topic` (the content control): "say what this text is about". μ = the mean of 32 texts the model writes from
   that word (x11's word prompt, seeds salted "x23"; the chat families' format line as in x12), read in the family's
   render; one set per distinct (word, family). If one kind yields more than 300 distinct words, 16 texts per word.

Predictions (pooled over the 5 plain families, val, vs zero):
- P1: sent:1 and sentx:1 each <= -0.05 (an input's own mean is mostly its content).
- P2: no a of sent / sentx beats zero by >= +0.03 on val.
- P3: user_modeling: sent:1 >= zero (its prefix is mostly the chat template and system message: context).
- P4: sentnn:8@fitall >= +0.15, sentnn:8@fitothers >= +0.112, and sentnn:8@fitall >= knnx8@fit (the sentence mean
  keys situations better than the read state, which carries the content).
- P5: word:ctx >= +0.146 (within 0.05 of glos:word, with no family label).
- P6: word:topic <= word:ctx - 0.10 (naming the content subtracts it).
- P7 (diagnostic): the ctx word is an accepted target form on < 5 % of scored items; the topic word's rate reported.
- P8: directed_modulation (judged, Haiku 5.5, layers 24/36/48/60, about $2.50, asked for before it runs): word:ctx,
  the fit-chosen sent arm and sentnn:8@fitall each within +0.15 of zero.
word:ctx and sentnn vary with the input, so x16's mention control applies to them before any fairness claim.

### x23 OUTCOME, A and B — 2026-10-11 20:29 BST (rms, strict; context captures and arms from 3ddba65; arm names
as built: sentnn:8:all@self / sentnn:8:others@self for the registered sentnn:8@fitall / @fitothers)
Pooled plain, vs zero (val 0.593 / fit 0.554):
| arm | val | fit |
|---|---|---|
| sent:0.25 | -0.079 [-0.107, -0.053] | -0.040 |
| sent:0.5 | -0.145 [-0.181, -0.112] | -0.103 |
| sent:1 (= sentx:1) | -0.282 [-0.328, -0.239] | -0.244 |
| sentnn:8:all | +0.181 [+0.135, +0.224] | +0.214 |
| sentnn:8:others | +0.028 [-0.008, +0.064] | +0.073 |
| knnx8@fit (iteration, keyed by the read state) | +0.229 | +0.275 |
sent:1 and sentx:1 read identically, by algebra: h - mean(1..t) = (t-1)/t (h - mean(1..t-1)), and both readouts
ignore scale. At 0.25 / 0.5 they differ by under 0.01.
- P1 PASS: sent:1 = sentx:1 = -0.282 (val); by family typo 0.57 -> 0.18, association 0.25 -> 0.03, multihop 0.57 -> 0.12.
- P2 PASS: every strength is below zero on both splits, monotone in a (fit choice: 0.25, val -0.079).
- P3 FAIL (narrowly): user_modeling sent:1 - zero = -0.03 [-0.13, +0.07] (val), 0.00 (fit); sent:0.5 +0.07 on val
  but 0.00 on fit.
- P4 SPLIT: sentnn:8:all >= +0.15 holds (+0.181); sentnn:8:others +0.028 < +0.112 fails; sentnn:8:all - knnx8 =
  -0.048 [-0.079, -0.020] (val), -0.060 (fit): the read state is the better key, not the sentence mean.
Chat families (descriptive, strict): user_modeling val sentnn:8:all +0.20, knnx8 +0.23, tok@fit +0.25;
directed_modulation val sent:1 -0.05, sentnn:8:all +0.04, knnx8 +0.26 (= tok@fit).
Reading: an input's own mean is its content, and subtracting any share of it deletes what the lens should read. As a
key for finding similar situations the sentence mean mostly re-finds the input's own task: without that task in the
pool it is worth a third of the plain-prompt bank. P5-P8 (one word) pending.

### x23 OUTCOME, C (word:ctx) — 2026-10-11 20:48 BST (rms, strict; naming and texts from 3ddba65: 193 distinct
situation words over 1,070 inputs, 32 texts each, no fallbacks)
| val (fit) | typo | assoc | basic | mhop | mling | UM | DM | pooled plain vs zero |
|---|---|---|---|---|---|---|---|---|
| zero | 0.57 | 0.25 | 0.86 | 0.57 | 0.95 | 0.62 | 0.07 | — |
| word:ctx | 0.77 | 0.53 | 0.91 | 0.57 | 0.91 | 0.74 | 0.09 | +0.115 [+0.076, +0.155] (fit +0.126) |
| glos:word | 0.86 | 0.73 | 0.86 | 0.60 | 0.95 | 0.74 | 0.09 | +0.196 (fit +0.189) |
- P5 FAIL: +0.115 < +0.146; word:ctx - glos:word = -0.081 [-0.112, -0.053] (val), -0.063 (fit); - glosall:word
  -0.056. user_modeling +0.115 [+0.033, +0.213] (= glos:word); DM +0.027 (strict).
- P7 SPLIT: the situation word is an accepted target form on 22 / 528 scored items (4.2 %, val) and 31 / 534 (5.8 %,
  fit), all but one of them association (21 / 102 and 30 / 102).
- P6 (topic) and P8 (DM judged) pending.
Where the gap comes from (by the word named): typo items named "typo" read as well as glos:word (val 0.86 / 0.86,
fit 0.93 / 0.93); items named "suspense" (the model's word for any text cut off before its answer) gain little (val
0.59 -> 0.62, glos:word 0.79). On association, when the "situation" word IS the answer (the scene's evoked activity),
the centre gains nothing (0.24 -> 0.24; fit 0.20 -> 0.23) and never passes falsely; on the other items 0.26 -> 0.60
(glos:word 0.72). Reading: one model-named word is as good as the hand-picked word when it names the situation; it
loses by naming a generic frame ("suspense") or, on association, the content itself, whose situation is its answer.

### x23 OUTCOME, C (word:topic) — 2026-10-11 22:16 BST (841 distinct topic words, 16 texts each by the registered rule)
val: typo 0.66, association 0.16, basic_readout 0.89, multihop 0.17, multilingual 0.84, UM 0.75, DM 0.03.
- P6 PASS: word:topic - word:ctx = -0.224 [-0.267, -0.181] (val), -0.209 (fit); word:topic - zero = -0.109
  [-0.155, -0.066] (val), -0.083 (fit). Multihop 0.57 -> 0.17: the topic word names the bridge or its country.
Reading: the same pipeline, one word apart: naming the situation gains +0.115, naming what the text is about loses
-0.109. The cleanest context / content contrast in the study.

## x23b — helping the model name the situation (registered 2026-10-11 21:42 BST, before any run)

User request after x23 C: in-context examples or a better prompt so the model picks the right word. x23 C lost to the
hand-picked word in two ways: a generic frame ("suspense" for any text cut off before its answer) and, on
association, the answer itself as the "situation". Three naming prompts, each one word, greedy, thinking off, on the
same texts the lens reads:
- `ctx2` (rules): name the kind of task or situation the text is in at its end, as a reader would recognise the
  activity; not a word from the text, not what it is about, not the missing word; no vague word ("suspense",
  "incomplete", "completion", "truncation", "continuation"); illustrated only by off-bench kinds (a recipe, a riddle,
  a weather report, a love letter, a sports commentary, a legal disclaimer).
- `ctx3` (ICL): x23's own ctx instruction with 8 worked examples as earlier turns, all off-bench situations: a
  rhyme, a recipe, a knock-knock joke, a complaint letter, code, a weather forecast, a riddle, a sports commentary.
- `ctx4`: the rules of ctx2 with the 8 examples of ctx3.
None of the examples or rules names a bench family's situation. μ as in x23 C: 32 texts per distinct (word, format)
from x11's word prompt; a word that already has texts in an earlier x23 set reuses them (same prompt and generator,
another seed). Arms word:ctx2 / word:ctx3 / word:ctx4 @self|rms, strict, dev fit and val, 7 families. The prompt is
chosen on FIT (best pooled plain gain over zero); val is reported for all three.
Predictions (pooled over the 5 plain families):
- P1: the fit-chosen prompt beats word:ctx on val (+0.115) by >= +0.03 and reaches >= +0.146 (x23's P5 bar).
- P2: its situation word is an accepted target form on < 5 % of scored items overall and < 10 % on association.
- P3: user_modeling: >= zero; directed_modulation: within +-0.05 of zero (strict).

### x23b OUTCOME — 2026-10-11 22:33 BST (rms, strict; from 04dc4aa; distinct words ctx2 98, ctx3 127, ctx4 114)
| pooled plain vs zero | fit | val | val typo / assoc / mhop / mling |
|---|---|---|---|
| word:ctx (x23) | +0.126 | +0.115 | 0.77 / 0.53 / 0.57 / 0.91 |
| word:ctx2 (rules) | **+0.174** | +0.130 [+0.092, +0.168] | 0.84 / 0.54 / 0.54 / 0.95 |
| word:ctx3 (ICL) | +0.121 | +0.112 | 0.80 / 0.52 / 0.53 / 0.94 |
| word:ctx4 (both) | +0.139 | +0.109 | 0.75 / 0.57 / 0.51 / 0.95 |
| glos:word | +0.189 | +0.196 | 0.86 / 0.73 / 0.60 / 0.95 |
Chosen on fit: ctx2 (fit: +0.048 [+0.018, +0.078] over word:ctx).
- P1 FAIL: on val ctx2 - word:ctx = +0.015 [-0.015, +0.048], and +0.130 < +0.146; ctx2 - glos:word -0.066.
- P2 SPLIT: ctx2's word is a target form on 20 / 528 scored items (3.8 %), but on 19 / 102 association items (19 %).
  The ICL prompt leaks most (association 28 / 102).
- P3 PASS: user_modeling +0.098, directed_modulation +0.027 (strict).
Reading: the rules remove the generic frame (no "suspense"; typo 0.77 -> 0.84 on val, = glos:word on fit), but the
fit gain mostly does not carry to val, and association does not move (0.54 against glos:word's 0.73): its situation
is an evoked activity, and the model names that activity, the answer, on a fifth of items whatever the prompt says.
Off-bench worked examples do not help (ctx3 = ctx). A closed list (x22's sit:pickg) is the remaining lever for the
naming; on association the family-level word stays ahead because it never names the item's own answer.

### Final pass — 2026-10-12 09:24 BST (from constant-mean-exploration 8154349: every arm x 14 dev banks, --force; then CM battery)
- No errors. The five judged DM val arms re-read byte-identical to their judged readouts.
- The re-score on the regenerated plain references changes no recorded headline: x9 gen / genfam, x10 genk:8, x11
  glos:word / glos:desc / glosx:desc and x20 P2 (glos:word typo +0.29, association +0.48 on val) all match to 0.01.
- Readers (x15 was never registered: descriptive). Val, pooled plain, vs zero|rms: jpp:zero +0.216, jpp:glos:word
  +0.237 (+0.041 [+0.013, +0.069] over glos:word), jpp:fam@fit +0.247; logit:zero -0.051, logit:glos:word -0.041
  (-0.237 vs glos:word), logit:fam@fit +0.094. Centring adds to J++ on every arm; on the logit lens a constant
  centre hurts.

### Strict + forms (eval-pipeline 5d88875, merged as 52f67f0) — 2026-10-12 09:37 BST, descriptive; strict stays of record
All banks rescored (evaluate.py --rescore; user_modeling/bench skipped: its local summary predates scored_ids, and
the remote copy is Anthony's, left alone). Pooled plain, vs zero, val (fit): glos:word +0.204 (+0.204), glos:none
+0.183 (+0.186), glosb:word +0.170 (+0.186), glosb:desc +0.204 (+0.212), word:ctx +0.117 (+0.126), word:ctx2 +0.137
(+0.184), word:topic -0.115 (-0.083), jpp:zero +0.219 (+0.252); every arm moves by <= 0.015.
No conclusion changes. glos:none - glos:word: -0.020 [-0.046, +0.005] val, -0.018 [-0.043, +0.008] fit (strict had
+0.005 on fit); on typo it is -0.098 [-0.174, -0.033] on fit, -0.033 [-0.099, +0.033] on val, so naming the
situation may matter on typo only (x14 P2 stays FAIL: association +0.010 on both scores).


## x24 — why does model-written text work as μ? (registered 2026-10-12 10:00 BST, before any run)
x14 B: 64 model-written "varied short texts" (glos:none) give +0.176 pooled plain (val, strict, rms); standalone
wikitext sentences (fam@sents) give +0.015. Both end in a period and are read there, so the read token is the same
kind. They differ in source (model / human), length (median 14 / 24 tokens) and style (generic scene prose /
encyclopedic, named entities). Four new reference sets, 64 per plain family, each family its own seeded draw (as
glos:none), plain render, one constant μ per layer (GlossaryMean, glos:<variant>@self|rms):
- wshort: wikitext sentences of 10-18 tokens (glos:none's own 10-90 % range is 11-17), read at the final token.
- mwiki: model-written, x11's generator and sampling, prompt "Write 8 varied short sentences in the style of an
  encyclopedia article." (model source, wiki style), read at the final token.
- mcut / wcut: glos:none's texts / wshort's sentences without their last word, read at the token before it (mid
  sentence, like the bank prompts, which stop before a one-word answer).
Strict, rms, plain families, dev fit and val; nothing chosen from val.
Predictions (pooled plain, val):
- P1 (length is not it): wshort - fam@sents within [-0.04, +0.04].
- P2 (style, not source): mwiki <= glos:none - 0.06, and mwiki is closer to wshort than to glos:none.
- P3 (read position is not it): mcut >= glos:none - 0.03; wcut within [-0.05, +0.05] of wshort.

### x24 OUTCOME — 2026-10-12 10:32 BST (refs from 2c072c1, scored from 81b2d60; rms, strict; pooled plain vs zero)
| μ (64 texts per family, read at their last token) | val | fit |
|---|---|---|
| fam@sents: wikitext sentences, median 24 tokens, at the period | +0.015 [-0.015, +0.048] | +0.033 |
| wshort: wikitext sentences, 10-18 tokens (median 15), at the period | +0.046 [+0.013, +0.079] | +0.043 |
| mwiki: model-written, encyclopedic, median 16-20, at the period | +0.117 [+0.081, +0.153] | +0.126 |
| glos:none: model-written, no entry, median 14, at the period | +0.176 [+0.132, +0.219] | +0.194 |
| wcut: wshort without its last word, mid-sentence | -0.043 [-0.074, -0.015] | +0.005 |
| mcut: glos:none without its last word, mid-sentence | +0.010 [-0.028, +0.048] | +0.050 |
- P1 PASS: wshort - fam@sents +0.031 [+0.010, +0.051] (val), +0.010 (fit): length adds a little at most.
- P2 FAIL: mwiki - glos:none -0.059 [-0.092, -0.025] (val; fit -0.068), and mwiki sits closer to glos:none than to
  wshort (mwiki - wshort +0.071 [+0.041, +0.102]). Source and style each carry about half: at matched length,
  human -> model in the same style +0.071, encyclopedic -> generic prose from the same model +0.059.
- P3 FAIL, strongly: mcut - glos:none -0.165 [-0.206, -0.125]; wcut - wshort -0.089 [-0.122, -0.056] (fit -0.144 /
  -0.038). The same texts read one word before their end lose almost all of the gain.
Reading: the model-written μ works because it is (a) the mean of sentence-END states, (b) of text the model itself
writes, (c) in plain generic prose; read position matters most. A mid-sentence mean is null or harmful (here, and
fam@corpus8 -0.038 earlier), although the bank prompts are themselves read mid-sentence. A hypothesis for the
section's write-up, not tested: a mid-sentence state holds the model's generic "next content word" component, which
a mid-sentence μ removes from the read cell along with the latent; a sentence-end μ removes only the shared offset.
Per family the position effect is not uniform: basic_readout reads best with mcut (0.94 val).
Per family (val, paired; added 2026-10-12 at the user's request, the pooled split above hides it): source and style
do not each carry half everywhere. typo: source (mwiki - wshort) +0.19 [+0.10, +0.27], style (none - mwiki) +0.04
n.s.; association: style +0.20 [+0.11, +0.28], source +0.05 n.s. (fit +0.13); position (mcut - none): association
-0.37, typo -0.19, multihop -0.12, basic_readout +0.06; basic_readout and multilingual move by <= 0.06 throughout.

## x25 — J++ with the data-free centres (registered 2026-10-12 10:00 BST, before any run)
Final pass (dev): jpp:zero +0.216 pooled plain val; with a centre: glos:word +0.020 [-0.010, +0.051] over it,
glosall:word +0.018, glosb:word -0.005; task-data centres more (fam@fit +0.031, tok@fit +0.041). Bench (x19b):
jpp:glos:word - jpp:zero +0.010 pooled, association +0.200. Added here: jpp:glos:none and jpp:glosb:desc (all 7
families), and jpp: with x24's four sets (plain families). Strict, rms, dev fit and val.
Predictions (val):
- P4: jpp:glos:none - jpp:zero within [-0.01, +0.04] pooled plain, and >= +0.08 on association.
- P5: no data-free centre adds >= +0.03 to jpp:zero pooled plain with its interval above 0.

### x25 OUTCOME — 2026-10-12 10:32 BST (same run; rms, strict; vs jpp:zero, pooled plain)
| J++ + centre | val | fit | association, val |
|---|---|---|---|
| jpp:zero | 0.809 (+0.216 over zero, 0.593) | +0.252 over zero | 0.66 |
| + glos:word | +0.020 [-0.010, +0.051] | +0.008 | 0.79 |
| + glos:none | +0.000 [-0.033, +0.033] | +0.010 | 0.76 |
| + glosb:desc | +0.031 [+0.005, +0.056] | +0.013 | 0.79 |
| + glosall:word | +0.018 | +0.008 | 0.78 |
| + x24 sets (wshort / wcut / mwiki / mcut) | -0.005 / -0.018 / +0.008 / -0.025 | -0.008 / -0.015 / +0.003 / -0.040 | 0.69-0.75 |
| + fam@fit (task data) | +0.031 [+0.000, +0.061] | +0.043 | 0.79 |
- P4 PASS: jpp:glos:none - jpp:zero +0.000 pooled (val), association +0.108 [+0.029, +0.186].
- P5 FAIL, narrowly: jpp:glosb:desc +0.031 [+0.005, +0.056] on val (one of eight centres; +0.013 n.s. on fit).
Chat families (val): jpp:glos:none +0.033 UM, +0.027 DM, neither interval above 0.
Reading: on top of J++ a data-free centre adds about +0.10 on association and costs about 0.06 on basic_readout,
so the pooled gain is 0 to +0.03; the task's own mean adds little more (+0.03 / +0.04). As on the bench (x19b:
jpp:glos:word 0.854 vs jpp:zero 0.844), J++ with a glossary centre is the best data-free reader, by a small margin.
Per family (val, vs jpp:zero): every centre helps association only (+0.11 to +0.14, intervals above 0); basic_readout
-0.03 to -0.06 (n = 35, n.s.); jpp:glos:none costs multilingual -0.05 [-0.10, -0.01]; typo, multihop, UM, DM within
0.05, n.s.
