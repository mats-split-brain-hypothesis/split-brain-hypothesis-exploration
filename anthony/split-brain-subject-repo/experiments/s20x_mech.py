"""S20x mechanism (instance e1, steward's card): what the averaged correction dbar does in readout space.

Per family F (typo, association, multihop) and layer, with s(v) = the cos readout of v, mean-removed over the vocabulary:
- the tokens dbar_{-F,twin} pushes up / down in the centred readout (g gains dbar, so the readout of h - g LOSES s(dbar):
  "promotes" below = most negative s(dbar));
- token-class means of -s(dbar) (z-scored): word-initial capitalised Latin, word-initial lowercase Latin, Latin subword
  pieces, CJK, digits, punctuation / specials;
- Pearson correlation over the vocabulary of -s(dbar) with -s(mu_fam) and -s(mean kmx64 g) (what fam and kmx64 remove),
  with S20z's token-class prior c and with the chat unigram log-prior; residual-stream cosines of dbar with fam and the
  kmx64 mean; top-30 overlaps.
Writes out/analysis/S20x/mechanism.{md,json}. Needs the lens and the fit pool: pod.
"""

import json
import re

import torch

from jlm import OUT, banks, capture, centres
from jlm.lens import Lens

FAMS = ["typo", "association", "multihop"]
LAYERS = [24, 32, 40, 44, 52, 60]
CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯　-〿＀-￯]")


def classes(tok, V: int) -> dict[str, torch.Tensor]:
    text = [tok.decode([i]) for i in range(len(tok))] + [""] * (V - len(tok))
    def m(rx):
        return torch.tensor([bool(re.match(rx, t)) for t in text])
    cjk = torch.tensor([bool(CJK.search(t)) for t in text])
    out = {"Cap word ( Xxx)": m(r"^ [A-Z][a-z]{2,}$"), "lower word ( xxx)": m(r"^ [a-z]{3,}$"),
           "Latin piece (no space)": m(r"^[A-Za-z]{2,}$"), "CJK": cjk, "digits": m(r"^ ?\d+$"),
           "punct / special": m(r"^\s*[^\w\s]+\s*$")}
    return out


def main() -> None:
    lens = Lens(LAYERS, device="cuda" if torch.cuda.is_available() else "cpu")
    V = lens.w_u.shape[0]
    D = torch.load(OUT / "analysis" / "S20x" / "dbar.pt", weights_only=False)
    cls = classes(lens.tokenizer, V)
    z_prior = torch.load(OUT / "priors" / "s20z-latin.pt", weights_only=False)["logp"].float()
    uni = torch.load(OUT / "priors" / "unigram-norobots.pt", weights_only=False)["logp"].float()

    def s(v, L):
        x = lens.scores(v[None].to(lens.device), L, "cos")[0].float().cpu()
        return x - x.mean()

    def corr(a, b):
        a, b = a - a.mean(), b - b.mean()
        return float((a @ b) / (a.norm() * b.norm()))

    res, lines = {}, ["# S20x mechanism: dbar in readout space (cos)", ""]
    for f in FAMS:
        items = capture.load(banks.load(f, "fit"))
        km = centres.make("kmx64")
        km.fit(items, f, {it.id: it.id for it in items})
        lines += [f"## {f}", "", "| L | readout gains (top 12) | readout loses (top 12) | class z: Cap / lower / piece / CJK / digit / punct | corr with fam removal / kmx64 removal / S20z prior / unigram | cos(dbar, fam) / cos(dbar, kmx64 g) |",
                  "|---|---|---|---|---|---|"]
        for L in LAYERS:
            d = D[f + "|twin"][L].float()
            mu = torch.cat([it.acts[L].float() for it in items]).double().mean(0).float()
            cells = centres.cell_refs(items, f, L)
            H = torch.stack([next(x for x in items if x.id == c.item).acts[L][c.i].float() for c in cells])
            gk = (H - centres.apply(km, centres.Batch(L, cells, H, {it.id: it for it in items}))).mean(0)
            gain = -s(d, L)  # the centred readout gains -s(dbar)
            fam_r, km_r = -s(mu, L), -s(gk, L)
            zc = (gain - gain.mean()) / gain.std()
            cz = {k: float(zc[m].mean()) for k, m in cls.items()}
            up, dn = gain.topk(12).indices.tolist(), (-gain).topk(12).indices.tolist()
            r = {"up": lens.display(up), "down": lens.display(dn), "class_z": cz,
                 "corr_fam": corr(gain, fam_r), "corr_kmx": corr(gain, km_r), "corr_s20z": corr(gain, -z_prior[:V]),
                 "corr_unigram": corr(gain, uni[:V]),
                 "cos_fam": float(torch.nn.functional.cosine_similarity(d, mu, dim=0)),
                 "cos_kmx": float(torch.nn.functional.cosine_similarity(d, gk, dim=0)),
                 "top30_overlap_fam": len(set(gain.topk(30).indices.tolist()) & set(fam_r.topk(30).indices.tolist()))}
            res[f"{f}/L{L}"] = r
            fmt = lambda xs: " ".join(repr(t) for t in xs)  # noqa: E731
            lines.append(f"| {L} | {fmt(r['up'])} | {fmt(r['down'])} | " + " / ".join(f"{cz[k]:+.2f}" for k in cls)
                         + f" | {r['corr_fam']:+.2f} / {r['corr_kmx']:+.2f} / {r['corr_s20z']:+.2f} / {r['corr_unigram']:+.2f}"
                         + f" | {r['cos_fam']:+.2f} / {r['cos_kmx']:+.2f} |")
        lines.append("")
    out = OUT / "analysis" / "S20x"
    (out / "mechanism.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (out / "mechanism.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
