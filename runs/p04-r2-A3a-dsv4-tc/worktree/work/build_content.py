"""K1: a "content vs continuation-boundary" contrast, distinct from both the white-bear stance
and from FDR (which works in readout space). Positive = prompt ends at the concrete concept noun;
negative = the same scene ending at its sentence boundary. Both read at the final token, so the
difference isolates "being at a contentful word" vs "being at a continuation point".

K2: subset variant with single-token concepts on simple carriers.
"""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric
from scenes import SCENES

LAYERS = list(range(14, 31))


def k1_specs():
    pos, neg = [], []
    for s, c in SCENES:
        pos.append({"user": f"{s} {c}", "assistant": ""})
        neg.append({"user": f"{s}", "assistant": ""})
    return pos, neg


FAMILIES = {"K1": k1_specs}


def main():
    fam = sys.argv[1]
    pos, neg = FAMILIES[fam]()
    out = {}
    for tag, prompts in [("pos", pos), ("neg", neg)]:
        r = metric.capture({"layers": LAYERS, "positions": "last", "prompts": prompts})
        out[tag] = r["mean"]
        print(f"[{fam}] {tag}: {r['n_prompts']} prompts", file=sys.stderr)
    u = {}
    print("layer  ||d_l||")
    for L in LAYERS:
        d = (out["pos"][L] - out["neg"][L]).float()
        nrm = d.norm().item()
        print(f"{L:5d}  {nrm:8.4f}")
        u[L] = d / d.norm()
    torch.save({L: u[L] for L in [20, 21, 22, 23, 24]}, f"work/{fam}_band.pt")
    torch.save(u, f"work/{fam}_u.pt")
    print(f"saved work/{fam}_band.pt", file=sys.stderr)


if __name__ == "__main__":
    main()