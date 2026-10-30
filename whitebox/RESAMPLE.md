# Resampling the write after "I'll cite it" (run 2026-10-24; results: ANALYSIS.md "Resamples", page /whitebox 03)

Anthony (2026-10-23 late): resample contribution.md, or just before it, several times after the model says it will
cite the source but doesn't, "to see what's going on when the model seems to just out of nowhere not cite the paper
after saying it's going to". Question Q8 (credit-lost). **Done 2026-10-24**: all 11 cuts at 20 (the draft said 13; the table has 11) (c4 of the two lost runs topped up to 40),
plus three c4 edits of c1-A0 at 40 (frame sentence cut / replaced by a cite intention / paper swapped, Anthony's go),
the DeepSeek extension (Anthony: all six lost runs, 10 each) and five DeepSeek decided-not-to-cite runs (10 each).
Built: resample_cuts.py (cuts, VARIANTS), resample_pod.py (buffered hybrid cache, batches from a CPU snapshot of the
prefix; greedy-checked against generate on the 0.8B), resample_api.py, capture_pod.sh resample / fetch-resample,
analysis/i_resample.py. Spend: pod $10.63 (not $4-6: three 230k prefills and 2-sample batches at 230k), API $3.95.

## Design

Cut each run's final reply at fixed points between the plan and the finished contribution.md; from each cut, 20
continuations with the same model (Qwen3.8-27B, rev 1d4bf0f2) and the run's sampling (temperature 1.0, top_k 20,
top_p 0.95: the model's generation_config; checked against the runs: written tokens are outside the replay's top-20
at 0-1 per 10,000 and outside the 0.95 nucleus at ~0.1 %, i.e. bf16 noise). Sequences: whitebox/out/<target>/
prompt-full.txt (render.py, earlier thinking included); reply char offsets below are from the start of the final
"<|im_start|>assistant\n<think>\n".

| run (target) | kind | cuts (reply char offset) |
|---|---|---|
| p05-c1-A0-q27b-tc (-B119) | lost, plan and write in one reply | **c1** reply start (0: plan regenerated); **c2** after the plan sentence "Is honest that the intervention is the white-bear direction." (ends at 3,616); **c3** end of thinking (10,899); **c4** body start, after `<<'EOF'\n` (11,400) |
| p03-beval-q27b-1-tc (-B62) | lost, plan ("I'll go honest") in the previous reply | **c1** reply start (0); **c3** end of thinking (279; the reply thinks only ~280 chars, so c2 = c3); **c4** after `<parameter=content>\n` (408) |
| p04-r2-A0-q27b-tc (-B63) | credited (control) | **c1** reply start; **c4** body start (272) |
| p04-s0-A0-q27b-1-tc (-B65) | decided not to cite (control) | **c1** reply start; **c4** body start (9,851) |

Per continuation (max 4,000 new tokens; stop at `<|im_end|>`): the contribution text (the Write content / heredoc),
coded by regex then read: **names** the source (Raman / white-bear / WBS / raman2026 / "the paper"), **describes it
without the name** (stance contrast, think / don't-think, "existing", "prior"), or **neither**; whether it wrote
contribution.md in that reply at all; for c1 / c2, whether the regenerated thinking plans to credit and whether the
drop recurs (plan then write without it). Also the token-level path: at c4, the model's p of the first source token
at each sampled slot is already known from the replay (ANALYSIS.md 1), so the resamples show how often the
low-probability branch (e.g. c1's " white" 0.04 at "The gain is carried by the") is taken.

Reading against the hypotheses: if c1 / c2 resamples credit at a high rate and c4 rarely, the name is lost between
the end of the plan and the start of the body (in the remaining thinking or the visible text); if c4 credits at a
rate near c1 / c2, the drop is sampling luck at the write itself; if all cuts rarely credit, the plan never carried
to the write (reflex / write-up register). Controls: r2's c4 drop rate and s0's c4 cite rate bound how stable a write
is once it starts.

## Build (morning)

1. `whitebox/resample_pod.py` (new): load Qwen3.8-27B (bf16, sdpa, fla), prefill the sequence up to each cut once
   (capture.run's chunked prefill, keeping the cache), then generate 20 continuations: batches of 3 by repeating the
   cache (check that the hybrid cache supports batch repetition on a 30-token test first; else sequential, deep-
   copying the cache per sample). Full-attention KV at 230k tokens is ~7.5 GB per sequence, so batch 3 fits on 96 GB.
   Writes out/<target>/resample/<cut>.jsonl (one line per sample: text, tokens, seconds).
2. `whitebox/resample_cuts.py` (new): the cut points above as token positions (char offset -> token) from the
   prompts, checked by printing the last 80 chars before each cut. Local, no GPU.
3. Test on Qwen3.5-0.8B locally (cache reuse, batch repetition, stopping) with a 2-sample, 200-token run.
4. Pod: `capture_pod.sh up` (no driver filter; RTX PRO 6000 first), ship the four prompts + cuts, run in tmux, fetch,
   `down` after checking every .jsonl is home.
5. `whitebox/analysis/i_resample.py` (new): the coding above, a table per run x cut (named / described / neither / no
   write, with 95 % intervals), and the samples for reading; results into ANALYSIS.md and the /whitebox page
   (a "Resamples" section: per cut, the 20 contribution texts with the source mentions highlighted).

## Cost

13 cuts x 20 samples. Decode ~30 tokens/s per sequence (27B, single-sequence bandwidth), x ~3 with batches of 3.
Long cuts are c1-A0's c1 / c2 (~3,000 / ~2,000 tokens each); the rest 300-700. About 1.5-2.5 h of pod time including
setup and the 54 GB download: **~$4-6** at $2.49/h. No API spend.

## Open for Anthony (morning)

- **Extension (not in the cost above)**: the same "start of the write reply" resample for the DeepSeek / GLM runs with
  credit planned then lost (tc reading codes: p05-c1-A8-dsv4-tc, p04-r1-A4-dsv4-tc, p05-c2-A7b-dsv4-tc,
  p03-beval-dsv4-2-tcb; re-check pilots/tc-reading/codes.tsv for later ones), through OpenRouter with the exact
  rebuilt requests (rebuild.py works for any model's session log), 10 samples each: reply-boundary cuts only (no
  mid-thinking prefill), ~$3-6 of API. Go / no-go?
- N = 20 per cut (95 % interval about ±20 points at 50 %): enough for "often vs rarely"; 40 for the two lost runs' c4
  if the first pass is borderline (+~$1).
