"""Probe the metric server API: capture with our own prompts, and report what comes back."""
import json, sys
import torch
sys.path.insert(0, "tools")
import metric

prompts = [
    {"user": "She leapt above the net and spiked the ball into the open corner.", "assistant": "volleyball"},
    {"user": "He hunched low over the handlebars, legs burning, as the peloton streamed past.", "assistant": "cycling"},
]

spec = {"layers": [20, 22, 24, 26, 28, 30], "prompts": prompts, "positions": "all"}
out = metric.capture(spec)
print("n_prompts", out.get("n_prompts"), "layers", out.get("layers"))
for k in ("mean", "per_prompt"):
    if k in out:
        print(k, {L: v.shape if hasattr(v,'shape') else len(v) for L,v in out[k].items()})
# also try positions 'last'
spec2 = {"layers": [22], "prompts": prompts, "positions": "last"}
out2 = metric.capture(spec2)
print("=== last ===", json.dumps({k:(v if not hasattr(v,'shape') else str(v.shape)) for k,v in out2.items() if k!='per_prompt'}, indent=1)[:800])
