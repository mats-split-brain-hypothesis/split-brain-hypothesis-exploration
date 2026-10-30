"""Programme LL, phases 2-3 screen on the pod: expert maps x anchors on the dev banks, strict pass@10 (plan.md §3).

    python experiments/ll2_screen.py --split fit [--families a,b] [--routers w8,o8,r8] --device cuda

Reads ``out/analysis/LL0/experts/experts-L*.pt`` (ll0_sweep.py merge). Two tables, both with the bench's ``cos``
readout ``(W_U J x)_t / ||J^T W_U[t]||`` (each map with its own denominator) and the bench's strict rule
(``evaluate.py``'s scorers; the piece proxy on the ``_mt`` families):

1. **Single experts, per layer (LL2: H1, H2).** For router R, expert i at layer L, map ``J_i`` read on every cell of
   the bank, with anchor g in {0, glob (pooled mean of the sweep), own (mu_i), other (mu_sigma(i), sigma a fixed
   derangement: the pairing control), fam (fam@self), knn (knnx8@self)}. Score: pass@10 at that layer alone.
2. **Combined maps, any layer (LL3: H4, H6).** The slope x intercept grid per router: slope in {n1000 (released J-lens),
   pool (our w1), routed (``J_c(h)``, c the router's own cluster of h)}, intercept in {0, glob, local (``mu_c(h)``),
   fam, knn}; plus J++ released with {0, glob, fam, knn}. Score: the item rule (any cell, any layer).
Writes ``out/analysis/LL2/<split>/{single,grid}.json`` (pass rates and per-item passes for paired bootstraps).
"""

import argparse
import json
import time
from pathlib import Path

import torch

from jlm import OUT, banks, capture, centres, mtproxy, score
from jlm.centres import Batch, apply, cell_refs
from jlm.judge import MULTI_TOKEN
from jlm.lens import Lens, load_maps
from jlm.mu.LL0 import Router

LAYERS = [24, 32, 40, 48, 56]
EXPERTS = Path("/root/ll0-ckpt/experts")  # merged on the sweep pod's container disk (ll0_sweep.py merge)
FAMILIES = banks.dev_families()
ROWS = 512


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Maps:
    """Maps on the device with their cos denominators ``||J^T W_U[t]||``, built on demand and kept."""

    def __init__(self, lens: Lens) -> None:
        self.lens, self.cache = lens, {}

    def get(self, key, J: torch.Tensor):
        if key not in self.cache:
            J = J.to(self.lens.device, torch.float32)
            w = self.lens.w_u
            den = torch.cat([(w[i : i + 32768] @ J).norm(dim=1) for i in range(0, len(w), 32768)]).clamp_min(1e-9)
            self.cache[key] = (J, den)
        return self.cache[key]


def top10(lens: Lens, X: torch.Tensor, J: torch.Tensor, den: torch.Tensor) -> torch.Tensor:
    """[n, 10] top token ids of the cos readout of states X [n, d] through J."""
    out = []
    for a in range(0, len(X), ROWS):
        z = X[a : a + ROWS].to(lens.device, torch.float32) @ J.T
        out.append(((z @ lens.w_u.T) / den).topk(10, dim=1).indices.cpu())
    return torch.cat(out) if out else torch.zeros(0, 10, dtype=torch.long)


def top10_rowwise(lens: Lens, X: torch.Tensor, Js: list, assign: torch.Tensor) -> torch.Tensor:
    """Routed readout: cell j read through map ``Js[assign[j]]`` (each (J, den))."""
    out = torch.zeros(len(X), 10, dtype=torch.long)
    for e, (J, den) in enumerate(Js):
        idx = (assign == e).nonzero(as_tuple=True)[0]
        if len(idx):
            out[idx] = top10(lens, X[idx], J, den)
    return out


class Bank:
    """One dev bank: cells per layer, the official anchors fam / knnx8 (@self), and its strict scorer."""

    def __init__(self, family: str, split: str, lens: Lens, vocab: list[str]) -> None:
        from evaluate import scorers  # experiments/ is on sys.path when run as a script

        self.family, self.bank = family, banks.load(family, split)
        self.items = capture.load(self.bank)
        self.by_id = {it.id: it for it in self.items}
        groups = {it["id"]: it.get("pair_id") or it["id"] for it in self.bank.items}
        self.layers = [L for L in LAYERS if any(L in it.acts for it in self.items)]
        if family in MULTI_TOKEN:
            units = mtproxy.units_of(self.bank, lens.tokenizer, lens.display)
            self.ids = [i for i, ok in mtproxy.reachable(units).items() if ok]
            self.strict = lambda rows: mtproxy.item_passes(rows, units)
            self.accepted = {i: sorted({t for u in us if u.required for t in u.ids}) for i, us in units.items()}
        else:
            sc, _ = scorers(self.bank, vocab, {it.id: lens.display(it.ids) for it in self.items})
            self.ids = [i for i, why in sc.conf.items() if not why]
            self.strict = lambda rows: score.strict_items(rows, self.bank)
            self.accepted = sc.accepted
        self.idset = set(self.ids)
        self.cells, self.H, self.g = {}, {}, {"fam": {}, "knn": {}}
        cs = {}
        for name, key in (("fam", "fam"), ("knn", "knnx8")):
            c = centres.make(key)
            c.fit(self.items, family, groups)
            cs[name] = c
        for L in self.layers:
            cells = cell_refs([it for it in self.items if L in it.acts], family, L, groups)
            H = torch.stack([self.by_id[c.item].acts[L][c.i].float() for c in cells])
            self.cells[L], self.H[L] = cells, H
            for name, c in cs.items():
                self.g[name][L] = H - apply(c, Batch(L, cells, H, self.by_id, None))

    def passes(self, lens: Lens, tops: dict[int, torch.Tensor]) -> dict[str, bool]:
        """Item passes under top-10 ids per layer (the item rule over the layers given)."""
        rows = []
        for L, T in tops.items():
            names = lens.display(T.flatten().tolist())
            for j, c in enumerate(self.cells[L]):
                rows.append({"id": c.item, "layer": L, "pos": c.pos, "tokens": names[j * 10 : (j + 1) * 10]})
        return self.strict(rows)

    def rate(self, p: dict[str, bool]) -> float:
        return sum(p[i] for i in self.ids) / max(1, len(self.ids))


def derangement(k: int) -> list[int]:
    return [(i + 1) % k for i in range(k)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="fit")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--routers", default="w8,o8,r8")
    ap.add_argument("--grid-routers", default="w8,w16,o8,r8")
    ap.add_argument("--skip-single", action="store_true")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--experts", default=str(EXPERTS))
    ap.add_argument("--layers", default=",".join(map(str, LAYERS)))
    ap.add_argument("--fake", action="store_true", help="smoke test: stand-in experts (n1000 copies)")
    ap.add_argument("--tag", default="", help="output subdirectory suffix")
    a = ap.parse_args()
    LAYERS[:] = [int(x) for x in a.layers.split(",")]
    root = OUT / "analysis" / "LL2" / (a.split + a.tag)
    root.mkdir(parents=True, exist_ok=True)
    lens = Lens(LAYERS, a.device)
    jpp = load_maps("jpp", LAYERS)
    vocab = lens.display(list(range(lens.vocab)))
    maps = Maps(lens)
    if a.fake:  # smoke test of the code paths: every expert is the n1000 map, anchors are wiki states
        rs = torch.load(OUT / "analysis" / "LL0" / "routers.pt", weights_only=False)
        routers = {s["name"]: Router.from_state(s) for s in rs["routers"]}
        ex = {}
        for L in LAYERS:
            w = torch.load(OUT / "analysis" / "LL0" / f"wiki-acts-L{L:03d}.pt").float()
            ex[L] = {R: {"J": lens.jac[L].half()[None].expand(r.k, -1, -1), "mu": w[: r.k], "count": torch.ones(r.k)}
                     for R, r in routers.items()}
    else:
        ex = {L: torch.load(Path(a.experts) / f"experts-L{L:03d}.pt", weights_only=False) for L in LAYERS}
        meta = torch.load(Path(a.experts) / "meta.pt", weights_only=False)
        routers = {s["name"]: Router.from_state(s) for s in meta["routers"]}
    single, grid = {}, {}
    for fam in a.families.split(","):
        t0 = time.time()
        b = Bank(fam, a.split, lens, vocab)
        log(fam, a.split, "cells", {L: len(b.cells[L]) for L in b.layers}, "scored items", len(b.ids))
        glob = {L: ex[L]["w1"]["mu"][0] for L in b.layers}
        # ---- 1. single experts, per layer ----
        if not a.skip_single:
            for R in a.routers.split(","):
                for L in b.layers:
                    E = ex[L][R]
                    k = len(E["count"])
                    sig = derangement(k)
                    for i in range(k):
                        J, den = maps.get((R, L, i), E["J"][i])
                        H = b.H[L]
                        anchors = {"0": torch.zeros_like(H[0]), "glob": glob[L], "own": E["mu"][i], "other": E["mu"][sig[i]],
                                   "fam": b.g["fam"][L], "knn": b.g["knn"][L]}
                        for an, g in anchors.items():
                            p = b.passes(lens, {L: top10(lens, H - g, J, den)})
                            single.setdefault(fam, {})[f"{R}|L{L}|e{i}|{an}"] = {"rate": b.rate(p), "n": int(E["count"][i])}
                    maps.cache = {kk: v for kk, v in maps.cache.items() if kk[0] != R}  # free GPU memory per router
            log(fam, "single done", f"{time.time() - t0:.0f}s")
        # ---- 2. combined maps, any layer ----
        G = grid.setdefault(fam, {})

        def add(name, tops):
            p = b.passes(lens, tops)
            G[name] = {"rate": b.rate(p), "items": {i: p[i] for i in b.ids}}

        for slope in ("n1000", "pool", "jpp"):
            for an in ("0", "glob", "fam", "knn"):
                tops = {}
                for L in b.layers:
                    Jsrc = lens.jac[L] if slope == "n1000" else ex[L]["w1"]["J"][0] if slope == "pool" else jpp[L]
                    J, den = maps.get((slope, L), Jsrc)
                    g = 0 if an == "0" else glob[L] if an == "glob" else b.g[an][L]
                    tops[L] = top10(lens, b.H[L] - g, J, den)
                add(f"{slope}|{an}", tops)
        for R in a.grid_routers.split(","):
            r = routers[R]
            for slope in ("n1000", "pool", "routed"):
                for an in ("0", "glob", "local", "fam", "knn"):
                    if slope != "routed" and an in ("0", "glob", "fam", "knn"):
                        continue  # the unrouted rows are above
                    tops = {}
                    for L in b.layers:
                        E = ex[L][R]
                        H = b.H[L]
                        c = r.assign(H, L, 0)  # read time: route by the cell's own state (no parity split)
                        c = c % r.k
                        mu = E["mu"][c] if an == "local" else glob[L] if an == "glob" else b.g[an][L] if an in ("fam", "knn") else 0
                        X = H - mu
                        if slope == "routed":
                            Js = [maps.get((R, L, e), E["J"][e]) for e in range(r.k)]
                            tops[L] = top10_rowwise(lens, X, Js, c)
                        else:
                            J, den = maps.get((slope, L), lens.jac[L] if slope == "n1000" else ex[L]["w1"]["J"][0])
                            tops[L] = top10(lens, X, J, den)
                    add(f"{R}:{slope}|{an}", tops)
            maps.cache = {kk: v for kk, v in maps.cache.items() if kk[0] != R}
        log(fam, "grid", {k: round(v["rate"], 3) for k, v in G.items()}, f"{time.time() - t0:.0f}s")
        (root / "single.json").write_text(json.dumps(single))
        (root / "grid.json").write_text(json.dumps(grid))
    log("SCREEN_DONE")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    main()
