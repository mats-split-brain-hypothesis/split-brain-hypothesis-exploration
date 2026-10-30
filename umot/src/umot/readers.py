"""Readers: turn captured residuals into rows of the bench's readout contract.

Two kinds:

* **Token readers** (logit lens, J-lens, R-lens) reuse the bench's own methods unchanged, so their
  numerics are the bench's.
* **Verbalizers** (olens, modulation lens, NLA) are one batched class configured by a
  :class:`VerbalizerSpec`. The bench's verbalizers generate one cell at a time (~31 s per NLA cell
  on an A100), and it has no modulation lens or collection olens.

A verbalizer injects the vector at the output of decoder block 1, at the single marker token of
its own prompt, and generates. Each spec's prompt is read verbatim from the checkpoint's
``nla_meta.yaml``, because the prompt is part of the trained lens.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import torch

from umot.capture import ItemCapture

InjectMode = Literal["replace", "add_normmatched"]


def row(
    item: ItemCapture, layer: int, i: int, readout: dict[str, Any]
) -> dict[str, Any]:
    """One readouts-contract row for cell ``(item, layer, i-th read position)``."""
    return {
        "id": item.id,
        "layer": layer,
        "pos": item.positions[i],
        "token": item.token(i),
        **readout,
    }


# ---------------------------------------------------------------- token readers


def token_rows(
    method: Any, items: list[ItemCapture], layers: list[int] | None = None
) -> Iterator[dict[str, Any]]:
    """Rows from a bound bench method (``wsbench.produce.method("jlens")`` etc.) over every
    captured cell, or over ``layers`` only."""
    for item in items:
        for layer, acts in sorted(item.acts.items()):
            if layers is not None and layer not in layers:
                continue
            for i in range(acts.shape[0]):
                yield row(item, layer, i, method.read(acts[i].float(), layer).row())


def cell_means(items: list[ItemCapture]) -> dict[int, torch.Tensor]:
    """Per layer, the mean residual over every captured cell of ``items`` (float64 sum, fp32
    out). Label-free: it uses the activations only, never the answers."""
    sums: dict[int, torch.Tensor] = {}
    counts: dict[int, int] = {}
    for item in items:
        for layer, acts in item.acts.items():
            s = acts.double().sum(0)
            sums[layer] = sums[layer] + s if layer in sums else s
            counts[layer] = counts.get(layer, 0) + acts.shape[0]
    return {L: (sums[L] / counts[L]).float() for L in sums}


@dataclass
class Centred:
    """A token method read on ``h − μ_l`` instead of ``h`` (the jlens-edits ``ctr:`` arms).

    Wraps a bound bench method, so its readout (for the J-lens, the cosine score with the same
    ``‖Jᵀ W_U[t]‖`` normaliser) and its row format are unchanged; only the input moves."""

    method: Any
    means: dict[int, torch.Tensor]

    def read(self, h: torch.Tensor, layer: int) -> Any:
        return self.method.read(h - self.means[layer].to(h.device, h.dtype), layer)


# ---------------------------------------------------------------- verbalizers


def strip_explanation(text: str) -> str:
    """NLA outputs wrap the answer in ``<explanation>`` tags."""
    return text.split("</explanation>")[0].removeprefix("<explanation>").strip()


@dataclass(frozen=True)
class Sampling:
    temperature: float = 1.0
    top_p: float = 1.0
    top_k: int = 0
    max_new_tokens: int = 256
    k: int = 1  # samples per cell


@dataclass(frozen=True)
class VerbalizerSpec:
    """Everything that defines one verbalizer arm.

    Attributes:
        name: Arm name, used in output paths.
        repo / revision: Hub repo and pinned revision of the adapter.
        subfolder: Adapter directory inside the repo ("" for the root).
        base: ``None`` to mount the adapter on the probed model; otherwise a directory in
            ``repo`` holding a separate reader model (the NLA's ``av_base``).
        inject_mode: ``replace`` writes the raw vector at the marker; ``add_normmatched`` adds
            ``||h_marker|| * unit(v)``.
        layer: The layer the lens was trained to read.
    """

    name: str
    repo: str
    revision: str
    subfolder: str
    inject_mode: InjectMode
    sampling: Sampling
    base: str | None = None
    meta_dir: str | None = None  # where nla_meta.yaml lives, if not in `subfolder`
    layer: int = 42
    postprocess: Callable[[str], str] = str.strip


def _block1(model: Any) -> Any:
    """The text decoder's block 1, wherever PEFT or a multimodal wrapper put it."""
    found = [m for n, m in model.named_modules() if re.search(r"(^|\.)layers\.1$", n)]
    found = [m for m in found if not hasattr(m, "blocks")]
    if len(found) != 1:
        raise RuntimeError(f"expected one decoder block 1, found {len(found)}")
    return found[0]


@dataclass
class Verbalizer:
    """A bound verbalizer: tokenized prompt, marker index, injection hook, generating model."""

    spec: VerbalizerSpec
    model: Any
    tokenizer: Any
    prompt_ids: list[int]
    marker: int
    device: str
    calls: int = 0  # how many prefill passes injected; checked by tests
    _vecs: torch.Tensor | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _block1(self.model).register_forward_hook(self._hook)

    def _hook(self, _mod: Any, _inp: Any, out: Any) -> Any:
        h = out[0] if isinstance(out, tuple) else out
        v = self._vecs
        if v is None or h.shape[1] <= self.marker:  # decode steps see one new token
            return out
        if h.shape[0] != v.shape[0]:
            raise RuntimeError(f"batch {h.shape[0]} != {v.shape[0]} injected vectors")
        v = v.to(device=h.device, dtype=h.dtype)
        if self.spec.inject_mode == "replace":
            h[:, self.marker, :] = v
        else:
            hp = h[:, self.marker, :]
            unit = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)
            h[:, self.marker, :] = hp + hp.norm(dim=-1, keepdim=True) * unit
        self.calls += 1
        return out

    @torch.no_grad()
    def next_token_logits(self, vecs: torch.Tensor) -> torch.Tensor:
        """Logits of the first generated token for each injected vector, [n, V]. The injection
        check: different vectors must give different logits (a silent no-op gives equal ones)."""
        n = vecs.shape[0]
        self._vecs = vecs.float()
        ids = torch.tensor([self.prompt_ids], device=self.device).expand(n, -1)
        try:
            out = self.model(ids, attention_mask=torch.ones_like(ids), logits_to_keep=1)
        finally:
            self._vecs = None
        return out.logits[:, -1, :].float()

    @torch.no_grad()
    def generate(
        self, vecs: torch.Tensor, sampling: Sampling | None = None
    ) -> list[list[str]]:
        """``k`` samples for each row of ``vecs`` ([n, d]), in one batched ``generate``."""
        s = sampling or self.spec.sampling
        n = vecs.shape[0]
        self._vecs = vecs.float().repeat_interleave(s.k, dim=0)
        ids = torch.tensor([self.prompt_ids], device=self.device).expand(n * s.k, -1)
        kw: dict[str, Any] = {"do_sample": s.temperature > 0}
        if s.temperature > 0:
            kw.update(temperature=s.temperature, top_p=s.top_p, top_k=s.top_k)
        try:
            out = self.model.generate(
                ids,
                attention_mask=torch.ones_like(ids),
                max_new_tokens=s.max_new_tokens,
                pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                **kw,
            )
        finally:
            self._vecs = None
        texts = self.tokenizer.batch_decode(
            out[:, len(self.prompt_ids) :], skip_special_tokens=True
        )
        texts = [self.spec.postprocess(t) for t in texts]
        return [texts[i * s.k : (i + 1) * s.k] for i in range(n)]

    def rows(
        self,
        items: list[ItemCapture],
        *,
        batch_size: int = 32,
        layer: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Rows over every captured cell at ``layer`` (default: the lens's own layer)."""
        layer = self.spec.layer if layer is None else layer
        cells = [(item, i) for item in items for i in range(item.acts[layer].shape[0])]
        for start in range(0, len(cells), batch_size):
            chunk = cells[start : start + batch_size]
            vecs = torch.stack([item.acts[layer][i] for item, i in chunk])
            for (item, i), samples in zip(chunk, self.generate(vecs), strict=True):
                yield row(item, layer, i, {"samples": samples})


def _meta(local: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load((local / "nla_meta.yaml").read_text(encoding="utf-8"))


def render_prompt(tokenizer: Any, meta: dict[str, Any]) -> tuple[list[int], int]:
    """The verbalizer prompt's ids and the marker index, with the marker's neighbours checked:
    a misplaced marker is a silent no-op injection."""
    tok_meta = meta["tokens"]
    content = meta["prompt_templates"]["actor"].format(
        injection_char=tok_meta["injection_char"]
    )
    out = tokenizer.apply_chat_template(
        [{"role": "user", "content": content}],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    ids = list(out["input_ids"] if hasattr(out, "keys") else out)
    marker = int(tok_meta["injection_token_id"])
    hits = [i for i, t in enumerate(ids) if t == marker]
    if len(hits) != 1:
        raise ValueError(
            f"expected one marker {marker} in the prompt, found {len(hits)}"
        )
    (m,) = hits
    for key, j in (
        ("injection_left_neighbor_id", m - 1),
        ("injection_right_neighbor_id", m + 1),
    ):
        if key in tok_meta and ids[j] != int(tok_meta[key]):
            raise ValueError(
                f"marker neighbour {key}: expected {tok_meta[key]}, got {ids[j]}"
            )
    return ids, m


def bind(
    spec: VerbalizerSpec, probed: Any = None, *, device: str = "cuda"
) -> Verbalizer:
    """Load ``spec``'s adapter (onto ``probed``, a loaded model or PeftModel, or onto its own
    ``base``) and return the bound verbalizer."""
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    pattern = [f"{spec.subfolder}/*"] if spec.subfolder else None
    meta_pattern = [f"{spec.meta_dir}/*"] if spec.meta_dir else []
    base_pattern = [f"{spec.base}/*"] if spec.base else []
    allow = None if pattern is None else pattern + meta_pattern + base_pattern
    root = Path(
        snapshot_download(spec.repo, revision=spec.revision, allow_patterns=allow)
    )
    adir = root / spec.subfolder if spec.subfolder else root
    meta = _meta(root / spec.meta_dir if spec.meta_dir else adir)

    if spec.base is None:
        if probed is None:
            raise ValueError(f"{spec.name} mounts on the probed model; pass it")
        if isinstance(probed, PeftModel):
            if spec.name not in probed.peft_config:
                probed.load_adapter(str(adir), adapter_name=spec.name)
            probed.set_adapter(spec.name)
            model = probed
        else:
            model = PeftModel.from_pretrained(probed, str(adir), adapter_name=spec.name)
        tok_dir = adir if (adir / "tokenizer_config.json").exists() else None
    else:
        model = AutoModelForCausalLM.from_pretrained(
            root / spec.base, dtype=torch.bfloat16, device_map=device
        )
        model = PeftModel.from_pretrained(model, str(adir), torch_dtype=torch.bfloat16)
        tok_dir = root / spec.base
    model.eval()
    if tok_dir is None:
        tok_dir = probed.config._name_or_path
    tokenizer = AutoTokenizer.from_pretrained(tok_dir)
    ids, marker = render_prompt(tokenizer, meta)
    return Verbalizer(spec, model, tokenizer, ids, marker, device)
