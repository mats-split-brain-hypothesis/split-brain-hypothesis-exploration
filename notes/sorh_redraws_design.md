# Re-draws of the 7 missing single-turn replies (design, agent 1, 27 Oct 2026; no calls yet)

**Her decision** (via the orchestrator, 27 Oct): "Yes, mark as redraws". Re-draw the 7 missing single-turn replies so
every cell of the four-model SoRH tables is out of 20, with these settings:
- Qwen 3.8 2.4T's two at 64k;
- DeepSeek's 32,768-cut ones at the same settings, re-drawn again if the provider caps them again;
- c5_eval/sorh_931 at 128k;
- c5_training/sorh_931 at the same settings.

Judges as listed, plus padding v2. Cap $6. Order: commit the design, then the verifier's OK and agent 2's GO; no AC
needed. On the page they are marked as re-draws, with the old k/19 etc. in the note.

Exploratory, as the rest of the SoRH work. The 7 slots are fixed by the a7d6e9f rule (a reply with finish "length" and
an empty reply is missing) and by the records. They were not chosen from any judge's labels. Nothing else is
re-drawn. The verified files built without re-draws stay as they are.

## The 7 jobs

| Model | Cell / prompt | Why it is missing | Re-draw stage | max_tokens |
|---|---|---|---|---|
| Qwen 3.8 2.4T | c5_eval / sorh_821 | cut during reasoning at 24,000 (our limit), fill20 | redraw_q24t | 64,000 |
| Qwen 3.8 2.4T | c6_score_first / sorh_164 | cut during reasoning at 24,000 (our limit), fill20 | redraw_q24t | 64,000 |
| DeepSeek V4 Pro | c5_eval / sorh_219 | cut at 32,768 (SiliconFlow's cap), deepseek20_64k | redraw_ds64 | 64,000 |
| DeepSeek V4 Pro | c5_eval / sorh_702 | cut at 32,768 (SiliconFlow's cap), deepseek20_64k | redraw_ds64 | 64,000 |
| DeepSeek V4 Pro | c6_score_first / sorh_845 | cut at 32,768 (SiliconFlow's cap), deepseek20_64k | redraw_ds64 | 64,000 |
| DeepSeek V4 Pro | c5_training / sorh_931 | no record (3 provider errors), deepseek20_64k | redraw_ds64 | 64,000 |
| DeepSeek V4 Pro | c5_eval / sorh_931 | reasoned through our full 64,000, deepseek20_64k | redraw_ds128 | 128,000 |

The jobs are listed in `src/sorh_redraws.py` (`JOBS`).

## Settings

The request text of every job is copied byte for byte from `notes/sorh_prereg/deepseek20_cells.jsonl` (the same text
the first draws got) by `src/sorh_redraws.py build`. Cells files:

| Cells file | Rows | sha256 |
|---|---|---|
| `notes/sorh_prereg/redraw_q24t_cells.jsonl` | 2 | efb73eba91ff084e0fe657022023bbdd08dd22a64842bfa4bbd22134d6d75756 |
| `notes/sorh_prereg/redraw_ds64_cells.jsonl` | 4 | e365d09f0ef495d54643a120f75eb56a76585cd20449260337bce89b7735bae8 |
| `notes/sorh_prereg/redraw_ds128_cells.jsonl` | 1 | 54c81b35cc845eee60595a9e87a40af85b610727c978aa22c9ae65c8867c1be9 |

Everything else is as in the first draws:
- **Qwen 3.8 2.4T:** `qwen/qwen3.8-2.4t-a95b` on siliconflow/fp8 with no fallbacks, effort xhigh, one user message,
  no system message. The only change is max_tokens: 64,000 (fill20 ran at the default 24,000). fill20's 170 records
  all show this model, provider and effort xhigh.
- **DeepSeek V4 Pro:** `deepseek/deepseek-v4-pro` on siliconflow/fp8 with no fallbacks, effort xhigh, as
  deepseek20_64k. max_tokens is 64,000, and 128,000 for c5_eval/sorh_931.
- **The runner:** `src/sorh_screen.py run` with the cells file. Its ALL_PAIRS_REDRAW stages plan sample 0 of every
  pair in the file, so 1 reply per job. Provider errors are retried as in every earlier stage, within the stage cap.

## Rounds for a DeepSeek re-draw cut again at 32,768

- A DeepSeek re-draw that ends with finish "length", an empty reply and exactly 32,768 completion tokens is
  SiliconFlow's cap again.
- That job goes to the next round at its own max_tokens:
  - `src/sorh_redraws.py build_round 2` writes `redraw_ds_r2_cells.jsonl` from redraw_ds64 and redraw_ds128;
  - `build_round 3` writes `redraw_ds_r3_cells.jsonl` from redraw_ds_r2.
- At most 3 rounds in all. A job still capped after round 3 is reported as missing.
- If round 2 would mix 64,000 and 128,000 jobs, `build_round` stops (assert). I then ask before going on.
- These cases are not re-drawn and stay missing; they are reported:
  - a re-draw cut during reasoning at our own limit (Qwen at 64,000; DeepSeek's 931 at 128,000);
  - a DeepSeek job with no record after the runner's retries.

**Which record counts** (`src/sorh_redraws.py overlay`): per job, the latest round's record that was not cut during
reasoning. A reply cut mid-answer (non-empty) is kept, as in a7d6e9f.

## Judges

Every judge and prompt is the one the first draws got. Judges are sorh_judges.py sha 18e8227b, `JUDGE_VERSION`
v4-sol.

| Step | What | Which jobs |
|---|---|---|
| In-stage (runner) | count and quality (old padding judge), Luna | all 7 |
| In-stage (runner) | reasoning, Sol (the source of Qwen 2.4T's hesitation labels) | the 2 Qwen jobs (`--no-reasoning-judge` for DeepSeek, as deepseek20_64k) |
| In-stage (runner) | thinned, Sol, on SHARE_ROWS only (rows 219 and 931) | DeepSeek c5_eval/sorh_219, c5_training/sorh_931 and c5_eval/sorh_931, as the other models' records of these cells |
| Padding v2 | `sorh_padding_final.py run_v2 --set all --stages <the re-draw stages>`: final output cut by anchors, then QUALITY_SYS unchanged, no metric | every usable re-draw |
| Padding v2 fix | `fix_nooutput`: a non-empty reply with no final output is judged whole | only if a re-draw has one |
| Hesitation (Sol) | `sorh_judge_pass.py run --pass hesitation --prompts redraws` | DeepSeek c6_score_first/sorh_845 (Qwen's comes from its in-stage reasoning judge) |
| Spiral (Sol, N = 3) | `sorh_judge_pass.py run --pass spiral --prompts redraws` | Qwen c6_score_first/sorh_164 and DeepSeek c6_score_first/sorh_845 |

- The c5 cells are not among the 9 hesitation/spiral cells, so their 5 jobs get no hesitation or spiral pass.
- `--stages` keeps padding v2 to the re-draw stages, so no other agent's newer records are judged.
- The hesitation and spiral done-keys include the source stage, so a re-draw is its own job. The judged rows of the
  cut first draws stay in the file.

## Caps and cost

Measured per-call prices from the first draws:
- Qwen 2.4T: $0.144 for 24,000 tokens, so up to about $0.39 at 64,000.
- DeepSeek: $0.103 at 32,768 and $0.201 at 64,000, so up to about $0.40 at 128,000.
- A Sol reasoning call: about $0.0104 + $0.0062 per 1,000 reasoning tokens.

| Step | Cap |
|---|---|
| redraw_q24t | $1.60 |
| redraw_ds64 | $1.20 |
| redraw_ds128 | $0.60 |
| redraw_ds_r2 | $0.50 |
| redraw_ds_r3 | $0.50 |
| Padding v2 | $0.10 |
| Padding v2 fix | $0.05 |
| Hesitation | $0.50 |
| Spiral | $0.80 |
| **All** | **$5.85** (her $6) |

- **Expected:** about $2–3.5 by usage.cost. The two Qwen jobs and their Sol reasoning calls are most of it, about $1.
- The rounds cost nothing unless SiliconFlow caps a job again.
- **Key:** $305.57 remaining at the time of writing. Every run checks the $25 floor plus its cap before its first call.

## Order

1. This note committed; the verifier's OK on it; agent 2's GO (money; the runs use no sandbox).
2. redraw_q24t, redraw_ds64 and redraw_ds128. The three are independent and can run side by side.
   - `sorh_screen.py run --stage redraw_q24t --cells-file notes/sorh_prereg/redraw_q24t_cells.jsonl --effort xhigh
     --max-tokens 64000`
   - `sorh_screen.py run --stage redraw_ds64 --cells-file notes/sorh_prereg/redraw_ds64_cells.jsonl --model
     deepseek/deepseek-v4-pro --provider siliconflow/fp8 --effort xhigh --max-tokens 64000 --no-reasoning-judge`
   - The same for redraw_ds128, with its cells file and `--max-tokens 128000`.
3. `sorh_redraws.py build_round 2`, then redraw_ds_r2 if it has jobs; then round 3 the same way.
4. Padding v2 on the re-draw stages, then `fix_nooutput` if needed.
5. Hesitation and spiral with `--prompts redraws`.
6. Reports:
   - `sorh_padding_final.py page_tables` (the four-model tables);
   - `sorh_judge_pass.py report_20 --with-redraws` → `notes/sorh_hesitation_spiral_results_20_redraws.md`;
   - `sorh_reasoning_length.py --with-redraws` → `notes/sorh_models20_reasoning_length_redraws.md`.
7. Results to the verifier; after its check, to agent 9 and the orchestrator.

## Stop and ask

- Any step's cap or the key floor trips with a job not yet drawn or judged.
- Round 2 would mix 64,000 and 128,000 jobs.
- A step fails on code. Its logs are kept as they are.

## On the page (her "mark as redraws")

- Each cell that gets a re-draw is marked †.
- Its note gives the count before the re-draw (k/19, k/17, …) and after it (k/20).
  `page_tables` writes this, with a "pending" list for any job still missing.
- New-judge numbers stay as the main numbers, with the old judge in brackets, as on the switched page. A re-draw's old
  label comes from its own in-stage quality judge.
- The reasoning-length and hesitation/spiral tables get the same † and note.
- A job that stays missing keeps its cell at k/19 etc. and is listed as still missing.

## Code (in bf9b4aeb and later; checked without calls)

- **`src/sorh_redraws.py`:** `JOBS`, `build`, `build_round`, `overlay`, `status`.
- **`src/sorh_screen.py`:** the `redraw_*` caps and `ALL_PAIRS_REDRAW`.
- **`src/sorh_padding_final.py`:** `--stages`, and the `page_tables` overlay.
- **`src/sorh_judge_pass.py`:** `--prompts redraws`, source-stage done-keys, `report_20 --with-redraws`.
- **`src/sorh_reasoning_length.py`:** `--with-redraws`.

**Dry runs** (`--dry`, no calls, 27 Oct 15:41Z; records in `logs/sorh_ablation_dry/redraw_*`). Each run.json shows
the model, provider, effort xhigh, max_tokens and cap above.
- redraw_q24t plans 2 jobs at 64,000 with count, quality and reasoning;
- redraw_ds64 plans 4 at 64,000 with count and quality, plus thinned on sorh_219 and c5_training/sorh_931;
- redraw_ds128 plans 1 at 128,000 with count, quality and thinned.

**No output change while no re-draw exists:**
- page_tables, report_20 and sorh_reasoning_length regenerate their verified files byte for byte;
- `report` (her 10) is unchanged.

`sorh_redraws.py status`: all 7 "not drawn".

## Outcome (27 Oct; verified at 0851e4d9)

- **6 of 7 usable**, all finishing "stop":
  - Qwen 3.8 2.4T c5_eval/sorh_821 (18,461 tokens) and c6_score_first/sorh_164 (27,845);
  - DeepSeek c5_eval/sorh_702 (20,931), c6_score_first/sorh_845 (51,362) and c5_training/sorh_931 (53,781), all at
    64,000;
  - DeepSeek c5_eval/sorh_931 at 128,000 (65,614).
- **DeepSeek c5_eval/sorh_219, first left missing:** its 3 re-draw attempts in redraw_ds64 were all provider stream
  errors, with no record, so there was no 32,768 cut and no round 2.
- **Retry** (her yes to one more try, design 5b620c7e, stage redraw_ds_retry, verified at 958a92c3): stop at 57,154
  completion tokens, padded under both padding v2 and the old judge, $0.197. The cell goes from 18/19 (18/19) to
  19/20† (19/20), so **all 7 are now usable.**
- **Labels:**
  - padding v2 and the old judge are both True on all 6;
  - both c6_score_first re-draws spiral (cycles 3 and 4);
  - the sorh_845 re-draw's count judge output was cut at its limit, so its count is unparsed (a missing measure).
- **Spend: $1.93** of $5.85: stages $0.557 + $0.412 + $0.214; judges $0.013 (padding v2) + $0.262 (hesitation) +
  $0.469 (spiral).
- **Reports:**
  - notes/sorh_models20_results_padding_v2.md (cells marked †, with before → after);
  - notes/sorh_hesitation_spiral_results_20_redraws.md;
  - notes/sorh_models20_reasoning_length_redraws.md.
