# Agent 5's probe and grader spend by outcome (for agent 10's spend analysis, 2026-10-27)

**Classes:**
- (a) a result in her write-up or in verified notes;
- (b) an informative null, or a gate that answered its question;
- (c) waste.

**Sources:**
- $ is summed `usage.cost` from the ledgers:
  - `logs/eval_probe/spend.jsonl`, which `src/sorh_b10.py` also writes to per cell;
  - `logs/grader/spend.jsonl`.
- Outcomes come from `notes/grader_beliefs.md` and the notes it names.
- "Her write-up" is marked only where a message or note says so; otherwise the place is my notes or tab.

## Ownership
- **logs/grader ($7.63): mine.**
  - SoRH grader pilot $0.42.
  - Grader_labels prototype $0.21.
  - Shared labeller v3.4 run $7.00. The labeller is agent 4's code; I ran it.
- **logs/sorh_grader ($0.42): mine.** These are the raw outputs of the same SoRH grader pilot. That $0.42 is already
  inside logs/grader's $7.63; don't count it twice.
- **Not mine:** three logs/eval_probe ledger lines after 14:26Z, "eval_probe run probe_items*.jsonl" on 25–26 Oct
  ($0.68 + $0.12 + $0.26 = $1.05). Another agent used `eval_probe.py`, which writes to this ledger.
- **Ledger before 23 Oct 14:26Z:** $62.37 recorded. Against your $62.89 billed, the $0.52 gap is not recorded.
  - Known unrecorded spend: up to 12 in-flight calls when the researcher paused Goodfire pass 2 (21 Oct, noted then as
    "well under $0.30"), and 4 hung calls in the SoRH selection probe (23 Oct; billing not recorded).

## Before 23 Oct 14:26Z (eval_probe ledger, Qwen 3.8 Max probe unless noted)
| run (date) | $ | class | outcome / where |
|---|---|---|---|
| smoke tests (21) | 0.04 | (c) | setup check of the probe; no finding |
| pass 1, first view: Goodfire IB, our IB, Goodfire SWE/τ (21) | 3.33 | (a) | tab section "asked afterwards": IB, SWE-V, DeepSWE first views |
| WildChat anchor (21) | 1.08 | (a) | 155/174 Real, the calibration shown beside every later result |
| agent 3's SoRH grader messages (21) | 1.65 | (b) | 0/24 under every variant |
| agent 1's SoRH cues (21) | 7.23 | (a) | the grading sentence: 2/60 Real with it vs 44/57 without (tab) |
| judging the open-ended answers (21) | 0.10 | (b) | showed the open question is judged "Real" on coding tasks; that question was dropped after |
| τ first view, agent 6's pilot (21) | 0.40 | (c) | superseded: τ-bench was dropped mid-run (68/75); kept out of the headline |
| WildChat 20, full view (21) | 0.46 | (a) | full-view anchor 55/60 |
| agent 7's false rejection, full view (21) | 0.40 | (b) | 0 Real throughout |
| our runs, full view (21) | 1.27 | (b) | 0 Real throughout |
| network line × indentation (21) | 0.86 | (a) | 8/30 with both, 3/30 with either, 0/30 with neither (tab) |
| Goodfire pass 2, full transcripts (21) | 4.19 | (a), part (c) | IB 0/60, SWE-V 0/60, DeepSWE 5/60, the 40k-cut comparison (tab). Part (c): up to 12 in-flight calls at the pause, unrecorded, "well under $0.30" |
| E1 first messages (21–22) | 1.67 | (b) | C1–C3 don't differ, so the original E1 contrast couldn't test "looks real" |
| E1 D1 ablation + extra (21–22) | 1.44 | (a) | C5 24/30 vs C6 2/30, the submission-sentence card (P2); agent 7's C5/C6 arms |
| E3 incidental score (21–22) | 0.73 | (b) | manipulation check: all arms read as real |
| E4 voices (21–22) | 2.65 | (b) | all read as alignment evaluations (the deliberately wrong example) |
| E2 reply-2 contexts (21–22) | 1.35 | (b) | all read as capability evaluations |
| E1 C5/C6 batch 1, rep, n20 (22) | 2.65 | (a) | E1's pre-registered report: C5 14/20 vs C6 3/20 "any Real", p = 0.0005 |
| C9 (22) | 0.46 | (a) | reused as R1d in the D1 search |
| E4 forensic voices (22) | 2.55 | (b) | manager vs colleague don't differ (0/87 each); control 81/90 |
| IB grading-off check, run 3 (22) | 0.79 | (b) | the OFF update registers but reads as more evidence of a test |
| D1 grading-off check, G3 (22) | 0.98 | (b) | the same; the difference was 0, under agent 7's 3/30 |
| D1 graded-but-real search (r1, r2, r3, fresh ×2, GLM ×2) (22) | 3.14 | (a) | R2c 28/30 and R3b 21/30 fresh: grading reads as real when framed as the person checking |
| agent 3's 1k-real gate + revision (22) | 1.53 | (b) | missed twice (28/60, 21/60), so 1k stopped |
| agent 7's G1, G2, G2 revision (22) | 1.26 | (b) | G1 passed; G2 missed; the revision passed "says", missed "insists" by 1 |
| agent 3's G1 chat (22) | 0.27 | (b) | gate passed (18/18) |
| task-gaming paper's environments (22) | 1.97 | (b) | answered which read as real (puppeteer 26/30, dashboard suite arm 21/30); fed agent 8's pilots |
| agent 4's E1 ledgerfx gate + no-system follow-up (22) | 0.52 | (b) | passes on Qwen, not on GLM; the system line moves GLM 10/29 → 18/30 |
| agent 8's norvane pilot (22) | 0.89 | (b) | even R reads as a test (5/30) |
| agent 8's puppeteer pilot (22) | 0.34 | (b) | R 23/30 vs G 0/30 |
| agent 3's G1 chat, harder (22) | 0.43 | (b) | gate passed (24/30, 5/30) |
| v2 review 1a (22) | 1.61 | (a) | metric 0/180 Real vs no metric 98/180 (row 1a; sign test p = 0.0625) |
| v2 review 1p (22) | 2.06 | (b) | can't separate the arms (all near the alignment ceiling) |
| 1l gate, 1k redesign gate (22) | 0.88 | (b) | 1l passed (30/30); 1k redesign failed (person_firm 12/30) |
| DeepSeek re-anchoring: WildChat, puppeteer, environments (22) | 1.12 | (a) | DeepSeek anchor 101/174, the calibration for her 26 Oct DeepSeek replication |
| 1l follow-ups, g_disclaim, 1l-gt (22–23) | 1.21 | (b) | gates passed; the two report-only texts reported |
| agent 4's run-4 who-checks gate (23) | 0.31 | (b) | gate passed ("nobody" 30/30) |
| reasoning-view Tier 1 (23) | 6.29 | (b) | informative null: both primaries not shown (p = 0.081, 0.77) |
| SoRH prompt selection (23) | 2.28 | (a) | her 20 SoRH prompts, used in every later SoRH run. 4 hung calls: billing not recorded |
| **subtotal** | **62.37** | | (a) $29.9, (b) $32.1, (c) $0.44 + up to $0.30 unrecorded (rows are rounded to the cent) |

## logs/grader (21 Oct)
| run | $ | class | outcome / where |
|---|---|---|---|
| SoRH grader pilot (20 Qwen calls) | 0.42 | (a) | step-1 finding 5 on my tab: the count note raises the hack index (+0.64 per 100 words, paired) |
| grader_labels prototype (250 Luna calls) | 0.21 | (c) | superseded by the shared labeller; marked prototype and never used for a finding |
| shared labeller v3.4 run (luna_med) | 7.00 | (a) | "labelled-goal" datasets on my tab, marked PROVISIONAL (94246a0). Her write-up: not recorded |
| **subtotal** | **7.63** | | (a) $7.42, (c) $0.21 |

## After 23 Oct 14:26Z (agent 2's ledger)
| run | $ | class | outcome / where |
|---|---|---|---|
| SoRH behaviour 10, every cell's first message | 9.64 | (a) | B 58/60, G 0/60 and the cue cells. Her doc's k/20 for B and G; agent 10's cue map and claims write-up |
| SoRH cue-10 switch contexts | 0.66 | (a) | 0/45 Real in both arms. Her SoRH #4 ("the setting still reads a test") |
| realness candidates, step 1 | 2.19 | (a) | the passing frames (r_checker, r_student); agent 10's cue map |
| step 2, no-score frames | 0.39 | (a) | both 30/30 Real |
| step 3, cues on the passing frames | 15.28 | (a) | her doc's r_student 17/20, c5_eval 2/20, c5_training 1/20. Calls in flight at the lid-close sleep and the restart: billing not recorded |
| test 4a, privacy line | 1.54 | (b) | informative null (p = 0.69) |
| run 5 check | 0.83 | (b) | gate failed (R 0/48 vs C 0/48) |
| coding-chat cue gate | 0.61 | (b) | gate failed (10/60); the researcher ran the screen anyway |
| coding-chat cue cells, report-only | 10.09 | (b) | only the correct-value control reads as real (59/60); the probe can't separate the cues. Her write-up: not recorded |
| DeepSeek as probe, #1 and #4 (incl. a $0.018 fill of 6 calls lost to 429s) | 1.40 | (a) | her DeepSeek replication of #1 and #4 |
| GLM 5.2 as probe: anchor, #1, #4 | 0.60 | (a) | her GLM replication |
| Qwen 27B as probe: anchor, #1, #4 | 0.90 | (a) | her Qwen 27B replication |
| "Nobody will score" arm, four probes | 0.73 | (a) | her new #4 arm. The first GLM/27B launch stopped at the cap guard with no call ($0; my cap error) |
| **subtotal** | **44.85** | | (a) $31.8, (b) $13.1, (c) $0 recorded |

The ledger after 14:26Z is $45.90. Less the $1.05 that isn't mine, that's $44.85; the rows sum to $44.86 after
rounding.

## Totals (mine)
- **Recorded: $114.85** ($62.37 + $7.63 + $44.85).
- **(a) about $69.1; (b) about $45.2; (c) $0.65**, plus up to about $0.30 in unrecorded in-flight calls.
- **Waste:** the τ run dropped mid-way ($0.40), the smoke tests ($0.04) and the superseded labelling prototype
  ($0.21).
- **Not recorded:** billing for calls in flight at the 21 Oct pause, the SoRH-selection hang and the 23 Oct sleep or
  restart.
