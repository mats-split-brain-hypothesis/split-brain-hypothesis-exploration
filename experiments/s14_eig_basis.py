"""S14e: the readout map's own top reading directions as the removed subspace (no token list at all).

``A_l = J^T W_U^T D^{-1} P D^{-1} W_U J`` (the cos map's gram with the constant-score direction projected out; cached as
``pb-eig`` by ``precompute_pullback.py``) has as its top eigenvectors the input directions along which the lens's token
scores vary most over the whole vocabulary. This writes their top-k spans as a token-set basis named ``eig``
(``out/lens/tbasis-<key>-<readout>-eig-k<k>-L.pt``), read as ``s14:eig:<k>[:fam]``. Cached eigendecompositions only,
one layer at a time (100 MB each): fine on the Mac.

  python experiments/s14_eig_basis.py [--ks 16,64,128] [--readout cos]
"""

import argparse

import torch

from jlm import pullback

LAYERS = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ks", default="16,64,128")
    ap.add_argument("--readout", default="cos")
    args = ap.parse_args()
    key = pullback.default_key()
    for L in LAYERS:
        obj = torch.load(pullback.CACHE / f"pb-eig-{key}-{args.readout}-L{L:03d}.pt")
        lam, Q = obj["evals"], obj["evecs"]
        for k in (int(k) for k in args.ks.split(",")):
            torch.save(Q[:, :k].contiguous().clone(), pullback.tbasis_path(key, args.readout, "eig", k, L))
        top = lam[:128].sum() / lam.sum()
        print(f"L{L}: top-16 / 64 / 128 eigen-energy {lam[:16].sum() / lam.sum():.3f} / {lam[:64].sum() / lam.sum():.3f} / {top:.3f}")


if __name__ == "__main__":
    main()
