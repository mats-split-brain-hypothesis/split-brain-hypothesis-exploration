import os, sys, torch
sys.path.insert(0, "tools"); sys.path.insert(0, os.path.dirname(__file__))
import metric

data = torch.load("steer/out/blank.pt", weights_only=False)
dirs = data["dirs"]; norms = data["norms"]
band = range(20, 25)

# reversed direction (same scale, flipped sign)
rev = {L: (dirs[L] * -3.0).float().cpu() for L in band}
r = metric.run_metric(rev, "prefix", 1.0)
print(f"REVERSED  pass@10={r['pass_at_10']:.4f}  mean_log10_rank={r['mean_log10_rank']:.3f}")

# random direction at the same per-layer absolute dose
g = torch.Generator().manual_seed(0)
rand = {L: (torch.randn(2560, generator=g) / ( (torch.randn(2560, generator=g)**2).sum()**0.5 ) * 3.0 * norms[L]).float().cpu() for L in band}
r2 = metric.run_metric(rand, "prefix", 1.0)
print(f"RANDOM     pass@10={r2['pass_at_10']:.4f}  mean_log10_rank={r2['mean_log10_rank']:.3f}")
