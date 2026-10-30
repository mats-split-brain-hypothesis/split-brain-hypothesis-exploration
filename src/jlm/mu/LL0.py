"""Programme LL, phase 0: expert Jacobians and their anchors from one backward sweep, many clusterings.

The J-lens estimator (``jlens.fitting.jacobian_for_prompt``): one forward on the prompt replicated ``B`` times, then
``d / B`` backward passes, each with a one-hot cotangent at output dim ``r`` at every kept position. The gradient at
source position ``p`` is row ``r`` of ``G_p = sum_{kept p' >= p} dh_final[p'] / dh_l[p]``. The J-lens averages
``G_p`` over positions; here each position is routed to a bin of several clusterings at once and ``G_p`` is summed
per bin, together with the bin's count and ``sum h`` (so the anchor ``mu_i`` is exactly the mean of the positions
behind ``J_i``). Expert ``J_i = sum G_p / count``, anchor ``mu_i = sum h / count`` (local-linearisation/plan.md, LL0).

Routers (per layer) follow J++'s recipe (``workspace_lens.routing``): unit-normalise, centre, project to the top
``proj`` PCs, k-means (k-means++, seed 0), nearest centroid. A ``split`` router doubles its bins by prompt parity
(bin ``e + E * (prompt % 2)``), giving split halves for noise estimates; the halves sum to the full expert.
A ``random`` router draws each position's bin from fixed proportions (the size-matched control).
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import torch

_POOL = ThreadPoolExecutor(2)  # host-side row adds (they release the GIL)
SKIP_FIRST = 16  # jlens / J++: early positions are attention sinks
MAX_SEQ_LEN = 128


# ---- routers (J++'s routing.cluster, reimplemented) ----

def unit_normalize(x: torch.Tensor) -> torch.Tensor:
    return x / x.norm(dim=-1, keepdim=True)


def fit_pca(x: torch.Tensor, dim: int) -> tuple[torch.Tensor, torch.Tensor]:
    mean = x.mean(0)
    xc = x - mean
    cov = (xc.T @ xc) / max(len(x) - 1, 1)
    _, vec = torch.linalg.eigh(cov)
    return mean, vec[:, -dim:].flip(dims=[1])


def kmeans(x: torch.Tensor, k: int, seed: int = 0, iters: int = 100, tol: float = 1e-6) -> tuple[torch.Tensor, torch.Tensor]:
    g = torch.Generator(device=x.device).manual_seed(seed)
    cent = [x[int(torch.randint(len(x), (1,), generator=g, device=x.device))]]
    for _ in range(k - 1):
        d2 = torch.cdist(x, torch.stack(cent)).pow(2).min(1).values
        cent.append(x[int(torch.multinomial(d2.clamp(min=1e-12), 1, generator=g))])
    C = torch.stack(cent)
    for _ in range(iters):
        dist = torch.cdist(x, C)
        a = dist.argmin(1)
        new = torch.stack([x[a == i].mean(0) if (a == i).any() else x[int(dist.gather(1, a[:, None]).argmax())]
                           for i in range(k)])
        shift = (new - C).norm(dim=1).max()
        C = new
        if shift < tol:
            break
    return C, torch.cdist(x, C).argmin(1)


@dataclass
class Router:
    """One clustering at every layer. ``kind``: ``kmeans`` (``params[L] = (mean, comp, cent)``) or ``random``
    (``probs[L]``: bin proportions per layer); ``split``: bins doubled by prompt parity."""

    name: str
    k: int
    kind: str = "kmeans"
    split: bool = False
    params: dict = field(default_factory=dict)
    probs: dict = field(default_factory=dict)
    seed: int = 0

    @property
    def bins(self) -> int:
        return self.k * (2 if self.split else 1)

    @classmethod
    def fit(cls, name: str, k: int, acts: dict[int, torch.Tensor], proj: int = 64, seed: int = 0, split: bool = False) -> "Router":
        r = cls(name, k, split=split, seed=seed)
        for L, x in acts.items():
            if k == 1:
                r.params[L] = None
                continue
            u = unit_normalize(x.float())
            mean, comp = fit_pca(u, proj)
            cent, _ = kmeans((u - mean) @ comp, k, seed)
            r.params[L] = (mean, comp, cent)
        return r

    def assign(self, h: torch.Tensor, layer: int, prompt_idx: int) -> torch.Tensor:
        """[P] bin index of states ``h`` [P, d] read from prompt ``prompt_idx`` at ``layer``."""
        if self.kind == "random":
            g = torch.Generator().manual_seed(self.seed * 1_000_003 + prompt_idx * 1009 + layer)
            a = torch.multinomial(self.probs[layer], len(h), replacement=True, generator=g).to(h.device)
        elif self.k == 1:
            a = torch.zeros(len(h), dtype=torch.long, device=h.device)
        else:
            mean, comp, cent = (t.to(h.device) for t in self.params[layer])
            a = torch.cdist((unit_normalize(h.float()) - mean) @ comp, cent).argmin(1)
        return a + self.k * (prompt_idx % 2) if self.split else a

    def state(self) -> dict:
        return {"name": self.name, "k": self.k, "kind": self.kind, "split": self.split, "seed": self.seed,
                "params": {L: None if p is None else tuple(t.cpu() for t in p) for L, p in self.params.items()},
                "probs": {L: p.cpu() for L, p in self.probs.items()}}

    @classmethod
    def from_state(cls, s: dict) -> "Router":
        return cls(**s)


# ---- the accumulator ----

class Accumulator:
    """Per layer: ``J[e]`` sums [E, d, d] fp32 (CPU), counts [E], ``sum h`` [E, d] fp64, over the bins of every
    router laid end to end (``offsets[name]`` is a router's first bin)."""

    def __init__(self, routers: list[Router], layers: list[int], d: int) -> None:
        self.routers, self.layers, self.d = routers, sorted(layers), d
        self.offsets, n = {}, 0
        for r in routers:
            self.offsets[r.name] = n
            n += r.bins
        self.E = n
        self.J = {L: torch.zeros(n, d, d, dtype=torch.float32) for L in self.layers}
        self.count = {L: torch.zeros(n, dtype=torch.long) for L in self.layers}
        self.hsum = {L: torch.zeros(n, d, dtype=torch.float64) for L in self.layers}
        self.prompts: list[int] = []

    def membership(self, h: torch.Tensor, layer: int, prompt_idx: int) -> torch.Tensor:
        """[E, P] 0/1 membership of every router's bins, and the counts / ``sum h`` side effects."""
        M = torch.zeros(self.E, len(h), device=h.device)
        cols = torch.arange(len(h), device=h.device)
        for r in self.routers:
            M[self.offsets[r.name] + r.assign(h, layer, prompt_idx), cols] = 1.0
        self.count[layer] += M.sum(1).long().cpu()
        self.hsum[layer] += (M.double() @ h.double()).cpu()
        return M

    def add_rows(self, layer: int, M: torch.Tensor, grad_rows: torch.Tensor, row0: int) -> None:
        """``grad_rows`` [b, P, d]: rows ``row0 .. row0 + b`` of each kept position's ``G_p``."""
        S = torch.einsum("ep,bpn->ebn", M, grad_rows.float())
        self.J[layer][:, row0 : row0 + grad_rows.shape[0], :] += S.cpu()

    def expert(self, name: str, layer: int, merge_split: bool = True) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """(J [k, d, d], mu [k, d], count [k]) of router ``name`` at ``layer`` (split halves summed)."""
        r = next(r for r in self.routers if r.name == name)
        sl = slice(self.offsets[name], self.offsets[name] + r.bins)
        J, c, hs = self.J[layer][sl], self.count[layer][sl], self.hsum[layer][sl]
        if r.split and merge_split:
            J, c, hs = J[: r.k] + J[r.k :], c[: r.k] + c[r.k :], hs[: r.k] + hs[r.k :]
        n = c.clamp_min(1)
        return J / n[:, None, None].float(), (hs / n[:, None]).float(), c

    def state(self) -> dict:
        return {"routers": [r.state() for r in self.routers], "layers": self.layers, "d": self.d,
                "count": self.count, "hsum": self.hsum, "prompts": self.prompts}


def sweep_prompt(model, acc: Accumulator, prompt: str, prompt_idx: int, batch: int = 8, timer: dict | None = None,
                 chunk_rows: int = 128) -> int:
    """One prompt of the sweep into ``acc``: jlens' estimator, rows binned. Returns the kept-position count."""
    import time

    from jlens.hooks import ActivationRecorder

    t0 = time.perf_counter()
    ids = model.encode(prompt, max_length=MAX_SEQ_LEN)
    S = ids.shape[1]
    if S <= SKIP_FIRST + 1:
        return 0
    pos = torch.arange(SKIP_FIRST, S - 1, device=ids.device)  # jlens.fitting.valid_position_mask
    target = model.n_layers - 1
    with ActivationRecorder(model.layers, at=[*acc.layers, target], start_graph_at=min(acc.layers)) as rec, torch.enable_grad():
        model.forward(ids.expand(batch, -1))
        tgt = rec.activations[target]
        src = [rec.activations[L] for L in acc.layers]
    Ms = {}
    for L, a in zip(acc.layers, src):
        Ms[L] = acc.membership(a[0, pos.to(a.device)].detach().float(), L, prompt_idx)
    t1 = time.perf_counter()
    d = acc.d
    n_pass = math.ceil(d / batch)
    bidx = torch.arange(batch, device=tgt.device)
    cot = torch.zeros_like(tgt)
    tpos = pos.to(tgt.device)
    t_acc = 0.0
    # rows are binned on the GPU into a buffer of ``chunk`` rows per layer and flushed to the host accumulator in one
    # copy per chunk (a host sync per pass and layer cost ~20 s per prompt, 2026-10-12 timing)
    chunk = max(batch, (chunk_rows // batch) * batch)
    buf = {L: torch.zeros(acc.E, chunk, d, device=src[i].device) for i, L in enumerate(acc.layers)}
    Mg = {L: Ms[L].to(src[i].device) for i, L in enumerate(acc.layers)}
    b0 = 0  # first row held in the buffers
    pending = []
    for k, r0 in enumerate(range(0, d, batch)):
        nb = min(batch, d - r0)
        cot.zero_()
        cot[bidx[:nb, None], tpos[None, :], r0 + bidx[:nb, None]] = 1.0
        grads = torch.autograd.grad(tgt, src, grad_outputs=cot, retain_graph=k < n_pass - 1)
        ta = time.perf_counter()
        for L, g in zip(acc.layers, grads):
            buf[L][:, r0 - b0 : r0 - b0 + nb] = torch.einsum("ep,bpn->ebn", Mg[L], g[:nb, pos.to(g.device)].float())
        del grads
        if r0 + nb - b0 == chunk or r0 + nb == d:
            for L in acc.layers:  # copy now (the buffer is reused), add on the host thread while the GPU goes on
                rows = buf[L][:, : r0 + nb - b0].cpu()
                pending.append(_POOL.submit(acc.J[L][:, b0 : r0 + nb, :].add_, rows))
            b0 = r0 + nb
        t_acc += time.perf_counter() - ta
    for f in pending:
        f.result()
    acc.prompts.append(prompt_idx)
    if timer is not None:
        timer.update(forward=t1 - t0, backward=time.perf_counter() - t1 - t_acc, accumulate=t_acc)
    return len(pos)
