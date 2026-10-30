"""Our finalist centres on the J++ paper's readout evals, through the J-lens and the J++ map (no judge, no forward pass).

    python experiments/jpp_finalists.py --device cuda [--arms S14bL,S20x] [--limit 8] [--parity-only]

Items, read cells, candidates, the fit / held / incorrect split (seed 0, 20 % fit) and the scoring are the J++
paper's, as umot's capture stored them (``umot/out/jpp/{residuals.pt,items.json}``: one read cell per item, every
layer 0-62) and as ``experiments/ll_jpp_evals.py`` scores them: Readout Filtering (ids whose decode has no letter or
digit excluded, candidates spared), rank = #(scores >= best candidate score) (ties count against), an (item,
intermediate) pair hits when its min rank over the layers is <= 10, recall@10 = mean over an eval's held-out pairs,
macro over the five evals (and over the four with a WorkspaceBench counterpart, poetry left out). Prompts from the J++
repo @ 93f02cd (``--jpp-repo``), tokenized as their runner does; 3 multilingual items whose local tokenization differs
from the capture keep the captured read token (their context tail is approximate; it only feeds knnxs's carrier rule).

Layers: the paper's min runs over the 7 recipe layers 8..56 (step 8); our centres are defined on our capture grid,
so every arm reads at grid ∩ [8, 56] = 20..56 (11 layers, ``sched:40`` switches there). The uncentred maps are also
reported on the recipe layers (the parity check: J++ 0.594, n1000 0.340, rms) so the layer change is visible.

Centres run unchanged (``jlm.centres.make``): each J++ item is an ``ItemCapture`` with one read cell, family =
its eval, fitted on our WorkspaceBench dev **fit** captures of that family (``fam@fit``'s reference); the bench pools
(kmx64, knnxs8, knnxd8l) are our fit pools as always. poetry has no counterpart: its ``fam`` is the pooled fit mean of
the five single-token families (typo, association, basic_readout, multihop, multilingual) and its S20x correction the
mean of all ten source families' corrections (no twin to leave out). ``ref`` is umot's in-distribution baseline: the
mean of the eval's own J++ fit-split items. knnxd8l's language is detected from the J++ prompt text.

Every learned or geometric piece is the J-lens's: S14's template bases (``out/lens/tbasis-*``, the J-lens's reading
directions) and S20x's corrections (``out/analysis/S20x/dbar*.pt``, fitted through the J-lens). Through the J++ map
they are reused as-is (the J++-native versions would need their own precompute / fit). rms arms use the rms-fitted
S20x corrections (``s20xtrms`` / ``s20xonrms``), as the val pipeline did; everything else is the same centre name.

Paired bootstrap (items resampled within eval, 2000 draws, the same draws for both arms) of the macro difference.
Writes ``out/analysis/jpp-finalists/{scores.json,summary.md,ranks.pt}``.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from umot.capture import ItemCapture
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, REPO_ROOT, banks, capture, centres, controls
from jlm.centres import Batch, cell_refs
from jlm.lens import MODEL, Lens, reader

JPP = REPO_ROOT / "umot" / "out" / "jpp"
JPP_COMMIT = "93f02cd"
EVALS = ("multihop", "multilingual", "typo", "association", "poetry")
MAPPED = ("multihop", "multilingual", "typo", "association")
SINGLE = ("typo", "association", "basic_readout", "multihop", "multilingual")
GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56]
RECIPE = [8, 16, 24, 32, 40, 48, 56]
B = "s14:template:64:mean={}:a=0.5"
#: label -> (cos centre, rms centre); "ref" is the J++ fit-split mean (built here, not a registered centre)
ARMS = {
    "zero": ("zero", "zero"),
    "fam": ("fam", "fam"),
    "ref": ("ref", "ref"),
    "S14k": ("sched:40:kmx64+s14t64",) * 2,
    "S14b": (f"sched:40:kmx64+{B.format('kmx64')}",) * 2,
    "S14b-knnxs8": (f"sched:40:kmx64+{B.format('knnxs8')}",) * 2,
    "S14bL": (f"sched:40:kmx64+{B.format('knnxd8l')}",) * 2,
    "S20x": ("s20xt:1", "s20xtrms:1"),
    "s20xon": ("s20xon:1:kmx64", "s20xonrms:1:kmx64"),
    "S21b": (f"sched:40:s20xon:1:kmx64+{B.format('kmx64')}", f"sched:40:s20xonrms:1:kmx64+{B.format('kmx64')}"),
    "rand.S14bL": (f"rand.sched:40:kmx64+{B.format('knnxd8l')}",) * 2,
    "rand.S20x": ("rand.s20xt:1", "rand.s20xtrms:1"),
    # x13's blind glossary: texts the model wrote from the entry it wrote from one README sentence (no item seen)
    "glosb:desc": ("glosb:desc",) * 2,
    "glosb:word": ("glosb:word",) * 2,
}
MAPS = ("jlens", "jpp")
READOUTS = ("rms", "cos")
DRAWS = 2000


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def jpp_items(meta, R, tok, jpp_repo: Path, layers: list[int]) -> tuple[list[ItemCapture], dict[str, str], int]:
    """One ``ItemCapture`` per J++ item (id ``jpp/<eval>/<name>``, never an id of our pools), acts at ``layers``."""
    prompts = {}
    for s in EVALS:
        for it in json.loads((jpp_repo / "data/jlens/evaluations" / f"lens-eval-{s}.json").read_text())["items"]:
            prompts[(s, it["name"])] = it["prompt"]
    out, off = [], 0
    for p, m in enumerate(meta):
        ids = tok(prompts[(m["eval"], m["item"])]).input_ids
        decoded = [tok.decode([t]) for t in ids]
        idx = m["read_pos"]
        if len(ids) != m["n_tokens"] or idx >= len(ids) or ids[idx] != m["read_token_id"]:
            off += 1
            idx = min(idx, len(ids) - 1)
            decoded[idx] = m["read_token"]
        out.append(ItemCapture(f"jpp/{m['eval']}/{m['item']}", ids, decoded[: idx + 1], [m["read_pos"]], [idx],
                               {L: R[L][p : p + 1].clone() for L in layers}))
    return out, {it.id: prompts[(m["eval"], m["item"])] for it, m in zip(out, meta, strict=True)}, off


def prepare_unseen_family() -> None:
    """poetry: no carrier field, S20x's correction = the mean over all its source families (no twin)."""
    from jlm.mu import S16, S20x

    S16._CARRIERS["poetry"] = {}
    for readout in ("cos", "rms"):
        S20x.dbar("typo|twin", GRID[0], readout)  # loads the table
        table = S20x._DBAR if readout == "cos" else S20x._DBAR_RMS
        table["poetry|twin"] = {L: torch.stack([table["d"][f][L].float() for f in table["d"]]).mean(0)
                                for L in table["typo|twin"]}


def fit_refs() -> dict[str, list]:
    refs = {f: capture.load(banks.load(f, "fit")) for f in SINGLE}
    refs["poetry"] = [it for f in SINGLE for it in refs[f]]
    return refs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--jpp-dir", default=str(JPP))
    ap.add_argument("--jpp-repo", default=str(Path.home() / "src" / "jpp_lens"))
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--limit", type=int, default=0, help="first N items per eval (plumbing)")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--merge", action="store_true", help="add --arms to the existing scores.json / ranks.pt (parity, zero "
                    "and fam ranks read from ranks.pt, not recomputed) instead of rewriting them")
    ap.add_argument("--pool", default="ours", choices=["ours", "jpp", "both"],
                    help="ours: the finalists fitted on our WorkspaceBench fit pool; jpp: refitted on the J++ evals' own "
                    "fit split (pool-jpp.json, its own summary.md section; the ours outputs are kept)")
    ap.add_argument("--s20-steps", type=int, default=150)
    ap.add_argument("--out", default=str(OUT / "analysis" / "jpp-finalists"))
    a = ap.parse_args()
    dev, root = a.device, Path(a.out)
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    res = torch.load(Path(a.jpp_dir) / "residuals.pt", weights_only=False, mmap=True)
    meta = json.loads((Path(a.jpp_dir) / "items.json").read_text())
    R = res["residuals_L_dict_PN"]
    cands = res["candidate_ids_by_item"]
    keep = list(range(len(meta)))
    if a.limit:
        seen: dict[str, int] = {}
        keep = [p for p, m in enumerate(meta) if (seen.__setitem__(m["eval"], seen.get(m["eval"], 0) + 1) or seen[m["eval"]] <= a.limit)]
    layers = sorted(set(GRID) | set(RECIPE))
    R = {L: R[L][keep].float() for L in layers}
    meta, cands = [meta[p] for p in keep], [cands[p] for p in keep]

    lenses = {"jlens": Lens(layers, dev)}
    lenses["jpp"] = Lens(layers, dev, "jpp", share=lenses["jlens"])
    jl = lenses["jlens"]
    V = jl.vocab
    spared = {t for c in cands for ids in c.values() for t in ids}
    excl = torch.zeros(V, dtype=torch.bool, device=dev)
    excl[controls.non_semantic_ids(jl.tokenizer, V, spared)] = True
    pairs = [(p, i, c) for p, cs in enumerate(cands) for i, c in cs.items()]
    C = max(len(c) for _, _, c in pairs)
    pair_item = torch.tensor([p for p, _, _ in pairs], device=dev)
    pair_c = torch.tensor([c + [c[0]] * (C - len(c)) for _, _, c in pairs], device=dev)
    split = [m["split"] for m in meta]
    held = [k for k, (p, _, _) in enumerate(pairs) if split[p] == "held"]
    held_item = [pairs[k][0] for k in held]
    held_eval = [meta[p]["eval"] for p in held_item]

    def ranks(X: torch.Tensor, lens: Lens, L: int, readout: str) -> torch.Tensor:
        S = lens.scores(X, L, readout).masked_fill(excl, float("-inf"))
        per = S[pair_item]
        best = per.gather(1, pair_c).max(1).values
        return (per >= best[:, None]).sum(1).cpu()

    def recall(R_pl: torch.Tensor) -> dict:  # R_pl [pairs, layers] -> per-eval and macro recall@10 (held pairs)
        hit = (R_pl.min(1).values <= 10).float()[held].numpy()
        per = {e: float(hit[[k for k, x in enumerate(held_eval) if x == e]].mean()) for e in EVALS}
        return {"macro": float(np.mean([per[e] for e in EVALS])), "macro4": float(np.mean([per[e] for e in MAPPED])), **per}

    # bootstrap draws: items resampled within eval; per draw, per eval, the pairs' hit mean
    rng = np.random.default_rng(0)
    eval_items = {e: sorted({p for p, x in zip(held_item, held_eval, strict=True) if x == e}) for e in EVALS}
    pair_rows = {p: [j for j, q in enumerate(held_item) if q == p] for p in set(held_item)}
    draws = {e: rng.integers(0, len(v), size=(DRAWS, len(v))) for e, v in eval_items.items() if v}

    def boot(hit: np.ndarray) -> dict[str, np.ndarray]:  # hit [held pairs] -> per-eval [DRAWS] recall
        out = {}
        for e, its in eval_items.items():
            s = np.array([hit[pair_rows[p]].sum() for p in its])
            n = np.array([len(pair_rows[p]) for p in its])
            out[e] = s[draws[e]].sum(1) / n[draws[e]].sum(1)
        return out

    def delta(Ra: torch.Tensor, Rb: torch.Tensor) -> dict:
        ha, hb = ((r.min(1).values <= 10).float()[held].numpy() for r in (Ra, Rb))
        ba, bb = boot(ha), boot(hb)
        out = {}
        for tag, evs in (("macro", EVALS), ("macro4", MAPPED)):
            d = np.mean([ba[e] - bb[e] for e in evs], 0)
            point = float(np.mean([ha[[k for k, x in enumerate(held_eval) if x == e]].mean()
                                   - hb[[k for k, x in enumerate(held_eval) if x == e]].mean() for e in evs]))
            out[tag] = [point, float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))]
        return out

    scores, all_ranks, old_diffs = {}, {}, {}
    if a.merge:
        old = json.loads((root / "scores.json").read_text())["result"]
        scores, old_diffs = old["scores"], old["diffs"]
        stored = torch.load(root / "ranks.pt", weights_only=False)
        assert stored["pairs"] == [(meta[p]["eval"], meta[p]["item"], i) for p, i, _ in pairs], "ranks.pt pairs differ"
        all_ranks = {k: v.long() for k, v in stored.items() if k != "pairs"}
    # ---- parity: the uncentred maps on the recipe layers and on our grid ----
    for m in MAPS if not a.merge else ():
        for ro in READOUTS:
            for tag, Ls in (("recipe7", RECIPE), ("grid11", GRID)):
                Rk = torch.stack([ranks(R[L].to(dev), lenses[m], L, ro) for L in Ls], 1)
                key = f"{m}|zero|{ro}|{tag}"
                scores[key], all_ranks[key] = recall(Rk), Rk
                log(key, round(scores[key]["macro"], 4))
    if a.pool != "jpp":
        (root / "scores.json").write_text(json.dumps(scores, indent=1))
    if a.parity_only:
        return

    # ---- the arms on our grid ----
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    items, text, off = jpp_items(meta, R, tok, Path(a.jpp_repo), GRID)
    log(f"{len(items)} items, {off} with an approximate context tail")
    import jlm.mu  # noqa: F401  (registers the study centres)
    from jlm.mu import S14

    S14.detected_language("__load__")
    S14._DET.update({it.id: S14.detect_language(text[it.id]) for it in items})
    prepare_unseen_family()
    refs = fit_refs()
    by_fam = {e: [it for it, m in zip(items, meta, strict=True) if m["eval"] == e] for e in EVALS}
    row_of = {it.id: p for p, it in enumerate(items)}
    fit_mask = torch.tensor([s == "fit" for s in split])

    def states(name: str, L: int) -> torch.Tensor:  # [items, d] the states each map reads, h - g, in meta order
        X = torch.empty_like(R[L])
        for e in EVALS:
            its = by_fam[e]
            if not its:
                continue
            rows = [row_of[it.id] for it in its]
            H = R[L][rows]
            if name == "ref":
                X[rows] = H - R[L][[r for r in rows if fit_mask[r]]].mean(0)
                continue
            c = cache[name][e]
            X[rows] = centres.apply(c, Batch(L, cell_refs(its, e, L), H, {it.id: it for it in its}))
        return X

    if a.pool in ("jpp", "both"):
        jpp_pool(a, root, dev, R, meta, cands, items, by_fam, lenses, ranks, recall, delta)
        if a.pool == "jpp":
            log(f"JPPF_DONE {time.time() - t0:.0f}s")
            return

    cache: dict = {}
    for label in a.arms.split(","):
        for ro in READOUTS:
            name = ARMS[label][0] if ro == "cos" else ARMS[label][1]
            t1 = time.time()
            if name != "ref" and name not in cache:
                cache[name] = {}
                for e in EVALS:
                    c = centres.make(name)
                    fam = e if e in MAPPED else "poetry"
                    if name.startswith("glos") and fam == "poetry":  # no entry: the pooled sets, as fam's pooled fit
                        parts = [centres.make(name) for _ in SINGLE]
                        for q, f in zip(parts, SINGLE, strict=True):
                            q.fit([], f)
                        c.fit([], SINGLE[0])
                        c.mu = {L: torch.stack([q.mu[L] for q in parts]).mean(0) for L in c.mu}
                    else:
                        c.fit(refs[fam], fam)
                    cache[name][e] = c
            Xs = {L: states(name, L).to(dev) for L in GRID}
            for m in MAPS:
                Rk = torch.stack([ranks(Xs[L], lenses[m], L, ro) for L in GRID], 1)
                key = f"{m}|{label}|{ro}|grid11"
                scores[key], all_ranks[key] = recall(Rk), Rk
                log(key, name, round(scores[key]["macro"], 4), round(scores[key]["macro4"], 4), f"({time.time() - t1:.0f}s)")
            (root / "scores.json").write_text(json.dumps(scores, indent=1))

    labels = [k for k in ARMS if any(f"{m}|{k}|rms|grid11" in scores for m in MAPS)]
    # ---- paired differences ----
    diffs = dict(old_diffs)
    for m in MAPS:
        for ro in READOUTS:
            z, f = f"{m}|zero|{ro}|grid11", f"{m}|fam|{ro}|grid11"
            for label in a.arms.split(","):
                k = f"{m}|{label}|{ro}|grid11"
                if k in all_ranks and label != "zero":
                    diffs[f"{k} - zero"] = delta(all_ranks[k], all_ranks[z])
                if k in all_ranks and label not in ("zero", "fam") and f in all_ranks:
                    diffs[f"{k} - fam"] = delta(all_ranks[k], all_ranks[f])
                jz = f"jpp|zero|{ro}|grid11"
                if m == "jlens" and k in all_ranks and jz in all_ranks:
                    diffs[f"{k} - {jz}"] = delta(all_ranks[k], all_ranks[jz])
    prov = Provenance(model=MODEL, model_revision=PINS[MODEL], reader=reader("jlens")[0], reader_revision=reader("jlens")[1],
                      dataset=f"jpp_lens readout evals @ {JPP_COMMIT} (umot/out/jpp)",
                      extra={"maps": {m: reader(m) for m in MAPS}, "arms": {k: ARMS[k] for k in labels},
                             "grid": GRID, "recipe": RECIPE, "draws": DRAWS, "limit": a.limit,
                             "approx_context_items": off, "poetry": "fam = pooled fit of " + ",".join(SINGLE)})
    write_artefact(root / "scores.json", prov, {"scores": scores, "diffs": diffs})
    torch.save({k: v.int() for k, v in all_ranks.items()} | {"pairs": [(meta[p]["eval"], meta[p]["item"], i) for p, i, _ in pairs]},
               root / "ranks.pt")
    old = (root / "summary.md").read_text() if (root / "summary.md").exists() else ""
    tail = old[old.index(POOL_HEAD):] if POOL_HEAD in old else ""  # the pool-jpp section (prediction, results) stays
    (root / "summary.md").write_text(summary(scores, diffs, labels, off) + ("\n" + tail if tail else ""))
    log(f"JPPF_DONE {time.time() - t0:.0f}s")


#: ``--pool jpp``: centres refitted on the J++ evals' own fit split (80 items, never scored); see ``jpp_pool``
POOL_ARMS = ("ref", "loo", "knn8", "knn8e", "km8", "T:ref+knn8", "T:km8+knn8", "S14b-knnxs8∪", "s20x-jpp", "s20xon-jpp")
#: our-pool arm (Part A) -> its J++-pool counterpart, for the cross-pool paired differences
CROSS = [("fam", "ref"), ("S14b-knnxs8", "T:km8+knn8"), ("S14b-knnxs8", "S14b-knnxs8∪"), ("S20x", "s20x-jpp"),
         ("s20xon", "s20xon-jpp")]
SPLIT_LAYER = 40
TOP10 = 10


def s20_const(lens: Lens, L: int, readout: str, H: torch.Tensor, targets: list[list[int]], steps: int,
              dev: str) -> torch.Tensor:
    """S20's ``ceil.const`` (``experiments/ceilings.py``: ``fit_layer``, class const, its defaults) on cells ``H`` with
    ``targets`` per cell: one g minimising softplus((10th competitor - best target) / tau) over a candidate vocabulary
    (each cell's top 64 under zero and under the mean, plus every target), L2 toward 0 (1e-3), Adam, init the mean."""
    import torch.nn.functional as F

    H = H.to(dev)
    fam = H.mean(0)
    counts = torch.zeros(lens.vocab, dtype=torch.long, device=dev)
    for X in (H, H - fam):
        counts += torch.bincount(lens.scores(X, L, readout).topk(64, dim=1).indices.flatten(), minlength=lens.vocab)
    acc = torch.tensor(sorted({t for ts in targets for t in ts}), device=dev)
    counts[acc] = 0
    k = min(32768 - len(acc), int((counts > 0).sum()))
    cand = torch.cat([acc, counts.topk(k).indices])
    Wc = lens.w_u[cand].float() * (lens.gain if readout == "rms" else 1)
    if not lens.identity:
        Wc = Wc @ lens.jac[L]
    if readout == "cos":
        Wc = Wc / lens.denom[L][cand, None]
    pos = {int(t): j for j, t in enumerate(cand.tolist())}
    tmask = torch.zeros(len(H), len(cand), dtype=torch.bool, device=dev)
    for j, ts in enumerate(targets):
        tmask[j, [pos[t] for t in ts]] = True
    mu = torch.nn.Parameter(fam.clone())
    opt = torch.optim.Adam([mu], lr=0.02 * H.norm(dim=1).mean().item() / H.shape[1] ** 0.5)
    with torch.no_grad():
        tau = 0.05 * (H @ Wc.T).std().item()
    for _ in range(steps):
        opt.zero_grad()
        S = (H - mu) @ Wc.T
        best = S.masked_fill(~tmask, float("-inf")).max(1).values
        comp = S.masked_fill(tmask, float("-inf")).topk(TOP10, dim=1).values[:, -1]
        loss = F.softplus((comp - best) / tau).mean() + 1e-3 * (mu**2).sum() / (H**2).sum()
        loss.backward()
        opt.step()
    return mu.detach().cpu()


def jpp_pool(a, root: Path, dev: str, R, meta, cands, items, by_fam, lenses, ranks, recall, delta) -> None:
    """The finalists refitted on the J++ evals' own fit split (80 items, ``split == "fit"``, never scored).

    - ``ref``: the eval's fit-split mean (umot's). ``loo``: the mean of every OTHER item of the eval, scored ones
      included (transductive, no targets; x100's loo1).
    - ``knn8``: the mean of the 8 nearest J++ fit cells (all evals pooled; knnx's centred unit space, own item out);
      ``knn8e``: the same eval's fit cells only. ``km8``: k-means 8 on the pooled J++ fit cells (clusters.ClusterMean's
      geometry), the raw mean of h's cluster, own item out.
    - ``T:<early>+knn8``: S14b / S14bL's form, ``sched:40``: early (ref or km8) up to L40, above it the template
      projection of ``h - 0.5 * g_knn8`` (S14's J-lens template basis). S14bL's language exclusion is moot here (the J++
      fit cells are English, bar 5 association / multilingual items in other Latin languages), so S14b = S14bL.
    - ``S14b-knnxs8∪``: S14b-knnxs8 with its bench pool (kmx64 and knnxs8) the union of our fit pool and the J++ fit cells.
    - ``s20x-jpp``: S20x's estimator refitted here, leave-one-eval-out: per eval G, S20's const g_G fitted on G's fit
      cells with their candidate ids as targets, ``d_G = g_G - ref_G``; reading F: ``h - ref_F - mean_{G != F} d_G``.
      Fitted per map and readout (map-matched; S20x's own corrections are J-lens only). ``s20xon-jpp``: on km8.
    - ``rand.<arm>``: the best two new arms (J-lens rms macro) with g replaced by a per-layer random direction of ||g||.
    """
    from jlm import pullback
    from jlm.mu import clusters

    t0 = time.time()
    n = len(meta)
    ev = [m["eval"] for m in meta]
    split = [m["split"] for m in meta]
    fit = [p for p in range(n) if split[p] == "fit"]
    fit_of = {e: [p for p in fit if ev[p] == e] for e in EVALS}
    all_of = {e: [p for p in range(n) if ev[p] == e] for e in EVALS}
    fit_t = torch.tensor(fit)
    tb = {L: pullback.load_tbasis(pullback.default_key(), "cos", "template", 64, L).float() for L in GRID if L > SPLIT_LAYER}

    def ref(L):
        H = R[L]
        X = torch.empty_like(H)
        for e in EVALS:
            X[all_of[e]] = H[all_of[e]] - H[fit_of[e]].mean(0)
        return X

    def loo(L):
        H = R[L]
        X = torch.empty_like(H)
        for e in EVALS:
            rows = all_of[e]
            S = H[rows].double().sum(0)
            X[rows] = H[rows] - ((S - H[rows].double()) / (len(rows) - 1)).float()
        return X

    def knn(L, same_eval=False, k=8):
        H, P = R[L], R[L][fit_t]
        U, c = clusters.unit_space(P)
        sims = clusters.unit_space(H, c)[0] @ U.T
        sims[fit_t, torch.arange(len(fit))] = -torch.inf  # own item out
        if same_eval:
            other = torch.tensor([[ev[q] != ev[p] for q in fit] for p in range(n)])
            sims[other] = -torch.inf
        return H - P[sims.topk(k, dim=1).indices].mean(1)

    km_fits = {}

    def km8(L):
        H, P = R[L], R[L][fit_t]
        if L not in km_fits:
            U, c = clusters.unit_space(P)
            C, labels = clusters.kmeans(U, 8, 0)
            km_fits[L] = (C, labels, c)
        C, labels, c = km_fits[L]
        assign = torch.cdist(clusters.unit_space(H, c)[0], C).argmin(1)
        G = torch.empty_like(H)
        own = {p: j for j, p in enumerate(fit)}
        for p in range(n):
            m = labels == assign[p]
            if p in own:
                m[own[p]] = False
            if not m.any():
                m = torch.ones(len(fit), dtype=torch.bool)
                if p in own:
                    m[own[p]] = False
            G[p] = P[m].double().mean(0).float()
        return H - G

    def template(early, L):
        if L <= SPLIT_LAYER:
            return early(L)
        H = R[L]
        X = H - 0.5 * (H - knn(L))
        return X - (X @ tb[L]) @ tb[L].T

    union = union_states(R, items, by_fam, fit_of, all_of)
    log(f"pool-jpp: union pool states ({time.time() - t0:.0f}s)")

    # S20x refit, leave-one-eval-out, per map and readout
    targets = {p: sorted({t for ids in cands[p].values() for t in ids}) for p in fit}
    dbar: dict = {}
    t1 = time.time()
    for m in MAPS:
        for ro in READOUTS:
            for L in GRID:
                H = R[L]
                d = {e: s20_const(lenses[m], L, ro, H[fit_of[e]], [targets[p] for p in fit_of[e]], a.s20_steps, dev)
                     - H[fit_of[e]].mean(0) for e in EVALS}
                for e in EVALS:
                    dbar[(m, ro, L, e)] = torch.stack([d[g] for g in EVALS if g != e]).mean(0)
    log(f"pool-jpp: S20x refit ({time.time() - t1:.0f}s)")

    def s20(base, m, ro, L):
        X = base(L).clone()
        for e in EVALS:
            X[all_of[e]] -= dbar[(m, ro, L, e)]
        return X

    arms = {
        "ref": lambda m, ro, L: ref(L),
        "loo": lambda m, ro, L: loo(L),
        "knn8": lambda m, ro, L: knn(L),
        "knn8e": lambda m, ro, L: knn(L, same_eval=True),
        "km8": lambda m, ro, L: km8(L),
        "T:ref+knn8": lambda m, ro, L: template(ref, L),
        "T:km8+knn8": lambda m, ro, L: template(km8, L),
        "S14b-knnxs8∪": lambda m, ro, L: union[L],
        "s20x-jpp": lambda m, ro, L: s20(ref, m, ro, L),
        "s20xon-jpp": lambda m, ro, L: s20(km8, m, ro, L),
    }
    scores, rk = {}, {}

    def score(label, fn):
        for ro in READOUTS:
            for m in MAPS:
                Rk = torch.stack([ranks(fn(m, ro, L).to(dev), lenses[m], L, ro) for L in GRID], 1)
                key = f"{m}|{label}|{ro}|grid11"
                scores[key], rk[key] = recall(Rk), Rk
                log("pool-jpp", key, round(scores[key]["macro"], 4), round(scores[key]["macro4"], 4))

    score("zero", lambda m, ro, L: R[L])
    for label, fn in arms.items():
        score(label, fn)
    learned = [x for x in arms if x not in ("ref", "loo")]
    best2 = sorted(learned, key=lambda x: -scores[f"jlens|{x}|rms|grid11"]["macro"])[:2]
    for label in best2:
        def rand(m, ro, L, fn=arms[label]):
            H = R[L]
            u = torch.randn(H.shape[1], generator=torch.Generator().manual_seed(L))
            return H - (H - fn(m, ro, L)).norm(dim=1, keepdim=True) * (u / u.norm())
        score(f"rand.{label}", rand)

    diffs = {}
    labels = list(arms) + [f"rand.{x}" for x in best2]
    for m in MAPS:
        for ro in READOUTS:
            z, f = f"{m}|zero|{ro}|grid11", f"{m}|ref|{ro}|grid11"
            for label in labels:
                k = f"{m}|{label}|{ro}|grid11"
                diffs[f"{k} - zero"] = delta(rk[k], rk[z])
                if label != "ref":
                    diffs[f"{k} - ref"] = delta(rk[k], rk[f])
                if m == "jlens":
                    diffs[f"{k} - jpp|zero|{ro}|grid11"] = delta(rk[k], rk[f"jpp|zero|{ro}|grid11"])
    cross = {}
    if (root / "ranks.pt").exists():  # Part A (our pool): the same arm on the J++ pool minus it on ours
        ours = torch.load(root / "ranks.pt", weights_only=False)
        for o, j in CROSS:
            for m in MAPS:
                for ro in READOUTS:
                    ko, kj = f"{m}|{o}|{ro}|grid11", f"{m}|{j}|{ro}|grid11"
                    if ko in ours:
                        cross[f"{kj} - ours:{o}"] = delta(rk[kj], ours[ko].long())
    prov = Provenance(model=MODEL, model_revision=PINS[MODEL], reader=reader("jlens")[0], reader_revision=reader("jlens")[1],
                      dataset=f"jpp_lens readout evals @ {JPP_COMMIT} (umot/out/jpp)",
                      extra={"pool": "J++ fit split", "fit_items": len(fit), "grid": GRID, "arms": labels, "rand_of": best2,
                             "s20_steps": a.s20_steps, "draws": DRAWS, "limit": a.limit})
    write_artefact(root / "pool-jpp.json", prov, {"scores": scores, "diffs": diffs, "cross": cross})
    torch.save({k: v.int() for k, v in rk.items()}, root / "ranks-pool-jpp.pt")
    write_pool_section(root / "summary.md", scores, diffs, cross, labels, len(fit))
    log(f"pool-jpp done ({time.time() - t0:.0f}s)")


def union_states(R, items, by_fam, fit_of: dict[str, list[int]], all_of: dict[str, list[int]]) -> dict[int, torch.Tensor]:
    """S14b-knnxs8 with its bench pool the union of our fit pool and the J++ fit cells (``S14b-knnxs8∪``), states at GRID.
    A J++ fit cell's carrier is its last 6 tokens."""
    from jlm.mu import S16, clusters

    bench = clusters.Pool.bench_fit()
    car = S16._bench_carriers(bench)
    parts = [clusters.Pool.of_items([items[p] for p in fit_of[e]], e) for e in EVALS if fit_of[e]]
    X = {L: torch.cat([bench.X[L]] + [pp.X[L].float() for pp in parts]) for L in GRID}
    cat = lambda f: [x for pp in [bench, *parts] for x in getattr(pp, f)]
    union = clusters.Pool(X, cat("groups"), cat("fams"), cat("toks"), cat("words"))
    union.carriers = car + [(None, tuple(items[p].decoded[max(0, items[p].idx[0] - 5): items[p].idx[0] + 1]))
                            for e in EVALS for p in fit_of[e]]
    saved = clusters._POOLS.pop(("bench",), None)
    clusters._POOLS[("bench",)] = union
    for key in [k for k in clusters._FITS if k[0] == ("bench",)]:
        clusters._FITS.pop(key)
    name = f"sched:40:kmx64+{B.format('knnxs8')}"
    refs = fit_refs()
    out = {L: torch.empty_like(R[L]) for L in GRID}
    for e in EVALS:
        its = by_fam[e]
        fam = e if e in MAPPED else "poetry"
        c = centres.make(name)
        c.fit(refs[fam], fam)
        rows = [all_of[e][j] for j in range(len(its))]
        for L in GRID:
            out[L][rows] = centres.apply(c, Batch(L, cell_refs(its, e, L), R[L][rows], {it.id: it for it in its}))
    clusters._POOLS.pop(("bench",))
    if saved is not None:
        clusters._POOLS[("bench",)] = saved
    for key in [k for k in clusters._FITS if k[0] == ("bench",)]:
        clusters._FITS.pop(key)
    return out


POOL_MARK = "<!-- pool-jpp results -->"
POOL_HEAD = "## Pool = the J++ evals' own fit split"


def write_pool_section(path: Path, scores: dict, diffs: dict, cross: dict, labels: list[str], n_fit: int) -> None:
    def ci(v):
        return f"{v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]" if v else ""

    out = [POOL_MARK, "", (f"Pool: the J++ evals' own fit split ({n_fit} items, never scored); held-out recall@10, grid11, "
                           "Readout Filtering. See `jpp_pool`'s docstring for each arm; `s20x-jpp` is fitted per map and readout."), ""]
    for ro in READOUTS:
        out += [f"### {ro}", "", "| arm | map | macro | macro4 | " + " | ".join(EVALS)
                + " | Δ plain same map | Δ ref | Δ plain J++ |", "|---" * (7 + len(EVALS)) + "|"]
        for label in ["zero"] + labels:
            for m in MAPS:
                k = f"{m}|{label}|{ro}|grid11"
                v = scores[k]
                out.append(f"| {label} | {m} | {v['macro']:.3f} | {v['macro4']:.3f} | " + " | ".join(f"{v[e]:.3f}" for e in EVALS)
                           + f" | {ci(diffs.get(f'{k} - zero', {}).get('macro'))} | {ci(diffs.get(f'{k} - ref', {}).get('macro'))}"
                           + f" | {ci(diffs.get(f'{k} - jpp|zero|{ro}|grid11', {}).get('macro'))} |")
        out.append("")
    if cross:
        out += ["### The same arm on the J++ pool minus on our pool (macro / macro4)", "", "| pair | macro | macro4 |", "|---|---|---|"]
        out += [f"| {k} | {ci(v['macro'])} | {ci(v['macro4'])} |" for k, v in cross.items()]
    text = path.read_text() if path.exists() else ""
    text = text.split(POOL_MARK)[0].rstrip() + "\n\n" + "\n".join(out) + "\n"
    path.write_text(text)


def summary(scores: dict, diffs: dict, labels: list[str], off: int) -> str:
    def ci(v):
        return f"{v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]"

    out = ["# Our finalist centres on the J++ readout evals (held-out recall@10, Readout Filtering)", "",
           "Layers: arms on our grid ∩ [8, 56] (20..56, 11 layers); `recipe7` = the paper's 8..56 step 8. macro = 5 evals,",
           "macro4 = without poetry (no WorkspaceBench counterpart). S14 bases and S20x corrections are the J-lens's, reused",
           f"through J++. {off} items with an approximate context tail. Intervals: paired bootstrap, items within eval.", "",
           "## Uncentred maps (parity: J++ rms recipe7 0.594, n1000 0.340)", "",
           "| map | readout | layers | macro | macro4 | " + " | ".join(EVALS) + " |", "|---" * (5 + len(EVALS)) + "|"]
    for k, v in scores.items():
        m, label, ro, tag = k.split("|")
        if label == "zero":
            out.append(f"| {m} | {ro} | {tag} | {v['macro']:.3f} | {v['macro4']:.3f} | " + " | ".join(f"{v[e]:.3f}" for e in EVALS) + " |")
    for ro in READOUTS:
        out += ["", f"## Arms, {ro}", "",
                "| arm | map | macro | macro4 | " + " | ".join(EVALS) + " | Δ zero (macro) | Δ fam (macro) | Δ fam (macro4) | Δ vs plain J++ (macro) |",
                "|---" * (8 + len(EVALS)) + "|"]
        for label in labels:
            for m in MAPS:
                k = f"{m}|{label}|{ro}|grid11"
                if k not in scores:
                    continue
                v = scores[k]
                dz, df = diffs.get(f"{k} - zero"), diffs.get(f"{k} - fam")
                dj = diffs.get(f"{k} - jpp|zero|{ro}|grid11")
                out.append(f"| {label} | {m} | {v['macro']:.3f} | {v['macro4']:.3f} | " + " | ".join(f"{v[e]:.3f}" for e in EVALS)
                           + f" | {ci(dz['macro']) if dz else ''} | {ci(df['macro']) if df else ''} | {ci(df['macro4']) if df else ''}"
                           + f" | {ci(dj['macro']) if dj else ''} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
