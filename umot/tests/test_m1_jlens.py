"""The memory-saving J-lens path must reproduce the bench's JLens.read exactly."""

import importlib.util
from types import SimpleNamespace

import torch
from transformers import AutoTokenizer
from wsbench.produce.methods import JLens

from umot.provenance import REPO_ROOT

spec = importlib.util.spec_from_file_location(
    "m1_run", REPO_ROOT / "experiments/m1_run.py"
)
m1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m1)


def test_lazy_stack_and_chunked_denominator_match_bench():
    torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-0.8B")
    V, d, n_layers = len(tok), 16, 4
    backend = SimpleNamespace(tokenizer=tok, device="cpu")
    w_u, jac = torch.randn(V, d), torch.randn(n_layers, d, d)
    h = torch.randn(d)

    ref = JLens()
    ref._b, ref._w_u, ref._jac = backend, w_u, jac
    ours = JLens()
    ours._b, ours._w_u = backend, w_u
    ours._jac = m1.LayerStack(jac, "cpu")
    ours._denom[2] = m1.jlens_denominator(w_u, ours._jac[2], chunk=1000)

    assert torch.allclose(ours._denom[2], (w_u @ jac[2]).norm(dim=1).clamp_min(1e-9))
    assert ref.read(h, 2) == ours.read(h, 2)
