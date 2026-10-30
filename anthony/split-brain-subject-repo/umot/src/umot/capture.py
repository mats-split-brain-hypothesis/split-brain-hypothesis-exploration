"""Capture residual-stream activations once, at exactly the bench's read cells.

Every reader then reads the same stored vectors, so readers differ only in how they read. Cells
come from the bench's own plan, render and position rules (``wsbench.readplan`` and
``wsbench.produce``), and activations from its ``Backend.capture``: a bench layer L is the output
of decoder block L. Storage is bf16, which is lossless because the model runs in bf16.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
from wsbench import readplan
from wsbench.produce.backend import Backend
from wsbench.produce.producer import _positions
from wsbench.produce.render import render

#: The layer the NLA, olens and modulation lens were trained at. Not on the bench grid, so it is
#: always captured in addition to the plan's layers.
READER_LAYER = 42


@dataclass
class ItemCapture:
    """One plan row: its render, the read positions and the residuals there.

    ``positions`` are as the plan reports them (negative for some rules) and go into readout
    rows; ``idx`` are the absolute indices into ``ids``.
    """

    id: str
    ids: list[int]
    decoded: list[str]
    positions: list[int]
    idx: list[int]
    acts: dict[int, torch.Tensor] = field(
        default_factory=dict
    )  # layer -> [n_pos, d] bf16

    def token(self, i: int) -> str:
        return self.decoded[self.idx[i]]


def specs(
    family: str, *, items: list[str] | None = None, limit: int = 0
) -> list[readplan.ReadSpec]:
    """The bench's read plan for ``family``, optionally restricted to ``items`` or the first
    ``limit`` rows."""
    out = readplan.plan(family)
    if items is not None:
        want = set(items)
        out = [s for s in out if s.id in want]
    return out[: limit or None]


def cells(spec: readplan.ReadSpec, tokenizer: Any) -> ItemCapture:
    """Render a plan row and resolve its read positions, without running the model."""
    rendered = render(spec, tokenizer)
    pos = _positions(spec.positions, rendered.tokens)
    return ItemCapture(
        id=spec.id,
        ids=list(rendered.ids),
        decoded=list(rendered.decoded),
        positions=list(pos),
        idx=[p % len(rendered) for p in pos],
    )


def capture_spec(
    backend: Backend, spec: readplan.ReadSpec, layers: list[int] | None = None
) -> ItemCapture:
    """Residuals for one plan row at its layers plus :data:`READER_LAYER` (or at ``layers``)."""
    item = cells(spec, backend.tokenizer)
    want = sorted(set(layers if layers is not None else [*spec.layers, READER_LAYER]))
    if item.idx:
        acts = backend.capture(item.ids, want, item.idx)
        item.acts = {L: acts[L].to(torch.bfloat16) for L in want}
    return item


def save(items: list[ItemCapture], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save([vars(i) for i in items], tmp)
    tmp.replace(path)
    return path


def load(path: str | Path) -> list[ItemCapture]:
    return [ItemCapture(**d) for d in torch.load(path, weights_only=False)]
