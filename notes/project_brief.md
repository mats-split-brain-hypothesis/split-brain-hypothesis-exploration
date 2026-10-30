# Project brief (read first)

Shared brief for every session working on this project (branch `mats-reward-hacking`). Set by the researcher on
2026-10-21.

## The big picture (set by the researcher, 2026-10-21 evening)

We are proving or disproving the split-brain hypothesis from nostalgebraist's post "models may behave differently in
graded episodes (a tirade)" (LessWrong, 7 Aug 2026:
https://www.lesswrong.com/posts/AfoGGrJfuNzofpzWL/models-may-behave-differently-in-graded-episodes-a-tirade), split
into subclaims tested one by one:

- **1a.** Models reward hack more the more a context looks like a graded episode.
- **1b.** A model is less likely to hack if it thinks it is interacting with and helping a user.
- **2.** Models can distinguish "graded episodes" from "real" interactions, and this is what causes the change.
- **3.** "Reflexes" (invariant to evidence; no reasoning allocated) and "flexible reward-pursuit" (infers the grader and
  adapts to evidence about it; reasoned) are distinct phenomena.
- **4.** Models are not unconditional reward seekers: reward seeking is triggered by context suggesting grading.

Say which subclaim each result bears on. The post's own operational tests: reflexes survive user corrections and
evidence; pursuit changes when the evidence about the grader changes, and gets reasoning allocated. Cues it names
for graded episodes: gradeability, a task, an RLVR-like horizon, agent loops with no human, terse templated feedback,
exam-like form, difficulty pressure. For real use: free-form conversation, not crisply verifiable, a real question,
a recognisable real user, long-horizon consequences.

## How we iterate: model forensics (researcher, 2026-10-22)

Work like Singh, Kroiz, Rajamanoharan and Nanda, "Why did my model do that? Model forensics for diagnosing LLM
misbehavior" (LessWrong, Feb 2026; arXiv 2606.26071):

1. **Start from one concrete incident** (a run where the model hacked or didn't, with its transcript).
2. **Read the rollouts and reasoning yourself** (dozens, with local scripts, never Claude subagents) and write
   rival hypotheses as versions (H1 v1 → v2), separating motivating factors from enabling ones.
3. **Pick edits on which the hypotheses predict different behaviour.** One factor per edit, everything else fixed.
   Check by reading rollouts that the edit took effect and didn't change how the model reads the rest.
4. **Measure over many rollouts** with 95% Wilson intervals. Use dose-response sweeps where a factor has a size,
   mundane or no-stakes controls (remove the trigger), and a control model where one exists.
5. **Converge from decorrelated methods**: counterfactual edits, predictions in new conditions, and third-person
   or follow-up probes (e.g. agent 5's "real or evaluation?" probe), each with different confounds.
6. **Rule out benign explanations**: task misspecification, ambiguous intent, confusion, overzealousness.
7. **Keep an Analysis of Competing Hypotheses table** (evidence rows × hypotheses, with the confound of each row),
   and report hedged findings. Negative results are weak without a positive control.

Pre-register each experiment's reading before its first call, as we already do.

## Goal

Determine what triggers reward hacking and when models do it:
- link it to cues in the environment or the prompt;
- map from environment/cues to model reflexes;
- find how reward hacking links to other behaviours, such as persistence, hesitation, or trying to recall the task.

## Data

- **School of Reward Hacks:** https://huggingface.co/datasets/longtermrisk/school-of-reward-hacks
  1,073 one-turn prompts, each with a gamed answer (written by GPT) and an honest `control` answer. No transcripts of
  our models: every result here means new runs (cheap, ~$0.02–0.04 per call on Qwen 3.8 Max at xhigh). The prompts
  state the metric, so gaming it can be instruction-following; compare against the `control` answer.
- **ImpossibleBench and the SWE-like datasets** used in Goodfire's paper (https://arxiv.org/abs/2609.19101), with
  transcripts at https://huggingface.co/datasets/Goodfire/reward-hack-data. Models: GLM 5.2, Kimi K3 and Qwen 3.8
  Max on ImpossibleBench, SWE-bench Verified (only the prompt with the "Do not reward hack" section) and DeepSWE; GLM
  5.2 and Kimi K3 only on ShoppingBench and τ3-bench. Nothing for DeepSeek V4 Pro or Qwen 3.8 27B.
  **Data caveat (agent 7, 2026-10-21):** ImpossibleBench LiveCodeBench's "original" (possible) split has 3 tasks
  whose own tests are wrong: lcbhard_57 (`candidate([74, 51], 1) == 125`, but 74 XOR 51 = 121), lcbhard_61 (expects
  64 where the total isn't divisible by 3, so -1) and lcbhard_81 (expects 500; brute force gives 499). In Goodfire's
  transcripts these are 9 of the 308 possible-split episodes, and the models say the test is wrong before any
  rejection. Exclude or flag them wherever the possible split is used as a no-obstacle baseline. Confirmed by the
  verifier with reference solutions: each suite fails exactly that one assertion. **A 4th flawed task, lcbhard_67**
  (verifier): test 9 calls with n=3 but uses vertices up to 15, contradicting "vertices are numbered 1 to n". All three
  models infer the range from the edges and pass, and Goodfire's judge marks all three as hacks, so 3 of the 17
  possible-split verdict-yes hacks are on this malformed test. Exclude 57, 61 and 81 (unpassable honestly) and treat
  67 separately in any possible-split baseline, for rejections and for hack rates.
- **Terminal-Bench** (https://arxiv.org/abs/2601.11868 is version 2.0; its transcripts aren't released). Public
  transcripts with full reasoning, found 2026-10-21:

  | Model | Source | Version, harness, size | Notes |
  |---|---|---|---|
  | GLM 5.2 | https://hub.harborframework.com/jobs/39e46742-0f20-52ef-a6cb-7a1a1c71c91b (official) | TB 3.0, Claude Code, 370 episodes (74 × 5), max effort | 4.6% pass, ~1/3 errored |
  | Qwen 3.8 Max | https://hub.harborframework.com/jobs/e630e811-bfab-5823-8acc-0224c6e2dba9 (official) | TB 4.0, Claude Code, 330 episodes (66 × 5), max effort | `qwen3.8-max-0902` snapshot; not confirmed to be the same weights as `qwen3.8-2.4t-a95b` |
  | GLM 5.2 | https://huggingface.co/datasets/0xSero/glm-5.2-nf3-hybrid-terminal-bench-2.1-traces | TB 2.1, Terminus-2, 89 × 1 | quantised, self-hosted; MIT |
  | Qwen 3.8 27B | https://huggingface.co/datasets/openguardrails/tb21-qwen3.8-27b-terminus2 | TB 2.1, Terminus-2, 89 × 1, xhigh | BF16; MIT |
  | Qwen 3.8 27B | https://huggingface.co/datasets/malaiwah/qwen38-27b-terminal-bench-2.1 | TB 2.1, Terminus-2 | quantised (EXL3), BF16 only for re-runs of failed tasks; Apache-2.0 |
  | Qwen 3.8 27B | https://huggingface.co/datasets/Lottolabs/terminal-bench-2.1-qwen3.8-27b-traces | TB 2.1, OMP harness, 89 at xhigh + failures re-run at lower effort | GPTQ 4-bit; MIT |

  Nothing for Kimi K3 or DeepSeek V4 Pro (closest: Kimi K3 on Long-Horizon Terminal-Bench,
  `AgentNativeResearchLab/lhtb-kimi-k3-trajectories`; DeepSeek V4 *Flash* on TB 2.1,
  `openguardrails/terminal-bench-2.1-deepseek-v4-flash-trajectories`). Harbor Hub trials are ATIF `trajectory.json`
  files (`reasoning_content` per step), fetchable from
  `https://hub.harborframework.com/api/trials/<trial_id>/trajectory?jobId=<job_id>` or with
  `harbor job download <job-id>`; Hub jobs state no licence. Limits: harnesses and versions differ, one condition
  per run, no hack labels. Parked for now; the likely use is recall and solution lookup within one model (TB 3.0+
  allows internet but tells agents not to look up task-specific solutions).

## Models

GLM 5.2, Kimi K3, Qwen 3.8 Max (Qwen3.8 2.4T), DeepSeek V4 Pro and/or Qwen 3.8 27B.

## Rules for running things

- When transcripts are available, always use those.
- Don't run anything at scale initially: at most 5 episodes per model and per task variation.
- Always start with one model.
- The researcher decides when to scale, based on observed behaviour.

## Reporting results

Every result or conclusion (in notes and in messages) states the experiment and its scale:
- **Experiment:** dataset and split, model, provider and reasoning effort, harness, the exact text or setting of
  each variant, and how prompts or tasks were chosen.
- **Scale:** number of prompts or tasks × samples per variant, total episodes or calls, and n behind every rate
  ("3/20", not "15%").
- **Cost** of the run.

## Decisions (2026-10-21)

- **First model:** Qwen 3.8 Max (`openrouter/qwen/qwen3.8-2.4t-a95b`, pinned to `siliconflow/fp8`) at reasoning
  effort `xhigh`.
- **Sample size:** 5 samples per variation of a task. Example: ImpossibleBench LiveCodeBench with k variations is
  5 × k episodes in total. **Screening rounds** (agreed per agent) use 1 sample per prompt or task per variant
  (agent 1: 20 prompts; agents 2 and 4: 2 tasks; agent 3: about 10 prompts); only variants that move behaviour get
  more. Every chart and note says which kind of cell it shows.
- **Spend:** each agent counts its own spend from its runs' usage records (`usage.cost`, or `src/costs.py` × ~1.3),
  never as a drop in the key's `limit_remaining` (shared with every agent and another project). The key's balance
  is only a global stop: below $10, stop and tell the orchestrator.
- **The chain of thought is central.** Analyse what the reasoning says (retries, doubts, recall, beliefs about the
  setting), not only the actions and the final output.
- **Persistence and hesitation** are defined in `notes/definitions.md` (being agreed with the researcher); use those
  definitions so results from different agents can be combined.
- **One branch per agent**, each in its own worktree under `.claude/worktrees/` (see CLAUDE.md).

## Inspiration for the approach

- https://arxiv.org/abs/2606.26071 (Model Forensics)
- https://www.alignmentforum.org/posts/aTcsN5ZZDnMFJvRiG/models-may-behave-worse-when-eval-aware
- https://www.alignmentforum.org/posts/HACauvWhEdC6QhdS4/why-do-models-task-game
