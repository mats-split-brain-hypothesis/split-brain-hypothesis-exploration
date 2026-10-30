"""Build the final submission vectors: concreteness steering direction.

Re-derives the direction from the contrast (attend to a concept's physical form -- size, weight,
texture, colour -- vs. do not think about it; matched within pairs; read on the generated carrier
cells; layers 20-24) and stores the unit directions in submission/vectors.pt. Applied at the
prefix, dose 7.
"""
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import msteer  # noqa: E402
from wbs_pairs import PAIRS  # (concept, carrier) pairs; content matched within each pair

BAND = msteer.BAND  # [20, 21, 22, 23, 24]

POS = "As you write, attend to the exact physical form of {c}: its size, weight, texture, and " \
      "colour. Now write exactly this sentence: \"{d}\""
NEG = "Do not think about {c} as you write. Now write exactly this sentence: \"{d}\""


def main() -> None:
    a = [{"user": POS.format(c=c, d=car), "assistant": car} for c, car in PAIRS]
    b = [{"user": NEG.format(c=c, d=d), "assistant": d} for c, d in PAIRS]
    d = msteer.contrast(a, b, BAND, positions="assistant")
    unit = {L: d[L] / d[L].norm() for L in BAND}
    out = ROOT / "submission" / "vectors.pt"
    out.parent.mkdir(exist_ok=True)
    msteer.save("final_unit.pt", unit)
    torch.save({L: unit[L].contiguous() for L in BAND}, out)
    print("wrote", out, "layers", sorted(unit), "norms", {L: round(float(unit[L].norm()), 3) for L in BAND})


if __name__ == "__main__":
    main()
