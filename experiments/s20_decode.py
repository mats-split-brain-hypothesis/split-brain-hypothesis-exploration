"""S20 deep dive: what the learned constant does beyond the family mean. For each family's ``ceil.const`` (fitted WITH
fit targets, ``ceilings.py --save-g``) and each layer, the cos readout of ``mu_fam - g`` (what reading ``h - g`` adds
over reading ``h - mu_fam``): its top tokens (promoted) and bottom tokens (demoted), ``||g - mu_fam|| / ||mu_fam||`` and
the cosine of g with mu_fam. Also: of the promoted top-200, the share that are word-initial (leading space) and the
share that are fit-split targets of the family (the target-prior check). Writes out/analysis/S20/decode.md / .json.

  python experiments/s20_decode.py --device cuda
"""

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import MULTI_TOKEN, scorers

from jlm import OUT, banks, capture, mtproxy
from jlm.lens import Lens
from jlm.mu import S20

GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--layers", default="28,40,48,56")
    args = ap.parse_args()
    layers = [int(x) for x in args.layers.split(",")]
    lens = Lens(layers, args.device)
    vocab = lens.display(list(range(lens.vocab)))
    tmpl = [t["id"] for t in json.loads((Path(__file__).resolve().parents[1] / "data" / "template_tokens" / "template.json").read_text())["tokens"]][:64]
    res, md = {}, ["# S20: what the learned constant (WITH fit targets) adds over the family mean", ""]
    for p in sorted(S20.GDIR.glob("*-const.pt")):
        fam = p.name[: -len("-const.pt")]
        g = torch.load(p, map_location="cpu")["layers"]
        bank = banks.load(fam, "fit")
        items = capture.load(bank)
        if fam in MULTI_TOKEN:
            units = mtproxy.units_of(bank, lens.tokenizer, lens.display)
            targets = {t for us in units.values() for u in us if u.required for t in u.ids}
        else:
            st, _ = scorers(bank, vocab, {it.id: lens.display(it.ids) for it in items})
            targets = {t for a in st.accepted.values() for t in a}
        res[fam] = {}
        md += [f"## {fam} ({len(targets)} fit target ids)", "", "| L | cos(g, fam) | ‖g−fam‖/‖fam‖ | promoted (top 12) | demoted (bottom 12) | word-initial / target share of top 200 | template[:64] in bottom 200 / mean percentile |", "|---|---|---|---|---|---|---|"]
        for L in layers:
            if L not in g:
                continue
            mu = torch.stack([it.acts[L][i].float() for it in items for i in range(len(it.positions))]).mean(0)
            gL = g[L]["mu"][0].float()
            s = lens.scores((mu - gL)[None], L, "cos")[0].cpu()
            top, bot200 = s.topk(200).indices.tolist(), (-s).topk(200).indices.tolist()
            bot = bot200[:12]
            t_in = len(set(bot200) & set(tmpl))
            pct = ((s[None, :] < s[tmpl][:, None]).float().mean(1).mean().item())  # mean percentile of the template tokens
            names = lens.display(top)
            wi = sum(n.startswith(" ") for n in names) / 200
            ts = sum(t in targets for t in top) / 200
            cosv = torch.nn.functional.cosine_similarity(gL, mu, dim=0).item()
            rel = ((gL - mu).norm() / mu.norm()).item()
            res[fam][L] = {"cos": cosv, "rel": rel, "promoted": names[:30], "demoted": lens.display(bot), "word_initial": wi, "target_share": ts,
                         "template64_in_bottom200": t_in, "template64_mean_percentile": pct}
            md.append(f"| {L} | {cosv:.2f} | {rel:.2f} | {' '.join(repr(n) for n in names[:12])} | {' '.join(repr(n) for n in lens.display(bot))} | {wi:.2f} / {ts:.2f} | {t_in} / {pct:.2f} |")
        md.append("")
        print(f"{fam} done", flush=True)
    (OUT / "analysis" / "S20" / "decode.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (OUT / "analysis" / "S20" / "decode.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
