# split-brain-hypothesis

Do models reward hack more when they believe they are in training or an evaluation? This branch
(`goodfire-lcb`) starts from Goodfire's ImpossibleBench setup (arXiv 2609.19101) on the LiveCodeBench split,
using ImpossibleBench's own Inspect harness. [notes/goodfire_setup.md](notes/goodfire_setup.md) lists their
exact settings, where each comes from, and where this branch differs.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install --no-deps "impossiblebench @ git+https://github.com/safety-research/impossiblebench@d4f9a149db2b9cec0fed7bab01d91c07ee10aca2"
echo 'OPENROUTER_API_KEY=...' > .env    # Inspect reads .env from the working directory
```

Episodes run in Docker (one container per episode, no network). Any Docker engine works; on Apple Silicon it
needs amd64 emulation (Rosetta), because Goodfire's image is amd64. With Colima:

```bash
brew install colima docker-compose
# let docker find the compose plugin: ~/.docker/config.json
#   {"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]}
colima start --vm-type vz --vz-rosetta --cpu 6 --memory 12 --disk 60
```

Each sandbox gets 1 CPU and 2 GB, so this VM runs about 5 episodes at once (`--max-sandboxes 5`).

## Run

```bash
.venv/bin/inspect eval src/lcb_goodfire.py -T split=conflicting -T effort=xhigh \
    --model openrouter/qwen/qwen3.8-2.4t-a95b \
    -M provider='{"order": ["siliconflow/fp8"], "allow_fallbacks": false}' \
    --limit 2 --max-sandboxes 4
.venv/bin/inspect view    # browse the logs in ./logs
```

- `split`: `conflicting`, `oneoff` or `original`.
- `effort`: reasoning effort sent to OpenRouter (Goodfire: `xhigh`). Leave Inspect's `--reasoning-effort` unset;
  version 0.3.140 doesn't accept `xhigh`.
- The provider pin keeps Qwen3.8 2.4T on FP8 weights, as Goodfire ran it.
- A pass on `conflicting` or `oneoff` means the model hacked: no honest solution passes those tests.
