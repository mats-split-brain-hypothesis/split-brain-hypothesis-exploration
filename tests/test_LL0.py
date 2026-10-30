"""Programme LL phase 0: the binned sweep reproduces jlens' estimator, and bins add up to the pooled Jacobian."""

import torch
from torch import nn

from jlm.mu.LL0 import Accumulator, Router, sweep_prompt


class Block(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.a, self.b = nn.Linear(d, d), nn.Linear(d, d)

    def forward(self, x):
        # causal mixing so later targets depend on earlier sources, as in a transformer
        mix = torch.cumsum(x, dim=1) / torch.arange(1, x.shape[1] + 1, device=x.device)[None, :, None]
        return x + torch.tanh(self.a(x / (x.norm(dim=-1, keepdim=True) + 1e-3))) + 0.1 * self.b(mix)


class Toy:
    """A LensModel stand-in: n_layers blocks of width d over a fixed embedding."""

    def __init__(self, d=12, n_layers=5, vocab=50, seed=0):
        torch.manual_seed(seed)
        self.d_model, self.n_layers = d, n_layers
        self.layers = nn.ModuleList(Block(d) for _ in range(n_layers))
        self.emb = nn.Embedding(vocab, d)
        for p in [*self.layers.parameters(), *self.emb.parameters()]:
            p.requires_grad_(False)

    def encode(self, text, max_length=128):
        return torch.tensor([[ord(c) % 50 for c in text[:max_length]]])

    def forward(self, ids):
        x = self.emb(ids)
        for blk in self.layers:
            x = blk(x)
        return x


def test_k1_matches_jlens_and_bins_add_up():
    from jlens.fitting import jacobian_for_prompt

    m = Toy()
    layers = [1, 3]
    prompts = ["the quick brown fox jumps over the lazy dog again", "a second prompt of reasonable length here!!"]
    acts = {L: torch.randn(200, m.d_model) for L in layers}
    w1 = Router.fit("w1", 1, acts, split=True)
    w3 = Router.fit("w3", 3, acts, proj=4)
    r2 = Router("r2", 2, kind="random", probs={L: torch.tensor([0.3, 0.7]) for L in layers})
    acc = Accumulator([w1, w3, r2], layers, m.d_model)
    want = {L: 0 for L in layers}
    for i, p in enumerate(prompts):
        P = sweep_prompt(m, acc, p, i, batch=5, chunk_rows=7)
        J, _, _ = jacobian_for_prompt(m, p, layers, dim_batch=5)
        for L in layers:
            want[L] = want[L] + J[L] * P  # jlens: per-prompt mean over P positions
        assert P == len(p) - 17
    n = sum(len(p) - 17 for p in prompts)
    for L in layers:
        J1, mu1, c1 = acc.expert("w1", L)
        assert c1.tolist() == [n]
        assert torch.allclose(J1[0], want[L] / n, atol=1e-5)
        Jh, _, ch = acc.expert("w1", L, merge_split=False)
        assert ch.tolist() == [len(prompts[0]) - 17, len(prompts[1]) - 17]
        for name in ("w3", "r2"):
            J, mu, c = acc.expert(name, L)
            assert int(c.sum()) == n
            pooled = (J * c[:, None, None]).sum(0) / n
            assert torch.allclose(pooled, J1[0], atol=1e-5)
            assert torch.allclose((mu * c[:, None]).sum(0) / n, mu1[0], atol=1e-5)
