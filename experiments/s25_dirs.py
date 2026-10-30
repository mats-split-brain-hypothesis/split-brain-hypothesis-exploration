"""S25: label-free "answer-position" directions from the chat-format corpus (instance e1, steward's card).

For every position t of the chat corpus capture (out/ctx/corpus-chat.pt; positions >= 2, as clusters.Pool.chat), the
next token ids[t + 1] is classed by its decoded form: cap (" Xxx..."), content (" xxx", 3+ lowercase letters), latin
(" " then 2+ Latin letters). d_class[L] = mean of the cells whose next token is in the class - mean of all cells; the
control d_rand[L] = mean of a random subset of the same size as cap's - mean of all (seeded). No bench data, no labels.
Writes out/analysis/S25/dirs.pt = {class: {layer: [d]}, "counts": ...}. Pod (the corpus is ~10 GB).
"""

import re

import torch
from transformers import AutoTokenizer
from umot.provenance import PINS

from jlm import OUT, context
from jlm.lens import MODEL

SKIP = 2
RX = {"cap": r"^ [A-Z][a-z]+", "content": r"^ [a-z]{3,}$", "latin": r"^ [A-Za-z]{2,}$"}


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    store = context.ContextStore(context.corpus_path("chat"))
    layers = store.layers()
    cache: dict[int, bool] = {}
    labels, rows = {k: [] for k in RX}, []
    for it in store.items.values():
        n = len(it.ids)
        for t in range(SKIP, n - 1):
            nxt = it.ids[t + 1]
            if nxt not in cache:
                cache[nxt] = tok.decode([nxt])
            s = cache[nxt]
            for k, rx in RX.items():
                labels[k].append(bool(re.match(rx, s)))
        rows.append((it, n))
    out = {k: {} for k in [*RX, "rand"]}
    masks = {k: torch.tensor(v) for k, v in labels.items()}
    g = torch.Generator().manual_seed(0)
    N = len(masks["cap"])
    rand = torch.zeros(N, dtype=torch.bool)
    rand[torch.randperm(N, generator=g)[: int(masks["cap"].sum())]] = True
    masks["rand"] = rand
    for L in layers:
        X = torch.cat([it.acts[L][SKIP: n - 1].float() for it, n in rows])
        mu = X.mean(0)
        for k, m in masks.items():
            out[k][L] = (X[m].mean(0) - mu).clone()
        del X
    out["counts"] = {k: int(m.sum()) for k, m in masks.items()} | {"all": N}
    path = OUT / "analysis" / "S25" / "dirs.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out, path)
    print(out["counts"], {k: [round(float(out[k][L].norm()), 2) for L in layers[:6]] for k in masks})


if __name__ == "__main__":
    main()
