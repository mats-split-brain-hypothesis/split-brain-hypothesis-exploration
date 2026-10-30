"""Export LL4's fitted expert weights as local lens maps (``out/maps/<name>.pt``, ``jlm.lens.MAPS``), so the
official pipeline (``evaluate.py``: strict, forms, echo, prompt-masked, next-token, sem) can read them as
``<name>:zero|cos`` / ``<name>:fam@self|cos``.

    python experiments/ll4_export.py --router w8 --anchor 0 --name ll4w8
    python experiments/ll4_export.py --router w8 --anchor fam --name ll4w8f

The map is ``sum_e w_e J_e`` (LL4's weights for that anchor, experts >= 200 positions) at the expert layers
(24, 32, 40, 48, 56) and the released n1000 J at every other layer, so it differs from ``zero|cos`` only where LL4
acts. Weights were fitted on the fit split only; val is the test.
"""

import argparse
from pathlib import Path

import torch

from jlm import OUT
from jlm.lens import MAPS, load_maps

EXPERTS = Path("/root/ll0-ckpt/experts")
LL_LAYERS = [24, 32, 40, 48, 56]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", default="w8")
    ap.add_argument("--anchor", default="0")
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    W = torch.load(OUT / "analysis" / "LL4" / a.router / "weights.pt")
    grid = list(range(20, 61, 4))  # the banks' read layers (the shared volume has no room for all 63)
    n1000 = load_maps("jlens", grid)
    J = {}
    for L in grid:
        if L in LL_LAYERS:
            E = torch.load(EXPERTS / f"experts-L{L:03d}.pt", weights_only=False)[a.router]
            keep = E["count"] >= 200
            w = W[f"{a.anchor}|L{L}"]
            J[L] = torch.einsum("e,eij->ij", w, E["J"][keep].float()).half()
        else:
            J[L] = n1000[L].half()
    MAPS.mkdir(parents=True, exist_ok=True)
    torch.save({"J": J, "source": f"LL4 {a.router} weights fitted on fit ({a.anchor} inputs) at {LL_LAYERS}, n1000 elsewhere"},
               MAPS / f"{a.name}.pt")
    print("saved", MAPS / f"{a.name}.pt", flush=True)


if __name__ == "__main__":
    main()
