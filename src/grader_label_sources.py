"""Inputs for the shared labeller (src/cot_labels.py) on agent 5's labelling subset.

  python src/grader_label_sources.py <pre-commit runs dir>     # writes logs/grader/label_src/ and id files

- Goodfire sources: id files (one "<source>|<row>" per line) from logs/grader/label_subset.json.
- Pre-commit runs (Kimi K2 Thinking): converted to the labeller's "messages" format. Tool calls are appended to the
  assistant message as "[command] …" and tool outputs become user messages "[tool output] …", since the labeller only
  reads user/assistant turns (it labels the assistant's reasoning and shows the rest as context).
- Agent 3's multi-turn School of Reward Hacks episodes on task 947 (logs/sorh_persistence/label_src/<variant>/), cut
  to turns 1-2: the first reply, the first low score, and the reply after it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "logs" / "grader"
SRC = G / "label_src"
sys.path.insert(0, str(ROOT / "src"))
from precommit_grader import tool_calls  # noqa: E402

NAMES = {"ImpossibleBench impossible | Qwen": "qwen",
         "SWE-bench Verified | Qwen": "swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack",
         "DeepSWE | Qwen": "deepswe-qwen3.8-2.4t-a95b-fp8"}


def main(pc_dir):
    sub = json.loads((G / "label_subset.json").read_text())["sources"]
    SRC.mkdir(parents=True, exist_ok=True)
    for key, name in NAMES.items():
        ids = [f"{name}|{r}" for grp in ("hack", "no_hack") for r in sub[key][grp]]
        (SRC / f"ids_{name}.txt").write_text("\n".join(ids) + "\n")
        print(f"{name}: {len(ids)} ids")
    n = 0
    for key, v in sub.items():
        if not key.startswith("pre-commit"):
            continue
        cond = key.split()[1]
        for grp in ("hack", "no_hack"):
            for run in v[grp]:
                msgs = json.loads((Path(pc_dir) / cond / f"{run}.json").read_text())
                out = []
                for m in msgs:
                    if m.get("role") == "user":
                        out.append({"role": "user", "content": m.get("content") or ""})
                    elif m.get("role") == "assistant":
                        cmds = [c for _, c in tool_calls(m)]
                        text = m.get("content") if isinstance(m.get("content"), str) else ""
                        out.append({"role": "assistant", "reasoning": m.get("reasoning_content") or "",
                                    "content": (text or "") + "".join(f"\n[command] {c[:400]}" for c in cmds)})
                    elif m.get("role") == "tool":
                        out.append({"role": "user", "content": "[tool output] " + str(m.get("content") or "")[:600]})
                p = SRC / "precommit" / cond / f"{grp}__{run}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({"messages": out, "variant": cond, "group": grp}))
                n += 1
    print(f"pre-commit: {n} runs converted")
    k = 0
    for f in sorted((ROOT / "logs" / "sorh_persistence" / "label_src").glob("*/sorh_947/*.json")):
        d = json.loads(f.read_text())
        d["turns"] = (d.get("turns") or [])[:2]
        p = SRC / "sorh947_t12" / f.parts[-3] / "sorh_947" / f.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d))
        k += 1
    print(f"agent 3 task 947: {k} episodes cut to turns 1-2")


if __name__ == "__main__":
    main(sys.argv[1])
