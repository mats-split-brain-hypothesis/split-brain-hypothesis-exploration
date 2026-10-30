"""Secret Number OG / REAL texts (agent 11, 2026-10-27): check and probe items.

    .venv/bin/python src/secret_number_texts.py check
        OG in aie_envs/secret_number/prompts.yaml must equal upstream's secret_number.yaml (vendored) rendered as
        upstream renders it: ${task.*} from the config, pct = int(x*100), pct_complement = int((1-x)*100)
        (scripts/run_common.py @ 310c03f); entrypoint.py adds nothing at noise_prob 0.3 with no scratchpad.
    .venv/bin/python src/secret_number_texts.py items logs/secret_number/probe_items.jsonl
        The "first" view (system prompt + first user message) of OG and REAL for the four probe families, in the
        items format of agent 5's src/eval_probe.py (run unmodified from its worktree).
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "aie_envs" / "secret_number"
FAMILIES = ("qwen", "deepseek", "glm", "qwen27b")   # agent 5's MODEL_OF keys (pins there)


def render_upstream():
    cfg = yaml.safe_load((ENV / "secret_number.upstream.yaml").read_text())
    task = cfg["task"]

    def sub(text):
        text = re.sub(r"\$\{pct_complement:\$\{task\.noise_prob\}\}", str(int((1 - float(task["noise_prob"])) * 100)), text)
        text = re.sub(r"\$\{pct:\$\{task\.noise_prob\}\}", str(int(float(task["noise_prob"]) * 100)), text)
        text = re.sub(r"\$\{task\.(\w+)\}", lambda m: str(task[m.group(1)]), text)
        assert "${" not in text, text
        return text
    return {k: sub(v) for k, v in cfg["prompts"].items()}


def check():
    P = yaml.safe_load((ENV / "prompts.yaml").read_text())
    up = render_upstream()
    ok = P["og"]["system_prompt"] == up["system_prompt"] and P["og"]["user_prompt"] == up["user_prompt"]
    print("OG == rendered upstream secret_number.yaml:", ok)
    for frame in ("og", "real"):
        print(f"{frame}: system {len(P[frame]['system_prompt'])} chars, user {len(P[frame]['user_prompt'])} chars")
    banned = re.compile(r"evaluat|algorithmic reasoning|grading|grade|problem \d|agent", re.I)
    hits = banned.findall(P["real"]["system_prompt"] + P["real"]["user_prompt"])
    print("REAL eval wording:", hits or "none")
    return 0 if ok and not hits else 1


def items(out):
    P = yaml.safe_load((ENV / "prompts.yaml").read_text())
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w") as f:
        for frame in ("og", "real"):
            chat = [{"role": "system", "content": P[frame]["system_prompt"]},
                    {"role": "user", "content": P[frame]["user_prompt"]}]
            for family in FAMILIES:
                iid = f"secret_number|{frame}"
                f.write(json.dumps({"item": f"{iid}|{family}|first", "id": iid, "source": "secret_number",
                                    "group": f"secret_number · {frame}", "family": family, "view": "first",
                                    "meta": {}, "chars": sum(len(m["content"]) for m in chat), "cut": False,
                                    "chat": chat}) + "\n")
                n += 1
    print(f"{n} items -> {out}")


if __name__ == "__main__":
    if sys.argv[1] == "check":
        sys.exit(check())
    items(sys.argv[2])
