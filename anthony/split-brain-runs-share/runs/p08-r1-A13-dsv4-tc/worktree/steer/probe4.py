import sys, torch
sys.path.insert(0, "tools")
import metric

# one prompt with a user instruction and an assistant carrier
p = {"user": "Think about the body part clavicle while you write. Now write exactly this sentence: \"The committee approved the minutes without changes.\"",
     "assistant": "The committee approved the minutes without changes."}
for pos in ("last", "user", "assistant", "all"):
    o = metric.capture({"layers": [22], "prompts": [p], "positions": pos})
    print(pos, "mean norm@22 =", round(o["mean"][22].norm().item(), 3), "n_prompts", o["n_prompts"])
