"""J-lens arms from stored captures, without the 27B model: only its unembedding is loaded.

The bench's J-lens readout ``(W_U J_l h) / ‖J_lᵀ W_U[t]‖`` needs ``W_U`` (``lm_head``, one
safetensors shard), the J transports at the captured layers and the captures in ``out/captures``.
That fits on a 16 GB Mac, so new J-lens arms on an existing capture need no pod.

Arms (see ``ARMS``): ``jlens`` (the bench's readout; a parity check against the pod's run), ``jlens-rms``
(jlens-edits' readout) and centred arms ``h − μ(cell)``, μ from ``umot.centring``: the family mean
(``-ctr-fam`` incl. the item, ``-ctr-loo`` excl. its pair, as x100's loo1), the same read token
(``-ctr-tok``, x100's tok1), the sentence-final "." only (``-ctr-stop``) and the same sentence at the same
position (``-ctr-carpos``).

  python experiments/token_local.py --family directed_modulation              # every arm
  python experiments/token_local.py --family directed_modulation --decode-means
  python experiments/token_local.py --family directed_modulation --arms jlens --out <scratch>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from huggingface_hub import hf_hub_download
from safetensors import safe_open

sys.path.insert(0, str(Path(__file__).parent))
from m1_run import MODEL, OUT_DEFAULT, TOKEN_FILES, jlens_denominator, write_rows  # noqa: E402

from umot import capture, centring, readers  # noqa: E402
from umot.provenance import PINS, REPO_ROOT, Provenance, write_artefact  # noqa: E402


@dataclass
class UnembedBackend:
    """The parts of ``wsbench.produce.backend.Backend`` that ``JLens.read`` touches."""

    tokenizer: Any
    unembed: torch.Tensor
    device: str


def load_unembed(model_id: str) -> torch.Tensor:
    rev = PINS[model_id]
    index = json.loads(
        Path(hf_hub_download(model_id, "model.safetensors.index.json", revision=rev)).read_text()
    )
    shard = hf_hub_download(model_id, index["weight_map"]["lm_head.weight"], revision=rev)
    with safe_open(shard, framework="pt") as f:
        return f.get_tensor("lm_head.weight")


def item_meta(family: str) -> dict[str, dict[str, Any]]:
    """Per item: its frame (the condition and template its prompt shares with others) and the
    concepts it involves (held or mentioned), from the family's bank."""
    if family in ("mention_control", "mention_many"):
        from umot import mention_control as mc

        return {
            it["id"]: {"frame": f"{it['condition']}/{it['where']}", "concepts": mc.concepts_of(it)}
            for it in mc.load(family)
        }
    bank = json.loads((REPO_ROOT / "third_party/workspace-bench/evals" / family / "items.json").read_text())
    rows = bank["items"] if isinstance(bank, dict) else bank
    return {b["name"]: {"frame": family, "concepts": frozenset([b["concept"]])} for b in rows}


def load_norm(model_id: str) -> torch.Tensor:
    """The final RMSNorm weight ``w`` (the module applies ``1 + w``; checked in jlens-edits)."""
    rev = PINS[model_id]
    index = json.loads(
        Path(hf_hub_download(model_id, "model.safetensors.index.json", revision=rev)).read_text()
    )
    key = next(k for k in index["weight_map"] if k.endswith("language_model.norm.weight"))
    with safe_open(hf_hub_download(model_id, index["weight_map"][key], revision=rev), framework="pt") as f:
        return f.get_tensor(key)


def load_jacobians(layers: list[int]) -> _Sparse:
    """The pinned J-lens transports, fp32, only at ``layers`` (memory-mapped: the full fp32
    stack is 6.6 GB). Indexed by source layer like the bench's tensor; other layers are empty."""
    repo, filename = TOKEN_FILES["jlens"]
    path = hf_hub_download(repo, filename, revision=PINS[repo])
    obj = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
    jac = obj["J"] if "J" in obj else obj["jacobians"]
    get = (lambda L: jac[L] if L in jac else jac[str(L)]) if isinstance(jac, dict) else jac.__getitem__
    return _Sparse({L: get(L).float().clone() for L in layers}, len(jac))


class _Sparse:
    """Layer-indexed transports with only the read layers materialised (``JLens.read`` only
    indexes one layer and checks ``shape[0]``)."""

    def __init__(self, stack: dict[int, torch.Tensor], n_layers: int) -> None:
        self.stack, self.shape = stack, (n_layers,)

    def __getitem__(self, layer: int) -> torch.Tensor:
        return self.stack[layer]


@dataclass
class RmsJLens:
    """jlens-edits' own J-lens readout (``rms``): ``rms_norm(J_l h, 1 + w) · W_Uᵀ``, the model's final
    RMSNorm (its ``1 + w`` gain) on the transported state, then the unembedding. Not the bench's."""

    jac: Any
    w_u: torch.Tensor
    norm_w: torch.Tensor  # 1 + w, fp32
    tokenizer: Any
    k: int = 10

    def read(self, h: torch.Tensor, layer: int) -> Any:
        from wsbench.produce.methods import Readout
        from wsbench.produce.render import display_tokens

        x = h.to(self.w_u.device) @ self.jac[layer].T
        x = self.norm_w * x / torch.sqrt(x.square().mean() + RMS_EPS)
        vals, ids = torch.topk(x @ self.w_u.T, self.k)
        return Readout(
            tokens=display_tokens(self.tokenizer, ids.tolist()),
            scores=[round(v, 4) for v in vals.tolist()],
        )


RMS_EPS = 1e-6  # config.json rms_norm_eps

#: arm -> (readout, centre, keep). Centres pool OTHER items' cells, never the item's own pair.
ARMS = {
    "jlens": ("cos", None, None),
    "jlens-rms": ("rms", None, None),
    "jlens-ctr-fam": ("cos", "fam_incl", None),  # first try: family mean incl. the item itself
    "jlens-ctr-loo": ("cos", "fam", None),  # x100 loo1: other items of the family
    "jlens-rms-ctr-loo": ("rms", "fam", None),
    "jlens-ctr-tok": ("cos", "tok", None),  # x100 tok1: same read token (>= 3 cells), else loo
    "jlens-ctr-stop": ("cos", "tok", "last"),  # the sentence-final "." only, same-token centre
    "jlens-ctr-carpos": ("cos", "carpos", None),  # same sentence, same position
    "jlens-ctr-fit": ("cos", "fit", None),  # the J-lens fit mean (out/fitmean/mu.pt), item-independent
    "jlens-rms-ctr-fit": ("rms", "fit", None),
}
CENTRE_DOC = {
    "fam_incl": "mean over every captured cell of the family at the layer (the item itself included)",
    "fam": "mean over the cells of every other item of the same frame sharing none of its concepts, per layer",
    "tok": "as fam, restricted to cells with the same read token (>= 3 cells, else the fam centre)",
    "carpos": "as fam, restricted to cells writing the same sentence at the same read position",
    "fit": "mu_fit: the mean residual of the J-lens's own fit pass (n1000 wikitext, positions 16..L-2, "
    "per-prompt position mean then prompt mean; experiments/fit_mean.py), one vector per layer",
}
FIT_MEAN = REPO_ROOT / "out" / "fitmean" / "mu.pt"


class FitMean:
    """The item-independent centre μ_fit,l (``centring.Centre``'s call signature)."""

    def __init__(self, path: Path = FIT_MEAN) -> None:
        self.mu = torch.load(path, map_location="cpu")["mu"]
        self.n_fallback = 0

    def __call__(self, item: capture.ItemCapture, layer: int, i: int) -> torch.Tensor:
        return self.mu[layer]


def build_centres(items: list[capture.ItemCapture], family: str) -> dict[str, centring.Centre]:
    """Every centre in ``CENTRE_DOC``, built over ``items`` (keys and exclusions from the family's bank)."""
    meta = item_meta(family)

    def sentence(it: capture.ItemCapture) -> tuple[str, ...]:
        return tuple(it.token(j) for j in range(len(it.positions)))

    def frame(it: capture.ItemCapture) -> str:  # centres never pool across conditions / templates
        return meta[it.id]["frame"]

    def concepts(it: capture.ItemCapture) -> frozenset:  # items sharing a concept never centre each other
        return meta[it.id]["concepts"]

    fam = centring.Centre(items, lambda it, i: frame(it), concepts)
    return {
        "fam_incl": centring.Centre(items, lambda it, i: frame(it), lambda it: frozenset()),
        "fam": fam,
        "tok": centring.Centre(items, lambda it, i: (frame(it), it.token(i)), concepts, min_cells=3, fallback=fam),
        "carpos": centring.Centre(items, lambda it, i: (frame(it), sentence(it), i), concepts, min_cells=1, fallback=fam),
        **({"fit": FitMean()} if FIT_MEAN.exists() else {}),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--arms", default=",".join(a for a in ARMS if a != "jlens"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--limit", type=int, default=0, help="first N items only (checks)")
    ap.add_argument("--decode-means", action="store_true", help="print what each centre reads, then exit")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    torch.set_float32_matmul_precision("highest")
    from transformers import AutoTokenizer
    from wsbench.produce import method

    out = Path(args.out)
    items = capture.load(OUT_DEFAULT / "captures" / f"{args.family}.pt")
    centres = build_centres(items, args.family)
    fam = centres["fam"]
    keeps = {"last": lambda it, i: i == len(it.positions) - 1}
    items = items[: args.limit or None]
    layers = sorted({L for it in items for L in it.acts})

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    w_u = load_unembed(MODEL).float().to(args.device)
    readouts_needed = {ARMS[a][0] for a in args.arms.split(",")} | ({"cos"} if args.decode_means else set())
    m = method("jlens")
    m._b = UnembedBackend(tok, w_u, args.device)
    m._w_u = w_u
    m._jac = load_jacobians(layers)
    for L in layers:
        m._jac.stack[L] = m._jac.stack[L].to(args.device)
        if "cos" in readouts_needed:
            m._denom[L] = jlens_denominator(w_u, m._jac[L])
    print(f"  lens ready ({time.time() - t0:.0f}s)", flush=True)
    rms = RmsJLens(m._jac, w_u, (1 + load_norm(MODEL)).float().to(args.device), tok)

    if args.decode_means:  # what each centre reads, per layer, at the sentence-final "." of item 0
        it0 = items[0]
        last = len(it0.positions) - 1
        decoded = {
            name: {L: m.read(fn(it0, L, last), L).tokens for L in layers}
            for name, fn in (("fam", fam), ("tok", centres["tok"]), ("carpos", centres["carpos"]))
        }
        dest = out / "centring" / f"{args.family}-centres.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({"item": it0.id, "cell": "final read position", "decoded": decoded}, ensure_ascii=False))
        write_artefact(
            dest.with_suffix(".provenance.json"),
            Provenance(
                model=MODEL, model_revision=PINS[MODEL], reader=TOKEN_FILES["jlens"][0],
                reader_revision=PINS[TOKEN_FILES["jlens"][0]], dataset=f"wsbench/{args.family}",
                extra={"readout": "cos", "centres": {k: CENTRE_DOC[k] for k in ("fam", "tok", "carpos")}},
            ),
            {"layers": layers},
        )
        print(f"{dest}: what each centre reads")
        return

    suffix = f"-limit{args.limit}" if args.limit else ""
    for arm in args.arms.split(","):
        readout, centre, keep = ARMS[arm]
        reader = m if readout == "cos" else rms
        dest = out / "readouts" / f"{arm}{suffix}" / f"{args.family}.jsonl"
        if dest.exists():
            print(f"{dest} exists, skipping")
            continue
        extra: dict[str, Any] = {
            "limit": args.limit,
            "device": args.device,
            "host_kind": "local",
            "readout": {"cos": "bench: (W_U J h)_t / ‖J_lᵀ W_U[t]‖", "rms": "ours: rms_norm(J h, 1 + w) W_Uᵀ"}[readout],
        }
        if centre:
            extra["edit"] = {"kind": "centre", "centre": CENTRE_DOC[centre], "cells": keep or "all"}
        prov = Provenance(
            model=MODEL,
            model_revision=PINS[MODEL],
            reader=TOKEN_FILES["jlens"][0],
            reader_revision=PINS[TOKEN_FILES["jlens"][0]],
            dataset=f"wsbench/{args.family}",
            extra=extra,
        )
        if centre is None:
            rows = readers.token_rows(reader, items)
        else:
            c = centres[centre]
            c.n_fallback = 0
            rows = centring.centred_rows(reader, items, c, keeps.get(keep))
        write_rows(rows, dest, prov)
        if centre:
            print(f"  {arm}: fallbacks to the family centre: {centres[centre].n_fallback}")


if __name__ == "__main__":
    main()
