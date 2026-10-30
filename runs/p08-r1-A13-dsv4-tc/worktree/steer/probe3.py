import json, sys, torch
sys.path.insert(0, "tools")
import metric

rng = torch.Generator().manual_seed(0)
v = torch.randn(2560, generator=rng); v = v / v.norm() * 0.5
r = metric.run_metric({20: v}, "prefix", 1.0)
print("=== run_metric response (prefix, scale 1) ===")
print(json.dumps(r, indent=1)[:2000])
