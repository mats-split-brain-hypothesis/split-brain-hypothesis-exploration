"""The models the pipeline can read, and which one this process reads (env ``JLM_MODEL``, default ``qwen27b``).

One :class:`ModelSpec` per model holds what the lens, capture and context code used to hard-code for Qwen3.6-27B:
the hub id and pin, the block count, the final norm (its tensor key and gain convention), the norm epsilon, the chat
template's extra arguments and the lens files. Selecting another model also moves its outputs under ``out/<key>/``
(:func:`out_dir`), so captures, context stores and lens caches of two models never share a path; the default model
keeps the top-level ``out/`` it has always used. ``out/<key>/...`` reaches the shared dataset like any other path.

Qwen3.x's final RMSNorm scales by ``1 + w`` (zero-centred weights); Llama's scales by ``w``. Getting this wrong
does not raise: the ``rms`` readout and ``Lens.logits`` would just be wrong. ``tests/test_models.py`` checks each spec
against the model's ``config.json``.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from jlm import OUT


@dataclass(frozen=True)
class ModelSpec:
    key: str  # short name: env JLM_MODEL, out/<key>/ for a non-default model
    hf_id: str
    revision: str
    n_layers: int  # decoder blocks; the final block is n_layers - 1
    d_model: int
    vocab: int
    norm_key: str  # the final norm's weight in model.safetensors.index.json
    norm_offset: float  # final-norm gain = norm_offset + w
    rms_eps: float
    lm_head_key: str = "lm_head.weight"
    chat_kwargs: dict = field(default_factory=dict)  # extra apply_chat_template arguments
    #: map name -> (HF repo, file); lens revisions come from umot's PINS. "logit" is the identity map.
    lenses: dict = field(default_factory=dict)
    #: read the bench's layer grid (set for the 27B) at the same relative depth in this model (``jlm.banks.specs``)
    bench_depth: bool = False

    @property
    def final_layer(self) -> int:
        return self.n_layers - 1

    def depth(self, layer: int, other: "ModelSpec") -> int:
        """``layer`` of ``other`` at the same relative depth in this model (for matching read layers)."""
        return round(layer * self.final_layer / other.final_layer)


NEURONPEDIA = "neuronpedia/jacobian-lens"

MODELS: dict[str, ModelSpec] = {
    s.key: s
    for s in (
        ModelSpec(
            key="qwen27b",
            hf_id="Qwen/Qwen3.6-27B",
            revision="6a9e13bd6fc8f0983b9b99948120bc37f49c13e9",  # = umot PINS, the bench's pin
            n_layers=64,
            d_model=5120,
            vocab=248320,
            norm_key="language_model.norm.weight",
            norm_offset=1.0,
            rms_eps=1e-6,
            chat_kwargs={"enable_thinking": False},
            lenses={
                "jlens": (NEURONPEDIA, "qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt"),
                "jpp": ("koayon/jpp-lenses", "qwen3.6-27b/lens.pt"),
            },
        ),
        # Liars' Bench's model. Released lens: wikitext, stopped at 125 prompts (Qwen's: 1000); layers 0..78, fp16.
        # The chat template always writes a "Cutting Knowledge Date / Today Date" system header; it is kept, since
        # Liars' Bench generated its transcripts through the same template.
        ModelSpec(
            key="llama70b",
            hf_id="meta-llama/Llama-3.3-70B-Instruct",
            revision="6f6073b423013f6a7d4d9f39144961bfbfbc386b",  # pinned 2026-10-13
            n_layers=80,
            d_model=8192,
            vocab=128256,
            norm_key="model.norm.weight",
            norm_offset=0.0,
            rms_eps=1e-5,
            lenses={"jlens": (NEURONPEDIA, "llama3.3-70b-it/jlens/Salesforce-wikitext/Llama-3.3-70B-Instruct_jacobian_lens.pt")},
        ),
        # A small Qwen to iterate on locally (16 GB GPU). Tied embeddings: W_U is the input embedding. Released lens:
        # wikitext, n=417, layers 0..30, fp16 (jle used it for its 4B bench runs).
        ModelSpec(
            key="qwen4b",
            hf_id="Qwen/Qwen3.5-4B",
            revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",  # = jle's PINS
            n_layers=32,
            d_model=2560,
            vocab=248320,
            norm_key="language_model.norm.weight",
            norm_offset=1.0,
            rms_eps=1e-6,
            lm_head_key="language_model.embed_tokens.weight",
            chat_kwargs={"enable_thinking": False},
            lenses={"jlens": (NEURONPEDIA, "qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens.pt")},
            bench_depth=True,  # L4, 8, ..., 60 of 64 -> L2, 4, ..., 30 of 32
        ),
        # The smallest Qwen with a released lens: CPU plumbing checks only.
        ModelSpec(
            key="qwen08b",
            hf_id="Qwen/Qwen3.5-0.8B",
            revision="2fc06364715b967f1860aea9cf38778875588b17",  # = jle's PINS
            n_layers=24,
            d_model=1024,
            vocab=248320,
            norm_key="language_model.norm.weight",
            norm_offset=1.0,
            rms_eps=1e-6,
            lm_head_key="language_model.embed_tokens.weight",
            chat_kwargs={"enable_thinking": False},
            lenses={"jlens": (NEURONPEDIA, "qwen3.5-0.8b/jlens/Salesforce-wikitext/Qwen3.5-0.8B_jacobian_lens.pt")},
            bench_depth=True,
        ),
    )
}
DEFAULT = "qwen27b"


def current() -> ModelSpec:
    """The model this process reads: env ``JLM_MODEL`` (a :data:`MODELS` key or hub id), else :data:`DEFAULT`."""
    want = os.environ.get("JLM_MODEL", DEFAULT)
    for s in MODELS.values():
        if want in (s.key, s.hf_id):
            return s
    raise KeyError(f"JLM_MODEL={want!r} is not one of {sorted(MODELS)}")


def out_dir(spec: ModelSpec | None = None) -> Path:
    """Where a model's outputs live: ``out/`` for the default model, ``out/<key>/`` for the others."""
    spec = spec or current()
    return OUT if spec.key == DEFAULT else OUT / spec.key
