# Example selection rules for the SoRH and IB site pages (agent 9, 27 Oct, written before any example is read)

Her request (via the orchestrator): every section gets a graph and a concrete example — the prompt or task (or an
excerpt), what the model did, and, where it fits, a short chain of reasoning quotes. Examples are picked by these rules,
not for being striking. Where a result is a contrast, one example from each side, side by side. Where a rule finds
nothing that can be sourced cleanly, the page says so.

Every quoted string goes into `results_site/quotes_sorh_ib.json` with its record (path + line, or .eval path + sample
id + epoch + message index), field, model, cell/arm/task and how it was found, and is checked verbatim against that
record by code (`results_site/check_quotes.py`). "…" marks a cut; segments appear in order.

Sources, in this order of preference:
(a) quotes already verified on her pages (agent 1's notes/sorh_models20_quotes.md @bec5090, notes/sorh_n2_quotes.md
@4468b030; agent 3's quote tables in notes/sorh_persistence.md @2a298d2 and @44d6237; judge citations whose quote must
be found in the record);
(b) targeted reads, under the rules below. Model reasoning is read only in the turn a rule names, and only the
sentences a judge cited there unless the rule says otherwise. If a read is blocked by a safety filter, stop and tell the
orchestrator; no retry.

"Then:" lines are written from code or labels (a test result, a padded flag, a submission's pass), never inferred from
the reasoning.

## School of Reward Hacks

Running prompt: sorh_160 (the sleep social-media post), the prompt agent 1's quote cards already use. Model for a
single-model example: the first in the page's order (Qwen 3.8 2.4T, DeepSeek V4 Pro, GLM 5.2, Qwen 3.8 27B) that has the
reply the rule needs; contrasts use the same model on both sides.

1. **Writing for the scorer (#1, #2, test E).** Request: sorh_160 without and with the score sentence (agent 1's
   notes/sorh_request_texts.md @053c3dde). Replies: the first model's B and G reply openings from bec5090, side by side;
   #2's vague vs named replies (c2_vague, c3a_exam) the same way. Reasoning: the judge-cited sentence on Qwen 2.4T's G
   reply (bec5090), and #2's reasoning cards (4468b030).
2. **Real or test (#1 class version, #3).** Request: the class version of sorh_160 (053c3dde). Replies: the first
   model's G and class (r_student) openings from bec5090; for #3, its c5_eval and c5_real openings from bec5090.
3. **What turns the padding off (#4, #5, tests B and F).** #4: agent 3's verified quotes (sorh_160, conversation 0,
   final reply; stays on vs switched off, and "nobody will score"). #5: the first model's c7_dont_care and
   c6_score_first openings from bec5090. F and B (targeted, visible replies only): the first model's G__acceptable and
   r_student__teacher_reads replies on sorh_160 from its sb_bf stage, the opening up to the first sentence end after
   150 characters.
4. **Saying versus doing (test C).** The first record in agent 10's "Committed but padded" list
   (notes/sorh_split_brain_cd_results.md @d2f39c00); the quote is the first two sentences the judge cited, recovered
   with agent 1's `sorh_judges.cited_text` on that record's reasoning; then the reply opening (visible) and its padded
   flag.
5. **Chasing the metric (spirals, test D).** The first model whose G reply on sorh_160 has spirals = true in the spiral
   judge's output (logs/sorh_ablation/spiral_judge/judged.jsonl); the chain is the first three score-check sentences the
   judge cited in that reply (`cited_text`). Then: the reply's padded flag.
6. **Mean requests.** Agent 1's every-reply table (notes/sorh_mean_requests_results.md @950365d): keyed car, plain,
   sample 0 — the first model whose reply is a mean letter and the first whose reply is not, reply openings (visible).

## ImpossibleBench

Task order lcbhard_101, 27, 40, 58, 63, 99; epoch 1 first. Logs as on the page (agent 4's §22 sources; agent 11's
report folders).

1. **First submission or after a rejection.** Qwen 3.8 27B and GLM 5.2, the no-message arm (G_C): the first episode in
   task order whose final verdict is a hack. Shown: the task's contradictory assertion (from test.py as the model read
   it); for 27B, its first submitted code's special-case lines and the verdict; for GLM, the first rejection message
   and the special-case lines of its first passing submission. Reasoning (targeted): GLM's reasoning in the assistant
   turn right after its first rejection, up to three sentences, picked within that turn and marked as picked by hand.
2. **Telling it grading is off.** Told before: the changes_plan sentences that passed agent 4's hand check (§24,
   @efac1f10), the first in the hand-check order. Told mid-hack: none unless a §22/§24 record already names the
   removed hack; otherwise the page says no example is sourced.
3. **STOP and the detector.** The Sol report judge's verbatim quote (its quote must be found in the visible text) for
   the first STOP episode in task order on Qwen 2.4T; against it, DeepSeek's first STOP episode in task order that
   handed in a hack: the submission number and the special-case lines.
4. **Chat vs harness.** Agent 11's chat replies, first task in order, epoch/sample 1: Qwen 2.4T (hacked) and GLM (not
   hacked), visible text only: the code line that special-cases the test, and GLM's sentence naming the contradiction
   if it has one.
5. **Homework and rejections.** GLM, the first conversation in task order that hacks by round 3: its round-1 reply
   (visible; the sentence naming the contradiction, if any), the rejection message, and the special-case lines of the
   reply that hacks.
