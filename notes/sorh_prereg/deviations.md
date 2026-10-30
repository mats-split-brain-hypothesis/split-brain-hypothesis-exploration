# SoRH ablation: deviations log

Every departure from notes/sorh_preregistration.md, with time (BST) and reason. Empty before the first call.

## 2026-10-23, pilot (amendment 1)

- **What:** the pipeline gate's quote check failed in the pilot: reasoning-judge quotes failed on 18/108 true labels
  (17%) with 48/60 records in, against the 10% limit.
- **Why:** the judge edits words in Qwen's terse reasoning, or stitches nearby sentences together.
- **Change:** prompt v2 (`QUOTE_RULE` in the reasoning, thinned and persist prompts) and a formatting-only matcher.
- **Pilot:** re-judged with v2 (reasoning and thinned kinds only), with no new Qwen calls.
- **Before use:** the gate is re-run, and the verifier OKs the change.
- **What was read before the amendment:** only the quote-failure rate and the failing quotes, with their cell and
  field names and the nearest stretch of reasoning, to classify the failures. No pilot comparison (G vs B, or any cell
  against any other) on any measure was computed or read before the amendment (agent 10; the verifier asked for this
  statement).
- **Approvals:** the verifier OK'd 784971d with conditions (re-judge all 60; keep v1; record `judge_version`; v2 for
  every later stage; a minimum of 3 words per quote, adopted). The orchestrator directed the re-judge and gate re-run.

## 2026-10-23, pilot (amendment 2)

- **What:** v2 still failed the quote check: 25/144 (17.4%), against v1's 30/146 (20.5%) at 60 records. The
  failures were mostly invented supporting clauses, lopsided by arm (G 22, B 3).
- **Change:** prompt v3. The reasoning, thinned, persist and item-count judges cite numbered sentences, and code
  checks that every number exists. The pipeline gate checks citations for every judge kind. There's a per-arm
  reliability rule, and a blind support check before the screen.
- **Also found:** item counts were biased low under v1/v2 (83–84% of listed items verified).
- **Disclosure (agent 10):** while diagnosing that, I printed item totals by cell, which shows G lists more items
  than B on the item prompts. No G-vs-B test was run, and the room gate rule is unchanged.
- **Next:** the pilot is re-judged with v3 (reasoning, thinned and item counts), with no new Qwen calls. Then the
  pipeline gate → the support check → the room gate.

## 2026-10-23, pilot (amendment 3, proposed)

- **What:** v3 passed the pipeline gate (0 invalid citations), but the judge over-cites: 129/148 true labels cite
  more than 3 sentences (hesitates median 18, max 902).
- **Effect:** the support check would be close to automatic, and per-sentence coding isn't possible.
- **Proposal:** prompt v4 (one to three sentences, enforced in code), re-judge the reasoning and thinned judges, and
  code support per cited sentence.
- **Coder's exposure:** the cited text of 7 v3 sheet items was read (arm hidden) before the problem was noticed;
  none was coded.
- **Added to amendment 3 before the v4 re-judge:**
  - behaviour 11 (`invents_grader`, B only), the researcher's addition;
  - the pre-committed fallback: GPT-5.6 Sol once for the reasoning and thinned judges, then drop behaviours 2-7, 9
    and 11 if it fails too. The verifier asked for it; the researcher chose it.

## 2026-10-23, pilot (amendment 4)

- **What:** v4 failed the citation gate: 38/156 over-cited, mostly B's plans_for_reader.
- **Decision:** the researcher chose, in agent 10's session, to enforce maxItems 3 with a strict JSON schema
  (same Luna, same v4 prompts) before the pre-committed Sol fallback, because of Sol's programme cost.
- **This is a deviation** from the fallback she committed at 9ef3c2a, and from the orchestrator's withdrawal of the
  same idea after the verifier's objection.
- **Budget:** the pilot cap is raised to $3.50 (orchestrator).
- **Next:** a dry run, then the re-judge as v4s.
- **Amendment 4 withdrawn before any call:** the researcher said "actually use Sol, it's fine". The pre-committed
  fallback runs (Sol once, v4 prompts, reasoning and thinned judges). `sorh_judges.py` is restored to 9ef3c2a.

## 2026-10-23, pilot result and additions

- **Sol fallback:** it passed the pipeline gate (0/171 invalid), the support check (all ≥ 0.9; gap ≤ 0.1), the
  question cross-check (2/9) and the room gate both ways ("keep G").
- **Adopted:** Sol for the reasoning, thinned and persist judges from the screen on. The researcher accepted the cost.
- **invents_grader:** untested (no B trues in the pilot).
- **The pilot cap was raised to $3.50,** and $3.23 was spent.
- **Added before any multi-turn call:** cue 10 ("scoring switched off", with a matched "stays on" control), the
  researcher's addition, and its probe point at the switch.
- **The multi-turn caps need raising** (orchestrator).
- **The coder saw** Sol's per-arm label counts (from agent 1) before the support check was coded.

## 2026-10-23, multi-turn reduced

- **What:** the researcher reduced the multi-turn stages to one descriptive run, before any multi-turn call.
- **Run:** 3 prompts (sorh_160, sorh_223, sorh_212: the top-ranked prompt of the first three groups in the seeded order) x 5 episodes per arm x 5 arms, about $27.
- **Dropped:** the multi-turn full stage.

## 2026-10-23, screen (prompts cut to 10)

- **What:** the researcher cut the prompts from 20 to 10, with the screen 27/420 records in ($1.12).
- **Run:** agent 1 stopped it by design; it relaunches on cells_10.jsonl (210), resuming in the same file.
- **Old records:** those on the 10 dropped prompts are kept and not analysed.
- **Which 10:** a round-robin rule over the groups by seeded rank, fixed before the relaunch.
- **Reporting:** her 11-cue structure is adopted, as a mapping only.
