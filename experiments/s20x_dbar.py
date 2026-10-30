"""S20x: the leave-one-family-out mean correction dbar_{-F} = mean over the other families G of (ceil.const_G - fam_G).

ceil.const_G is C's S20 constant fitted with G's fit targets (out/analysis/S20/g/<G>-const.pt); fam_G the mean of G's
fit read cells. For each family F (all 11, whether or not F has its own ceiling) and each layer, dbar_{-F} averages the
other families' d's, so a centre reading F never sees F's targets ("<F>|twin": also without F's _mt / plain twin, the same task) (fit targets of other families only: the research
loop's "learned" row). Writes out/analysis/S20x/dbar.pt = {F: {layer: [d]}, "norms": ...}; light (read-cell captures).
"""

import torch

from jlm import OUT, banks, capture
from jlm.mu.clusters import FAMILIES


#: Frozen when the card ran (02:50 BST): every S20 constant then available, i.e. all but user_modeling's. Every s20x arm
#: in out/eval was read with this set; a later constant must not change it silently.
SOURCES = [f for f in FAMILIES if f != "user_modeling"]


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--all-sources", action="store_true", help="also user_modeling's constant (11 sources) -> dbar-11.pt "
                    "(S20x's ensemble test; the frozen 10-source table is untouched)")
    ap.add_argument("--readout", default="cos", help="cos: C's constants <F>-const.pt; rms: <F>-const-rms.pt (fitted "
                    "through the rms map) -> dbar-rms.pt")
    args = ap.parse_args()
    suffix = "" if args.readout == "cos" else f"-{args.readout}"
    G = OUT / "analysis" / "S20" / "g"
    D = {}
    for f in (FAMILIES if args.all_sources else SOURCES):
        p = G / f"{f}-const{suffix}.pt"
        g = torch.load(p, weights_only=False)["layers"]
        items = capture.load(banks.load(f, "fit"))
        D[f] = {L: g[L]["mu"][0].float() - torch.cat([it.acts[L].float() for it in items]).double().mean(0).float() for L in g}
    out = {"sources": sorted(D), "d": D}  # "d": each source's own correction (single-source transfer, s20x1)
    for f in FAMILIES:
        others = [D[g] for g in D if g != f]
        out[f] = {L: torch.stack([d[L] for d in others]).mean(0) for L in others[0]}
        twin = f.removesuffix("_mt") if f.endswith("_mt") else f + "_mt"  # the same task in other languages
        others = [D[g] for g in D if g not in (f, twin)]
        out[f + "|twin"] = {L: torch.stack([d[L] for d in others]).mean(0) for L in others[0]}
        for tag, keep in (("plain", lambda g: not g.endswith("_mt")), ("mt", lambda g: g.endswith("_mt"))):
            others = [D[g] for g in D if g not in (f, twin) and keep(g)]  # source-set robustness: plain or _mt sources only
            out[f + "|" + tag] = {L: torch.stack([d[L] for d in others]).mean(0) for L in others[0]}
    path = OUT / "analysis" / "S20x" / f"dbar{suffix}{'-11' if args.all_sources else ''}.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out, path)
    for f in FAMILIES:
        print(f, "sources", len([g for g in D if g != f]), " ".join(f"L{L}:{v.norm():.1f}" for L, v in out[f].items() if L in (36, 44, 52, 60)))


if __name__ == "__main__":
    main()
