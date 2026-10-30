# Agent 9 brief: exploratory write-up of the split-brain project

Set by the researcher on 2026-10-22: "once all agents finish, have new agent 9 pull everything in an exploratory write
up that is similar to the task game blog. Have the verifier verify the claims. Claims should be backed well or
labeled as potential, and explained how they fit in our bigger question about split-brain hypothesis."

## What to write

An exploratory research post in the style of "Why do models task game?" (Singh, Nanda, Rajamanoharan, Alignment
Forum, Aug 2026; our summary: notes/task_gaming_post.md). Audience: alignment researchers (MATS mentors, Alignment
Forum readers), technical but not on this project.

Shape, following that post:
1. **TL;DR**: the main claims, each tagged.
2. **The question**: nostalgebraist's split-brain hypothesis ("models may behave differently in graded episodes (a
   tirade)") and our subclaims 1a, 1b, 2, 3, 4 (notes/project_brief.md, "The big picture").
3. **Setup**: models (mainly Qwen 3.8 Max; GLM 5.2 and Kimi K3 screens), settings (School of Reward Hacks chats,
   ImpossibleBench, our own agentic scenarios such as D1, Terminal-Bench and DeepSWE transcripts and screens, the
   task-gaming environments we ported), how "reads as real vs graded" was measured (the realness probe and its
   gates), and the methods (pre-registration, single-factor edits, decision-turn resampling, blind hand checks, a
   separate verifier session).
4. **Claims**, one section each, written as existence claims ("cue X causally moves behaviour Y in setting Z"),
   with: the experiment, n, the numbers (k/n), controls, caveats, and a paragraph on what it means for the subclaims.
5. **What didn't move behaviour**, and how much power we had.
6. **Method lessons**: e.g. one sentence about a test suite makes a request read as a test; a person repeating a
   value the model already corrected makes a chat read as a test; graded wording can read as real when the check is
   framed as the person's own; DeepSWE's system line reads as a benchmark to GLM.
7. **Limitations and open questions.**
8. **Appendix**: a table of every result with its map row id and source commit.

## Claim labels (use exactly these)

- **Supported**: pre-registered, verified, and either replicated or seen in more than one setting.
- **Potential**: post hoc, a single task or setting, small n, marginal p, or unverified pieces. Say which.
- **Against**: evidence that cuts against a split-brain subclaim. Report these as prominently as the others.

Every claim states which subclaim(s) it bears on and whether it supports, weakens or doesn't test them.

## Sources and rules

- Numbers come only from verified results: dashboard/data/ov_map.json (rows, verified wording) and
  dashboard/data/ov_map_read.json (reading cards), on the main branch. Cite the row id for each number. Agents'
  notes and notes/review_v2.json give context and plain explanations; the review page's examples
  (notes/review_examples.json in each agent's worktree) give quotes.
- Quotes: use only the curated, verbatim examples already collected. Don't bulk-read raw transcripts or other models'
  reasoning (that tripped a safety filter before); no Claude subagents for reading transcripts.
- Anything that combines rows (a synthesis) is labelled as interpretation, not as a result.
- Match the hedging of the verified wording; don't strengthen it. Where the verifier added a caveat, keep it.
- No API calls; this is writing only.

## Process

1. Work in your own worktree: .claude/worktrees/agent-9-writeup on branch mats/agent-9-writeup off mats-reward-hacking.
2. Write notes/writeup_split_brain.md. Commit as you go.
3. When the draft is complete, tell the orchestrator. The verifier then checks every claim, label and number against
   the sources; fix what it flags, and keep a short changelog at the end of the file.
4. The orchestrator publishes the verified version for the researcher.
