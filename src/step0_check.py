"""Step 0 for a model replication (notes/ib_persistence.md §21): one tiny OpenRouter call, pinned to one provider with
no fallbacks, reasoning effort as Inspect sends it (extra_body reasoning.effort). Prints counts and types only: HTTP
status, serving provider, finish reason, usage (incl. reasoning tokens), the reasoning field's length and the
reasoning_details types (reasoning.text = full text; reasoning.summary / reasoning.encrypted = not full). Never prints
the reasoning text. Generalises §16's DeepSeek step 0.

    python src/step0_check.py <model> <provider> [effort]
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

model, provider = sys.argv[1], sys.argv[2]
effort = sys.argv[3] if len(sys.argv) > 3 else "xhigh"
key = next(l.split("=", 1)[1].strip().strip("'\"") for l in (Path(__file__).parents[1] / ".env").read_text().splitlines()
           if l.startswith("OPENROUTER_API_KEY="))
body = {"model": model, "provider": {"order": [provider], "allow_fallbacks": False}, "reasoning": {"effort": effort},
        "max_tokens": 4000, "messages": [{"role": "user", "content": "What is 17 * 23? Reply with just the number."}]}
req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=300))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read()[:500])
    raise SystemExit(1)
ch, u = r["choices"][0], r.get("usage", {})
msg = ch["message"]
print(f"{model} via {provider}: served by {r.get('provider')} | finish {ch.get('finish_reason')} | prompt "
      f"{u.get('prompt_tokens')} completion {u.get('completion_tokens')} reasoning "
      f"{(u.get('completion_tokens_details') or {}).get('reasoning_tokens')} | cost {u.get('cost')}")
print(f"  reasoning field chars {len(msg.get('reasoning') or '')} | reasoning_details types "
      f"{[d.get('type') for d in (msg.get('reasoning_details') or [])]} | answer {(msg.get('content') or '')[:40]!r}")
