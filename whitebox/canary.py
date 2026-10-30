"""Does a model behind OpenRouter (provider pinned) see its earlier-turn thinking? Canary through api_proxy.py, in
Claude Code's request shape (adaptive thinking, a tool loop).

    python3 canary.py --port P [--tries 3]     # api_proxy.py --model M --provider alibaba listening on 127.0.0.1:P

Turn 1: the model picks a secret 6-digit number in its thinking only, then calls get_time. Turn 2: the tool result
and "what was the number?", sent twice: with the turn-1 thinking block in the history, and with it removed. Thinking
dropped downstream => same input tokens both ways and no recall.
"""

import argparse
import json
import re
import urllib.request

ASK1 = ("Before anything else, privately choose a random 6-digit number in your reasoning. Do not write it in your "
        "visible reply or in any tool call. Then call the get_time tool.")
ASK2 = ("What was the 6-digit number you chose in your reasoning before calling the tool? If you cannot see it, reply "
        "exactly: NOT VISIBLE.")
TOOLS = [{"name": "get_time", "description": "Returns the current time.",
          "input_schema": {"type": "object", "properties": {}}}]
PARAMS = {"max_tokens": 4000, "thinking": {"type": "adaptive", "display": "summarized"},
          "output_config": {"effort": "high"}, "tools": TOOLS}


def call(port: int, messages: list[dict]) -> dict:
    body = json.dumps({"model": "x", "messages": messages, **PARAMS}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/messages", body,
                                 {"content-type": "application/json", "anthropic-version": "2023-06-01",
                                  "x-api-key": "via-proxy"})
    return json.loads(urllib.request.urlopen(req, timeout=600).read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--tries", type=int, default=3)
    a = ap.parse_args()
    for t in range(a.tries):
        u1 = {"role": "user", "content": ASK1}
        r1 = call(a.port, [u1])
        thinking = " ".join(c.get("thinking", "") for c in r1["content"] if c["type"] == "thinking")
        visible = json.dumps([c for c in r1["content"] if c["type"] != "thinking"])
        nums = re.findall(r"\b\d{6}\b", thinking)
        use = next((c for c in r1["content"] if c["type"] == "tool_use"), None)
        if not nums or not use or nums[-1] in visible:
            print(f"try {t}: no clean secret (numbers {nums[-3:]}, tool call {bool(use)}); skipped")
            continue
        secret = nums[-1]
        u2 = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": use["id"], "content": "12:00"},
                                          {"type": "text", "text": ASK2}]}
        with_th = call(a.port, [u1, {"role": "assistant", "content": r1["content"]}, u2])
        without = call(a.port, [u1, {"role": "assistant", "content": [c for c in r1["content"]
                                                                       if c["type"] != "thinking"]}, u2])
        for name, r in (("with thinking", with_th), ("without", without)):
            ans = " ".join(c.get("text", "") for c in r["content"] if c["type"] == "text").strip()
            u = r.get("usage", {})
            n = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
            print(f"try {t}: secret {secret} ({len(thinking)} thinking chars) | {name:13}: input {n:>5} tokens, "
                  f"recalled {secret in ans}, answer {ans[:70]!r}")


if __name__ == "__main__":
    main()
