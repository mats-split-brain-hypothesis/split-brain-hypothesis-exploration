"""Milestone 1: capture a family once, then run every reader over the same cells.

Stages, in the order they should run (each skips work whose output already exists):

  capture   residuals at the bench's read cells, grid layers + 42   -> out/captures/<family>.pt
  token     logit lens, J-lens, R-lens on every captured cell
  blackbox  family-specific prefill, one readout per item
  verbal    olens / modulation lens, mounted on the probed model
  nla       the NLA (a separate reader model; the probed model is unloaded first)

Readouts land in out/readouts/<arm>/<family>.jsonl, each with a .provenance.json beside it.

  python experiments/m1_run.py --family directed_modulation --stages capture,token --limit 3
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import torch

from umot import arms, blackbox, capture, readers
from umot.provenance import PINS, REPO_ROOT, Provenance, write_artefact

OUT_DEFAULT = REPO_ROOT / "out"
MODEL = "Qwen/Qwen3.6-27B"
TOKEN_FILES = {  # bench defaults, loaded at our pinned revisions
    "jlens": (
        "neuronpedia/jacobian-lens",
        "qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt",
    ),
    "rlens": ("camilablank/workspace-lenses", "qwen3.6-27b/r-lens/lens.pt"),
}


def load_backend(model_id: str, device: str) -> Any:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from wsbench.produce.backend import Backend

    rev = PINS.get(model_id)
    tok = AutoTokenizer.from_pretrained(model_id, revision=rev)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=rev, dtype=torch.bfloat16, device_map=device
    )
    model.eval()
    return Backend(model=model, tokenizer=tok, device=device, model_id=model_id)


class LayerStack:
    """J-lens transports kept in CPU memory, each layer moved to the GPU on first use.

    The full fp32 stack (63 x 5120^2, 6.6 GB) next to the 27B model and an fp32 unembedding
    leaves too little GPU memory; the bench's ``read`` only ever indexes one layer at a time
    and checks ``shape[0]``, so this stands in for its on-device tensor with identical numerics.
    """

    def __init__(self, stacked: torch.Tensor, device: str) -> None:
        self.cpu, self.device, self._gpu = stacked, device, {}
        self.shape = stacked.shape

    def __getitem__(self, layer: int) -> torch.Tensor:
        if layer not in self._gpu:
            self._gpu[layer] = self.cpu[layer].to(self.device)
        return self._gpu[layer]


def load_jacobians(repo: str, filename: str, device: str) -> LayerStack:
    """``wsbench.produce.methods._load_jacobians`` with a pinned revision, layers on demand."""
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(repo, filename, revision=PINS[repo])
    obj = torch.load(path, map_location="cpu", weights_only=False)
    jac = obj["J"] if "J" in obj else obj["jacobians"]
    if isinstance(jac, dict):
        layers = sorted(int(k) for k in jac)
        if layers != list(range(len(layers))):
            raise ValueError(f"{filename}: source layers not contiguous from 0")
        stacked = torch.stack([jac[L] if L in jac else jac[str(L)] for L in layers])
    else:
        stacked = jac
    return LayerStack(stacked.float(), device)


def jlens_denominator(
    w_u: torch.Tensor, jac: torch.Tensor, chunk: int = 16384
) -> torch.Tensor:
    """The bench's ``(w_u @ J).norm(dim=1).clamp_min(1e-9)``, computed over vocabulary chunks
    so the [V, d] product (5 GB in fp32) is never materialised at once."""
    norms = [
        (w_u[i : i + chunk] @ jac).norm(dim=1) for i in range(0, w_u.shape[0], chunk)
    ]
    return torch.cat(norms).clamp_min(1e-9)


def bind_token_method(name: str, backend: Any, layers: list[int]) -> Any:
    from wsbench.produce import method

    m = method(name)
    if name in TOKEN_FILES:  # bypass the bench's unpinned download, keep its read()
        m._b = backend
        m._w_u = backend.unembed.detach().float()
        m._jac = load_jacobians(*TOKEN_FILES[name], backend.device)
        if (
            name == "jlens"
        ):  # fill the bench's per-layer cache without the 5 GB temporary
            for L in layers:
                m._denom[L] = jlens_denominator(m._w_u, m._jac[L])
    else:
        m.bind(backend)
    return m


def write_rows(rows: Iterable[dict[str, Any]], path: Path, prov: Provenance) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t0, n = time.time(), 0
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(path)
    secs = time.time() - t0
    write_artefact(
        path.with_suffix(".provenance.json"),
        prov,
        {"rows": n, "seconds": round(secs, 1)},
    )
    print(f"{path}: {n} rows in {secs:.0f}s", flush=True)


def injection_check(v: readers.Verbalizer, items: list[capture.ItemCapture]) -> float:
    """Max logit change between two real vectors and a zero vector. Raises if injection is a
    no-op (the failure mode in which the text still looks fluent)."""
    acts = items[0].acts[v.spec.layer]
    vecs = torch.cat([acts[:1], acts[-1:], torch.zeros_like(acts[:1])]).float()
    logits = v.next_token_logits(vecs)
    diff = min((logits[0] - logits[2]).abs().max(), (logits[1] - logits[2]).abs().max())
    if diff < 1e-3:
        raise RuntimeError(
            f"{v.spec.name}: injection changes nothing (max diff {diff:.2e})"
        )
    return float(diff)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--stages", default="capture,token,blackbox,verbal,nla")
    ap.add_argument("--verbalizers", default="olens-s390,olens-s390-replace,modlens")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument(
        "--limit", type=int, default=0, help="first N items only (smoke runs)"
    )
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--token-arms", default=",".join(arms.TOKEN_ARMS))
    ap.add_argument(
        "--layers",
        default="",
        help="override capture layers, e.g. 2,5 (small-model plumbing tests only)",
    )
    ap.add_argument(
        "--capture-suffix",
        default="",
        help="extra capture file suffix, e.g. -final with --layers 63 (a side capture next to the main one)",
    )
    ap.add_argument("--out", default=str(OUT_DEFAULT), help="output root")
    ap.add_argument(
        "--k", type=int, default=1, help="samples per cell for prose readers"
    )
    args = ap.parse_args()
    torch.set_float32_matmul_precision("highest")
    # Inference only. Without this, ops on the unembedding (a Parameter) record autograd
    # history and keep every intermediate alive: 5 GB per J-lens layer, an OOM on the pod.
    torch.set_grad_enabled(False)
    stages = set(args.stages.split(","))
    out = Path(args.out)
    layers = [int(x) for x in args.layers.split(",")] if args.layers else None
    fam, rev = args.family, PINS.get(args.model, "unpinned")
    suffix = f"-limit{args.limit}" if args.limit else ""
    if args.model != MODEL:  # never mix small-model plumbing runs with real ones
        suffix += "-" + args.model.split("/")[-1]
    cap_path = out / "captures" / f"{fam}{suffix}{args.capture_suffix}.pt"

    def dest(arm: str) -> Path:
        return out / "readouts" / f"{arm}{suffix}" / f"{fam}.jsonl"

    def prov(reader: str | None, extra: dict[str, Any]) -> Provenance:
        return Provenance(
            model=args.model,
            model_revision=rev,
            reader=reader,
            reader_revision=PINS.get(reader or "", None),
            dataset=f"wsbench/{fam}",
            extra={"limit": args.limit, "device": args.device, **extra},
        )

    backend = None
    if stages & {"capture", "token", "blackbox", "verbal"}:
        backend = load_backend(args.model, args.device)

    if "capture" in stages and not cap_path.exists():
        t0 = time.time()
        items = [
            capture.capture_spec(backend, s, layers)
            for s in capture.specs(fam, limit=args.limit)
        ]
        capture.save(items, cap_path)
        write_artefact(
            cap_path.with_suffix(".provenance.json"),
            prov(None, {}),
            {"items": len(items), "seconds": round(time.time() - t0, 1)},
        )
        print(f"[capture] {fam}: {len(items)} items -> {cap_path}", flush=True)
    items = capture.load(cap_path)

    if "token" in stages:
        for name in args.token_arms.split(","):
            if dest(name).exists():
                continue
            cap_layers = sorted({L for it in items for L in it.acts})
            m = bind_token_method(name, backend, cap_layers)
            reader = TOKEN_FILES.get(name, (None,))[0]
            write_rows(readers.token_rows(m, items), dest(name), prov(reader, {}))
            del m
            gc.collect()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None

    if "blackbox" in stages and not dest("blackbox").exists():
        s = readers.Sampling(**{**vars(blackbox.SAMPLING), "k": args.k})
        rows = blackbox.rows(
            backend.model, backend.tokenizer, fam, items, sampling=s, device=args.device
        )
        extra = {"prefill": blackbox.PREFILLS[fam], "sampling": vars(s)}
        write_rows(rows, dest("blackbox"), prov(None, extra))

    if "verbal" in stages:
        for name in args.verbalizers.split(","):
            if dest(name).exists():
                continue
            spec = arms.VERBALIZERS[name]
            v = readers.bind(spec, backend.model, device=args.device)
            backend.model = (
                v.model
            )  # a PeftModel now; capture/blackbox disable adapters
            s = readers.Sampling(**{**vars(spec.sampling), "k": args.k})
            v.spec = readers.VerbalizerSpec(**{**vars(spec), "sampling": s})
            extra = {
                "inject_mode": spec.inject_mode,
                "sampling": vars(s),
                "injection_logit_diff": injection_check(v, items),
            }
            rows = v.rows(items, batch_size=args.batch_size)
            write_rows(rows, dest(name), prov(spec.repo, extra))

    if "nla" in stages and not dest("nla-i400").exists():
        backend = None
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        spec = arms.VERBALIZERS["nla-i400"]
        v = readers.bind(spec, device=args.device)
        s = readers.Sampling(**{**vars(spec.sampling), "k": args.k})
        v.spec = readers.VerbalizerSpec(**{**vars(spec), "sampling": s})
        extra = {
            "inject_mode": spec.inject_mode,
            "sampling": vars(s),
            "injection_logit_diff": injection_check(v, items),
        }
        rows = v.rows(items, batch_size=args.batch_size)
        write_rows(rows, dest("nla-i400"), prov(spec.repo, extra))


if __name__ == "__main__":
    main()
