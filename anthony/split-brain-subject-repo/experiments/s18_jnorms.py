"""S18 insight 2, measured: how large is each part of fam in readout space?

Per family (fit) and grid layer, with m = fam's top-k coordinates (k = 8, 32): the spread (std over the vocabulary,
which ignores a constant shift) of the cos readout of fam's outlier part ``fam*m``, of its dense part ``fam*(1-m)``,
and of the wikitext-minus-fam difference on the outliers ``(w - fam)*m`` (what s18w<k> gets wrong). Writes
out/analysis/S18/jnorms.{json,md}. Needs the lens (W_U + J at the grid layers): pod.
"""

import json

import torch

from jlm import OUT, banks, capture
from jlm.lens import Lens
from jlm.mu.S18 import wiki_mean

FAMS = ["typo", "association", "multihop", "user_modeling", "multilingual_mt", "multihop_mt"]


def main() -> None:
    items0 = capture.load(banks.load("typo", "fit"))
    layers = sorted(items0[0].acts)
    lens = Lens(layers, device="cuda" if torch.cuda.is_available() else "cpu")
    res, lines = {}, ["| family | L | k | spread(outliers) | spread(dense) | spread((w - fam) on outliers) | ratio last/dense |",
                      "|---|---|---|---|---|---|---|"]
    for f in FAMS:
        items = capture.load(banks.load(f, "fit"))
        for L in layers:
            mu = torch.cat([it.acts[L].float() for it in items]).mean(0)
            w = wiki_mean(L)
            for k in (8, 32):
                m = torch.zeros_like(mu)
                m[mu.abs().topk(k).indices] = 1
                vs = torch.stack([mu * m, mu * (1 - m), (w - mu) * m]).to(lens.device)
                sp = lens.scores(vs, L, "cos").float().std(dim=1).tolist()
                res[f"{f}/L{L}/k{k}"] = sp
                lines.append(f"| {f} | {L} | {k} | {sp[0]:.3f} | {sp[1]:.3f} | {sp[2]:.3f} | {sp[2] / sp[1]:.2f} |")
    out = OUT / "analysis" / "S18"
    out.mkdir(parents=True, exist_ok=True)
    (out / "jnorms.json").write_text(json.dumps(res, indent=1))
    (out / "jnorms.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
