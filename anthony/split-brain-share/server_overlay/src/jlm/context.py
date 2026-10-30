"""Every-position residuals: the context capture behind g's that look beyond the read cell.

The read-cell captures (``jlm.capture``) hold h only where the bench reads. A context capture holds h at
**every** position of each item's render, at the bank's layers plus ``FINAL_LAYER`` (the last block, whose
normed output gives the model's own next-token distribution: the next-token baseline control). Bench
prompts are short (8-52 tokens), so a whole bank is 0.05-0.6 GB in bf16.

Files: ``out/ctx/<family>-<split>.pt`` for banks and ``out/ctx/corpus-<name>.pt`` for text corpora (neutral
or reference text with no read cells). Each holds a list of ``CtxItem`` dicts. A store loads the whole file
into memory by default: on the pods the files sit on the network volume, where mmap turns every row access
into a network read (a check over 2k cells took 8-10 minutes that way). ``mmap=True`` suits a local disk.
"""

from dataclasses import dataclass, field
from pathlib import Path

import torch
from umot.provenance import Provenance, write_artefact

from jlm import models
from jlm.banks import Bank, specs

SPEC = models.current()
FINAL_LAYER = SPEC.final_layer  # Qwen3.6-27B: 63 of 64 blocks; the model's logits are W_U norm(h_final)
CTX = models.out_dir() / "ctx"


@dataclass
class CtxItem:
    id: str
    ids: list[int]
    decoded: list[str]
    idx: list[int]  # absolute indices of the read cells (as in the read-cell capture); [] for corpus text
    acts: dict[int, torch.Tensor] = field(default_factory=dict)  # layer -> [T, d] bf16, every position


def bank_path(bank: Bank) -> Path:
    return CTX / f"{bank.family}-{bank.split}.pt"


def corpus_path(name: str) -> Path:
    return CTX / f"corpus-{name}.pt"


class ContextStore:
    """The context capture of one bank (or corpus): ``states(item, layer)`` -> [T, d] bf16 for every
    position, ``at(item, layer, i)`` -> the state at the item's i-th read cell."""

    def __init__(self, path: Path, mmap: bool = False) -> None:
        if not path.exists():
            raise FileNotFoundError(f"no context capture at {path}; run experiments/capture_ctx.py on the pod")
        self.path = path
        self.items = {d["id"]: CtxItem(**d) for d in torch.load(path, weights_only=False, mmap=mmap)}

    @classmethod
    def of(cls, bank: Bank) -> "ContextStore":
        return cls(bank_path(bank))

    def layers(self) -> list[int]:
        return sorted(next(iter(self.items.values())).acts)

    def states(self, item: str, layer: int) -> torch.Tensor:
        return self.items[item].acts[layer]

    def at(self, item: str, layer: int, i: int) -> torch.Tensor:
        it = self.items[item]
        return it.acts[layer][it.idx[i]]


def _save(rows: list[CtxItem], path: Path, prov: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".pt.tmp")
    torch.save([vars(r) for r in rows], tmp)
    tmp.replace(path)
    write_artefact(path.with_suffix(".provenance.json"),
                   Provenance(model=SPEC.hf_id, model_revision=SPEC.revision, **prov),
                   {"items": len(rows), "tokens": sum(len(r.ids) for r in rows)})
    return path


def capture_bank(backend, bank: Bank, *, limit: int = 0) -> Path:
    """Every position of every item of ``bank``, at its plan's layers, umot's reader layer 42 and ``FINAL_LAYER``."""
    from umot import capture as ucap

    rows = []
    for s in specs(bank)[: limit or None]:
        it = ucap.cells(s, backend.tokenizer)
        layers = sorted({*s.layers, ucap.READER_LAYER, FINAL_LAYER})
        acts = backend.capture(it.ids, layers, list(range(len(it.ids))))
        rows.append(CtxItem(it.id, it.ids, it.decoded, it.idx, {L: acts[L].to(torch.bfloat16) for L in layers}))
    path = bank_path(bank) if not limit else bank_path(bank).with_name(f"{bank.family}-{bank.split}-limit{limit}.pt")
    return _save(rows, path, {"dataset": f"jlm/{bank.name}", "extra": {"kind": "context", "limit": limit}})


def capture_texts(backend, name: str, texts: list[tuple[str, list[int]]], layers: list[int], source: str) -> Path:
    """Every position of each (id, token ids) text at ``layers`` + ``FINAL_LAYER`` (no read cells)."""
    rows = []
    want = sorted({*layers, FINAL_LAYER})
    for tid, ids in texts:
        acts = backend.capture(ids, want, list(range(len(ids))))
        rows.append(CtxItem(tid, ids, backend.tokenizer.convert_ids_to_tokens(ids), [],
                            {L: acts[L].to(torch.bfloat16) for L in want}))
    return _save(rows, corpus_path(name), {"dataset": source, "extra": {"kind": "corpus", "name": name}})
