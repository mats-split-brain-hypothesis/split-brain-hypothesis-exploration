# IB / SoRH graph and statement coverage inventory

27 October 2026. Read-only inventory for the root agent's direct reasoning review. No model calls, no raw model reasoning read, no existing page edits. Paths below are relative to the main repository unless otherwise stated. The companion JSON records 15 relevant current/archived pages, 123 embedded figures (including quote panels and overview figures outside these two benchmarks), dashboard headings/datasets, slide lists and handview manifest counts. Those are rendered artifacts, not 123 independent experiments.

## Current sources

- **Current SoRH write-up:** `published_pages/HsCSuEFhu8ruyso8XiQSHw/doc.md`, 17 embeds = 11 charts and 6 visible-output quote panels. The first five headings retain the researcher's original broad statements; the body often supplies a narrower suggested heading.
- **Current IB write-up:** `published_pages/Ez4fbmxa9Zg5tZdkNpgy2M/doc.md`, 7 charts. Includes four-model replications and agent 11's chat/homework follow-ups.
- **Current observational Goodfire page:** `published_pages/2R9va7TYYgek2gECyQxmje/db/files/index.html.json`, 6 main questions/graph groups plus definitions, examples and caveats. Its datasets provide exact saved asset pointers.
- **Build sources:** `.claude/worktrees/agent-9-presentation/page_sources/`. `four_page.py`, `four_S*.json`, `four_I*.json`, subsequent `padsw*.py/json` edits, and saved source notes. The published embed JSON is the final displayed data; the builder's earlier output can be stale.
- **Older dashboard:** `published_pages/UFyDGQWri9evCV6EUVxwY8/db/`. Main `dashboard/` is an earlier local shell and is not the latest four-model pages. Each `aN_methods` dataset describes chart provenance.
- **Latest local reading site:** `logs/handview/index.html`, built by `src/handview_site.py`. The script is dirty in main; it was inspected read-only. Source manifests carry original raw-record pointers and labels. This local site contains full reasoning and is not a published page.

## Current SoRH chart checklist

All files below are `published_pages/HsCSuEFhu8ruyso8XiQSHw/embed_<id>.json` (matching `.jsx` files also exist). Model order is Qwen 2.4T, DeepSeek, GLM, Qwen 27B. Paired reasoning review should distinguish the stated metric, perceived audience, inferred grader, user's priorities, and whether the output actually violates the user's intent.

| Component / parent statement | Embed ID | Displayed takeaway / measure | Source to connect to reasoning |
|---|---|---|---|
| `sorh4-1-padded`, #1 | `f2c1216a-3693` | All models pad with stated score; class version slightly lower. Final-output padding v2, 20 prompts/condition. | Agent1 `sorh_models20_results.md`; `sorh_padding_final_v2_results.md`; handview #1 |
| `sorh4-1-probe`, #1 | `c8e4811c-8dfc` | Score sentence reads as test; class reads real. Majority of3 probe answers/prompt, separate WildChat calibration. | Agent5 `probe_prereg_glm_q27_sorh.md`, `probe_prereg_deepseek_sorh.md` |
| `sorh4-1-length`, #1 | `7d3e98e7-c7c0` | Score increases reasoning tokens, 2.6–21× paired ratio. | Agent1 `sorh_models20_reasoning_length.md`; raw usage vs content distinction |
| `sorh4-1-hes`, #1 | `dda2ebbb-49e7` | With score,5–7/10 spiral,8–10/10 hesitate; no-score0/10 spiral. | Agent1 `sorh_hesitation_spiral_results.md`; Sol reasoning labels need direct content check |
| `sorh4-2-named`, #2 | `424b0799-ce02` | Named score vs named “checked for” vs vague “will be scored.” | Agent1 models20; handview #2 |
| `sorh4-3-who`, #3 | `9bef3c78-2e4a` | Evaluator / own tool / manager; training / evaluation / real use. | Agent1 models20; handview #3 |
| `sorh4-4-switch`, #4 and nobody | `d4bb9d6b-d626` | Final padding after off/on/nobody; realness probes all zero. | Agent3 `sorh_persistence.md`, cue10; Agent5 probe prereg |
| `sorh4-5-priority`, #5 | `2b119405-d60f` | Quality first / don't care / score first, plain and class. | Agent1 models20; handview #5 |
| `sorh4-5-length`, #5 | `aab8e9f4-86c6` | Priorities change reasoning length. | Agent1 reasoning-length note; same #5 records |
| `sorh4-5-hes`, #5 | `34be78f0-aebe` | Don't-care reduces score-cycle spirals; score-first keeps them. | Agent1 hesitation/spiral note; same #5 records |
| `sorh4-mean`, mean requests | `eac6cdc1-3f8a` | Thank-you letters, keyed car, bad-word score, “meaner the better.” | Agent1 `sorh_mean_requests_results.md`;90 record pointers |

Six quote panels are examples of the above, not additional tests: q1=`f791a21c-875e`, q2=`b064805c-65b6`, q3=`25505e33-b3fa`, q4=`079ec0e5-e238`, q4n=`6dea4252-8a89`, q5=`684cb8d1-59a7`. They largely use sorh_160, first draw, opening300 visible characters; cue4 uses conversation0, reply5. A root reasoning review should also cover counterexamples beyond this single repeated quote prompt.

**Newer than the published page:** handview `tests_BF` has400 manifest rows for teacher quality review / explicit acceptable-behavior rule experiments dated27Oct. This family must be added to coverage even though no embed appears on the current page.

## Current IB chart checklist

All files are `published_pages/Ez4fbmxa9Zg5tZdkNpgy2M/embed_<id>.json`. Source tasks are conflicting LCB101,27,40,58,63,99. The outcome definition is not identical across every chart; preserve the experiment-specific scoring rule.

| Component | Embed ID | Displayed takeaway / comparison | Source |
|---|---|---|---|
| `ib4-1a-before` | `812c7758-8c1b` | Grade-off before first submission cuts Qwen hacks; GLM/DS baseline floor. | Agent4 `ib_persistence.md` §§20–22, handview #1 “Told before” |
| `ib4-1b-after` | `3007b90c-bae4` | Grade-off after first hack step: Qwen2.4T/GLM abandon some; DS/27B retain all. Working and unfinished strata. | Agent4 §§20–22; Qwen2.4T Agent8 exp10; handview #1 “Told right after” |
| `ib4-2-detector` | `442413d3-bace` | Cheating detector works only on Qwen2.4T;6 tasks ×1. | Agent4 §§20–22; handview #2 |
| `ib4-3-stop` | `7440f628-de54` | STOP works on3 models; DS hacks4/6. | Agent4 §§20–22; handview #3 |
| `ib4-4-chat` | `1ce1d858-146e` | No harness: Qwens still hack; GLM0/16,DS2/17 Novita or0/13 capped SF. | Agent11 `ib_chat_vs_harness.md`; report.json in chat run folders |
| `ib4-5-homework` | `a8669123-95cc` | Homework first reply0/4 or0/6 vs automated chat; contradiction named separately. | Agent11; `logs/ib_chat_homework/report.json` |
| `ib4-6-rejection` | `6ed5eafb-f4d2` | Homework rejection rounds cause cumulative hacking by round3. | Agent11; `logs/ib_chat_rejection/report.json`; registered vs fixed Q27 extraction |

## Additional families retained only in older/auxiliary pages

Current four-model pages do not exhaust “all statements and graphs.” These older families need a reasoning entry or an explicit link to an entry covering the same underlying data:

| Family | Exact location / locator | Distinction to preserve |
|---|---|---|
| Goodfire hacks seldom undone; forced continuation; flawed-test stopping counterfactual | Old IB page `UErqyTUGsjXQxitHmFad6w/doc.md`:16–34; dashboard agent4 findings1–6 | Considered vs attempted/enacted hacks; observational stopping counterfactual |
| Rejection, noticing flaw, own-test failure, length-matched onset | Current Goodfire page `2R9va7TYYgek2gECyQxmje`; old dashboard agent7 charts1–10 | First remark/first hack hazards vs episode prevalence; matching isn't randomization |
| Alignment-eval vs capability-eval awareness, order, future-hack prediction, restraint/violation use | Current Goodfire page six groups | Different label definitions, judge overlap and explanatory versus causal role |
| IB return to tests, tool allocation, onset after own test vs submission rejection | Old dashboard agent5 charts1–6 and15 | Tool use and stated goals need original timeline |
| No-STOP/STOP × automated framing, network line/indentation, minimal scaffold/permission, light/firm correction | Old dashboard agent2, old IB page #2/#5 | Tiny screens and pooled different-day cells vs replication |
| Own earlier reasoning removed | Old IB page #6; dashboard agent4 “Without its earlier reasoning…” |33/54→6/54 at hack step; ablated history need not isolate belief |
| Reviewer/person/checker at decision point and full episodes | Old IB page #3; original forensics exps3,7,8 |8/42 vs0/44 plans;4/8 vs0/8 episodes are different endpoints |
| Explicit real/eval belief sentence inserted in reasoning | Old IB page #4, forensics exp9 |19/20 vs19/20; intervention uptake caveat |
| Early/late grading-off momentum, task58/27/99 incident variants, openness | Old IB page #7–9, forensics exp10 and momentum set | Stage/history confounds, disclosure vs code behavior |
| IB-SWE and SWE-V cue screens | Old IB page #10–11 | Keep separate benchmark; source recall/lookup not automatically hacking |
| SoRH initial full sample and house-style/reflex analysis | Old dashboard agent1, old cue-impact page `LSVmFhRenaAZwvxkv55BHZ` | Original metric distributions versus selected20; reasoning-length bins not absence of deliberation |
| Soft/firm wording, exact/vague target with “more”, conversational/exam variants | Cue-impact page §§2–4; old SoRH Results #2/#3 | Some variants absent current three-row named chart |
| Score feedback target/no-target, vague pushback, bare/no-metric pushback | Cue-impact page §§9–11; old dashboard agent3 | Actual score, target and feedback wording change separately |
| Honesty-test sentence every turn, personal tool score, unreachable target, visible unsolicited score | Agent3 findings page `YFSi7Rby7P3UPTiHQ6nBmm/doc.md` claims3–6,9–10 | Local variants outside current cue10 trio |
| Grader-belief accuracy and invented8-FAQ target | Old dashboard agent5 charts14,16,17 | “Invented grader” label versus misunderstanding/guessing actual count rule |
| Coding chats / human pushback / CI relay / false-test-run claims | Agent3 findings claims7–8,11–12; old dashboard agents3/7 | Adjacent custom coding tasks, not IB/SORH; mark scope explicitly |

Decks #21/#23/#24 and the old project overview mostly duplicate these findings. Their exact slide IDs and heading lists are in the companion JSON; they should link to the analysis of the underlying experiment rather than be treated as independent evidence.

## Statement/graph mismatches to fix or qualify

1. **SoRH#2 says “no padding on any model,” but the current vague-score chart is2/20,1/20,0/20,1/20.** “Almost none” is supported. “Doesn't verbalise a scoring function” is only an earlier Qwen reasoning-label claim, not established across all four models.
2. **SoRH#3 “doesn't matter” is stronger than its own3–6-prompt spreads.** The body supplies “changes little.” Missing longest responses and absent probes for these exact cells limit interpretations.
3. **SoRH#4 denominators:** current chart has Q27 off3/14 and nobody6/14; DS scoring-on12/14. Handoff/prose summaries sometimes use15. Preserve actual chart valid denominators and identify exclusions.
4. **SoRH version2 padding changes the apparent class-vs-plain direction.** Notes to the student were removed before judging; earlier figures use whole-reply labels. Some paragraph/quote captions retain older labels. Do not describe these as newly observed model behavior.
5. **Reasoning length graphs' `n0`…`n3` fields are display-axis maxima, not sample counts.** Sample size is20; bars show median tokens. Do not mechanically treat every data row's `n` as a behavioral denominator.
6. **SoRH page says three models had no reasoning judge, while later spiral charts cite a Sol reasoning judge for all four.** This is likely stale scope wording: distinguish earlier semantic planner labels from newer cycle/hesitation labels rather than repeat a blanket no-judge assertion.
7. **IB#2 title “Any cheating detection mechanism…” is contradicted by the three null model columns.** The body explicitly suggests narrowing to Qwen2.4T.
8. **IB#1 “before it starts” actually inserts the message after its first reply and before the first submission.** It is not necessarily before any reasoning/action. The chart subtitle makes this clear.
9. **DeepSeek harness end counts differ:** current #1 chart shows8/18, chat comparison5/18. These need experiment/scorer reconciliation, not one pooled number. The chat definition is final function passing the original contradictory file; #1 may use a broader historical hack label.
10. **Q27 homework rejection:** registered2/6 by round3 versus function-block extraction4/6, with some feedback missing the failing assert. Both appear in the chart; keep both and inspect actual code.
11. **“No model reasoning was read” plus “why it likely happens” on IB:** explanations are hypotheses inferred from actions/regex/visible notes, not already established mechanism evidence. This is exactly where root's new direct reading adds value.
12. **Historical Goodfire claims involve Qwen/GLM/Kimi and source STOP prompts, whereas new charts involve Qwen/GLM/DeepSeek/27B and often no-STOP automated prompts.** Opposite aggregate timing patterns across these collections are not inherently contradictions.

## Raw-pointer coverage

- Agent1 `notes/handview_manifest_sorh.json`:2497 rows, not unique calls because records repeat across statements: #1=400,#2=400,#3=565,#5=642,tests_BF=400,mean=90. Includes redraw and superseded flags; source can be null for missing originals.
- Agent3 `notes/handview_manifest_sorh4.json`:180 conversations, #4=120,nobody=60. Turns1–2 are copied/shared across arms; do not count them as independent observations.
- Agent4 `notes/handview_manifest_ib4.json`:337 rows: #1=241,#2=48,#3=48. Includes stage sections.
- Agent11 `notes/handview_manifest_ib11.json`:144 rows: chat91,homework/rejections53. Round lists reconstruct later conversations; later `.eval` events may hold reasoning absent from plain message text.

The local handview builder already handles duplicate input prefixes and event-based reasoning recovery for later IB rounds. Root should use original source pointers and label whether a reading is full trajectory, exact decision window, or sampled evidence; graph coverage must not be presented as reading every underlying episode.
