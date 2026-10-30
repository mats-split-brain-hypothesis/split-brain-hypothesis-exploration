"""One `claude -p` call on the logged-in Max plan: no tools, a system prompt, JSON-schema output, an empty cwd (no
CLAUDE.md, no project settings). Shared by the run coders (audience_relation.py, deception_scale.py)."""

import json
import re
import subprocess
import tempfile


def claude_json(prompt: str, system: str, schema: dict, model: str, effort: str, timeout: int = 1800) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(["claude", "-p", "--model", model, "--effort", effort, "--tools", "", "--system-prompt", system,
                            "--output-format", "json", "--json-schema", json.dumps(schema), "--no-session-persistence"],
                           input=prompt, capture_output=True, text=True, cwd=tmp, timeout=timeout)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"claude exited {r.returncode}: {r.stderr[-300:]}")
    j = json.loads(r.stdout)
    if j.get("is_error"):
        raise RuntimeError(f"claude error: {str(j.get('result'))[:300]}")
    out = j.get("structured_output") or json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", j["result"].strip()))
    u = j.get("usage", {})
    return out, {"input": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                 "cache_read": u.get("cache_read_input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
                 "output": u.get("output_tokens", 0), "cost_usd_list": j.get("total_cost_usd"), "ms": j.get("duration_ms")}


# ---- Anthropic Messages API via OpenRouter (billed; key OPENROUTER_API_KEY in ~/j-lens-mean/umot/.env, never printed;
# the Anthropic key ran out of credits 2026-10-26). OpenRouter's /v1/messages takes the Anthropic body; routing is pinned
# to the anthropic provider with no fallback so the prompt cache stays on one backend. Unlike `claude -p` it
# caches: the shared prefix (a run's transcript) is one content block marked for the cache, the varying part follows.
# List prices per 1M tokens (input, output); cache writes 1.25x input (5 min TTL), reads 0.1x. Haiku 5.5's input price
# is $0.50 above 100k prompt tokens ($0.10 below), output $2.50 above.
PRICES = {"claude-sonnet-5": (2.00, 10.00), "claude-haiku-5-5": (0.50, 2.50)}
_client = None


def _api():
    global _client
    if _client is None:
        import anthropic
        from pathlib import Path
        env = (Path.home() / "j-lens-mean/umot/.env").read_text().splitlines()
        key = next((l.split("=", 1)[1].strip().strip('"') for l in env if l.startswith("OPENROUTER_API_KEY=")), None)
        if not key:
            raise SystemExit("no OPENROUTER_API_KEY in umot/.env")
        _client = anthropic.Anthropic(api_key=None, auth_token=key, base_url="https://openrouter.ai/api", max_retries=4)
    return _client


def _or_model(model: str) -> str:
    """claude-haiku-5-5 -> anthropic/claude-haiku-5.5 (OpenRouter writes the version with a dot)."""
    return "anthropic/" + re.sub(r"-(\d+)-(\d+)$", r"-\1.\2", model)


def api_json(prefix: str, suffix: str, system: str, schema: dict, model: str, effort: str, cache: bool = True,
             max_tokens: int = 64000) -> tuple[dict, dict]:
    """One streamed call with structured output; `prefix` is cached (identical across a run's calls) unless cache=False."""
    import time
    t0 = time.time()
    with _api().messages.stream(
        model=_or_model(model), max_tokens=max_tokens, system=system,
        extra_body={"provider": {"order": ["anthropic"], "allow_fallbacks": False}},
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prefix, **({"cache_control": {"type": "ephemeral"}} if cache else {})},
            {"type": "text", "text": suffix}]}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        d = msg.stop_details
        raise RuntimeError(f"refusal ({getattr(d, 'category', None)}): {getattr(d, 'explanation', '')}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("hit max_tokens")
    out = json.loads(next(b.text for b in msg.content if b.type == "text"))
    u = msg.usage
    fresh, write, read = u.input_tokens, u.cache_creation_input_tokens or 0, u.cache_read_input_tokens or 0
    pin, pout = PRICES.get(model, (0, 0))
    cost = (fresh * pin + write * pin * 1.25 + read * pin * 0.1 + u.output_tokens * pout) / 1e6
    return out, {"input": fresh + write + read, "cache_read": read, "cache_write": write, "output": u.output_tokens,
                 "cost_usd_list": round(cost, 4), "ms": round((time.time() - t0) * 1000), "request_id": getattr(msg, "_request_id", None) or getattr(msg, "id", None)}
