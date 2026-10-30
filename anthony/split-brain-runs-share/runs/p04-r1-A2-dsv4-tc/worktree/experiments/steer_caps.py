"""Capture residual means for conditions through the metric server, cached to out/steer/."""
import json, sys, time
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

LAYERS = [26, 28, 30]
CACHE = Path("out/steer/caps")


def capture_prompts(name, prompts, positions="user", layers=LAYERS):
    p = CACHE / f"{name}.pt"
    if p.exists() and not __import__("os").environ.get("RECAP"):
        d = torch.load(p, weights_only=False)
        print(f"[{name}] cached n={d['n_prompts']}", flush=True)
        return d
    t0 = time.time()
    out = metric.capture({"layers": layers, "prompts": [{"user": x} for x in prompts], "positions": positions})
    print(f"[{name}] n={out['n_prompts']} {time.time()-t0:.1f}s", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    torch.save(out, p)
    return out


def capture_family(name, family, split="fit", layers=LAYERS):
    p = CACHE / f"{name}.pt"
    if p.exists() and not __import__("os").environ.get("RECAP"):
        d = torch.load(p, weights_only=False)
        print(f"[{name}] cached n={d['n_prompts']}", flush=True)
        return d
    from jlm import banks
    bank = banks.load(family, split)
    ids = [it["id"] for it in bank.items]
    t0 = time.time()
    out = metric.capture({"layers": layers, "bench_items": ids, "family": family, "split": split})
    print(f"[{name}] n={out['n_prompts']} family={family} {time.time()-t0:.1f}s", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    torch.save(out, p)
    return out

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "family":
        capture_family(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else sys.argv[2])
