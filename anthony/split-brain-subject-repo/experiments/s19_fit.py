"""S19: fit the learned g ``U V^T h + b`` per layer with the controls as the loss (src/jlm/mu/S19.py; card S19).

  python experiments/s19_fit.py --name s19r16 --rank 16 --device cuda
  python experiments/s19_fit.py --name s19b --rank 0 --device cuda
  python experiments/s19_fit.py --name s19r16sh --rank 16 --shuffle-prompt --device cuda   # control
  python experiments/s19_fit.py --name s19r16p --rank 16 --terms prompt --device cuda       # one loss term

Training set: the read cells of every family's ``fit`` bank (``clusters.FAMILIES``). Per cell a token set S: (i) its
item's prompt-content ids (``controls.prompt_forms`` / ``mask_ids``: template forms shared by half the bank's renders
are left out, so this is the item's own content) and (ii) the model's own next-token top 10 at the cell (layer 63 of
the context capture through the final norm and ``W_U``). Loss, per cell, under the cos readout of ``h - g``:
``mean_{t in S} softplus((s_t - c_10) / tau)``, ``c_10`` the 10th best score outside S (so: keep S out of the top 10),
plus ``lam * mean ||g||^2 / mean ||h||^2``. **No targets.** ``--shuffle-prompt`` gives every item another item's prompt
set (a derangement within the family): the control for "the gain is the constant, not the cell-specific part".

Each layer is fitted ``K + 1`` times: once on every fit group (read on val / bench) and once per fold of a K-fold split
by group (a fit cell is read with the model that never saw its group). Mini-batches over cells, full vocabulary,
bf16 autocast. Writes ``out/priors/S19/<name>.pt`` and ``<name>.json`` (losses, ||g|| / ||h||, decoded L(b)).
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jlm import banks, capture, context, controls
from jlm.lens import Lens
from jlm.mu import S19, clusters

GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def build(lens: Lens, vocab: list[str], layers: list[int], shuffle: bool, seed: int, families: list[str]):
    """Rows of the pooled fit cells: states per layer, the (family/group) key, prompt ids, next-token top-10 ids."""
    H = {L: [] for L in layers}
    keys, prompt, nxt = [], [], []
    rng = random.Random(seed)
    for f in families:
        bank = banks.load(f, "fit")
        items = capture.load(bank)
        groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
        forms = controls.prompt_forms({it.id: lens.display(it.ids) for it in items})
        pids = controls.mask_ids(forms, vocab)
        if shuffle:  # every item gets another item's prompt set (one random cycle)
            order = [it.id for it in items]
            perm = order[:]
            rng.shuffle(perm)
            pids = {a: pids[perm[(perm.index(a) + 1) % len(perm)]] for a in order}
        ctx = context.ContextStore.of(bank)
        cells = [(it, i) for it in items for i in range(len(it.positions))]
        fin = torch.stack([ctx.at(it.id, context.FINAL_LAYER, i).float() for it, i in cells])
        top = torch.cat([lens.logits(fin[a : a + 256]).topk(10, dim=1).indices.cpu() for a in range(0, len(fin), 256)])
        for j, (it, i) in enumerate(cells):
            keys.append(f"{f}/{groups[it.id]}")
            prompt.append(pids[it.id])
            nxt.append(top[j].tolist())
            for L in layers:
                H[L].append(it.acts[L][i].float())
        print(f"  {f}: {len(cells)} cells, prompt set {sum(len(pids[it.id]) for it, _ in cells) / len(cells):.1f} ids/cell", flush=True)
    return {L: torch.stack(v) for L, v in H.items()}, keys, prompt, nxt


def sets_mask(rows: list[int], prompt, nxt, terms: set[str], V: int, device: str) -> torch.Tensor:
    m = torch.zeros(len(rows), V, dtype=torch.bool, device=device)
    for j, r in enumerate(rows):
        ids = (prompt[r] if "prompt" in terms else []) + (nxt[r] if "next" in terms else [])
        if ids:
            m[j, ids] = True
    return m


def fit_one(W: torch.Tensor, H: torch.Tensor, rows: list[int], prompt, nxt, args, tau: float, h2: float) -> dict:
    d, dev = H.shape[1], W.device
    b = torch.zeros(d, device=dev, requires_grad=True)
    params = [b]
    U = V = None
    if args.rank > 0:
        g0 = torch.Generator().manual_seed(args.seed)
        V = torch.linalg.qr(torch.randn(d, args.rank, generator=g0))[0].to(dev).requires_grad_(True)
        params += [V]
        if not args.tied:
            U = torch.zeros(d, args.rank, device=dev, requires_grad=True)
            params += [U]
    scale = H.norm(dim=1).mean().item() / d**0.5
    opt = torch.optim.Adam(params, lr=args.lr * scale)
    gen = torch.Generator().manual_seed(args.seed)
    terms = set(args.terms.split(","))
    hist = []
    for step in range(args.steps):
        pick = torch.tensor(rows)[torch.randperm(len(rows), generator=gen)[: args.batch]]
        Hb = H[pick].to(dev)
        S_mask = sets_mask(pick.tolist(), prompt, nxt, terms, W.shape[0], dev)
        g = b.expand_as(Hb)
        if args.tied and V is not None:  # g = b + Q Q^T h: remove h's component in a learned subspace
            Q = torch.linalg.qr(V)[0]
            g = g + (Hb @ Q) @ Q.T
        elif U is not None:
            g = g + (Hb @ V) @ U.T
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=dev.type == "cuda"):
            S = ((Hb - g) @ W.T).float()
        c10 = S.masked_fill(S_mask, float("-inf")).topk(10, dim=1).values[:, -1:]
        pen = F.softplus((S - c10) / tau) * S_mask
        main = (pen.sum(1) / S_mask.sum(1).clamp_min(1)).mean()
        reg = (g.square().sum(1).mean()) / h2
        loss = main + args.lam * reg
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 50 == 0 or step == args.steps - 1:
            with torch.no_grad():
                inset = ((S > c10) & S_mask).sum(1).float().mean().item()
            hist.append({"step": step, "loss": round(main.item(), 4), "reg": round(reg.item(), 4), "set_in_top10": round(inset, 3)})
    if args.tied and V is not None:  # store as U = V = Q, so the centre reads g = b + Q Q^T h unchanged
        Q = torch.linalg.qr(V.detach())[0].cpu()
        return {"b": b.detach().cpu(), "U": Q, "V": Q, "hist": hist}
    out = {"b": b.detach().cpu(), "U": None if U is None else U.detach().cpu(), "V": None if V is None else V.detach().cpu(),
           "hist": hist}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--terms", default="prompt,next")
    ap.add_argument("--shuffle-prompt", action="store_true")
    ap.add_argument("--tied", action="store_true", help="g = b + Q Q^T h with a learned orthonormal Q (bounded by ||h||)")
    ap.add_argument("--lam", type=float, default=0.1, help="weight of mean ||g||^2 / mean ||h||^2")
    ap.add_argument("--tau", type=float, default=0.05, help="softplus temperature, x the score std at the layer")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--layers", default="grid")
    ap.add_argument("--families", default=",".join(clusters.FAMILIES))
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    torch.backends.cuda.matmul.allow_tf32 = True
    layers = GRID if args.layers == "grid" else [int(x) for x in args.layers.split(",")]
    t0 = time.time()
    lens = Lens(layers, args.device)
    vocab = lens.display(list(range(lens.vocab)))
    H, keys, prompt, nxt = build(lens, vocab, layers, args.shuffle_prompt, args.seed, args.families.split(","))
    groups = sorted(set(keys))
    rng = random.Random(args.seed)
    rng.shuffle(groups)
    fold_of = {g: k % args.folds for k, g in enumerate(groups)}
    n = len(keys)
    print(f"{n} cells, {len(groups)} groups, {args.folds} folds, layers {layers} ({time.time() - t0:.0f}s)", flush=True)
    out = {"meta": vars(args) | {"n_cells": n}, "fold_of": fold_of, "layers": {}}
    report = {"meta": out["meta"], "layers": {}}
    dev = torch.device(args.device)
    for L in layers:
        t = time.time()
        W = lens.w_u @ lens.jac[L]
        W = (W / lens.denom[L][:, None]).to(dev)  # the cos readout map [V, d]
        HL = H[L]
        with torch.no_grad():
            sample = HL[torch.randperm(n, generator=torch.Generator().manual_seed(0))[:256]].to(dev)
            tau = args.tau * (sample @ W.T).std().item()
        Wb = W.to(torch.bfloat16) if dev.type == "cuda" else W
        del W  # keep only the bf16 copy on the GPU
        h2 = HL.square().sum(1).mean().item()
        models = {"full": fit_one(Wb, HL, list(range(n)), prompt, nxt, args, tau, h2)}
        for k in range(args.folds):
            models[k] = fit_one(Wb, HL, [r for r in range(n) if fold_of[keys[r]] != k], prompt, nxt, args, tau, h2)
        m = models["full"]
        with torch.no_grad():
            g = m["b"].expand_as(HL) + ((HL @ m["V"]) @ m["U"].T if m["U"] is not None else 0)
            ratio = (g.norm(dim=1) / HL.norm(dim=1)).mean().item()
            top_b = lens.display((Wb.float() @ m["b"].to(dev)).topk(15).indices.tolist())
        report["layers"][L] = {"g_over_h": round(ratio, 3), "b_norm_over_h": round(m["b"].norm().item() / h2**0.5, 3),
                               "L(b) top": top_b, "hist_full": m["hist"]}
        for mm in models.values():
            mm.pop("hist")
        out["layers"][L] = models
        print(f"L{L}: ||g||/||h|| {ratio:.3f}, set in top10 {report['layers'][L]['hist_full'][0]['set_in_top10']} -> "
              f"{report['layers'][L]['hist_full'][-1]['set_in_top10']}, L(b) {top_b[:8]} ({time.time() - t:.0f}s)", flush=True)
        del Wb
        if dev.type == "cuda":
            torch.cuda.empty_cache()
    S19.ROOT.mkdir(parents=True, exist_ok=True)
    tmp = S19.path_of(args.name).with_suffix(".tmp")
    torch.save(out, tmp)
    tmp.rename(S19.path_of(args.name))
    (S19.ROOT / f"{args.name}.json").write_text(json.dumps(report, indent=1))
    print(f"wrote {S19.path_of(args.name)} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
