"""The J-lens without the model (the selected model, ``jlm.models``): ``W_U``, the final norm gain and the transports ``J_l``.

Three maps: ``jlens`` (the released n1000 wikitext lens, the bench's; every centre is read through it), ``jpp``
(the J++ lens, Ayonrinde & Lindsey 2026) and ``logit`` (the logit lens: no map, ``J_l = I``, the state read straight
through the final norm and ``W_U``). The last two are comparison maps, never a centre's lens. Each is one linear
``J_l`` per layer, so the readouts and centring apply to any of them unchanged. A study can add a map it fitted itself
as ``out/maps/<name>.pt`` (:data:`MAPS`): it reads as ``<name>:`` like the others. A local map may also carry a bias
``b_l`` (``{"J": ..., "b": {layer: [d]}}``), read as the affine ``J_l h + b_l``: a bias is ``-J_l mu`` for a fixed mu.
Instead of a dense ``J`` it may hold low-rank factors (``"U"``, ``"V"``: ``J_l = U_l V_l``) or name another map
(``"base": "jlens"``, optionally ``"layer_map": {l: l'}`` to read ``J_l'`` at layer ``l``), so a bias-only or
re-indexed map is a small file.

Two readouts, both linear in the state, so a centred read is ``L(h) - L(mu)``:
``cos`` (the bench's): ``(W_U J h)_t / ||J^T W_U[t]||``;
``rms`` (jle's): ``rms_norm(J h, 1 + w) W_U^T``.
"""

import hashlib
import json
from functools import cache
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from safetensors import safe_open
from umot.provenance import PINS

from jlm import REPO_ROOT, models

SPEC = models.current()
MODEL = SPEC.hf_id
LENS_REPO, LENS_FILE = SPEC.lenses["jlens"]
#: map name -> (HF repo, file); revisions from ``PINS``.
LENSES = {**SPEC.lenses, "logit": (MODEL, "logit-lens (no map: final norm + lm_head)")}
#: Maps with no file: J_l is the identity (pinned by the model's own revision).
IDENTITY = {"logit"}
#: Locally fitted maps: ``<name>.pt`` holding ``{"J": {layer: [d, d]}}``, registered as ``(None, path)`` and pinned by
#: content hash. They live under ``out/`` and reach the other machine through the shared dataset (``maps`` scope).
MAPS = models.out_dir() / "maps"


def local_maps(root: Path = MAPS) -> dict[str, tuple[None, str]]:
    return {p.stem: (None, str(p)) for p in sorted(root.glob("*.pt"))}


LENSES |= {k: v for k, v in local_maps().items() if k not in LENSES}
READOUTS = ("cos", "rms")
RMS_EPS = SPEC.rms_eps  # config.json rms_norm_eps
DENOM_CACHE = models.out_dir() / "lens"


@cache
def _digest(path: str, mtime: float) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 24):
            h.update(chunk)
    return h.hexdigest()[:16]


def reader(name: str) -> tuple[str, str]:
    """(the map, its revision) for provenance: an HF file at its pin, or a local map's path and content hash."""
    repo, file = LENSES[name]
    if repo is None:
        p = Path(file)
        return str(p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p), "sha256:" + _digest(file, p.stat().st_mtime)
    return f"{repo}/{file}", _pin(repo)


def _pin(repo: str) -> str:
    """A repo's pinned revision: the model's own from its spec, the others from umot's ``PINS``."""
    return SPEC.revision if repo == MODEL else PINS[repo]


def _map_file(name: str) -> dict:
    repo, file = LENSES[name]
    path = file if repo is None else hf_hub_download(repo, file, revision=_pin(repo))
    obj = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
    return obj.get("parameters", obj)  # J++ nests its maps under "parameters"


def _per_layer(tab, layers: list[int], device: str) -> dict[int, torch.Tensor]:
    get = (lambda L: tab[L] if L in tab else tab[str(L)]) if isinstance(tab, dict) else tab.__getitem__
    return {L: get(L).float().clone().to(device) for L in layers}


def load_maps(name: str, layers: list[int], device: str = "cpu") -> dict[int, torch.Tensor]:
    """``J_l`` of map ``name`` at ``layers``, fp32 on ``device`` (none for an identity map)."""
    if name in IDENTITY:
        return {}
    obj = _map_file(name)
    if "base" in obj:
        remap = {int(k): int(v) for k, v in obj.get("layer_map", {}).items()}
        src = load_maps(obj["base"], sorted({remap.get(L, L) for L in layers}), device)
        return {L: src[remap.get(L, L)] for L in layers}
    if "U" in obj:
        U, V = _per_layer(obj["U"], layers, device), _per_layer(obj["V"], layers, device)
        return {L: U[L] @ V[L] for L in layers}
    return _per_layer(obj["J"] if "J" in obj else obj["jacobians"], layers, device)


def load_bias(name: str, layers: list[int], device: str = "cpu") -> dict[int, torch.Tensor]:
    """``b_l`` of an affine local map at ``layers`` (none for a linear map)."""
    if name in IDENTITY:
        return {}
    obj = _map_file(name)
    return _per_layer(obj["b"], layers, device) if "b" in obj else {}


def _model_tensor(suffix: str) -> torch.Tensor:
    rev = SPEC.revision
    index = json.loads(Path(hf_hub_download(MODEL, "model.safetensors.index.json", revision=rev)).read_text())
    keys = index["weight_map"]
    key = suffix if suffix in keys else next(k for k in keys if k.endswith("." + suffix))
    with safe_open(hf_hub_download(MODEL, index["weight_map"][key], revision=rev), framework="pt") as f:
        return f.get_tensor(key)


class Lens:
    """The pinned lens ``name`` (a ``LENSES`` key) at ``layers``, fp32 on ``device``."""

    def __init__(self, layers: list[int], device: str = "cpu", name: str = "jlens", share: "Lens | None" = None) -> None:
        """``share``: another map's lens whose tokenizer, ``W_U`` and norm gain this one reuses (same model)."""
        from transformers import AutoTokenizer

        self.layers, self.device, self.name = sorted(layers), device, name
        self.repo, self.file = LENSES[name]
        if share is not None:
            self.tokenizer, self.w_u, self.gain = share.tokenizer, share.w_u, share.gain
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=SPEC.revision)
            self.w_u = _model_tensor(SPEC.lm_head_key).float().to(device)  # [V, d]
            self.gain = (SPEC.norm_offset + _model_tensor(SPEC.norm_key).float()).to(device)  # Qwen 1 + w, Llama w
        self.identity = name in IDENTITY
        self.jac = load_maps(name, self.layers, device)  # the logit lens: none
        self.bias = load_bias(name, self.layers, device)  # an affine local map's b_l: none for the others
        self.denom = {L: self._denominator(L) for L in self.layers}

    @property
    def vocab(self) -> int:
        return self.w_u.shape[0]

    def _denominator(self, layer: int, chunk: int = 16384) -> torch.Tensor:
        """``||J_l^T W_U[t]||`` per token (the bench's, clamped at 1e-9), cached on disk."""
        key = self.name if self.identity else _pin(self.repo)[:8] if self.repo else f"{self.name}-{reader(self.name)[1][7:15]}"
        path = DENOM_CACHE / f"cos-denom-{key}-L{layer:03d}.pt"
        if path.exists():
            return torch.load(path).to(self.device)
        d = torch.cat(
            [(self.w_u[i : i + chunk] if self.identity else self.w_u[i : i + chunk] @ self.jac[layer]).norm(dim=1)
             for i in range(0, self.vocab, chunk)]
        ).clamp_min(1e-9)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(d.cpu(), path)
        return d

    def scores(self, x: torch.Tensor, layer: int, readout: str) -> torch.Tensor:
        """[n, V] readout scores of states ``x`` [n, d] (already centred by the caller)."""
        z = x.to(self.device, torch.float32)
        if not self.identity:
            z = z @ self.jac[layer].T
        if layer in getattr(self, "bias", {}):
            z = z + self.bias[layer]
        if readout == "cos":
            return (z @ self.w_u.T) / self.denom[layer]
        if readout == "rms":
            z = self.gain * z / torch.sqrt(z.square().mean(dim=1, keepdim=True) + RMS_EPS)
            return z @ self.w_u.T
        raise ValueError(f"readout {readout!r} not in {READOUTS}")

    def logits(self, h: torch.Tensor) -> torch.Tensor:
        """[n, V] the model's own next-token logits from final-block states ``h`` (``context.FINAL_LAYER``)."""
        z = h.to(self.device, torch.float32)
        z = self.gain * z / torch.sqrt(z.square().mean(dim=1, keepdim=True) + RMS_EPS)
        return z @ self.w_u.T

    def display(self, ids: list[int]) -> list[str]:
        from wsbench.produce.render import display_tokens

        return display_tokens(self.tokenizer, ids)
