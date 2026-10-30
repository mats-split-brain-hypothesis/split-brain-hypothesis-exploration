# Spend analysis: where the money went and what it bought (agent 10, 27 Oct)

The researcher asked, via the orchestrator on 27 Oct: "can you do an analysis of how we've spent so much money by now
and whether they've lead to results or were wasted?"

This is analysis only: no API calls, and no reasoning was read. The item table is
[spend_analysis_items.csv](spend_analysis_items.csv), one row per run or part of a run, with its $, basis, class,
outcome and source. It is built by [src/spend_items.py](../src/spend_items.py).

**Classes:**
- (a) a result in her write-ups or verified notes;
- (b) an informative null, a gate, or "couldn't use";
- (c) waste;
- (p) pending: still running, or awaiting her check;
- (u) untraced.

## Summary

- **The key's total to date is $1,443:** usage on the $1,600 limit at 27 Oct 11:16Z.
- **Ours is about $1,235 at token list price** (the best estimate). It is $1,387 if every token estimate takes the × 1.3
  markup, but that overstates (see the next section), so × 1.3 figures here are only for comparison.
- **Not ours: about $177** was already on the key at 20 Oct 15:41Z, when our logs held $2.47.
  - A further ~$31 since then isn't in any of our logs. It is the other project's, or our own in-flight and label
    calls that no log kept; the two can't be told apart from here.
- **What it bought (best estimate, $1,235):**

  | Class | Best (list price) | At × 1.3 (overstates) |
  |---|---|---|
  | (a) result | $767 (62%) | $846 (61%) |
  | (b) null, gate, couldn't use | $411 (33%) | $474 (34%) |
  | (c) waste | $43 (3.5%) | $52 (3.8%) |
  | (p) pending | $11 (0.9%) | $11 (0.8%) |
  | (u) untraced | $3 (0.3%) | $3 (0.2%) |

  The waste row counts only recorded waste. Further in-flight losses are known but unrecorded; they sit inside the
  ~$31 above.
- **Where it went:**
  - ImpossibleBench $566 (46%);
  - SoRH $378 (31%);
  - the realness probe, which served both, $116 (9%);
  - other environments and transcript judges $174 (14%).
- **Waste was small. What took a third of the money was "no answer" (class b).** The largest (b) blocks:
  - the IB ablation screens (LCB and IB-SWE, with their pilots and judges), $121, which ended as leads when IB was
    wrapped up;
  - probe gates and nulls, $45;
  - the graded-context cells that didn't separate, $45;
  - the SWE-V and DeepSWE nulls, $43;
  - agent 4's inconclusive runs, $40;
  - the Dark Mode three-way null, $32;
  - HVTB, $23.

## How ours is separated from the other project's

- **Before our work:** at 20 Oct 15:41Z the key's usage was $179.66 (logs/key_usage_before_automated_pass.txt). Our
  logs before then hold $2.47 (effort_pilot, an estimate).
- **Now:** at 27 Oct 11:16Z the key had $156.75 remaining. This is the last key reading in logs/sorh_monitor/watch.log,
  from agent 2's monitor, which polls the free key endpoint. That gives usage of $1,443.25.
  - This assumes the limit was still $1,600. It was at 07:47Z: $206.74 remaining = $1,393.26, the orchestrator's
    reading.
- **The rise since the snapshot is $1,263.59.** Our traced spend over the same period is $1,232.65 at list price, or
  $1,384.65 at × 1.3.
- **× 1.3 overstates.** It would put our spend $121 above the key's whole rise, which is impossible. At list price,
  $30.94 is left over for the other project and for our unlogged spend.
  - So list price is the best estimate. × 1.3 is not a bound: the bound on our spend since the snapshot is the key's
    rise itself, $1,263.59, which also includes the other project.
  - The data allow an average markup of at most 1.061 on the estimate rows ((508.56 + 30.94) / 508.56), and only if
    all of the $30.94 were ours.
  - The markup varies by run. The first effort pilot's key-measured $2.49 matched its × 1.3 estimate ($2.47), not list
    ($1.90).
  - This agrees with agent 11, who found its watchdog's × 1.3 ran 25–70% above billed on its screens.
  - It also agrees with agent 4: some watchdog readings ran high before the GLM cache price was fixed on 26 Oct
    22:27Z.
- **The ~$177 before 20 Oct** is in none of our logs. It is the other project's, or earlier unlogged work, such as the
  framing-pilot branch.

## Sources and basis

**Before 23 Oct 14:26Z** (when agent 2's run ledger starts):
- The base is my header-only scan of logs/: .eval `stats.model_usage` × `src/costs.py` prices, plus `usage.cost` in
  records and ledgers.
- Owners' recounts replace it where they found errors:
  - **Agent 2:** backup copies and summary files doubled $31 ($23.30 of Inspect logs and $7.82 of records). Its
    recount is $72.27 logged, plus $0.51 from its notes and $1.26 that is in no log.
  - **Agent 3:** a shared first reply is repeated in every arm's file. Its recount is $98.9, including $18.9 of label
    judges that my scan skipped.
  - **From owners' notes:** agent 4's billed labelling ($26.32); agent 8's per-experiment labels ($0.84) and τ3
    labelling ($0.66).

**From 23 Oct 14:26Z:** agent 2's ledger (export at 27 Oct 11:00Z: 180 runs, $740.18), with four kinds of correction:
- **final figures** for runs that ended after the export (spiral judge $20.35; mt_nobody; agent 1's mean stages);
- **owners' billed figures** where they have them (agent 11's pilots, chats, homework and rejection; agent 6's
  dashboard seeds);
- **runs the ledger doesn't list:**
  - agents 12, 14 and 15 on 24 Oct, $2.19;
  - agent 4's judges, $0.58;
  - the Dark Mode gates ($0.83) and HVTB framing gates ($0.23);
  - agent 6's test-3 pilots and catalogue;
- **$1.05 of eval_probe lines** whose owner is untraced.

**Basis of the rows** (the CSV labels each one):

| Basis | $ | Note |
|---|---|---|
| billed (`usage.cost`) | $701 | |
| token estimate | $661 at × 1.3 | $509 at list price |
| key rise | $22.59 | the HVTB runs; an upper bound, since it counts all key spend in the window |
| owners' notes | $1.15 | |
| unlogged estimates | $1.26 | |

## By experiment

Best = list price. The "× 1.3" column overstates and is only for comparison. The class columns are at best.

| Family | Best | × 1.3 | a | b | c | p / u | What it bought |
|---|---|---|---|---|---|---|---|
| **SoRH** | **377.92** | | | | | | |
| Multi-turn and persistence, 21–22 Oct (agent 3) | 98.90 | 98.90 | 94.70 | 3.91 | 0.29 | – | map rows 1a 1b 1h 1k 1l 1n 1o 1p 2i 2j 2r 3e |
| Ablation screen and realness frames (agent 1) | 72.65 | 72.65 | 71.26 | 0.27 | 1.12 | – | Qwen's numbers in her SoRH #1/#2/#3/#5; the k/20 cells |
| Multi-turn screen and replications (agent 3) | 45.64 | 45.64 | 44.96 | – | 0.68 | – | her #4 on four models, the "nobody" experiment, cues #9–#11 |
| Judges: hesitation, spiral, depth | 43.50 | 43.50 | 35.59 | 7.91 | – | – | hesitation/spiral results (verified); the depth judge failed validation (b) |
| Cue studies, 21–22 Oct (agent 1) | 40.64 | 40.64 | 40.64 | – | – | – | sorh_cues: games the stated metric, 0/40 say tested |
| DeepSeek / GLM / 27B replications (agent 1) | 37.59 | 37.59 | 34.77 | – | 2.72 | 0.10 p | the four-model SoRH tables |
| Priority study (agent 1) | 21.65 | 21.65 | 21.65 | – | – | – | sorh_priority_results (verified) |
| Coding-chat cue screen (agent 3) | 11.99 | 15.59 | 11.87 | 0.12 | – | – | code measures in verified notes |
| Thank-you / count-free versions (agent 1) | 5.36 | 5.36 | 5.36 | – | – | – | sorh_thanks_table (verified) |
| **ImpossibleBench** | **565.90** | | | | | | |
| Cue screens (agents 2, 11) | 166.24 | 202.53 | 40.83 | 122.70 | 2.72 | – | (a) agent 2's round 1 and 1g (3c, 1g); (b) agent 11's LCB / IB-SWE screens, leads only |
| Rejection and graded context (agent 7) | 115.08 | 148.78 | 59.95 | 44.80 | 10.15 | 0.18 u | 2d (stage 1); the graded-context stand-in (n20, G3 ext); nulls G1, C12, G3 |
| Persistence and momentum (agent 4) | 107.01 | 131.22 | 50.10 | 40.33 | 14.95 | 1.63 u | 1s grading-off (her finding 1), 2e; nulls step 3, runs 1–2, E1; run 5 stopped (3 episodes cited in §18) |
| DeepSeek / GLM / 27B charts, §16–§22 (agent 4) | 75.28 | 96.91 | 70.35 | 4.49 | 0.45 | – | charts A–D for four models; finding 3 |
| Who reads the reply (agent 8) | 62.91 | 76.35 | 47.20 | 14.68 | 1.03 | – | 2o, 2q; exp 10 (her IB write-up); exp 9 null |
| Chat vs harness, homework, rejection (agent 11) | 20.86 | 21.05 | 17.93 | – | 2.29 | 0.63 p | verified, on her IB page |
| Goodfire-setup pilots, 20 Oct (main session) | 14.28 | 18.56 | 10.12 | 4.15 | – | – | 1g: the STOP clause |
| Momentum set and follow-ups (agents 8, 14, 15) | 4.24 | 4.88 | – | 3.72 | 0.52 | – | descriptive, n = 1 per variant |
| **Realness probe (agent 5)** | **116.43** | 116.43 | 69.06 | 45.17 | 0.65 | 1.55 u | anchors, her 20 SoRH prompts, 1a, E1, realness frames; many gates |
| **Other environments and judges** | **174.30** | | | | | | |
| Dark Mode (agent 8, orchestrator) | 47.61 | 60.59 | 11.84 | 31.55 | 4.22 | – | (a) 1t/3h, 3/5 vs 0/5; (b) the three-way null |
| SWE-V / DeepSWE (agents 2, 11) | 44.09 | 44.09 | – | 43.30 | 0.79 | – | nulls (20/20 resolved; 0/72 measurable; no rule-visible hack) |
| Transcript judges and labels (agents 6, 7, 8) | 28.56 | 28.56 | 26.95 | 1.56 | 0.05 | – | stakes; reality 5/16; test 3 (2v); 4a; Goodfire 5(c) |
| HVTB (agent 8, orchestrator) | 22.82 | 22.82 | – | 22.80 | 0.02 | – | the pilot's behaviour; the framing test null |
| Dashboard (agent 6) | 15.44 | 15.79 | – | 14.26 | – | 1.18 p | seeds: no gaming, an honest success; the hard run is still going |
| Cooperation study (agent 10) | 8.73 | 8.73 | – | – | – | 8.73 p | labels awaiting her spot check |
| Other envs: B1/D1, D1b/c, provenance, norvane | 4.31 | 5.57 | – | 3.69 | 0.62 | – | couldn't use |
| Terminal-Bench (agent 6) | 1.54 | 1.54 | 1.54 | – | – | – | tb_shortcuts phase 2 |
| τ-bench (agent 6) | 1.20 | 1.20 | – | 1.17 | 0.03 | – | floor effect; closed. Agent 5's τ probe ($0.40) is under the probe |
| **Total** | **1,234.55** | **1,387.12** | **766.68** | **410.58** | **43.30** | **10.64 p, 3.36 u** | |

## Waste (c) by cause

| Cause | Best | × 1.3 | Main items (best) |
|---|---|---|---|
| A run stopped by a change of plan | 13.18 | 16.47 | run 5 $9.33 (its 3 cited episodes, $1.47 pro rata, count as a); exp 11 $1.03; the 20-prompt SoRH screen $1.12; DeepSeek homework on SiliconFlow $0.64; D1c $0.62; the τ first view and smoke tests $0.44 |
| Superseded after a design or limit was fixed | 10.45 | 13.33 | agent 7's 50-message arms $6.16; C1–C4 all read as a test $1.84; 1g launch 1 (one task per cell) $1.58; labeller v3.3 $0.74 |
| In-flight work lost at a pause, cap, guard or sleep | 8.80 | 10.91 | the 21 Oct pause $3.66; the Dark Mode first launch $1.46; caps and guards $2.49 (file probe, run 1, GLM chart 1); Mac sleep (DeepSWE) $0.79; restarts $0.41 |
| A provider cut or a harness-format failure | 6.29 | 7.11 | DeepSeek's tool-call format in Dark Mode $2.75; SiliconFlow's hidden 24k cap $1.44; length cuts $1.58; agent 14's API errors $0.52 |
| Our bug | 2.40 | 2.40 | an unquoted zsh variable sent a full-episode Sol run $2.04; a scorer bug and a labelling stop $0.29; small fixes $0.07 |
| Made but never used | 2.17 | 2.17 | DeepSeek Sol reasoning labels $1.96; a labelling prototype $0.21 |
| **Total** | **43.30** | **52.40** | |

The CSV lists every (c) row with its owner and reason.

**Known but unrecorded** (in no log, so not in these totals):
- the stage-1 pause, about $1–2 (agent 7);
- the realness frames' stops, $0.2–0.8, and the first SoRH screen launch, ~$0.3 (agent 1);
- fill20's dropped streams (agent 1);
- up to $0.30 at the 21 Oct pause, plus 4 hung calls (agent 5);
- the 2 LCB episodes at the guard stop, 2 Qwen-chat calls at the cap, and 2 DeepSeek homework calls (agent 11);
- a 504 in ds_off_before (agent 4);
- G3's provider hang (agent 7);
- agent 14's unconfirmed reservations, up to $2.63.

## Untraced

- **$3.36 of spend** with no itemised use:
  - agent 4's IB re-flag, $1.63;
  - $1.05 of eval_probe lines on 25–26 Oct whose owner is unknown;
  - $0.50 of eval_probe ledger lines before 23 Oct that aren't in agent 5's rows;
  - $0.18 of agent 7's record usage.
- **Outcomes not recorded:**
  - whether her write-up uses agent 8's momentum set, agent 11's screens, or agent 1's pre-23-Oct cue studies;
  - what agent 5 did with agent 7's c11 validation;
  - the use of agent 6's v3.4 repeat run ($0.64);
  - the frames among agent 1's 434 realness records that are outside her cells.
- **.eval files with no usage in their headers** were counted at $0:
  - agent 7's 2 were the cancelled launch, before any call;
  - agent 2's 6 are round1c's hung launch, rebuilt from the buffer and counted once;
  - agent 8's are its mockllm audits (aie 32, forensics 39). From the notes, not checked file by file.

## Lessons: the largest sources of waste

1. **A run stopped by a change of plan is the largest cause ($13.18), and run 5 alone is about a fifth of all waste
   ($9.33 of $43.30, after its 3 cited episodes are counted as a result).** It was launched as a 90-episode quantitative run and stopped after 22 when the work became
   investigative. Exp 11, the 20-prompt screen and D1c follow the same pattern. Two things would have saved most of
   it:
   - settling "quantitative or investigative" before the launch;
   - one episode per arm first, which costs about $3 for run 5.
2. **Limits found after paying ($10.45).**
   - Agent 7's 50-message limit left room for only 2 false rejections, so those arms were re-run at 100 messages.
   - C1–C4 all read as a test, which the probe found after the episodes had run.
   - 1g's first launch put one task in each cell.
   - The fixes: a free mockllm pass counting the messages each arm needs, and the realness probe before the
     episodes, as the later gates did.
3. **In-flight losses at stops ($8.80 recorded, more unrecorded).** The 21 Oct pause alone cost $3.66; caps that
   killed running episodes cost $2.49; Mac sleep cost $0.79. What would have kept most of it:
   - stopping at episode boundaries: no new episodes past the cap, while the running ones finish within a margin;
   - caps sized from the measured cost per episode;
   - AC power, with no lid-close.
4. **A new model or provider without a one- or two-call check ($6.29).** DeepSeek's tool-call format broke the Dark
   Mode harness, and SiliconFlow's hidden 24k cap cut DeepSeek replies. Two cheap checks would have caught them:
   - a length check, like the one later used for GLM and 27B ($0.07), for the hidden cap;
   - a one-call harness smoke test for the tool-call format.

## Addendum (27 Oct)

The tables above are the 11:16Z snapshot and are unchanged. By 13:13Z (when it was recorded, 976666c), the cooperation
study had been dropped by her decision before her spot check. Its $8.73 therefore moves from pending (p) to (b),
"dropped before checking". After the move, at list price: (b) $419.3 (34.0%) and (p) $1.9 (0.2%).
