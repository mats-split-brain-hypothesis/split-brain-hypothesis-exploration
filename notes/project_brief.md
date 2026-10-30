# Project brief (read first)

Shared brief for every session working on this project (branch `mats-reward-hacking`). Set by the researcher on
2026-10-21.

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
