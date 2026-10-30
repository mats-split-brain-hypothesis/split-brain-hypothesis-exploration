"""Probe items for agent 8's norvane real-vs-graded pilot (notes/aie_norvane_pilot_first_messages.json on
mats/agent-8-user-facing, c30900c).

  python src/norvane_pilot_items.py <first_messages.json> logs/eval_probe/p1_norvane_pilot.jsonl

Four items: R and G as system prompt + first user message (the main result), and R and G with the episode's two
pre-executed tool calls appended as the agent's own (secondary). Rendered with src/eval_probe.py's to_chat.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import eval_probe as EP  # noqa: E402


def main(src, out):
    d = json.loads(Path(src).read_text())
    prefix = []
    for tc in d["prefix_tool_calls"]:
        prefix += [{"role": "assistant", "content": "", "calls": [("execute_command", json.dumps({"command": tc["command"]}))]},
                   {"role": "tool", "content": tc["output"], "calls": []}]
    rows = []
    for arm, key in (("R", "R_upstream"), ("G", "G_graded")):
        base = [{"role": "system", "content": d["system_prompt"], "calls": []}, {"role": "user", "content": d[key], "calls": []}]
        for view, msgs in (("first message", base), ("with the 2 pre-executed tool calls", base + prefix)):
            chat = EP.to_chat(msgs)
            rows.append({"item": f"norvane_pilot|{arm}|{view}", "id": f"norvane_pilot|{arm}|{view}", "source": "agent 8 norvane pilot",
                         "group": f"norvane pilot · {arm} · {view}", "family": "qwen", "view": "first",
                         "meta": {"arm": arm, "view": view}, "chars": sum(len(m["content"]) for m in chat), "cut": False,
                         "chat": chat})
    Path(out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    for r in rows:
        print(r["group"], r["chars"], "chars,", len(r["chat"]), "messages")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
