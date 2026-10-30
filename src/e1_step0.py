"""E1 step 0 (pre-registered, §11): one GLM-5.2 call through the harness's own path (Inspect's OpenRouter provider,
provider pinned) to check that full reasoning comes back. About $0.01.

    python src/e1_step0.py siliconflow/fp8 [none|high]
"""
import asyncio
import sys

from dotenv import load_dotenv
from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model

load_dotenv(".env")
provider = sys.argv[1]
effort = sys.argv[2] if len(sys.argv) > 2 else "none"


async def main():
    model = get_model("openrouter/z-ai/glm-5.2", provider={"order": [provider], "allow_fallbacks": False})
    config = GenerateConfig(extra_body={"reasoning": {"effort": effort}}) if effort != "none" else GenerateConfig()
    out = await model.generate([ChatMessageUser(content="A shop sells pens at 3 for $2. How much do 17 pens cost if "
                                                        "you must buy them in packs of 3? Answer in one line.")],
                               config=config)
    m = out.message
    parts = m.content if isinstance(m.content, list) else []
    reasoning = [getattr(p, "reasoning", "") or "" for p in parts if getattr(p, "type", "") == "reasoning"]
    redacted = [getattr(p, "redacted", False) for p in parts if getattr(p, "type", "") == "reasoning"]
    u = out.usage
    print(f"provider {provider}, effort {effort}: reasoning blocks {len(reasoning)}, chars {sum(map(len, reasoning))}, "
          f"redacted {redacted}; reasoning_tokens {getattr(u, 'reasoning_tokens', None)}, "
          f"input {u.input_tokens}, output {u.output_tokens}")
    print("reasoning head:", " ".join((reasoning[0] if reasoning else "").split())[:200])
    print("answer:", " ".join((m.text or "").split())[:200])


asyncio.run(main())
