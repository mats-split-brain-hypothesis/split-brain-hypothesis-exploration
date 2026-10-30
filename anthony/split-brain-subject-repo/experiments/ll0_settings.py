"""LL0 gate diagnosis D3: which fit setting moves our pooled J toward the released n1000 lens? jlens' own
``jacobian_for_prompt`` on the same prompts under several settings; each setting's mean J is compared with n1000
per layer (paired: the same prompts, so prompt sampling cancels between settings).

    python experiments/ll0_settings.py --prompts 8 --settings 16:128,0:128,16:256

Writes ``out/analysis/LL0/settings.json``.
"""

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from ll0_sweep import ROOT, load_model, wiki  # noqa: E402

from jlm.lens import load_maps  # noqa: E402

LAYERS = [24, 32, 40, 48, 56]


def cos(x, y):
    x, y = x.flatten().double(), y.flatten().double()
    return round(float(x @ y / (x.norm() * y.norm())), 5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=int, default=8)
    ap.add_argument("--settings", default="16:128,0:128,16:256", help="skip_first:max_seq_len,...")
    ap.add_argument("--dim-batch", type=int, default=16)
    a = ap.parse_args()
    from jlens.fitting import jacobian_for_prompt

    n = load_maps("jlens", LAYERS)
    model = load_model()
    prompts = wiki(400)[: a.prompts]
    path = ROOT / "settings.json"
    out = json.loads(path.read_text()) if path.exists() else {}
    for st in a.settings.split(","):
        skip, seq = map(int, st.split(":"))
        acc = {L: torch.zeros(5120, 5120) for L in LAYERS}
        for p in prompts:
            J, S, P = jacobian_for_prompt(model, p, LAYERS, dim_batch=a.dim_batch, max_seq_len=seq, skip_first=skip)
            for L in LAYERS:
                acc[L] += J[L]
            print(st, "seq", S, "kept", P, flush=True)
        out[st] = {L: {"cos_n1000": cos(acc[L], n[L]), "norm_ratio": round(float(acc[L].norm() / len(prompts) / n[L].norm()), 4)}
                   for L in LAYERS}
        torch.save({L: acc[L] / len(prompts) for L in LAYERS}, Path("/root/ll0-ckpt") / f"settings-{skip}-{seq}.pt")
        print("SETTING", st, out[st], flush=True)
        path.write_text(json.dumps(out, indent=1))
    print("SETTINGS_DONE", flush=True)


if __name__ == "__main__":
    main()
