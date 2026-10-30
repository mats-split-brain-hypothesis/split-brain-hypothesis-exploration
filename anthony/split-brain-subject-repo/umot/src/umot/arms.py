"""Named arms. An arm is a reader plus everything that changes its output (checkpoint,
injection, sampling, layers); its name is the directory its readouts are written to."""

from __future__ import annotations

from umot.provenance import PINS
from umot.readers import Sampling, VerbalizerSpec, strip_explanation

#: Token readers: bench method names, read at every captured layer (bench grid + 42).
TOKEN_ARMS = ("logit_lens", "jlens", "rlens")

OLENS_REPO = "ceselder/olens-rl-grpo-trajectory-qwen36-27b"
MODLENS_REPO = "ceselder/modulation-lens-meta-model-qwen36-27b"
NLA_REPO = "ceselder/qwen3.6-27b-nla-rl"

VERBALIZERS: dict[str, VerbalizerSpec] = {
    # The collection's oracle lens. Its nla_meta.yaml gives the prompt and marker but not the
    # injection mode; norm-matched add is the NLA-framework default (the skip-lens card calls
    # its injection "identical"). Unverified: check against `replace` before trusting it.
    "olens-s390": VerbalizerSpec(
        name="olens-s390",
        repo=OLENS_REPO,
        revision=PINS[OLENS_REPO],
        subfolder="step_00390",
        inject_mode="add_normmatched",
        sampling=Sampling(temperature=1.0, top_p=1.0, top_k=0, max_new_tokens=256),
    ),
    "olens-s390-replace": VerbalizerSpec(
        name="olens-s390-replace",
        repo=OLENS_REPO,
        revision=PINS[OLENS_REPO],
        subfolder="step_00390",
        inject_mode="replace",
        sampling=Sampling(temperature=1.0, top_p=1.0, top_k=0, max_new_tokens=256),
    ),
    # An early step of the same GRPO run: reward is already at its plateau (≈ 0.47-0.50 from step
    # 10) but the policy has had less time to drift (the run had no KL penalty). Same injection.
    "olens-s050": VerbalizerSpec(
        name="olens-s050",
        repo=OLENS_REPO,
        revision=PINS[OLENS_REPO],
        subfolder="step_00050",
        inject_mode="add_normmatched",
        sampling=Sampling(temperature=1.0, top_p=1.0, top_k=0, max_new_tokens=256),
    ),
    # Model card: replace at block-1 output; temperature 1, top_p 1, top_k 0, 16 tokens.
    "modlens": VerbalizerSpec(
        name="modlens",
        repo=MODLENS_REPO,
        revision=PINS[MODLENS_REPO],
        subfolder="",
        inject_mode="replace",
        sampling=Sampling(temperature=1.0, top_p=1.0, top_k=0, max_new_tokens=16),
    ),
    # The bench's `nla` arm, batched: separate av_base reader, norm-matched add, bench sampling.
    "nla-i400": VerbalizerSpec(
        name="nla-i400",
        repo=NLA_REPO,
        revision=PINS[NLA_REPO],
        subfolder="av_rl_adapters/iter_000400",
        base="av_base",
        meta_dir="av_base",
        inject_mode="add_normmatched",
        sampling=Sampling(temperature=1.0, top_p=0.95, top_k=64, max_new_tokens=256),
        postprocess=strip_explanation,
    ),
}
