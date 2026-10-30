"""S20z: a label-free statement of S20x's shared correction, as a token-class prior for S13's pullback machinery.

S20x's dbar (learned from other families' targets) decodes to "the centred readout gains word-initial Latin tokens and
loses CJK tokens". Here c is set from the tokenizer alone: c = -1 on word-initial Latin-alphabet tokens (leading space,
then 2+ ASCII letters), +1 on tokens containing a CJK character, 0 elsewhere, each class scaled to unit mean |c| inside
it. Subtracting g = beta * pullback(c) moves the readout by about -beta * c: up for Latin word starts, down for CJK.
Writes out/priors/s20z-latin.pt and the control s20z-latin-shuf.pt (the same values permuted over the vocabulary),
in build_priors.py's format ({"logp": [V], "meta": ...}); pull back with experiments/precompute_pullback.py --priors.
"""

import re

import torch
from transformers import AutoTokenizer
from umot.provenance import PINS

from jlm import OUT
from jlm.lens import MODEL

CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯　-〿＀-￯]")
LATIN_START = re.compile(r"^ [A-Za-z]{2,}$")


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    V = torch.load(OUT / "priors" / "unigram-norobots.pt", weights_only=False)["logp"].shape[0]  # W_U's rows (padded)
    text = [tok.decode([i]) for i in range(len(tok))] + [""] * (V - len(tok))
    c = torch.zeros(V)
    latin = torch.tensor([bool(LATIN_START.match(t)) for t in text])
    cjk = torch.tensor([bool(CJK.search(t)) for t in text])
    c[latin], c[cjk] = -1.0, 1.0
    meta = {"latin_start": int(latin.sum()), "cjk": int(cjk.sum()), "vocab": V,
            "rule": "c = -1 on ' [A-Za-z]{2,}' tokens, +1 on tokens with a CJK / kana / hangul / CJK-punctuation character"}
    (OUT / "priors").mkdir(parents=True, exist_ok=True)
    torch.save({"logp": c, "meta": meta}, OUT / "priors" / "s20z-latin.pt")
    # S20w (S20x mechanism, insight 2a): capitalised word starts up, punctuation / specials down, nothing else
    cap = torch.tensor([bool(re.match(r"^ [A-Z][a-z]{2,}$", t)) for t in text])
    punct = torch.tensor([bool(re.match(r"^\s*[^\w\s]+\s*$", t)) for t in text])
    w = torch.zeros(V)
    w[cap], w[punct] = -1.0, 1.0
    torch.save({"logp": w, "meta": {"cap": int(cap.sum()), "punct": int(punct.sum()), "rule": "c = -1 on ' [A-Z][a-z]{2,}', +1 on punctuation-only tokens"}},
               OUT / "priors" / "s20w-cap.pt")
    perm = torch.randperm(V, generator=torch.Generator().manual_seed(0))
    torch.save({"logp": c[perm], "meta": {**meta, "control": "values permuted over the vocabulary (seed 0)"}},
               OUT / "priors" / "s20z-latin-shuf.pt")
    print(meta)


if __name__ == "__main__":
    main()
