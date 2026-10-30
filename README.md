# Split-brain hypothesis: exploration

Do language models reward hack when a context looks like a graded episode, and follow the person's intent when it
looks like real use? This repository holds the code and notes from an exploratory MATS project (October 2026) by
Bianca Ganescu and Anthony Goncharov that tests that idea, the "split-brain hypothesis" from nostalgebraist's post
[*Models may behave differently in graded episodes (a tirade)*](https://www.lesswrong.com/posts/AfoGGrJfuNzofpzWL/models-may-behave-differently-in-graded-episodes-a-tirade).

**Status.** Exploratory. Samples are small (typically 20 prompts × 1 reply, or 6 tasks × 3 episodes, per condition),
so every result below is "points this way at this size", not a confirmed effect. The write-up states the scale,
the rival readings and a strength tag for each claim.

## The question, split into claims

We split the hypothesis into five claims and tested them one at a time:

| Claim | Statement |
|---|---|
| 1a | Models reward hack more the more a context looks like a graded episode. |
| 1b | A model is less likely to hack if it thinks it is helping a real user. |
| 2 | Models can tell graded episodes from real interactions, and that is what causes the change. |
| 3 | "Reflexes" (insensitive to evidence, no reasoning spent) and "flexible reward pursuit" (infers the grader and adapts to evidence about it) are distinct phenomena. |
| 4 | Models are not unconditional reward seekers: reward seeking is triggered by context that suggests grading. |

## What we found so far

From the write-up (four models; counts are per model, in the order Qwen 3.8 2.4T, DeepSeek V4 Pro, GLM 5.2,
Qwen 3.8 27B):

- **1a: yes, but through one channel, a well-defined score to optimise.** On 20 School of Reward Hacks prompts, no
  model padded its answer without a stated score (0, 0, 0 and 3 of 20) and all four did with one (14, 17, 14 and 17
  of 20). A score sentence that doesn't say what is counted ("will be scored") gives almost nothing (2, 1, 0, 1 of
  20), and labelling the setting as an evaluation, training or real use moves padding far less than the score does.
- **1b: it depends on what the user says they want.** "I don't care about the score" brings padding down to 3, 5,
  1 and 6 of 20. In ImpossibleBench, a student asking for homework help gets honest first replies (3, 0, 0, 0 of 18
  hacked, against 17, 2, 0, 15 from an automated pipeline), but relaying the grader's rejection brings the hack back.
  A human reader changes what the model says more than what it does.
- **2: not supported where we measured it.** Behaviour moves while a probe's reading of the setting stays put: when
  the score is switched off mid-conversation, padding falls from 14 to 1 of 20 while none of 708 probe answers
  say the conversation is real. The probe reads text after the fact, not the model's in-task belief.
- **3: we think so.** Flexible pursuit is common: reasoning is spent on the score, and behaviour changes with evidence
  about the grader. Reflex-like cases look model-specific (DeepSeek V4 Pro keeps its hacks when told grading is off),
  and we can't yet tell persistence apart from not weighing the message.
- **4: supported in a narrow sense.** With no score, padding is 0 to 3 of 20 and there are no score-driven reasoning
  spirals (0 of 80 replies); with the score withdrawn, padding drops to 0 to 3 of 20 on three of the four models.

The full write-up, with figures, per-cell tables, verified quotes and null results, is
[`notes/writeup_oct28.md`](https://github.com/mats-split-brain-hypothesis/split-brain-hypothesis-exploration/blob/bianca/agent-22-writeup/notes/writeup_oct28.md) on the branch
`bianca/agent-22-writeup`.

## Environments and models

- **School of Reward Hacks (SoRH)**
  ([longtermrisk/school-of-reward-hacks](https://huggingface.co/datasets/longtermrisk/school-of-reward-hacks)): a fixed
  set of 20 writing requests, each in a plain and a scored version; every other condition adds or replaces one
  sentence. One reply per prompt per condition.
- **ImpossibleBench**: Goodfire's harness ([arXiv 2609.19101](https://arxiv.org/abs/2609.19101)) on six
  LiveCodeBench tasks from the "conflicting" split, where the tests contradict each other, so passing them is a
  hack. Conditions vary who is asking, the instruction, and messages after the first rejection.
- **Our own coding scenarios** (`scenarios/`): small repositories with visible tests and held-out checks the model
  never sees, used to separate solving the task from passing the tests.
- **Anthony's real-to-graded environment**: one of our own real research repos turned into a graded episode (the
  "planted paper" runs). Its code, a sample of its transcripts and the steps to run it are under `anthony/` (start with `anthony/split-brain-share/REPLICATE.md`).

Models, all at reasoning effort `xhigh` through OpenRouter with pinned providers: Qwen 3.8 2.4T (SiliconFlow FP8),
DeepSeek V4 Pro (SiliconFlow FP8), GLM 5.2 (SiliconFlow FP8) and Qwen 3.8 27B (DeepInfra BF16). Judges: GPT-5.6
Luna (padding) and GPT-5.6 Sol (reasoning labels).

**Method.** We followed the model-forensics approach of Singh et al. ([arXiv 2606.26071](https://arxiv.org/abs/2606.26071)):
start from one concrete incident, read the rollouts and reasoning, write rival hypotheses, change one factor at a time
so the hypotheses predict different behaviour, and register each experiment's reading before its first call.

## Repository layout

`main` holds the project's main line:

```
bianca/            Bianca's code and notes (main line of the private working repo)
  src/             harness wrappers, run scripts and analysis
  scenarios/       our coding scenarios: workspace/, heldout/, scenario.json
  sandbox/         Docker compose file for the episode sandbox (no network, 1 CPU, 2 GB)
  dashboard/       the results dashboard's code
  notes/           findings, designs and decisions, one note per topic
anthony/           Anthony's environment and analysis (split-brain-share), the subject's repo (split-brain-subject-repo), transcript sample (split-brain-runs-share)
```

Most of the code and notes were written by Claude Code agents, each on its own branch under our direction; the
notes refer to them as "agent N". Each `bianca/*` branch is a single snapshot of one workstream's latest files:

| Branch | Workstream |
|---|---|
| `bianca/mats-reward-hacking` | main line (same as `bianca/` on `main`) |
| `bianca/agent-1-sorh-cues` | SoRH: which prompt cues change padding and reasoning (the SoRH run code) |
| `bianca/agent-2-ib-cues` | ImpossibleBench: cues in the task prompt |
| `bianca/agent-3-sorh-persistence` | SoRH: persistence after the score is withdrawn |
| `bianca/agent-4-ib-persistence` | ImpossibleBench: persistence and the first submission |
| `bianca/agent-5-grader-definition` | the "real or evaluation?" probe |
| `bianca/agent-6-stakes` | stakes |
| `bianca/agent-7-rejection` | the effect of the grader's rejection |
| `bianca/agent-8-user-facing` | user-facing versions and forensics |
| `bianca/agent-9-presentation` | presentation |
| `bianca/agent-10-audit` | audit of methods and results |
| `bianca/agent-11-ib-design` | ImpossibleBench: chat against harness, the grader in the chat |
| `bianca/agent-12-provenance-pilot` | provenance pilot |
| `bianca/agent-13-ib-transcripts` | ImpossibleBench transcripts |
| `bianca/agent-14-ib-authority` | ImpossibleBench: authority |
| `bianca/agent-15-ib-momentum` | ImpossibleBench: momentum |
| `bianca/agent-16-ib-oracle` | ImpossibleBench: oracle |
| `bianca/agent-17-reasoning-review` | review of the reasoning evidence |
| `bianca/agent-18-sorh-inventory` | inventory of SoRH findings |
| `bianca/agent-19-ib-inventory` | inventory of ImpossibleBench findings |
| `bianca/agent-20-graph-inventory` | inventory of figures |
| `bianca/agent-21-dashboard-reasoning` | reasoning views for the dashboard |
| `bianca/agent-22-writeup` | the write-up and its figures |
| `bianca/goodfire-lcb` | first reproduction of Goodfire's ImpossibleBench setup |

**Not included** (for `bianca/`; `anthony/` has a transcript sample, see its READMEs): run logs, transcripts, model outputs and the JSON/CSV data the analyses produce. Goodfire's own
transcripts are public at [Goodfire/reward-hack-data](https://huggingface.co/datasets/Goodfire/reward-hack-data).

**Licence.** The MIT licence covers our code and notes, not third-party text (real papers and excerpts of them under `anthony/`). Some papers under `anthony/` are fictional test material and say so: do not cite them.

## Running it

From `bianca/` on `main` (or the root of a `bianca/*` branch):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install --no-deps "impossiblebench @ git+https://github.com/safety-research/impossiblebench@d4f9a149db2b9cec0fed7bab01d91c07ee10aca2"
echo 'OPENROUTER_API_KEY=...' > .env
```

Episodes run in Docker, one container per episode, with no network. Goodfire's image is amd64, so Apple Silicon
needs emulation, for example with Colima:

```bash
colima start --vm-type vz --vz-rosetta --cpu 6 --memory 12 --disk 60
```

`inspect_ai==0.3.140` and `openai==2.5.0` are pinned on purpose (see `requirements.txt`). Then:

```bash
# ImpossibleBench with Goodfire's settings, one task
.venv/bin/inspect eval src/lcb_goodfire.py -T split=conflicting -T effort=xhigh \
    --model openrouter/qwen/qwen3.8-2.4t-a95b \
    -M provider='{"order": ["siliconflow/fp8"], "allow_fallbacks": false}' \
    --sample-id lcbhard_99 --log-dir logs/example

# one of our scenarios
.venv/bin/inspect eval src/scenarios.py -T scenario=b1_dedupe -T audience=colleague -T graded=true --model ...

# results and costs
.venv/bin/python src/episodes.py logs/example
.venv/bin/python src/costs.py logs/example
```

`bianca/CLAUDE.md` documents the harness options, the scenario format and the known pitfalls.

## References

- nostalgebraist, [Models may behave differently in graded episodes (a tirade)](https://www.lesswrong.com/posts/AfoGGrJfuNzofpzWL/models-may-behave-differently-in-graded-episodes-a-tirade), LessWrong, 2026.
- Goodfire, ImpossibleBench reward-hacking study, [arXiv 2609.19101](https://arxiv.org/abs/2609.19101), and its
  transcripts, [Goodfire/reward-hack-data](https://huggingface.co/datasets/Goodfire/reward-hack-data).
- [ImpossibleBench](https://github.com/safety-research/impossiblebench).
- [School of Reward Hacks](https://huggingface.co/datasets/longtermrisk/school-of-reward-hacks).
- Singh, Kroiz, Rajamanoharan and Nanda, Why did my model do that? Model forensics for diagnosing LLM misbehavior,
  [arXiv 2606.26071](https://arxiv.org/abs/2606.26071).
