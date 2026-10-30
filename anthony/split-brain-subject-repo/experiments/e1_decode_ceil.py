"""Cross-check of S20 (instance e1, read-only on C's files): what does the target-fitted constant add over fam?

Per family and layer, decode the readout of ``d = g_ceil.const - mu_fam`` (cos map, mean-removed over the vocabulary):
the 15 tokens d promotes most (which ``J(h - g)`` therefore demotes) and the 15 it demotes most (promoted by the
centred readout). Also the cosine of d between families at each layer: a shared d would be a label-free
correction. Writes out/analysis/S18/ceil-decode.{json,md}. Needs the lens: pod.
"""

import json

import torch

from jlm import OUT, banks, capture
from jlm.lens import Lens
from jlm.mu.clusters import FAMILIES


def main() -> None:
    G = OUT / "analysis" / "S20" / "g"
    fams = [f for f in FAMILIES if (G / f"{f}-const.pt").exists()]
    layers = [36, 44, 52, 60]
    lens = Lens(layers, device="cuda" if torch.cuda.is_available() else "cpu")
    D, res, lines = {}, {}, []
    for f in fams:
        g = torch.load(G / f"{f}-const.pt", weights_only=False)["layers"]
        items = capture.load(banks.load(f, "fit"))
        for L in layers:
            if L not in g:
                continue
            mu = torch.cat([it.acts[L].float() for it in items]).mean(0)
            d = g[L]["mu"][0].float() - mu
            D[(f, L)] = d
            s = lens.scores(d[None].to(lens.device), L, "cos")[0].float()
            s = s - s.mean()
            up, dn = s.topk(15).indices.tolist(), (-s).topk(15).indices.tolist()
            res[f"{f}/L{L}"] = {"promoted_by_d": lens.display(up), "demoted_by_d": lens.display(dn)}
            lines.append(f"- {f} L{L}: d promotes (centred readout demotes) {' '.join(repr(t) for t in lens.display(up)[:10])}; "
                         f"d demotes (readout promotes) {' '.join(repr(t) for t in lens.display(dn)[:10])}")
    lines.append("")
    lines.append("Cosine of d between families (mean over the layers):")
    for a in fams:
        row = []
        for b in fams:
            cs = [float(torch.nn.functional.cosine_similarity(D[(a, L)], D[(b, L)], dim=0)) for L in layers if (a, L) in D and (b, L) in D]
            row.append(sum(cs) / len(cs))
        res[f"cos/{a}"] = dict(zip(fams, row, strict=True))
        lines.append(f"- {a}: " + " ".join(f"{b[:8]} {c:+.2f}" for b, c in zip(fams, row, strict=True)))
    out = OUT / "analysis" / "S18"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ceil-decode.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (out / "ceil-decode.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
