"""The 27B J-lens without the model: ``W_U``, the final norm gain and the transports ``J_l``.

Three maps: ``jlens`` (the released n1000 wikitext lens, the bench's; every centre is read through it), ``jpp``
(the J++ lens, Ayonrinde & Lindsey 2026) and ``logit`` (the logit lens: no map, ``J_l = I``, the state read straight
through the final norm and ``W_U``). The last two are comparison maps, never a centre's lens. Each is one linear
``J_l`` per layer, so the readouts and centring apply to any of them unchanged. A study can add a map it fitted itself
as ``out/maps/<name>.pt`` (:data:`MAPS`): it reads as ``<name>:`` like the others.

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

from jlm import OUT, REPO_ROOT

MODEL = "Qwen/Qwen3.6-27B"
LENS_REPO = "neuronpedia/jacobian-lens"
LENS_FILE = "qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt"
#: map name -> (HF repo, file); revisions from ``PINS``.
LENSES = {"jlens": (LENS_REPO, LENS_FILE), "jpp": ("koayon/jpp-lenses", "qwen3.6-27b/lens.pt"),
          "logit": (MODEL, "logit-lens (no map: final norm + lm_head)")}
#: Maps with no file: J_l is the identity (pinned by the model's own revision).
IDENTITY = {"logit"}
#: Locally fitted maps: ``<name>.pt`` holding ``{"J": {layer: [d, d]}}``, registered as ``(None, path)`` and pinned by
#: content hash. They live under ``out/`` and reach the other machine through the shared dataset (``maps`` scope).
MAPS = OUT / "maps"


def local_maps(root: Path = MAPS) -> dict[str, tuple[None, str]]:
    return {p.stem: (None, str(p)) for p in sorted(root.glob("*.pt"))}


LENSES |= {k: v for k, v in local_maps().items() if k not in LENSES}
READOUTS = ("cos", "rms")
RMS_EPS = 1e-6  # config.json rms_norm_eps
DENOM_CACHE = OUT / "lens"


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
    return f"{repo}/{file}", PINS[repo]


def load_maps(name: str, layers: list[int], device: str = "cpu") -> dict[int, torch.Tensor]:
    """``J_l`` of map ``name`` at ``layers``, fp32 on ``device`` (none for an identity map)."""
    if name in IDENTITY:
        return {}
    repo, file = LENSES[name]
    path = file if repo is None else hf_hub_download(repo, file, revision=PINS[repo])
    obj = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
    obj = obj.get("parameters", obj)  # J++ nests its maps under "parameters"
    jac = obj["J"] if "J" in obj else obj["jacobians"]
    get = (lambda L: jac[L] if L in jac else jac[str(L)]) if isinstance(jac, dict) else jac.__getitem__
    return {L: get(L).float().clone().to(device) for L in layers}


def _model_tensor(suffix: str) -> torch.Tensor:
    rev = PINS[MODEL]
    index = json.loads(Path(hf_hub_download(MODEL, "model.safetensors.index.json", revision=rev)).read_text())
    key = next(k for k in index["weight_map"] if k == suffix or k.endswith("." + suffix))
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
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
            self.w_u = _model_tensor("lm_head.weight").float().to(device)  # [V, d]
            self.gain = (1 + _model_tensor("language_model.norm.weight").float()).to(device)
        self.identity = name in IDENTITY
        self.jac = load_maps(name, self.layers, device)  # the logit lens: none
        self.denom = {L: self._denominator(L) for L in self.layers}

    @property
    def vocab(self) -> int:
        return self.w_u.shape[0]

    def _denominator(self, layer: int, chunk: int = 16384) -> torch.Tensor:
        """``||J_l^T W_U[t]||`` per token (the bench's, clamped at 1e-9), cached on disk."""
        key = self.name if self.identity else PINS[self.repo][:8] if self.repo else f"{self.name}-{reader(self.name)[1][7:15]}"
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
