"""Pins and provenance for every results artefact.

CLAUDE.md, "Provenance": every artefact under ``out/`` records the git SHA, whether
the tree was dirty, the host, the model and its revision, and the reader (lens /
NLA / oracle lens) and its revision. :func:`write_artefact` is the sanctioned way
to write a JSON result.

Unlike the sibling ``jlens-edits`` repo, a dirty tree is allowed (this is an
exploration repo) but always recorded, so a number from uncommitted code is
visibly marked as such.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Hub revisions this project is pinned to. Bump deliberately and note why in
#: notes/research-log.md: a moving model or reader silently invalidates every
#: cross-run comparison.
PINS: dict[str, str] = {
    # The model. Same pin as WorkspaceBench work in jlens-edits (2026-09-24).
    "Qwen/Qwen3.6-27B": "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9",
    # J-lens transports (neuronpedia release, fp16, layers 0..62). Pin carried from
    # jlens-edits; the hub's main has moved since, do not follow it silently.
    "neuronpedia/jacobian-lens": "a4114d7752d11eb546e6cf372213d7e75526d3a1",
    # Bench lenses: qwen3.6-27b/{j-lens,r-lens}/lens.pt and template-lens passages.
    "camilablank/workspace-lenses": "d740106d1e0f95456dc8718fba2895e9c8ffd6ef",
    # NLA: av_base + av_rl_adapters/iter_000400 (the bench's `nla` arm), layer 42.
    "ceselder/qwen3.6-27b-nla-rl": "5a13b7ec21a69fcdd0fb24d5edbe96a92aef4b9f",
    # The bench's `olens` arm (a dataset repo): ckpts/ao/rl/s3d.ddp600.s0/iter_000600.
    # Pinned 2026-10-08; the bench's loader downloads main, so callers compare.
    "agu18dec/local-workspace": "5653a7fead43ecbd87e3b6d2a2990a98b32843ca",
    # Meta-models programme (meta/), pinned 2026-10-14: the same oracle lens (olens_s3d_rl600) and its matched
    # reconstructor (ar_ptag_pooled) in one public model repo.
    "agu18dec/olens_and_ar": "c95215d5d2f6250f20c305ae55c6e4d7569f92dc",
    # ceselder "good meta-models" collection, pinned 2026-10-08.
    "ceselder/modulation-lens-meta-model-qwen36-27b": "a29b940ccecabe3ba06dd9d100012e1e94fe1990",
    "ceselder/olens-rl-grpo-trajectory-qwen36-27b": "913d4ccc0ee4a391d3bf5a27ffffd6d0d8a59ad7",
    "ceselder/skip-lens-qwen36-27b-RL-surprisal": "c40a0928b7ccc088638e43bd8e574622e75fd7ab",
    "ceselder/qwen36-27b-bsf-l42-1b": "52b898a524c0f9d3a54dd111f8ebf6913529365b",
    # J++ Lens (Ayonrinde & Lindsey 2026): qwen3.6-27b/lens.pt, fp32, layers 0..62. Pinned 2026-10-09.
    "koayon/jpp-lenses": "6c96867a91c43c14cec17cf0f6d157b933c5fee5",
}

#: github.com/safety-research/jpp_lens commit whose eval items, split and scoring we use.
JPP_COMMIT = "93f02cd6c27db765abb127f20eff656bb5d27340"

#: WorkspaceBench commit checked out into third_party/ by tools/bootstrap.sh.
WSBENCH_COMMIT = "92d763e722377f5bfae045e829a308ab5919a820"


def git_sha() -> str:
    """Current commit of this repo, or ``"unknown"`` outside a checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return out.stdout.strip()


def git_dirty() -> bool:
    """Whether tracked files have uncommitted changes."""
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return bool(out.stdout.strip())


@dataclass(frozen=True, kw_only=True)
class Provenance:
    """What a results artefact must carry.

    Attributes:
        model / model_revision: Hub id and commit SHA (checked against PINS).
        reader / reader_revision: The lens, NLA or oracle-lens checkpoint, if any
            (checked against PINS when the repo is pinned).
        dataset: Bank or dataset name, e.g. ``wsbench/agentic_misalignment``.
        extra: Anything run-specific: layers, positions, sampling settings, seed,
            judge model, dtype.
    """

    model: str
    model_revision: str
    reader: str | None = None
    reader_revision: str | None = None
    dataset: str | None = None
    seed: int | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)
    git_sha: str = field(default_factory=git_sha)
    git_dirty: bool = field(default_factory=git_dirty)
    host: str = field(default_factory=platform.node)

    def __post_init__(self) -> None:
        for repo, rev in (
            (self.model, self.model_revision),
            (self.reader, self.reader_revision),
        ):
            if repo in PINS and rev != PINS[repo]:
                raise ValueError(
                    f"{repo} is pinned to {PINS[repo]} but this artefact records "
                    f"{rev}; update PINS deliberately or pass the pinned revision"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_artefact(
    path: str | os.PathLike[str], provenance: Provenance, payload: Mapping[str, Any]
) -> Path:
    """Write ``payload`` as JSON with ``provenance`` attached, atomically."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = {"provenance": provenance.to_dict(), "result": dict(payload)}
    tmp = destination.with_suffix(destination.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, destination)
    return destination
