"""Probe items for the precommit_hook realness check (agent 6): the "first" view (system prompt + first user message)
of the OG and REAL framings in aie_envs/precommit_hook/prompts.yaml, for Qwen 3.8 2.4T and DeepSeek V4 Pro, in the
items format of agent 5's src/eval_probe.py (run unmodified from its worktree).

    python src/precommit_probe_items.py logs/stakes/precommit/probe_items.jsonl
"""
import json
import sys
from pathlib import Path

import yaml

P = yaml.safe_load((Path(__file__).resolve().parents[1] / "aie_envs/precommit_hook/prompts.yaml").read_text())
out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w") as f:
    for frame in ("og", "real"):
        chat = [{"role": "system", "content": P[frame]["system_prompt"]},
                {"role": "user", "content": P[frame]["user_prompt"]}]
        for family in ("qwen", "deepseek"):
            iid = f"precommit_hook|{frame}"
            f.write(json.dumps({"item": f"{iid}|{family}|first", "id": iid, "source": "precommit_hook",
                                "group": f"precommit_hook · {frame}", "family": family, "view": "first", "meta": {},
                                "chars": sum(len(m["content"]) for m in chat), "cut": False, "chat": chat}) + "\n")
print(f"4 items -> {out}")
