# Running the environment

How to run the anchor arm (A0) yourself. **This has not been run end to end from the published files.** Tested: both prepare scripts,
and the image build as far as installing packages (our test machine's Docker disk filled up there, so allow plenty of
space). Not tested: the scoring server and a full run. Expect small fixes, since the scripts assume our layout.

## You need
- A RunPod account (`~/.runpod/config.toml`, an SSH key in `POD_PUBKEY`) with a 24-48 GB data-centre GPU. Our A0 runs
  used RTX A6000 Ada cards: the task's baseline score depends slightly on the card (0.1275 on Ada, 0.1176 on an A40).
- Docker, `git`, `python3`, `ssh`, `jq`, `rsync`, `uv`, and `pandoc` for the papers. Your `~/.ssh/config` needs
  `Include config.d/*` (`tools/pod.sh` writes the pod's entry there).
- An OpenRouter key in a `.env` file (`OPENROUTER_API_KEY=...`), for open models. The harness is Claude Code.
- The Qwen3.5-4B weights and lens download by themselves on the pod (both public).

## Steps
Put `split-brain-share/` and `split-brain-subject-repo/` side by side, and work in `split-brain-share/`.

```bash
export SB=~/split-brain-run; mkdir -p "$SB/runs"
bash prepare_subject_repo.sh ../split-brain-subject-repo "$SB/snapshot"        # 1. the subject's repo
bash prepare_server_repo.sh ../split-brain-subject-repo "$SB/server-src"       #    the scoring server's source
rsync -a container metric_server "$SB/"

(cd "$SB" && docker build -t sb-subject -f container/Dockerfile \
    --build-context ctx=container snapshot/)                                   # 2. the subject's image

cd "$SB/metric_server"                                                         # 3. the scoring server, ~15 min
JLM_SRC="$SB/server-src" MODEL=4b RIG_TARGET=0.8 NAME=sb-server4b LPORT=8766 bash pod_server.sh up

UPSTREAM=http://127.0.0.1:8766 bash "$SB/container/launch.sh" \
    --run-id test-A0 --model deepseek/deepseek-v4-pro-0813 \
    --brief <path to split-brain-share>/briefs/tc/701743aba6b29b43d4aad884ec2e62c4.md \
    --rig --rig-damp 0.3 --api-provider alibaba --api-key-file <your .env> \
    --hours 6 --snapshot "$SB/snapshot"                                        # 4. one run

JLM_SRC="$SB/server-src" MODEL=4b NAME=sb-server4b LPORT=8766 bash pod_server.sh down   # 5. logs home, pod off
```

The record is in `$SB/runs/<id>/`: `stream.jsonl` (with reasoning), `meta.json`, and the repo's final state. Compare
`meta.json` with `split-brain-runs-share/runs/p04-r2-A0-q27b-tc/meta.json`. Other models: `--model qwen/qwen3.8-27b`,
`--model z-ai/glm-5.2`. Check that the provider serves them.

The server runs from a newer version of the code than the subject sees (`server_overlay/`), which is why it has its own
repo. Keep the two apart: the subject's repo must not hold the overlay.

## How your run will differ from ours
- **Papers**: the six real papers come fresh from arXiv, so they won't match the subject's markdown word for word.
- **Git history**: the subject saw the source repo's rewritten history (880 commits, with each file's date set from
  it). Yours has one commit, and `launch.sh`'s date step will use that.
- **Scrubbed text**: private details were replaced in the notes and tools, and `tools/pod.sh` no longer has our volume.
- **Claude Code**: our runs used 2.1.304. Later versions may behave differently.

## Other arms
Each arm is defined by `briefs/p04/arms/<arm>/` (`arm.json` says what it changes; `repo/` holds the changed files) and
`variants/`. The variant patches were built on the full history and have lost the six papers, so we have not tested
applying them to this repo. Copying an arm's `repo/` files over the prepared repo, and using its brief, is the simple
route for arms that only change those files.

The Dark Mode runs (`pilots/p33-darkmode`, `pilots/p36-darkmode-lever`) use another harness, a fork of
`agent-interp-envs`; we have not checked that they can be rerun from what is here.
