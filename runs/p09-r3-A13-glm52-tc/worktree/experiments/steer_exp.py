"""Steering-vector experiments for the plain J-lens on association fit.

Builds contrastive steering vectors from prompt pairs (no association targets),
captures their residual means via the metric server, and scores them.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import torch
from tools import metric


def build_vector(specs_A, specs_B, layers, positions="last"):
    """Capture two conditions and return v = mean_A - mean_B per layer, plus norms."""
    capA = metric.capture({"layers": layers, "prompts": specs_A, "positions": positions})
    capB = metric.capture({"layers": layers, "prompts": specs_B, "positions": positions})
    v = {}
    for L in layers:
        mA = capA["mean"][L]
        mB = capB["mean"][L]
        v[L] = (mA - mB).float()
    return v, capA, capB


def score(v, positions="prefix", scale=1.0):
    return metric.run_metric(v, positions=positions, scale=scale)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--out")
    ap.add_argument("--positions", default="prefix")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--cap-positions", default="last")
    ap.add_argument("--layers", default="26,28,30")
    ap.add_argument("--name", default="v")
    ap.add_argument("--vectors")
    ap.add_argument("--rest")
    ap = ap.parse_args()
    layers = [int(x) for x in ap.layers.split(",")]
    if ap.cmd == "score":
        v = {int(L): t for L, t in torch.load(ap.vectors, weights_only=False).items()}
        print(json.dumps(score(v, ap.positions, ap.scale), indent=1))
    # subcommands handled inline in notebooks/scripts
