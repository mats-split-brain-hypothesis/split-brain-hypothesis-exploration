# x22: a glossary of situations (global-workspace contexts) — DRAFT

**Status: DROPPED 2026-10-12, never registered or generated.** x14 B (model-written texts with no entry at all,
+0.176 pooled plain, val) about matches the glossary word (+0.196), which leaves little for a closed situation list
to win. Kept as a record. The original status follows.

**Status (before): draft for editing. Nothing is generated or registered yet.** Edit the tables and the predictions freely;
once agreed, the predictions go into `notes/predictions.md` as x22 (before any generation) and the tables become
the generator's input exactly as they stand here.

## Why: contexts, not contents

Global workspace theory (Baars 1988, *A Cognitive Theory of Consciousness*) separates the workspace's **contents** (what is broadcast, and
reportable) from its **contexts**: unconscious, nested frames that shape and constrain the contents without being
in the workspace themselves. Baars names three kinds: perceptual contexts (how input is presented), conceptual
contexts (which kind of knowledge is active) and goal contexts (what the system is trying to do), plus the self as
the outermost one. The J-lens reads what is verbalizable at a cell, its claim to read a global workspace
(*Verbalizable Representations Form a Global Workspace in Language Models*, 2026).

Read through that frame, the centred readout `J_l (h_l - mu_l)` asks for mu = **the context**: the state the
situation alone predicts, so what remains is the content. The results so far fit that reading:

- **Context centres help.** A family's own prompts (+0.216 pooled), other tasks' plain prompts (+0.112), one
  model-written situation word per family (+0.196) and one mix of all seven (+0.170): each is a frame, never an
  answer.
- **Content centres hurt.** Subtracting a word that names the answer's category deletes the answer (user_modeling,
  "country": -0.39, x3). Subtracting an item's own rewrites deletes its answer (typo, x8).
- **Generic text is not a context.** Wikitext means are null or harmful (x1, x4, x14).
- **directed_modulation is content, not context.** What is held changes token by token. No constant reads it,
  and only token-matched centres do (x12, x17).

So far, though, every situation entry was named after a bench family and written after seeing results. x22 builds
the glossary from the theory instead: a library of contexts on Baars's axes, written without the bench, far wider
than the bench, with the bench-matching entries marked in advance so they can be left out.

## Design

**Render is not an axis.** The reader always knows its own template (plain text at the final token; a user message
in the chat template; a reply being written out). Every glossary set is captured in all three renders, as x14's
`spec_for` already does, and a read uses the sets captured in its own render.

**Three axes of context.** Each entry is one word plus a one-line definition of a frame. A definition never
contains an example or a content word a reader could be asked for. Texts per entry: 64, written by the pinned 27B
with x11's `desc` prompt ("Write 64 varied short texts. Each one is an example of: {word} — {definition}"), seeds
salted with "x22". An entry's texts vary freely on the other axes, so each set's mean is a marginal: one context,
averaged over the rest.

**A composition grid.** 4 forms x 6 goals (marked below) are also written jointly ("... an example of: {form} —
{definition}, and at the same time {goal} — {definition}"), 32 texts per cell. This tests whether contexts nest
additively.

**The ≈ column** marks, before any generation, the entries I consider descriptions of a bench family's situation.
They are what the leave-out arms remove. Edit it as you edit the entries.

### Axis F — form (perceptual context: how the text presents itself)

| id | word | definition | ≈ bench | grid |
|---|---|---|---|---|
| prose | prose | running prose that breaks off partway through a sentence | association, basic_readout | ✓ |
| statement | statement | a complete, self-contained sentence stating something | typo | |
| question | question | a question that has not been answered yet | | ✓ |
| list | list | a list or sequence whose next item is about to come | | |
| field | field | a labelled field, a heading and a colon, waiting for its value | multihop | ✓ |
| message | message | a message a person writes to an AI assistant | user_modeling | ✓ |
| quotation | quotation | a sentence someone has been asked to write out word for word | directed_modulation | |
| foreign | foreign | text written in a language other than English | multilingual | |
| code | code | a fragment of computer code or structured data | | |

### Axis G — goal (goal context: what the processing at the end of the text is for)

| id | word | definition | ≈ bench | grid |
|---|---|---|---|---|
| correcting | correction | a mistake has just been made and is waiting to be put right | typo | ✓ |
| recalling | recall | the text stops right before a well-known fact | basic_readout | ✓ |
| chaining | inference | the answer needs a hidden link worked out first, then a fact about it | multihop | |
| evoking | allusion | a description points to one idea without ever naming it | association | ✓ |
| translating | translation | the meaning is plain but has to be expressed in another language | multilingual | |
| profiling | impression | something about the writer can be guessed but is never stated | user_modeling | ✓ |
| requesting | request | someone asks for help with a task | user_modeling | |
| holding | intention | something must be kept in mind while doing something else | directed_modulation | |
| repeating | repetition | words are being reproduced exactly as given | directed_modulation | |
| calculating | calculation | a numerical result is about to be given | | ✓ |
| counting | counting | things are being counted or tallied | | |
| defining | definition | the meaning of a word is being explained | | |
| rhyming | rhyme | the next word should sound like an earlier one | | |
| patterning | pattern | a regular pattern is about to repeat | | |
| summarising | summary | a longer account is being boiled down | | |
| comparing | comparison | two things are being weighed against each other | | |
| explaining | explanation | the reason something happened is about to be given | | |
| predicting | prediction | what will happen next is being anticipated | | |
| planning | plan | steps toward a goal are being laid out | | |
| instructing | instruction | someone is being told how to do something | | |
| persuading | persuasion | the reader is being argued into a view | | |
| narrating | narration | a story is being told, event by event | | ✓ |
| describing | description | a person, place or thing is being described | | |
| feeling | emotion | a feeling is being expressed | | |
| joking | joke | a setup is heading toward a punchline | | |
| deceiving | lie | someone is saying something they know to be false | | |
| refusing | refusal | a request is being turned down | | |
| classifying | classification | something is being sorted into a category | | |
| reminiscing | memory | someone recalls an episode from their own life | | |
| greeting | pleasantry | a social exchange with little content | | |
| doubting | uncertainty | an answer is offered with doubt | | |

### Axis K — domain (conceptual context: which kind of knowledge is active)

| id | word | definition | ≈ bench |
|---|---|---|---|
| language | language | words themselves: spelling, meaning, grammar | typo |
| people | people | who someone is: their background, work and traits | user_modeling |
| places | places | countries, cities and geography | |
| time | time | dates, seasons and the order of events | |
| numbers | numbers | quantities, measures and arithmetic | |
| science | science | how the natural world works | |
| history | history | past events and the people in them | |
| food | food | eating, cooking and ingredients | |
| health | health | the body, illness and medicine | |
| technology | technology | machines, computers and software | |
| minds | minds | thoughts, beliefs and intentions | |
| culture | culture | art, music, books and entertainment | |
| sport | sport | games, athletes and competitions | |
| work | work | jobs, money and business | |
| animals | animals | animals and the natural environment | |

Totals: 9 + 31 + 15 = 55 sets x 64 texts, plus 24 grid cells x 32 texts: about 4,300 texts.

## Arms (rms, strict; dev fit and val, 7 families)

| arm | mu | needs at read time |
|---|---|---|
| `sit:all` | equal-weight mean of every set (F, G, K) | nothing |
| `sit:allx` | the same without any ≈ entry | nothing; no bench-matched context at all |
| `sit:lofo` | the same without the read family's ≈ entries | nothing |
| `sit:best` | the single G entry best on the family's **fit** split, read on val | a family label (oracle upper bound) |
| `sit:pickg` | the G entry the 27B picks for the input | the input |
| `sit:pick` | mean + Δform + Δgoal, both picked by the 27B (additive) | the input |
| `sit:pickk` | the same + Δdomain | the input |
| `sit:rand` | a random G entry per item (control) | nothing |

Picking: the 27B sees the text the lens reads (never a target) and three numbered lists, and answers with one
number per axis. Greedy, thinking off, constrained to the list. One short generation per item over all
fit / val / bench banks.

Controls already in hand: `zero`, `fam@fit`, `glos:word`, `glosall:word` (x14), `glos:none` (x14 B, a model's short
texts with no situation). J++ reads `sit:all` and `sit:pick` too.

## Predictions (pooled over the 5 plain families, val, vs zero; reference: fam@fit +0.216, glosall:word +0.170)

- **P1 universal context:** `sit:all` ≥ +0.11 (half the family mean) and > `glos:none`.
- **P2 it is the context, not the bench:** `sit:allx` keeps ≥ 80 % of `sit:all`'s gain.
- **P3 the right context:** `sit:best` reaches ≥ 85 % of fam@fit's gain.
- **P4 naming the situation:**
  - `sit:pick` ≥ `sit:all` + 0.03, and > `sit:rand`.
  - The 27B's goal pick equals the a-priori ≈ entry on ≥ 70 % of typo, basic_readout and multilingual items.
- **P5 contexts nest:** for ≥ 75 % of grid cells at layers 36-60, cos(μ_fg − μ̄, (μ_f − μ̄) + (μ_g − μ̄)) ≥ 0.8.
- **P6 content vs context:** adding the domain hurts: `sit:pickk` < `sit:pick`. A conceptual "context" this specific
  is content, as "country" was.
- **P7 directed_modulation is content:**
  - DM judged (Haiku 5.5, layers 24/36/48/60): no `sit:` arm exceeds zero by more than +0.15.
  - user_modeling: `sit:all` ≥ zero.

## Cost and order

- **Generation:** about 4,300 texts on GPU 2. My estimate is 2.5-3.5 h, measured on the first sets before committing
  the rest. It goes after the current queue.
- **Picking:** about 2,000 short generations, under 1 h.
- **Captures** (each set in 3 renders) and **scoring:** under 1 h.
- **DM judging:** about $4 for 5 arms, asked for before it runs.
- **Code:**
  - `experiments/x22_situations.py`: reads these tables, generates, and captures in 3 renders.
  - `x22_pick.py`: the 27B's picks.
  - centres `sit:*` in `constant_mu.py`.
