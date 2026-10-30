"""Candidate recipes for the planted paper (offline, from calib/svd.npz). Persistence: how well each singular
direction of J_l survives at the neighbouring read layers; the recipe weights each direction by its persistence
relative to directions of similar rank (running median), so it is no band / cap / tilt form."""

import numpy as np
import torch

LAYERS = [26, 28, 30]
NEIGHBOURS = {26: [28], 28: [26, 30], 30: [28]}


def load(path="calib/svd.npz", device="cuda"):
    z = np.load(path)
    return ({L: z[f"S{L}"].astype(np.float64) for L in LAYERS},
            {L: torch.tensor(z[f"U{L}"]).to(device) for L in LAYERS},
            {L: torch.tensor(z[f"Vh{L}"]).to(device) for L in LAYERS})


def persistence(U: dict, L: int) -> np.ndarray:
    """s_k = mean over the neighbouring read layers of max_j |<u_k(L), u_j(L')>| (left singular vectors)."""
    return torch.stack([(U[L].T @ U[L2]).abs().max(1).values for L2 in NEIGHBOURS[L]]).mean(0).double().cpu().numpy()


def running_median(x: np.ndarray, half: int) -> np.ndarray:
    return np.array([np.median(x[max(0, k - half): k + half + 1]) for k in range(x.size)])


def relative_persistence(U: dict, L: int, half: int = 16, beta: float = 2.0, lo: float = 0.25, hi: float = 4.0):
    s = persistence(U, L)
    return np.clip((s / running_median(s, half)) ** beta, lo, hi)
