"""Render a rebuilt request (rebuild.py) into Qwen3.8-27B's prompt text with the model's own chat template, the way an
Anthropic -> OpenAI-style conversion would hand it over: system blocks joined, tool_result blocks as tool messages,
thinking as reasoning_content, tool_use as tool_calls, mid-conversation system messages as user messages.

    python render.py out/RUN [--drop-thinking] [--effort xhigh|medium|low|none] [--with-response]

Prints the token count (to compare with the input tokens OpenRouter reported for that turn) and writes
out/RUN/prompt[-variant].txt. With --with-response the subject's actual reply (thinking, text, tool calls) is appended
after the generation prompt, as one teacher-forced sequence.
"""

import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "Qwen/Qwen3.8-27B"


def text(blocks) -> str:
    if isinstance(blocks, str):
        return blocks
    return "\n".join(b["text"] if b.get("type") == "text" else json.dumps(b) for b in blocks)


def convert(req: dict, drop_thinking: bool) -> tuple[list[dict], list[dict]]:
    msgs = [{"role": "system", "content": "\n".join(b["text"] for b in req["system"])}]
    for m in req["messages"]:
        if m["role"] == "assistant":
            out = {"role": "assistant", "content": "\n".join(c["text"] for c in m["content"] if c["type"] == "text")}
            th = "\n".join(c["thinking"] for c in m["content"] if c["type"] == "thinking")
            if th and not drop_thinking:
                out["reasoning_content"] = th
            calls = [{"type": "function", "function": {"name": c["name"], "arguments": c["input"]}}
                     for c in m["content"] if c["type"] == "tool_use"]
            if calls:
                out["tool_calls"] = calls
            msgs.append(out)
            continue
        rest = []
        for c in m["content"]:
            if c.get("type") == "tool_result":
                msgs.append({"role": "tool", "content": text(c.get("content", ""))})
            else:
                rest.append(c["text"])
        if rest:
            msgs.append({"role": "user", "content": "\n".join(rest)})
    tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                               "parameters": t.get("input_schema", {})}} for t in req["tools"]]
    return msgs, tools


def response_text(resp: dict) -> str:
    """The reply as the model emits it after '<think>\\n': thinking, '</think>', text, tool calls."""
    th = "\n".join(c["thinking"] for c in resp["content"] if c["type"] == "thinking").strip()
    body = "\n".join(c["text"] for c in resp["content"] if c["type"] == "text").strip()
    calls = ""
    for c in resp["content"]:
        if c["type"] == "tool_use":
            params = "".join(f"<parameter={k}>\n{v if isinstance(v, str) else json.dumps(v)}\n</parameter>\n"
                             for k, v in c["input"].items())
            calls += f"\n\n<tool_call>\n<function={c['name']}>\n{params}</function>\n</tool_call>"
    return f"{th}\n</think>\n\n{body}{calls}<|im_end|>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--drop-thinking", action="store_true")
    ap.add_argument("--effort", default="xhigh", choices=["xhigh", "medium", "low", "none"])
    ap.add_argument("--with-response", action="store_true")
    a = ap.parse_args()
    d = Path(a.dir)
    req = json.loads((d / "request.json").read_text())
    tok = AutoTokenizer.from_pretrained(MODEL)
    msgs, tools = convert(req, a.drop_thinking)
    kw = {} if a.effort == "none" else {"reasoning_effort": a.effort}
    if a.effort == "none":
        kw["enable_thinking"] = True
    prompt = tok.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=True, **kw)
    if a.effort == "none":  # the template always adds an effort line when thinking is on: strip it for this variant
        prompt = prompt.replace("Reasoning effort is set to xhigh. Please think carefully through the task, validate key "
                                "assumptions, consider plausible alternatives, and prioritize correctness, consistency, "
                                "and clarity in the final answer.\n\n", "")
    n = len(tok(prompt, add_special_tokens=False)["input_ids"])
    tag = ("-nothink" if a.drop_thinking else "") + (f"-{a.effort}" if a.effort != "xhigh" else "")
    if a.with_response:
        prompt += response_text(json.loads((d / "response.json").read_text()))
        tag += "-full"
    (d / f"prompt{tag}.txt").write_text(prompt)
    total = len(tok(prompt, add_special_tokens=False)["input_ids"])
    print(f"prompt{tag}: {n:,} prompt tokens" + (f", {total:,} with the response" if a.with_response else ""))


if __name__ == "__main__":
    main()
