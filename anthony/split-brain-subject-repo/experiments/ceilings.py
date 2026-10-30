"""S20 headroom ceilings per class of g: how much can a constant, a per-token, a per-cluster or a rank-k projection
centre gain at all, when fitted *with the targets* (notes/iteration-anthony/mu-log.md, card S20).

  python experiments/ceilings.py --family typo --split fit                       # in-sample + 3-fold by group
  python experiments/ceilings.py --family typo --split fit --val                 # also read val with the fit-fitted g
  python experiments/ceilings.py --family user_modeling --split fit --classes const,proj16 --device cuda

This is a DIAGNOSTIC under the "no crystal ball" rule: an in-sample ceiling, labelled as such, never a method. Nothing
here writes under ``out/eval`` or registers a centre; the results go to ``out/analysis/S20/<family>-<split>.{json,md}``
with every fitted arm named ``ceil.<class>``.

Objective: J++'s surrogate of recall@10, per layer and cell: ``softplus((s_10th_competitor - s_best_target) / tau)``
over a candidate vocabulary (the union of each cell's top-64 tokens under zero and under fam, plus every accepted id),
plus a small L2 penalty on g. Scored exactly afterwards (full-vocabulary ranks, the bench's item rule: a target in the
top 10 at any cell and any grid layer). Reported: in-sample, K-fold by group (fit on K-1 folds, score the held-out
fold: the honest ceiling of the class), and ``--val`` (fit on the whole split, read val). Baselines zero and fam
(leave-one-group-out) go through the same scorer.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import MULTI_TOKEN, scorers

from jlm import OUT, banks, capture, mtproxy
from jlm.lens import Lens
from jlm.mu import clusters

GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]
TOP_K = 10


def first_tokens(bank: banks.Bank, tokenizer) -> dict[str, set[int]]:
    """Per item, the first token id of every form of its required units (article dropped; " form" and "form"): the
    token a judge needs to see to read the whole form, where the piece proxy accepts any distinctive piece."""
    from wsbench.multitoken import regex

    contract = regex.contract_for(bank.header, str(bank.header.get("family", bank.family)))
    out = {}
    for it in bank.items:
        ids = set()
        for u in regex.scored_units(it, contract):
            if not u.required:
                continue
            for f in (f for forms in u.forms.values() for f in forms):
                f = mtproxy._strip_article(f)
                for v in (f, " " + f):
                    t = tokenizer(v, add_special_tokens=False)["input_ids"]
                    first = tokenizer.decode(t[:1]).strip() if t else ""
                    if first and (len(first) >= mtproxy.MIN_PIECE or first.isdigit()):  # not ' ', 'n', 'con'
                        ids.add(t[0])
        out[it["id"]] = ids
    return out


class Problem:
    """One bank's cells, states, accepted ids and groups, with the lens."""

    def __init__(self, lens: Lens, bank: banks.Bank, items, layers: list[int], mt_ids: str = "pieces") -> None:
        self.lens, self.bank, self.items, self.layers = lens, bank, items, layers
        vocab = lens.display(list(range(lens.vocab)))
        if bank.family in MULTI_TOKEN:
            units = mtproxy.units_of(bank, lens.tokenizer, lens.display)
            self.accepted = {i: sorted({t for u in us if u.required for t in u.ids}) for i, us in units.items()}
            if mt_ids == "first":  # only the first token of each required form (with and without a leading space)
                self.accepted = {i: sorted(ids) for i, ids in first_tokens(bank, lens.tokenizer).items()}
            ok = mtproxy.reachable(units)
            self.scored = [i for i, r in ok.items() if r and self.accepted[i]]
        else:
            strict, _ = scorers(bank, vocab, {it.id: lens.display(it.ids) for it in items})
            self.accepted, self.scored = strict.accepted, [i for i, why in strict.conf.items() if not why and strict.accepted[i]]
        self.groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
        scored = set(self.scored)
        self.cells = [(it, i) for it in items for i in range(len(it.positions)) if it.id in scored]
        self.item_of = [it.id for it, _ in self.cells]
        self.group_of = [self.groups[it.id] for it, _ in self.cells]
        self.H = {L: torch.stack([it.acts[L][i].float() for it, i in self.cells]) for L in layers}
        self.tokens = [it.token(i) for it, i in self.cells]
        self.offset = [i for _, i in self.cells]  # index into the item's read cells = offset in its read span

    def states(self, L: int, rows: torch.Tensor) -> torch.Tensor:
        return self.H[L][rows]

    def best_rank(self, X: torch.Tensor, L: int, readout: str, rows: torch.Tensor) -> torch.Tensor:
        """Exact rank (0-based) of the best accepted id of each cell's item under the readout of states ``X``."""
        out = torch.empty(len(rows), dtype=torch.long)
        for a in range(0, len(rows), 256):
            S = self.lens.scores(X[a : a + 256], L, readout).cpu()
            for j, r in enumerate(rows[a : a + 256].tolist()):
                ids = self.accepted[self.item_of[r]]
                best = S[j, ids].max()
                out[a + j] = int((S[j] > best).sum())
        return out

    def item_pass(self, ranks: dict[int, torch.Tensor], rows: torch.Tensor) -> dict[str, bool]:
        """The bench's item rule over the given cells: a target in the top 10 at any cell, any layer."""
        passes = {self.item_of[r]: False for r in rows.tolist()}
        for rk in ranks.values():
            for j, r in enumerate(rows.tolist()):
                if rk[j] < TOP_K:
                    passes[self.item_of[r]] = True
        return passes


def candidates(prob: Problem, L: int, readout: str, rows: torch.Tensor, fam_g: torch.Tensor, per_cell: int = 64, cap: int = 32768) -> torch.Tensor:
    """Candidate token ids: each cell's top tokens under zero and under fam, the most shared first, plus accepted ids."""
    H = prob.states(L, rows)
    counts = torch.zeros(prob.lens.vocab, dtype=torch.long)
    for X in (H, H - fam_g):
        for a in range(0, len(X), 256):
            top = prob.lens.scores(X[a : a + 256], L, readout).topk(per_cell, dim=1).indices.cpu().flatten()
            counts += torch.bincount(top, minlength=prob.lens.vocab)
    acc = torch.tensor(sorted({t for r in rows.tolist() for t in prob.accepted[prob.item_of[r]]}), dtype=torch.long)
    counts[acc] = 0
    k = min(cap - len(acc), int((counts > 0).sum()))
    cand = counts.topk(k).indices if k > 0 else torch.empty(0, dtype=torch.long)
    return torch.cat([acc, cand])


class Param:
    """The learnable centre of one class at one layer: ``g(h, key) = mu_key + Q Q^T (h - mu_key)`` (Q empty unless proj)."""

    def __init__(self, cls: str, prob: Problem, L: int, rows: torch.Tensor, init: torch.Tensor, device: str) -> None:
        self.cls, self.d = cls, init.shape[0]
        H = prob.states(L, rows)
        if cls == "const":
            keys = [0] * len(rows)
        elif cls == "tok":
            toks = [prob.tokens[r] for r in rows.tolist()]
            common = {t for t in set(toks) if toks.count(t) >= 3}
            names = sorted(common)
            keys = [names.index(t) + 1 if t in common else 0 for t in toks]
        elif cls == "pos":  # the cell's offset in the item's read span (U1's u1rel key), >= 3 cells per key
            offs = [prob.offset[r] for r in rows.tolist()]
            common = sorted({o for o in set(offs) if offs.count(o) >= 3})
            keys = [common.index(o) + 1 if o in common else 0 for o in offs]
            self.pos_key = {o: common.index(o) + 1 for o in common}
        elif cls == "clu":
            cm = clusters.ClusterMean(64, "bench")
            cm.fit(prob.items, prob.bank.family, prob.groups)
            labels = cm.assign(H, L).tolist()
            keys = labels
        elif cls.startswith("proj"):
            keys = [0] * len(rows)
        else:
            raise ValueError(cls)
        self.n_keys = max(keys) + 1
        self.keys = torch.tensor(keys, device=device)
        self.tok_key = {prob.tokens[r]: k for r, k in zip(rows.tolist(), keys, strict=True)} if cls == "tok" else {}
        if cls != "pos":
            self.pos_key = {}
        self.cm = cm if cls == "clu" else None
        self.mu = torch.nn.Parameter(init.to(device).repeat(self.n_keys, 1).clone())
        self.V = None
        if cls.startswith("proj"):
            k = int(cls[4:])
            X = (H - init).double()
            _, _, Vt = torch.linalg.svd(X - X.mean(0), full_matrices=False)
            self.V = torch.nn.Parameter(Vt[:k].T.float().to(device).contiguous())

    def params(self) -> list[torch.nn.Parameter]:
        return [self.mu] + ([self.V] if self.V is not None else [])

    def key_of(self, prob: Problem, L: int, rows: torch.Tensor) -> torch.Tensor:
        """Keys for any cells of any bank: const / proj share one; tok by token name (unseen tokens: the shared
        key 0); clu by the fitted clustering's assignment."""
        if self.cls == "const" or self.cls.startswith("proj"):
            return torch.zeros(len(rows), dtype=torch.long, device=self.mu.device)
        if self.cls == "tok":
            return torch.tensor([self.tok_key.get(prob.tokens[r], 0) for r in rows.tolist()], device=self.mu.device)
        if self.cls == "pos":
            return torch.tensor([self.pos_key.get(prob.offset[r], 0) for r in rows.tolist()], device=self.mu.device)
        return torch.tensor(self.cm.assign(prob.states(L, rows), L).tolist(), device=self.mu.device).clamp_max(self.n_keys - 1)

    def apply(self, H: torch.Tensor, keys: torch.Tensor) -> torch.Tensor:
        X = H - self.mu[keys]
        if self.V is not None:
            Q, _ = torch.linalg.qr(self.V)
            X = X - (X @ Q) @ Q.T
        return X


def fit_layer(prob: Problem, L: int, readout: str, rows: torch.Tensor, cls: str, fam_g: torch.Tensor, args) -> Param:
    device = args.device
    cand = candidates(prob, L, readout, rows, fam_g)
    Wc = prob.lens.w_u[cand].float()
    if readout == "rms":  # rms divides each cell by a positive scalar: its ranking is that of W_U diag(gain) J
        Wc = Wc * prob.lens.gain
    if not prob.lens.identity:
        Wc = Wc @ prob.lens.jac[L]
    if readout == "cos":
        Wc = Wc / prob.lens.denom[L][cand, None]
    Wc = Wc.to(device)  # [K, d]
    H = prob.states(L, rows).to(device)
    pos = {int(t): j for j, t in enumerate(cand.tolist())}
    tmask = torch.zeros(len(rows), len(cand), dtype=torch.bool, device=device)
    for j, r in enumerate(rows.tolist()):
        tmask[j, [pos[t] for t in prob.accepted[prob.item_of[r]]]] = True
    init = fam_g.mean(0) if fam_g.dim() == 2 else fam_g
    p = Param(cls, prob, L, rows, init, device)
    opt = torch.optim.Adam(p.params(), lr=args.lr * H.norm(dim=1).mean().item() / H.shape[1] ** 0.5)
    with torch.no_grad():
        tau = args.tau * (H @ Wc.T).std().item()
    for _ in range(args.steps):
        opt.zero_grad()
        S = p.apply(H, p.keys) @ Wc.T
        best = S.masked_fill(~tmask, float("-inf")).max(dim=1).values
        comp = S.masked_fill(tmask, float("-inf")).topk(TOP_K, dim=1).values[:, -1]
        anchor = init.to(device) if args.l2_anchor == "init" else 0.0  # "init": shrink toward fam, not toward zero
        loss = F.softplus((comp - best) / tau).mean() + args.l2 * ((p.mu - anchor) ** 2).sum() / (H**2).sum()
        loss.backward()
        opt.step()
    return p


def evaluate(prob: Problem, readout: str, rows: torch.Tensor, g_of, label: str) -> dict:
    """Exact item pass rate over ``rows`` for states ``g_of(L, rows) -> X`` [n, d]."""
    ranks = {L: prob.best_rank(g_of(L, rows), L, readout, rows) for L in prob.layers}
    passes = prob.item_pass(ranks, rows)
    ids = sorted(passes)
    return {"label": label, "n": len(ids), "pass": sum(passes.values()) / max(1, len(ids)), "passes": passes,
            "by_layer": {L: float((rk < TOP_K).float().mean()) for L, rk in ranks.items()}}


def fam_logo(prob: Problem, L: int, rows: torch.Tensor) -> torch.Tensor:
    """Leave-one-group-out family mean for each row, over the problem's cells."""
    H, G = prob.H[L], prob.group_of
    tot, n = H.sum(0), len(H)
    out = torch.empty(len(rows), H.shape[1])
    for j, r in enumerate(rows.tolist()):
        own = [k for k, g in enumerate(G) if g == G[r]]
        out[j] = (tot - H[own].sum(0)) / max(1, n - len(own))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--split", default="fit")
    ap.add_argument("--classes", default="const,tok,clu,proj16")
    ap.add_argument("--readout", default="cos")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--val", action="store_true", help="also read the val bank with the g fitted on the whole split")
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--lr", type=float, default=0.02)
    ap.add_argument("--tau", type=float, default=0.05, help="softplus temperature, x the score std")
    ap.add_argument("--l2", type=float, default=1e-3)
    ap.add_argument("--layers", default="grid")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--save-g", action="store_true",
                    help="save each class's whole-split fit to out/analysis/S20/g/<family>-<class>.pt (centre s20:<class>)")
    ap.add_argument("--frac", type=float, default=1.0,
                    help="fit the whole-split g (the val read) on this share of fit groups (seeded): n-scaling")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--l2-anchor", default="zero", choices=["zero", "init"], help="the L2 pulls g toward 0 or toward its init (fam)")
    ap.add_argument("--mt-ids", default="pieces", choices=["pieces", "first"],
                    help="_mt families: fit (and score) on the proxy's distinctive pieces or on each form's first token")
    ap.add_argument("--tag", default="", help="suffix of the json / md names (a second run does not overwrite the first)")
    args = ap.parse_args()
    layers = GRID if args.layers == "grid" else [int(x) for x in args.layers.split(",")]
    t0 = time.time()
    bank = banks.load(args.family, args.split)
    items = capture.load(bank)
    layers = [L for L in layers if all(L in it.acts for it in items)]
    lens = Lens(layers, args.device if args.device != "cpu" else "cpu", "jlens")
    prob = Problem(lens, bank, items, layers, args.mt_ids)
    rows = torch.arange(len(prob.cells))
    print(f"{bank.name}: {len(prob.scored)} scored items, {len(rows)} cells, layers {layers} ({time.time() - t0:.0f}s)", flush=True)
    results = {"bank": bank.name, "readout": args.readout, "layers": layers, "n_items": len(prob.scored), "classes": {},
               "args": vars(args), "note": "in-sample ceilings with targets (S20): not a method, never on the leaderboard"}
    with torch.no_grad():
        results["zero"] = evaluate(prob, args.readout, rows, lambda L, r: prob.states(L, r), "zero")
        results["fam_logo"] = evaluate(prob, args.readout, rows, lambda L, r: prob.states(L, r) - fam_logo(prob, L, r), "fam (leave-one-group-out)")
    print(f"zero {results['zero']['pass']:.3f}  fam(logo) {results['fam_logo']['pass']:.3f}", flush=True)
    groups = sorted(set(prob.group_of))
    fold_of = {g: k % max(1, args.folds) for k, g in enumerate(groups)}  # --folds 0: no K-fold reads
    for cls in args.classes.split(","):
        t = time.time()
        fam_all = {L: fam_logo(prob, L, rows) for L in layers}
        fit_rows = rows
        if args.frac < 1.0:
            import random
            gs = sorted(set(prob.group_of))
            keep = set(random.Random(args.seed).sample(gs, max(1, round(args.frac * len(gs)))))
            fit_rows = torch.tensor([j for j, g in enumerate(prob.group_of) if g in keep])
        fitted = {L: fit_layer(prob, L, args.readout, fit_rows, cls, fam_all[L][fit_rows], args) for L in layers}
        with torch.no_grad():
            ins = evaluate(prob, args.readout, rows,
                           lambda L, r, fitted=fitted: fitted[L].apply(prob.states(L, r).to(args.device), fitted[L].key_of(prob, L, r)).cpu(),
                           f"ceil.{cls} in-sample")
            held_passes: dict[str, bool] = {}
            for k in range(args.folds):
                train = torch.tensor([j for j, g in enumerate(prob.group_of) if fold_of[g] != k])
                test = torch.tensor([j for j, g in enumerate(prob.group_of) if fold_of[g] == k])
                if len(test) == 0:
                    continue
                with torch.enable_grad():
                    fk = {L: fit_layer(prob, L, args.readout, train, cls, fam_all[L][train], args) for L in layers}
                res = evaluate(prob, args.readout, test,
                               lambda L, r, fk=fk: fk[L].apply(prob.states(L, r).to(args.device), fk[L].key_of(prob, L, r)).cpu(),
                               f"ceil.{cls} fold {k}")
                held_passes |= res["passes"]
            held = {"n": len(held_passes), "pass": sum(held_passes.values()) / max(1, len(held_passes)), "passes": held_passes}
            entry = {"in_sample": ins, "held_out_folds": held}
            if args.val:
                vbank = banks.load(args.family, "val")
                vprob = Problem(lens, vbank, capture.load(vbank), layers, args.mt_ids)
                vrows = torch.arange(len(vprob.cells))
                entry["val"] = evaluate(vprob, args.readout, vrows,
                                        lambda L, r, fitted=fitted, vprob=vprob: fitted[L].apply(vprob.states(L, r).to(args.device), fitted[L].key_of(vprob, L, r)).cpu(),
                                        f"ceil.{cls} val")
                entry["val_zero"] = evaluate(vprob, args.readout, vrows, lambda L, r, vprob=vprob: vprob.states(L, r), "zero val")
                entry["val_fam_fit"] = evaluate(vprob, args.readout, vrows, lambda L, r, vprob=vprob, fam_all=fam_all: vprob.states(L, r) - fam_all[L].mean(0), "fam@fit val")
        results["classes"][cls] = entry
        if args.save_g:
            gdir = OUT / "analysis" / "S20" / "g"
            gdir.mkdir(parents=True, exist_ok=True)
            torch.save({"family": args.family, "class": cls, "readout": args.readout, "note": "fitted WITH fit targets (S20)",
                        "layers": {L: {"mu": p.mu.detach().cpu(), "V": None if p.V is None else torch.linalg.qr(p.V.detach())[0].cpu(),
                                       "tok_key": p.tok_key, "pos_key": p.pos_key} for L, p in fitted.items()}},
                       gdir / (f"{args.family}-{cls}" + ("" if args.readout == "cos" else f"-{args.readout}")
                               + ("" if args.mt_ids == "pieces" else f"-{args.mt_ids}") + ".pt"))
        print(f"ceil.{cls}: in-sample {ins['pass']:.3f}, {args.folds}-fold held-out {held['pass']:.3f}"
              + (f", val {entry['val']['pass']:.3f} (zero {entry['val_zero']['pass']:.3f}, fam@fit {entry['val_fam_fit']['pass']:.3f})" if args.val else "")
              + f" ({time.time() - t:.0f}s)", flush=True)
    root = OUT / "analysis" / "S20"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{args.family}-{args.split}{args.tag}.json").write_text(json.dumps(results, indent=1, default=str))
    lines = [f"# S20 ceilings: {bank.name} ({args.readout}; {len(prob.scored)} items; in-sample fits WITH targets: not a method)", "",
             "| arm | in-sample | held-out folds | val |", "|---|---|---|---|",
             f"| zero | {results['zero']['pass']:.3f} | | |", f"| fam (logo) | {results['fam_logo']['pass']:.3f} | | |"]
    for cls, e in results["classes"].items():
        lines.append(f"| ceil.{cls} | {e['in_sample']['pass']:.3f} | {e['held_out_folds']['pass']:.3f} | "
                     f"{e['val']['pass']:.3f} (zero {e['val_zero']['pass']:.3f}, fam {e['val_fam_fit']['pass']:.3f}) |" if "val" in e else
                     f"| ceil.{cls} | {e['in_sample']['pass']:.3f} | {e['held_out_folds']['pass']:.3f} | |")
    (root / f"{args.family}-{args.split}{args.tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
