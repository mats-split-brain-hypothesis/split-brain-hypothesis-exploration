# Ports of agent-interp-envs environments

Environments from https://github.com/gkroiz/agent-interp-envs (MIT; licence in `LICENSE.agent-interp-envs`), commit
`310c03fbafdbb16df9ee043a7d9dd18a6d8cd3ec`, rebuilt for our Inspect harness: the model loop runs on the host
(`src/aie_<env>.py`), the sandbox holds only the task and has no network. Task files and prompts are copied verbatim
(`task/` is byte-identical to upstream's `environments/<env>/task/`; `prompts.yaml` holds the shipped config's
prompts). Plan and differences from upstream: `notes/aie_port_plan.md`.

- `norvane/`: Broken Test Runner. Task `src/aie_norvane.py`; mock check `src/aie_mock_norvane.py` (4 scripted
  episodes, all passing).
