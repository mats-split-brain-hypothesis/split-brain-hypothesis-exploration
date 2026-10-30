# Abstract-concept mu: candidate concepts per WorkspaceBench family (2026-10-10)

The README idea (line 19): mu_l = the representation of the most abstract word that
represents the category (bunch of typos -> "typo"), optionally as a steering vector with
tuned magnitude. `notes/synthesis.md` lists it as not done. This note picks the words and
positions the idea in the mu ladder. Bench clone restored at
`third_party/workspace-bench` @ 92d763e (the symlinks work again).

## Why this arm is worth running

The own-family mean is the strongest fair-ish centre so far (rms 0.55/0.58/0.59 ->
0.67/0.68/0.77 at 4B/9B/27B), but synthesis lesson 2 says much of its gain is that on the
bench it is effectively **token- and position-matched** (every item reads the same template
cell). The family mean plausibly decomposes as

    mu_fam  ~=  token/position prior  +  category direction  +  mean of item specifics (~0)

An abstract-word mu isolates the middle term: it carries the category semantics ("this is a
typo-correction context") with **no** template, token or position information, and it needs
no item bank — only the family's name. So it separates two explanations of the family
mean's gain:

- If G2 + alpha*v_concept recovers most of fam's gain -> the family mean is just
  "token prior + what the task is about", and a label-free mu only needs a cheap category
  guess (which an unsupervised method could produce, e.g. from the model's own prediction).
- If it recovers nothing beyond G2 -> the gain lives in the residual item-matching, and the
  open problem (label-free context-matched mu) is harder than a category label.

**Fairness position.** One bit of label information (the family's identity), strictly less
than the own-family mean (which sees real items at the exact read cell). Sits between
G1/G2 and fam on the fair axis. Subtracting the representation of the *item's own target*
would be cheating (that is the "optimal mu" in-sample ceiling, a different row).

## Two abstract words per family, not one

The "most abstract word" is ambiguous between:

1. **Task word** — what every *prompt* in the family shares ("typo", "poem", "riddle",
   "code"). This is what the category direction of mu_fam should encode.
2. **Answer-class hypernym** — the type of the *latent* ("colour", "number", "emotion").
   This is what the model is "holding" at the read cell, minus which specific one.

For typo they nearly coincide; for brew they are far apart (task = rule-puzzle, hypernym =
colour). Subtracting the hypernym is the more interesting arm: `h - v_colour` keeps the
*deviation of green from generic colour*, which is exactly the shape of signal centring is
supposed to expose. It is also the riskier one — too specific and it leans toward the
answer. **Abstraction level is a dial on the fair axis**: concept of everything (~G1) <-
hypernym <- answer's basic category <- the answer itself (cheating). Worth running 2-3
rungs of the hypernym ladder on one family (brew: colour -> property -> concept) to see
the dial move.

## The table

Checked against each family README and sampled `items.json` golds. Both lineages' banks are
the same families; jle's dev bank v2 uses the same family keys.

| family | scored latent | task word | answer-class hypernym | notes |
|---|---|---|---|---|
| typo | the corrected word (February) | **typo** / misspelling | spelling / word | prompt-only floor is 1.00 here; report beside it |
| typo_mt | corrected multi-token form | **typo** | phrase; **number** for the 15 `tyh-arith-*` | |
| multilingual_typo | correction + language | **typo** | word + **language** | language is a scored unit: check subtraction doesn't hurt it |
| basic_readout | obvious next concept | **answer** | per subfamily: **fact** (entity), **number** (processing), **preference** (implicit) | subfamily-level words are still label-light |
| basic_readout_mt | multi-token next concept | **answer** | **name** (dynasties, compounds, processes) | |
| multihop | silent bridge (iron, May) | **fact** (prompts literally start `Fact:`) | **entity** / referent | bridge = referent of a descriptive phrase |
| multihop_mt | multi-token bridges (Simula 67) | **fact** | **name** | |
| multilingual_multihop | bridge, en/zh form | **fact** | **name** + language | |
| multilingual | English concept of the answer | **translation** | **meaning** / concept | latent is language-independent by design |
| multilingual_mt | concept + language | **translation** | concept + **language** | |
| arithmetic_intermediates | unwritten intermediate (−51) | **arithmetic** / calculation | **number** | |
| chain_intermediates | chain intermediates | **arithmetic** | **number** | |
| brew_intermediates | colour after first stir | **puzzle** / rules | **colour** | cleanest hypernym in the bench: 12-word palette; best family for the hypernym-ladder probe |
| association | unnamed implied concept (carnaval, chess, child) | **scene** / evocation | **concept** / theme | golds too heterogeneous for a tight hypernym; task word is the real arm here |
| conjunctive_association | compound state ("grief over … death of her child") | **story** / vignette | **emotion** / emotional state | contrast pairs differ in the state word (grief vs guilt) |
| role_bound_association | directed relation (who chased whom) | **story** | **action** / event | binding is the latent; a single word can't carry direction — expect null, itself informative |
| directed_modulation | held / suppressed concept | **instruction** / secrecy | **thought**; **secret** for secret+preference items | DM read cells vary -> abstract mu must ride on tok1/ctr-tok, not alone |
| multi_concept_directed_modulation | 1-3 held concepts + binding | secrecy | **thought** / imagined scene | |
| moral_rationale | the consideration the model weighs | **dilemma** / ethics | **reason** / value | deliberative items hold two reasons |
| buggy_code | the bug (or none, on clean twins) | **code** | **bug** / error | clean twins: subtracting "bug" must not *induce* bug reports — a precision check for free |
| hallucination | — (precision instrument) | conversation / chat | — | no target latent; only sanity-check that centring doesn't raise the rate |
| jlens_concept_pr | — (precision instrument) | — | — | same |
| jailbreak_recognition | model's own read: this is a jailbreak | **jailbreak** | **manipulation** / trick / deception | the latent is an assessment, not an entity |
| agentic_misalignment | model's plan to misbehave | **scenario** (agentic email env) | **scheme** / plan / wrongdoing; per-scenario: blackmail, leak, sabotage | per-scenario words edge toward cheating — that's the dial again |
| user_modeling | inferred user attribute (paraguay, south korea) | **user** / profile | per stratum: **country**, continent, gender, occupation; generic: **identity** | tok1 already best here; test alpha*v on top of it |
| poetry | committed rhyme word (led, game, black) | **poem** / rhyme | **word** (any English word — weak) | task word "rhyme" doubles as both |
| baselines | — (floors, not a family) | — | — | |

## Construction recipe (proposed)

1. **Carrier capture.** h_l at the last token of the word in k neutral carriers:
   `"typo"`, `"a typo"`, `"Concept: typo"`, `"Think about typos."` (plain render, matching
   the family's render where possible); average over carriers.
2. **Contrastive (steering) variant.** Same carriers with a neutral placeholder word
   ("thing") subtracted out: v = mean_c[h(c, word)] − mean_c[h(c, "thing")]. Removes the
   carrier's own template/token prior, leaving the concept direction. This is the README's
   "steering vector" reading.
3. **Magnitude.** mu = alpha * v with alpha tuned on dev bank v2 only (the real mean has
   ||mu||/||h|| = 0.81-0.98; an isolated word rep will not land there by luck). alpha = 1 and
   alpha matching the family-mean norm are the two pinned defaults.
4. **Composition.** Abstract mu alone is not token/position matched, so the arm of record
   is additive: mu = G2(token) + alpha * v_concept, with v alone as a diagnostic arm.

## Position: nothing to subtract literally, so condition the mean on it

README line 13 says "look into positional embeddings". Qwen3.6-27B (like all Qwen decoder
models) uses **RoPE**: position enters by rotating Q/K inside every attention block. There
is no additive positional-embedding vector in h_l, so "remove the position embedding" has
no literal reading here (in a GPT-2-style model you could subtract `W_pos[p]`; not in this
one). What exists instead is position-*correlated* structure that attention and MLPs write
into the residual: x101 already hit it ("the first positions carry outsized norms", hence
its MIN_POS cutoff — the attention-sink region), and the mention-control result (separation
only at sentence-final "." cells) is position structure too.

The functional analogue is a **position-conditioned corpus mean**:

    P:  mu(l, p) = E_corpus[ h_l | position p ]        (binned / smoothed over p)

- This is the *fair* cousin of carpos (same sentence, same position), which won on DM but
  failed the mention control because its reference reads the prompt. P's reference is
  neutral corpus text, so it carries no prompt content by construction.
- **Coordinate choice matters.** Two candidates: absolute index (captures the sink region
  and early-position norm decay) and **distance from end of prompt** (likely the right
  coordinate for bench reads at final-prompt tokens, where "2 tokens before generation
  starts" is the shared situation). Run both; absolute p pooled into log-spaced bins
  beyond ~64.
- **P vs G2.** Tokens and positions are correlated on bench (template tokens sit at fixed
  offsets from the end), so G2 may already absorb most of P there; the families where read
  cells vary (DM, agentic_misalignment, user_modeling, hallucination) are where P can add
  something G2 cannot. The joint (token, position-bucket) mean G2xP is the finer rung but
  needs more reference tokens per cell (sparsity — watch n per bucket).
- **Implementation is small**: `x101_generic_mean.py`'s accumulator already holds
  `[n_layers, n_pos, d]` residuals per passage and keys float64 sums by token id; add a
  per-position (and per token x pos-bucket) sum alongside. `jle/out/` is not live, so the
  means must be regenerated anyway (pod for 27B; 4B/9B were jle's local models).

The decomposition in "Why this arm is worth running" then gains a term:

    mu_fam  ~=  token prior (G2)  +  position prior (P)  +  category direction (alpha*v)  +  residual

## First experiment sketch

Arms {0, G2, P, G2+P, v alone, G2+P + alpha*v (task word), G2+P + alpha*v (hypernym), fam} at 27B on
3-4 families spanning the table: **brew** (tight hypernym), **typo** (task=hypernym, big
fam gain 0.55->0.91), **association** (heterogeneous golds, biggest fam gain), **multihop**
(fam was mixed). Captures for the x89/x90 banks are archived on the desktop
(`jle/notes/archive-manifest/`); association residuals exist as `jle/out/x96-capture-*.pt`
per synthesis, but spills were not imported — check what is live before planning pod time.
Register predictions per `jle/notes/predictions.md` before judging. Headline read: how much
of (fam − G2) do P and alpha*v each recover on top of G2, per family.

Prediction to register (mine): v alone ~ null on bench template cells (lesson 2);
G2 + alpha*v recovers a visible minority of the fam gain on association and
conjunctive_association (semantically coherent categories), little on typo (its fam gain
looks like token-prior removal at a fixed cell), and the brew hypernym ladder shows
colour > property > concept.

## Where the global-workspace concept set stands after x1-x6 (2026-10-10)

As SUBTRACTION material the GW content types failed: per-sample dictionary words = the
derangement control pooled (x2, x3), and content-type words actively delete the signal where the
answer instantiates the type (user_modeling -0.39). What survives of the taxonomy:
(1) the frame / content split it made visible — the workspace's situational FRAME is subtractable
("typo": +0.09..+0.18 held out across x3/x5), its content type never is; (2) the model can NAME
the workspace content type per sample (the 27B self-labels, 85 % on typo) — a capability result
independent of mu; (3) as a diagnostic, the taxonomy predicts which reads a constant helps
(frame-salient, content-orthogonal cells) and which it harms. Untested GW material: the
self_meta group (secret / thought / reason / plan), which lives in DM, moral_rationale and
agentic_misalignment — the families where frames should be strongest ("I am holding a secret") —
plus group-level directions (one vector per GW type; x2's derangement result predicts null) and
frame PROPOSITIONS as carriers ("There is a typo in this sentence." as a state, not a word).
DM is the decisive next test: umot's tok1 took DM judged 0.21 -> 0.82, and a secret-frame mu
needs no token matching to try.

## x1 results (2026-10-10, typo only; registration and outcome in notes/predictions.md)

Both arms ran at 27B on typo fit/val (dev bank), strict free tier, captures and reads local
(3x A100 box). Val, n=91, vs zero 0.692/0.571 (cos/rms); fam@fit = 0.923/0.901.

- **Position: null.** pos@corpus -0.011 cos / -0.055 rms vs zero; fam@corpus8, tok@corpus8 and
  fam@sents the same or worse. On typo (reads at positions 5-11, where the early-position norm
  structure lives) a position-matched neutral-corpus mu removes nothing the readout cares
  about. The "position prior" term of the decomposition is ~0 here; P still untested where read
  cells vary (DM, user_modeling).
- **Abstract word: real but partial, and readout-dependent.** cpt:typo:1 beats the matched
  giraffe control by +0.194 cos [+0.097,+0.291] (also +0.097 at alpha 0.5), taking zero 0.69 ->
  0.78-0.80; under rms the concept-specific part is +0.043 [-0.054,+0.140] and the arm's gain
  is mostly the generic any-word norm effect (+0.077). "misspelling" carries about half the
  typo effect (+0.086 cos, CI includes 0); alpha = 2 harms; the carrier-free contrast direction
  (cptc) is null-to-harmful on its own.
- **The family mean stays 0.12-0.22 ahead** of the best abstract-word arm (paired, outside the
  bootstrap). With token, position, genericity and category semantics all now measured and
  insufficient, what remains of mu_fam's gain on typo is item-level family content at the read
  cell (correction-shaped / orthographic structure). That sharpens the open problem: the
  label-free mu must reconstruct that, not the category.

Revisits to the sketch above: the prediction "little on typo" was wrong in an interesting way —
the concept component is the one piece that does transfer under cos; the corpus rungs
(G1/G2/P/sentence-end), which x101 measured as small-positive pooled, are flat-to-negative on
typo val at 27B.

## Per-sample selection from a global dictionary (x2, 2026-10-10)

The dictionary (`data/abstract_concepts.json`, 30 words + 3 neutral) spans the six single-token
families' data: family words (typo/theme/answer/fact/meaning/identity), stratum words from bank
metadata (basic_readout subfamilies; user_modeling `attr_class`: country/continent/gender/
occupation/religion/diet/marriage/pet/job/age) and data-level hypernyms (month, element, organ,
number, game, place, organization, person, event, emotion, colour, word, language).

Label-free GEOMETRIC selection is weak on typo fit: argmax cosine of (h − sentence-end mean)
against neutral-contrast carrier directions picks "typo" for 22 % of cells (26 % restricted to
L >= 40, z-scored no better); selection in READOUT space (z-scored lens scores of each word's own
tokens against the sentence population) reaches 36 % with saner confusions ("age" absorbs the
rest). The category is simply not the dominant linear component of h at the read cell against 30
alternatives. Hence the judged labels: the pinned 27B itself picks the fittest word per sample
from the item's text + the dictionary (never the target, never the family name) —
`experiments/label_concepts.py`, mode `dict:llm`. Fairness: one category word per item, derived
from the prompt; the derangement arm controls specificity. The judge's labels are good where the
frame is salient (typo 85-86 % "typo") and sane hypernyms elsewhere (multihop: place / element /
month / number; basic_readout implicit: preference); weakest on user_modeling (58 % "answer").

### x2 outcome: the per-sample dictionary is a pooled NULL, with a sign-flip worth keeping

Full outcome in `notes/predictions.md`; table in `out/eval/x2-pooled.md`. Pooled over the six
families (n=472): judged per-sample words = derangement control exactly (+0.000 [-0.032,+0.032]
under cos); fam@self stays +0.155/+0.214 ahead of the best dict arm. Word-matched minus wrong-word
at alpha 1, cos, per family: typo +0.20, multihop **-0.11**, everything else ~0. The split is
between **frame words** (what kind of situation the context is: "typo" — the correction is not
itself a typo) and **content hypernyms** (the answer's own category: "country", "place", "month").
Frame subtraction cleans the readout; hypernym subtraction deletes the subspace the answer lives
in — user_modeling with `attr_class` words is the limit case (0.47 -> 0.19). High-baseline
families (zero cos 0.82-0.94) also have little headroom and real downside for any constant
alpha=1 mu. So the GW-flavoured taxonomy that survives x2 is not "one abstract word per latent"
but: **mu may subtract the workspace's frame, never the content's hypernym.** Beyond typo-like
families, the abstract-word mu is not a path to the family mean's gain, whose content x1 and x2
together show is item-level, not categorical.
