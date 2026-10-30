"""The white-bear direction and the steering vectors (paper §3.1-3.2)."""

from collections.abc import Callable, Iterable

import torch


def white_bear_direction(capture: Callable[[dict], dict], layers: Iterable[int],
                         pairs: list[tuple[dict, dict]]) -> dict[int, torch.Tensor]:
    """``u_l = d_l / ||d_l||`` with ``d_l = mean_think(h_l) - mean_dont(h_l)`` over the carrier tokens.

    ``capture(spec)`` returns ``{"mean": {layer: tensor[d_model]}}``, the residual mean over the assistant
    (carrier) tokens of the prompts in ``spec``; per-prompt means are averaged per condition.
    """
    layers = list(layers)
    spec = lambda prompts: {"layers": layers, "prompts": prompts, "positions": "assistant"}
    think = capture(spec([t for t, _ in pairs]))["mean"]
    dont = capture(spec([d for _, d in pairs]))["mean"]
    u = {}
    for L in layers:
        d = think[L].float() - dont[L].float()
        u[L] = d / d.norm()
    return u


def steering_vectors(u: dict[int, torch.Tensor], dose: float,
                     step: float | dict[int, float]) -> dict[int, torch.Tensor]:
    """``k * s_l * u_l`` per layer: ``dose`` is k, ``step`` the per-layer step s_l (a number or ``{layer: s_l}``).

    The paper's best dose on Qwen3.6-27B is k = 6 at layers 40-48, added at every prompt position up to and
    including the read position.
    """
    return {L: dose * (step[L] if isinstance(step, dict) else step) * v for L, v in u.items()}
