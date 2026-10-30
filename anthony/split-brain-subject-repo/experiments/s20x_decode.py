"""S20x: decode the shared correction dbar (cos map, mean-removed): the tokens the centred readout gains and loses
when dbar is added to g, for a few read families and the all-source mean. Writes out/analysis/S20x/dbar-decode.md. Pod.
"""

import torch

from jlm import OUT
from jlm.lens import Lens


def main() -> None:
    D = torch.load(OUT / "analysis" / "S20x" / "dbar.pt", weights_only=False)
    layers = [36, 44, 52, 60]
    lens = Lens(layers, device="cuda" if torch.cuda.is_available() else "cpu")
    keys = ["typo|twin", "multihop|twin", "directed_modulation|twin", "multilingual_mt|twin", "user_modeling|twin",
            "typo|plain", "typo|mt"]
    lines = []
    for k in keys:
        for L in layers:
            s = lens.scores(D[k][L][None].to(lens.device), L, "cos")[0].float()
            s = s - s.mean()
            up = lens.display(s.topk(15).indices.tolist())  # g gains these: the centred readout loses them
            dn = lens.display((-s).topk(15).indices.tolist())  # the centred readout gains these
            lines.append(f"- {k} L{L}: readout gains {' '.join(repr(t) for t in dn)} | loses {' '.join(repr(t) for t in up)}")
    (OUT / "analysis" / "S20x" / "dbar-decode.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
