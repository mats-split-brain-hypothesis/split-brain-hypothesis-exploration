"""S3: regression statistics for a lag-1 predictor of h_t from h_{t-1}, per layer, on a text corpus (pod).

  python experiments/s3_stats.py --corpus wikitext --device cuda

From the corpus context capture (``out/ctx/corpus-<name>.pt``), at each grid layer: X = h_{t-1}, Y = h_t over every
window position t >= SKIP (the first positions of a window carry the attention-sink regime), and saves the means and
the centred cross-products ``C = Xc^T Xc``, ``B = Xc^T Yc`` (float32, [d, d] each) to
``out/analysis/S3/arstats-<corpus>-L<layer>.pt``. ``jlm.mu.S3`` solves the ridge from them. No bank item is used.
"""

import argparse
import time

import torch

from jlm import OUT, context

SKIP = 16


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="wikitext")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    out = OUT / "analysis" / "S3"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    store = context.ContextStore(context.corpus_path(args.corpus))
    print(f"loaded {len(store.items)} windows ({time.time() - t0:.0f}s), layers {store.layers()}", flush=True)
    for L in store.layers():
        path = out / f"arstats-{args.corpus}-L{L:03d}.pt"
        if path.exists():
            continue
        S = torch.stack([store.states(i, L) for i in store.items])  # [n, T, d] bf16
        X = S[:, SKIP - 1 : -1].reshape(-1, S.shape[-1]).to(args.device, torch.float64)
        Y = S[:, SKIP:].reshape(-1, S.shape[-1]).to(args.device, torch.float64)
        mx, my = X.mean(0), Y.mean(0)
        X, Y = X - mx, Y - my
        stats = {"n": len(X), "mx": mx.float().cpu(), "my": my.float().cpu(), "C": (X.T @ X).float().cpu(),
                 "B": (X.T @ Y).float().cpu(), "skip": SKIP, "corpus": args.corpus}
        tmp = path.with_suffix(".tmp")
        torch.save(stats, tmp)
        tmp.replace(path)
        print(f"L{L}: n={len(X)} ({time.time() - t0:.0f}s)", flush=True)
        del S, X, Y, stats


if __name__ == "__main__":
    main()
