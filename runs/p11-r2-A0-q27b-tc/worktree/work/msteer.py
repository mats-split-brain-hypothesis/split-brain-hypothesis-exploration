"""Shared helpers for the steering task (jlens-steer-assoc-017).

Wraps tools/metric.py. All activations come from the metric server (the only compute).
"""
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E42

OUT = ROOT / "out" / "steer"
OUT.mkdir(parents=True, exist_ok=True)

BAND = [20, 21, 22, 23, 24]  # WBS mid-depth band; read happens at 26/28/30 (after the band)


def save(name: str, obj) -> Path:
    p = OUT / name
    torch.save(obj, p)
    return p


def load(name: str):
    return torch.load(OUT / name, weights_only=False)


def capture_mean(prompts: list[dict], layers: list[int], positions: str = "assistant") -> dict[int, torch.Tensor]:
    """Per-condition mean residual at ``layers`` over the ``positions`` cells of each prompt."""
    spec = {"layers": layers, "positions": positions, "prompts": prompts}
    out = metric.capture(spec)
    return {L: out["mean"][L].clone() for L in layers}


def contrast(cond_a: list[dict], cond_b: list[dict], layers: list[int], positions: str = "assistant") -> dict[int, torch.Tensor]:
    """d_L = mean_A(h_L) - mean_B(h_L)."""
    ma = capture_mean(cond_a, layers, positions)
    mb = capture_mean(cond_b, layers, positions)
    return {L: ma[L] - mb[L] for L in layers}


def run(vecs: dict[int, torch.Tensor], positions: str = "read", scale: float = 1.0) -> dict:
    return metric.run_metric(vecs, positions, scale)


def norms(d: dict[int, torch.Tensor]) -> dict[int, float]:
    return {L: float(d[L].norm()) for L in d}
