import json, sys, torch
sys.path.insert(0, "tools")
import metric

prompts = [
    {"user": "She leapt above the net and spiked the ball into the open corner.", "assistant": "volleyball"},
    {"user": "He hunched low over the handlebars, legs burning, as the peloton streamed past.", "assistant": "cycling"},
]
out2 = metric.capture({"layers": [22], "prompts": prompts, "positions": "last"})
print("=== last keys ===", list(out2.keys()))
print("mean", {L: tuple(v.shape) for L,v in out2["mean"].items()})
if "per_prompt" in out2:
    print("per_prompt", {L: tuple(v.shape) for L,v in out2["per_prompt"].items()})

# full layer range
out3 = metric.capture({"layers": list(range(32)), "prompts": prompts[:1], "positions": "last"})
print("=== layers 0..31 ===", out3["layers"], "mean shapes", out3["mean"][0].shape)

# run_metric response format with tiny random vector at layer 20
rng = torch.Generator().manual_seed(0)
v = torch.randn(2560, generator=rng); v = v / v.norm() * 0.01
r = metric.run_metric({20: v}, "prefix", 1.0)
print("=== run_metric response ===")
print(json.dumps(r, indent=1)[:1500])
