"""LL0 gate diagnosis D1: does the gated-delta-rule kernel (flash-linear-attention vs transformers' reference PyTorch
path) change the J-lens estimator? jlens' own ``jacobian_for_prompt`` on the same prompts in two processes.

    python experiments/ll0_kernelcheck.py --mode fla      # fla importable (the sweep's setting)
    python experiments/ll0_kernelcheck.py --mode ref      # fla hidden: transformers falls back to its reference path
    python experiments/ll0_kernelcheck.py --compare       # cos per layer and prompt, and each vs n1000

Writes ``/root/ll0-ckpt/kc-<mode>.pt`` (container disk) and ``out/analysis/LL0/kernelcheck.json``.
"""

import argparse
import json
import sys
from pathlib import Path

LAYERS = [24, 40, 56]
PROMPTS = [0, 1]
CK = Path("/root/ll0-ckpt")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["fla", "ref"])
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--dim-batch", type=int, default=4)
    a = ap.parse_args()
    if a.mode == "ref":
        sys.modules["fla"] = None  # import fla -> ImportError: transformers uses its reference kernels
    import torch

    sys.path.insert(0, str(Path(__file__).parent))
    from ll0_sweep import ROOT, load_model, wiki

    if a.compare:
        from jlm.lens import load_maps

        n = load_maps("jlens", LAYERS)
        f, r = torch.load(CK / "kc-fla.pt"), torch.load(CK / "kc-ref.pt")

        def cos(x, y):
            x, y = x.flatten().double(), y.flatten().double()
            return round(float(x @ y / (x.norm() * y.norm())), 5)

        out = {}
        for L in LAYERS:
            out[L] = {"fla~ref": [cos(f[i][L], r[i][L]) for i in PROMPTS],
                      "fla~n1000": [cos(f[i][L], n[L]) for i in PROMPTS], "ref~n1000": [cos(r[i][L], n[L]) for i in PROMPTS],
                      "norm fla/ref": [round(float(f[i][L].norm() / r[i][L].norm()), 4) for i in PROMPTS]}
            print(L, out[L], flush=True)
        (ROOT / "kernelcheck.json").write_text(json.dumps(out, indent=1))
        return
    from jlens.fitting import jacobian_for_prompt

    model = load_model()
    prompts = wiki(400)
    res = {}
    for i in PROMPTS:
        J, S, P = jacobian_for_prompt(model, prompts[i], LAYERS, dim_batch=a.dim_batch, max_seq_len=128)
        res[i] = J
        print(a.mode, "prompt", i, "seq", S, "kept", P, flush=True)
    torch.save(res, CK / f"kc-{a.mode}.pt")
    print("KC_DONE", a.mode, flush=True)


if __name__ == "__main__":
    main()
