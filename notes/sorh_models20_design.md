# GLM 5.2 and Qwen 3.8 27B on her SoRH single-turn conclusions #1, #2, #3, #5 (pre-registered, no calls yet)

Agent 1, 2026-10-26. The researcher: "Ok, we need to replicate everything of SORH and ImpossibleBench on GLM 5.2 and Qwen
3.8 27B" (via the orchestrator). Her budget approval: "ok, go ahead", for the orchestrator's total that includes this
part's $41 in caps.

## Design

The same as DeepSeek's `deepseek20_64k` (notes/sorh_deepseek20_design.md, amendment 1).

- **Texts:** the 400 texts of `notes/sorh_prereg/deepseek20_cells.jsonl`, unchanged (sha256 1288766b…abc30). That's
  the 20 cells her 4 conclusions rest on × her 20 prompts, each the text Qwen 3.8 2.4T's first sample got.
- **Replies:** 1 fresh reply per text per model, effort xhigh, max_tokens 64,000.
- **Judges:** as for DeepSeek, from sorh_judges.py sha256 18e8227b… (v4-sol), with no reasoning judge:
  - Luna: quality (with padding) and count;
  - Sol: thinned on the 6 share prompts.
- **Measure:** padded k/n per cell (the quality judge's padding flag).
  - A reply cut during reasoning counts as missing (a7d6e9f), and so does a job with no record after 3 failed
    attempts.
  - A reply cut in the answer is kept and judged, as Qwen's and DeepSeek's were.
  - Nothing is re-drawn.
- **Report:** `src/sorh_deepseek20.py analyse_all` writes notes/sorh_models20_results.md, with these columns per heading:
  Qwen 3.8 2.4T | DeepSeek V4 Pro | GLM 5.2 | Qwen 3.8 27B.
  - For each model it also gives: the length cuts, split into missing and kept; jobs retried and lost; the longest
    finish; replies past or below the requested limit; the direction of the missing replies (median tokens in cells
    with a cut); and count-judge parse failures (not used).
  - No tests: with 1 reply per prompt it is k/n side by side, and nothing beyond her conclusions.
- **Realness probe for #1:** agent 5 runs it on the same 100 texts (its 5124d34).

| model | OpenRouter id | provider (no fallbacks) | listed max output | price in / out per M |
|---|---|---|---|---|
| GLM 5.2 | z-ai/glm-5.2 | siliconflow/fp8 | 262,144 | $0.70 / $2.20 |
| Qwen 3.8 27B | qwen/qwen3.8-27b | deepinfra/bf16 | 235,929 | $0.15 / $1.875 |

The limits and prices are from OpenRouter's endpoint list, read on 2026-10-26. Both endpoints support `reasoning` and
`max_tokens`.

The 16,384 cap on DeepInfra in that list is DeepSeek V4 Pro's DeepInfra endpoint (deepinfra/fp8), not Qwen 27B's.
Listed limits can differ from what happens: SiliconFlow listed 393,216 for DeepSeek and cut some calls at 32,768.

**Full reasoning.**
- GLM 5.2 on SiliconFlow: the earlier SoRH run (logs/sorh_evidence_glm, 17 single-turn replies, effort max) returned
  reasoning text at about 4.1 characters per reasoning token. All 17 finished with stop; median 2,085 completion
  tokens, max 8,682.
- Qwen 27B on DeepInfra: full reasoning per CLAUDE.md. There are no earlier SoRH runs on it.

## Step 1: length check (no judges, not used in the results)

- **What runs:** stages `len_check_glm52` and `len_check_qwen27b`. Each is 1 reply on each of the 2 texts where
  DeepSeek reasoned longest: c3a_exam/sorh_529 (107,578 tokens) and r_student__c5_eval/sorh_559 (85,895).
  - The texts are in `notes/sorh_prereg/len_check_cells.jsonl` (sha256 8cea3cf5…cf68d), copied from deepseek20_cells.
  - max_tokens 64,000, effort xhigh, `--no-judges`.
- **What it records:** `src/sorh_deepseek20.py lencheck --stage …` prints numbers only: provider, finish, completion
  and reasoning tokens, reasoning and reply length in characters, seconds and cost. No text is read.
- **Cap:** $0.50 per model. At most about 2 × 64k × $2.20/M ≈ $0.28.

**Rule, fixed now, applied per model:**
- **Go to step 2** if both replies come from the requested provider, both return reasoning (reasoning tokens and
  reasoning characters above 0), and neither ends "length" below 64,000.
  - A reply that ends "length" at 64,000 has reasoned through the full limit. That is no reason to stop; such cuts
    count as missing, as for DeepSeek.
- **Stop and ask her** (through the orchestrator) before that model's step 2 if:
  - a reply ends "length" below 64,000, which would mean a provider cap below the request;
  - a reply returns no reasoning;
  - the provider differs from the one requested; or
  - both calls fail.
- The check's numbers go to the verifier and the orchestrator before step 2 launches.
- **Limit (the verifier, on OK of e260e1e).** Two calls per model catch a fixed provider cap below 64k, but not a
  per-call one like SiliconFlow's on DeepSeek (some calls capped at 32,768, others not). So step 2 reports every
  "length" finish per cell with its token count. A cluster of cuts at a round number below 64,000 is flagged to the
  orchestrator as it appears.

## Step 2: the main runs

```
caffeinate -i nohup .venv/bin/python src/sorh_screen.py run --stage glm52_20 \
    --cells-file notes/sorh_prereg/deepseek20_cells.jsonl --model z-ai/glm-5.2 --provider siliconflow/fp8 \
    --effort xhigh --max-tokens 64000 --no-reasoning-judge
caffeinate -i nohup .venv/bin/python src/sorh_screen.py run --stage qwen27b_20 \
    --cells-file notes/sorh_prereg/deepseek20_cells.jsonl --model qwen/qwen3.8-27b --provider deepinfra/bf16 \
    --effort xhigh --max-tokens 64000 --no-reasoning-judge
```

The length checks are the same commands with `--stage len_check_glm52` / `len_check_qwen27b`,
`--cells-file notes/sorh_prereg/len_check_cells.jsonl` and `--no-judges` in place of `--no-reasoning-judge`.

- **Guards:** spend.jsonl per billed call; key floor $25; concurrency 16, halving on 429/5xx/timeout; stop above 2
  empty-reasoning records; no retry on finish=length; up to 3 attempts on provider errors.
- **Running together:** the two models are on different providers, so they can run at the same time. Each should take
  about 1–3 h. The laptop must stay awake.
- **Offline checks:** dry runs (stub calls) of all four stages:
  - the length checks wrote 2 records each, with no judge calls and run.json `judges: false`;
  - the main stages wrote 400 records each: count and quality on all, thinned on 120, no reasoning judge, the right
    model and provider, max_tokens 64000, caps 20;
  - `analyse_all` wrote the four-column table and the per-model notes.

## Cost

Replies are priced on the 400 texts' completion tokens, at each provider's output price. The low end uses Qwen 3.8
2.4T's first samples (2.35M tokens, capped at 24k). The high end uses DeepSeek's 64k run (6.6M). Judges are about $1.2,
as in DeepSeek's run. Prompt tokens are under $0.05.

| run | replies | + judges | estimate | cap |
|---|---|---|---|---|
| GLM 5.2 (glm52_20) | $5.2–14.5 | $1.2 | ~$8 (GLM's earlier replies were short, so nearer the low end) | $20 |
| Qwen 3.8 27B (qwen27b_20) | $4.4–12.4 | $1.2 | ~$10 (a small model may reason longer) | $20 |
| length checks | ≤ $0.6 | — | ≤ $0.6 | $0.50 each |
| **total** | | | ~$19 | **$41** |
