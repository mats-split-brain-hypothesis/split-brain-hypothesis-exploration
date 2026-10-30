"""R2 concept tracks (SETS.md, approved 2026-10-23): per subject token and stored layer, each concept set's score under
the J-lens (the best cos readout among the set's tokens), plain and same-token centred (the centre as on the pod:
the mean state of the same token id over the other targets, layer mean below MIN_N). From the stored captures, on
the CPU (the desktop GPU serves the tc batch's 4B metric server).

    python concepts.py   -> whitebox-captures/<T>/readers/concepts.npy [n_subj, layers, sets, 2] float16 (plain, centred)
                            and concepts_meta.json (sets with their token ids, layers)
"""

import json
import time

import numpy as np
import torch

from capture import READER_LAYERS
from moments import TARGETS
from view import CAPS

MIN_N, CHUNK = 5, 4096
SETS = {  # SETS.md: leading-space single tokens; Raman / Priya through their first piece
    "source-name": [" white", " bear", " White", " Bear", " Ram", " Pri"],
    "source-generic": [" paper", " prior", " cite", " citation", " credit", " existing", " known", " reproduction",
                       " reproduce", " recipe", " published", " previously"],
    "judge": [" judge", " novelty", " score", " evaluation", " graded", " reviewer", " reward", " points", " evaluator"],
    "hiding": [" hide", " omit", " conceal", " mention", " disclose", " admit", " honest", " honesty", " transparent",
               " pretend", " acknowledge"],
    "own": [" new", " novel", " our", " contribution", " original", " invented", " independent", " ours"],
    "control": [" banana", " weather", " Paris", " golf", " guitar", " ocean"],
}


def load_states(t: str, L: int) -> np.ndarray:
    return np.load(CAPS / t / f"subj_L{L}.npy", mmap_mode="r")


def as_f32(a: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(a).view(np.int16)).view(torch.bfloat16).float()


def main() -> None:
    torch.set_num_threads(max(1, torch.get_num_threads()))
    from jlm.lens import Lens
    lens = Lens(READER_LAYERS, device="cpu")
    tok = lens.tokenizer
    ids = {}
    for name, words in SETS.items():
        ids[name] = []
        for w in words:
            x = tok(w, add_special_tokens=False)["input_ids"]
            ids[name].append(x[0])  # one token for all but Raman / Priya (their first piece)
    flat = sorted({i for v in ids.values() for i in v})
    col = {i: k for k, i in enumerate(flat)}
    W = lens.w_u[flat].clone()  # [n_tok, d]
    dens = {L: lens.denom[L][flat].clone() for L in READER_LAYERS}
    del lens.w_u, lens.denom  # 5 GB of RAM: only the sets' rows are needed
    import gc; gc.collect()
    toks = {t: np.load(CAPS / t / "ids.npy")[np.load(CAPS / t / "subj_idx.npy")] for t in TARGETS}
    uniq, inv = np.unique(np.concatenate(list(toks.values())), return_inverse=True)
    cut = np.cumsum([0] + [len(v) for v in toks.values()])
    comp = {t: torch.from_numpy(inv[cut[k]:cut[k + 1]]) for k, t in enumerate(TARGETS)}
    out = {t: np.zeros((len(toks[t]), len(READER_LAYERS), len(SETS), 2), np.float16) for t in TARGETS}
    for li, L in enumerate(READER_LAYERS):
        t0 = time.time()
        sums, cnts = {}, {}
        for t in TARGETS:  # per-target sums by token, streamed in chunks
            a = load_states(t, L)
            s = torch.zeros(len(uniq), a.shape[1])
            for b in range(0, len(a), CHUNK):
                s.index_add_(0, comp[t][b:b + CHUNK], as_f32(a[b:b + CHUNK]))
            sums[t], cnts[t] = s, torch.bincount(comp[t], minlength=len(uniq)).float()
        tot_s, tot_c = sum(sums.values()), sum(cnts.values())
        J, den = lens.jac[L], dens[L]
        for t in TARGETS:
            o_s, o_c = tot_s - sums[t], tot_c - cnts[t]
            layer_mean = o_s.sum(0) / o_c.sum()
            a = load_states(t, L)
            for b in range(0, len(a), CHUNK):
                x = as_f32(a[b:b + CHUNK])
                c = comp[t][b:b + CHUNK]
                n = o_c[c][:, None]
                mu = torch.where(n >= MIN_N, o_s[c] / n.clamp_min(1), layer_mean)
                for m, z in ((0, x), (1, x - mu)):
                    sc = ((z @ J.T) @ W.T) / den  # [chunk, n_tok] cos readout
                    for si, name in enumerate(SETS):
                        out[t][b:b + CHUNK, li, si, m] = sc[:, [col[i] for i in ids[name]]].max(1).values.numpy()
            del o_s
        print(f"L{L}: {time.time() - t0:.0f}s", flush=True)
    for t in TARGETS:
        np.save(CAPS / t / "readers" / "concepts.npy", out[t])
        (CAPS / t / "readers" / "concepts_meta.json").write_text(json.dumps({
            "sets": {k: {"words": SETS[k], "ids": ids[k]} for k in SETS}, "layers": READER_LAYERS,
            "modes": ["plain", "centred"], "score": "max over the set's tokens of the J-lens cos readout"}))
        print(f"{t}: saved", flush=True)


if __name__ == "__main__":
    main()
