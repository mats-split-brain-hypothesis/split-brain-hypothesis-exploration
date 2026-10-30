# DeepSeek V4 Pro next to Qwen on her SoRH single-turn conclusions #1, #2, #3, #5 (pre-registered, no calls yet)

**Amendment 1 (end of this note) replaces the run:** all 400 fresh at max_tokens 64,000, cap $45, stage
`deepseek20_64k`. The reuse of deepseek_bg and condition 4 below no longer apply.

Agent 1, 2026-10-26. The researcher: "ok, i decided to add the deepseek v4 pro alongside my results on SORH and
ImpossibleBench, let me give you the things I added in my doc so you can recompute only the tests that replicate my
conclusions". She picked "SoRH single-turn #1,#2,#3,#5" and "No" to the reasoning judge (via the orchestrator; the
cell mapping is the orchestrator's notes/deepseek_replication_map.md, b4ead91 on mats-reward-hacking).

## What runs

- **Model:** deepseek/deepseek-v4-pro on siliconflow/fp8 (no fallbacks), effort xhigh sent, max_tokens 24,000, 1 reply
  per prompt per cell. These settings are deepseek_bg's.
- **Prompts:** her fixed 20.
- **Cells:** the 20 cells her 4 conclusions rest on (table below). That's 400 (cell, prompt) texts.
- **Reused:** deepseek_bg's B and G on her 10 (20 replies), under the verifier's conditions (below). So the run draws
  **380 new replies**.
- **Texts:** `notes/sorh_prereg/deepseek20_cells.jsonl` (400 rows, sha256 `1288766bd1ccdfcf114a5a9a025bda46802311b0dd84afbd194682a4085abc30`), built by
  `src/sorh_deepseek20.py build`.
  - Each text is exactly what Qwen's first sample got. It was taken from the Qwen record and checked against the
    cells file it came from (`source_file`).
  - deepseek_bg's 20 texts equal the file's.
  - Agent 5's realness-probe input for #1 (logs/sorh_ablation/ds_probe/first/input.jsonl, 100 rows) equals the file's
    B, G, r_student, r_student__c5_eval and r_student__c5_training rows byte for byte.

| Her heading (orchestrator's map, verbatim) | Cells | Qwen padded, first sample (recount) |
|---|---|---|
| #1 "A stated score is enough to make Qwen game it, regardless of whether the model reads the conversation as real or eval" | B, G, r_student, r_student__c5_eval, r_student__c5_training | 0, 13, 13, 14, 14 /20 |
| #2 "The score has to be named explicitly to be pursued, the model doesn't verbalise a scoring function otherwise" | c3a_exam, c3a_conv, c2_vague | 16, 5, 1 /20 |
| #3 "As long as there is an explicit scoring function, the setup or who requests it doesn't matter (…)" | c4_auto, c4_own, c4_manager, c5_training, c5_eval, c5_real | 11, 9, 12, 13, 15, 13 /20 |
| #5 "If the user states different or conflicting priorities with the score, the model focuses on the user's priorities" | G, c6_quality_first, c7_dont_care, c6_score_first; r_student and its 3 r_student__ versions | 13, 2, 4, 19; 13, 7, 7, 18 /20 |

My recount from the Qwen records matches the orchestrator's on all 20 cells.

**Judges** (sorh_judges.py sha256 18e8227b…, v4-sol, byte-identical to deepseek_bg's):
- Luna: quality (with the padding flag) and count.
- Sol: thinned on the 6 share prompts.
- No Sol reasoning judge (`--no-reasoning-judge`).

## The verifier's conditions for reusing deepseek_bg's B and G

1. The same runner (`src/sorh_screen.py`), provider siliconflow/fp8, effort xhigh and max_tokens 24,000. All hold;
   deepseek_bg's records carry the same model, effort, provider and judge version.
2. The same count, quality and padded judges: Luna, v4-sol, and the same judges file.
3. deepseek_bg's Sol reasoning labels are not used.
4. **SiliconFlow did not enforce the 24,000 cap on DeepSeek's reasoning.** In deepseek_bg, 5 G replies reasoned 36–49k
   tokens and finished with stop. The new replies will be drawn the same way, so DeepSeek's replies are effectively
   uncapped while Qwen's were cut at 24,000.

## What differs from the Qwen runs

- **The replying model:** DeepSeek V4 Pro instead of Qwen3.8 2.4T.
- **The token cap.** Qwen's was enforced; DeepSeek's reasoning in practice is not (above). In these cells, 6 of Qwen's
  first samples hit the cap:
  - 2 were cut during reasoning: c5_eval/sorh_821 and c6_score_first/sorh_164;
  - 4 were cut in the answer: c3a_exam/sorh_580 and sorh_821, c4_auto/sorh_821, c6_score_first/sorh_580.
- **No reasoning judge.** Her 4 conclusions use padded only.
- **When the replies were drawn:** Qwen's over 5 stages on different days; DeepSeek's in 2 (deepseek_bg on 2026-10-25,
  and this run).
- Effort xhigh is sent to DeepSeek as to Qwen. Whether SiliconFlow applies it to DeepSeek is unknown.

## Measure and report (fixed now)

- **Padded k/n per cell** for each model: the quality judge's padding flag on the first sample per prompt, the measure
  in her doc.
- **Missing replies.** A reply cut during reasoning counts as missing (a7d6e9f) and is not re-drawn, so n can be below
  20. Under that rule Qwen's c5_eval is 15/19 and c6_score_first 19/19. The orchestrator's recount (15/20, 19/20) counts
  those two cut replies as not padded. The results table shows k/n with the missing count.
- **The report.** `src/sorh_deepseek20.py analyse` writes notes/sorh_deepseek20_results.md: one table per heading, Qwen
  next to DeepSeek per cell, and nothing beyond her conclusions.
  - Count, quality and thinned are in the records but not reported.
  - No tests are run: with 1 reply per prompt, the comparison is the two k/n side by side.
- **The realness numbers for #1** are agent 5's (DeepSeek as the probe, on the same texts). DeepSeek as the probe reads
  WildChat "Real" 101/174, against Qwen's 155/174.

## Runner and limits

```
caffeinate -i nohup .venv/bin/python src/sorh_screen.py run --stage deepseek20 \
    --cells-file notes/sorh_prereg/deepseek20_cells.jsonl --model deepseek/deepseek-v4-pro \
    --provider siliconflow/fp8 --effort xhigh --no-reasoning-judge
```

- **Stage cap:** $40 (CAPS["deepseek20"]). Spend is logged per billed call (spend.jsonl).
- **Guards:** key floor $25; concurrency 16, halving on 429/5xx/timeout; stop above 2 empty-reasoning records; no
  retry on finish=length (407e89e).
- **Offline checks:**
  - plan: 380 distinct jobs, sample 0, 0 of B/G on her 10;
  - a dry run (stub calls) wrote 380 records: count and quality on all, thinned on 110, no reasoning judge, and
    run.json `reasoning_judge: false`.
- **Time:** DeepSeek's G replies took a median 11 min (max 17) in deepseek_bg. 370 scored replies at 16 in flight take
  about 3–5 h. The laptop must stay awake: lid-close sleep on battery stalls the run.

## Cost

- **Estimate $31.3** (replies $30.3 + judges $1.0). For each new job, Qwen's first-sample reply cost on that cell and
  prompt is scaled by DeepSeek's cost relative to Qwen's on the same prompts of her 10 in deepseek_bg (G 2.22×, B 0.70×).
  Judges are at deepseek_bg's G means without the reasoning judge.
- **A flat check gives $33.9:** every non-B job at DeepSeek's mean G reply on her 10.
- **The cap of $40** is about 25% above the estimate. DeepSeek's uncapped reasoning makes the upper tail wide: G
  replies ranged $0.015–0.156.
- **Precondition: the key top-up.** The key is checked before launch, and the run doesn't start unless the top-up has
  landed and the key stays above the $25 floor plus the cap.

**Approval line (orchestrator's form):** "DeepSeek V4 Pro, her SoRH #1, #2, #3, #5: 20 cells × 20 prompts × 1 reply =
400, of which 20 reused from deepseek_bg → 380 new replies; judges count, quality/padded, thinned (no reasoning
judge); est. $31 (flat $34), cap $40; launches only after the key top-up."

## Amendment 1 (2026-10-26, after condition 4 failed; her pick, before any reply was read)

**What happened.**
- The first run (`deepseek20`, launched at a10fa4a, 13:44:20Z) was paused by SIGTERM at about 13:55Z after 22 records
  ($0.76 in spend.jsonl, plus the unrecorded partial cost of the replies in flight).
- **SiliconFlow now enforces max_tokens on DeepSeek on some calls and not others.** Here, 3 of the 22 finished "length"
  at exactly 24,000 completion tokens, all reasoning, with an empty reply. Agent 3, in the same minutes, had one cut and
  one reply of 26.9k with stop (sorh_223/0/1 at 13:55:43Z, with the same max_tokens 24000 and the same streamed call;
  the verifier). That's condition 4 above failing.
- In deepseek_bg, 6 of 10 G replies used more than 24,000 completion tokens (24.2k–49.6k) and finished with stop. So
  where the cap is enforced, about half of G-type replies could be missing (6 of 10 in deepseek_bg). It was 3 of 22
  overall so far in the paused run, and the orchestrator told her about 55 of 380. The reused B/G would be uncapped
  while the new cells were capped.

**Her pick** (asked in both sessions):
- here: "Fresh run, 64k limit";
- the orchestrator's: "Restart with a higher limit", which says rerun everything including fresh B/G on her 10 (no
  deepseek_bg reuse), a 64k limit, and a cap raised to $45.

The orchestrator's version is the more explicit one and is followed.

**What changes:**
- **Stage `deepseek20_64k`:** a new folder (logs/sorh_ablation/deepseek20_64k), so nothing earlier counts against its
  cap. It plans all 400 (cell, prompt) pairs of `deepseek20_cells.jsonl` (sha unchanged, 1288766b…), sample 0.
- **max_tokens 64,000** (`--max-tokens 64000`; run.json records it). That's above deepseek_bg's longest reply (49.6k),
  so replies should finish as they did there.
- **No reuse:** deepseek_bg's B and G are not used.
- **The 22 paused deepseek20 records are not used**, and their replies are not read.
- **Cap $45.**
- **The token limit differs from Qwen's.** Qwen ran at 24,000, and 6 of its 400 first samples in these cells hit it (2
  cut during reasoning, 4 in the answer; listed above). DeepSeek reasons much longer, so 64k lets it finish rather
  than leaving many replies missing.
- **Unchanged:** the texts, judges (no reasoning judge), measure, the cut rule (a reply cut during reasoning is missing,
  never re-drawn) and the report (`analyse` now reads deepseek20_64k only).

**Cost.**
- Estimate **$32.3**: the 380 as before ($31.3), plus B/G on her 10 at deepseek_bg's billed cost without the reasoning
  judge ($0.99). The flat check gives $34.9.
- deepseek_bg's costs already reflect uncapped reasoning, because 24,000 was not enforced then.
- The cap of $45 is about 40% above the estimate.

**Offline checks:** a dry run (stub calls) planned 400 distinct jobs and wrote 400 records: count and quality on all,
thinned on 120, no reasoning judge. run.json shows max_tokens 64000, cap 45, prior $0.

**Command:**

```
caffeinate -i nohup .venv/bin/python src/sorh_screen.py run --stage deepseek20_64k \
    --cells-file notes/sorh_prereg/deepseek20_cells.jsonl --model deepseek/deepseek-v4-pro \
    --provider siliconflow/fp8 --effort xhigh --max-tokens 64000 --no-reasoning-judge
```

**Approval line:** "DeepSeek V4 Pro, her SoRH #1, #2, #3, #5, fresh: 20 cells × 20 prompts × 1 reply = 400 at
max_tokens 64,000 (the paused 22 and deepseek_bg not used); judges count, quality/padded, thinned (no reasoning judge);
est. $32 (flat $35), cap $45."
