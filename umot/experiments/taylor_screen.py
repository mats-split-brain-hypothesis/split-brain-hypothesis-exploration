"""Taylor-point J-lens screen (free, no judge): read ``W_U (β c + J_l (h − μ_l))`` instead of the
centred ``W_U J_l (h − μ_l)``.

First-order expansion of the map f_l from the layer-l residual to the final (pre-norm) residual
around the centre μ_l: ``f_l(h) ≈ f_l(μ_l) + J_l (h − μ_l)``, and to first order f_l(μ_l) ≈ μ_L,
the mean final residual over the same cells. Constants ``c``:

  ``Jmu``  J_l μ_l: with β = 1 this is exactly the uncentred J-lens (J_l h = J_l μ_l + J_l δ)
  ``mul``  μ_l, the layer-l centre itself (logit lens of the mean; the wrong space, kept as asked)
  ``muL``  μ_63, the final-residual centre: the actual Taylor constant (needs the side capture
           ``out/captures/<family>-final.pt``, layer 63; skipped without it)

β scales the constant against the first-order term (β = 0 is the centred J-lens). Ranks are
invariant to a positive scale of x, so β = 1/4 is the same as 4× the J term. Two readouts: the
bench's cosine ``(W_U x)_t / ‖J_lᵀ W_U[t]‖`` and ``rms`` (the final RMSNorm then W_U; for ranks the
norm's per-row scalar drops out, leaving the ``1 + w`` gain). The centre is the leave-one-out family
centre (``fam``) at every layer, 63 included, so μ_l and μ_63 exclude the item and its concept.

Per item, cell, layer, arm: the full-vocabulary rank of the concept (best of its tokens, as
``mc_screen``) and the top-10 tokens. With the final capture, a linearisation diagnostic per layer:
‖h_63 − (μ_63 + J_l δ)‖ / ‖h_63 − μ_63‖ and the top-1 agreement of each readout with the model's
own next-token prediction ``argmax W_U norm(h_63)``.

  python experiments/taylor_screen.py --family directed_modulation          # -> out/taylor/
  python experiments/taylor_screen.py --family directed_modulation --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from m1_run import MODEL, OUT_DEFAULT, TOKEN_FILES, jlens_denominator  # noqa: E402
from mc_screen import word_tokens  # noqa: E402
from token_local import build_centres, load_jacobians, load_norm, load_unembed  # noqa: E402

from umot import capture  # noqa: E402
from umot.provenance import PINS, REPO_ROOT, Provenance, write_artefact  # noqa: E402

FINAL = 63  # output of the last decoder block, before the final norm: the J-lens target
BETAS = (1.0, 0.25, 0.0625)


def arms(have_final: bool) -> list[tuple[str, str | None, float]]:
    """(name, constant, β); the centred arm is the β = 0 reference."""
    out = [("ctr", None, 0.0)]
    for c in ("Jmu", "mul", *(("muL",) if have_final else ())):
        out += [(f"{c}-b{b:g}", c, b) for b in BETAS]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", default="directed_modulation")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    torch.set_float32_matmul_precision("highest")
    from transformers import AutoTokenizer
    from wsbench.produce.render import display_tokens

    items = capture.load(OUT_DEFAULT / "captures" / f"{args.family}.pt")
    side = OUT_DEFAULT / "captures" / f"{args.family}-final.pt"
    have_final = side.exists()
    if have_final:
        fin = {it.id: it for it in capture.load(side)}
        for it in items:
            assert fin[it.id].idx == it.idx, f"{it.id}: side capture cells differ"
            it.acts[FINAL] = fin[it.id].acts[FINAL]
    centre = build_centres(items, args.family)["fam"]  # before --limit: same centres as a full run
    items = items[: args.limit or None]
    layers = sorted({L for it in items for L in it.acts} - {FINAL})
    bank = json.loads((REPO_ROOT / "third_party/workspace-bench/evals" / args.family / "items.json").read_text())
    bank = {b["name"]: b for b in (bank["items"] if isinstance(bank, dict) else bank)}

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    dev = args.device
    w_u = load_unembed(MODEL).float().to(dev)
    gain = (1 + load_norm(MODEL)).float().to(dev)
    jac = load_jacobians(layers)
    denom = {L: jlens_denominator(w_u, jac[L].to(dev)) for L in layers}
    print(f"lens ready ({time.time() - t0:.0f}s), final capture: {have_final}", flush=True)
    arm_list = arms(have_final)

    rows, diag = [], []
    for n, it in enumerate(items):
        b = bank[it.id]
        forms = {b["concept"], b["concept"].lower()} | {
            m for u in b.get("units", []) if u.get("role") == "concept" for m in u["match"]
        }
        tc = word_tokens(tok, forms)  # empty for concepts split into short fragments: no rank
        npos = len(it.positions)
        if have_final:
            hL = it.acts[FINAL].float().to(dev)
            muL = torch.stack([centre(it, FINAL, i) for i in range(npos)]).to(dev)
            model_top1 = ((gain * hL) @ w_u.T).argmax(1)
        for L in layers:
            J = jac[L].to(dev)
            h = it.acts[L].float().to(dev)
            mu = torch.stack([centre(it, L, i) for i in range(npos)]).to(dev)
            parts = {"d": (h - mu) @ J.T, "Jmu": mu @ J.T, "mul": mu}
            if have_final:
                parts["muL"] = muL
            # logits are linear in x, so score each part once and combine per arm
            sc = {
                (ro, k): ((v * gain) @ w_u.T if ro == "rms" else (v @ w_u.T) / denom[L])
                for ro in ("cos", "rms")
                for k, v in parts.items()
            }
            for ro in ("cos", "rms"):
                for name, c, beta in arm_list:
                    s = sc[ro, "d"] + (beta * sc[ro, c] if c else 0)
                    if tc:
                        ranks = (s > s[:, tc].max(1, keepdim=True).values).sum(1).tolist()
                    else:
                        ranks = [None] * npos
                    top = torch.topk(s, 10).indices.tolist()
                    agree = (s.argmax(1) == model_top1).tolist() if have_final else [None] * npos
                    for i in range(npos):
                        rows.append({
                            "id": it.id, "polarity": b["polarity"], "layer": L, "i": i,
                            "readout": ro, "arm": name, "rank": ranks[i], "agree": agree[i],
                            "top": display_tokens(tok, top[i]),
                        })
            if have_final:
                dL = hL - muL
                lin = (hL - muL - parts["d"]).norm(dim=1) / dL.norm(dim=1)
                unc = (hL - h @ J.T).norm(dim=1) / hL.norm(dim=1)
                for i in range(npos):
                    diag.append({
                        "id": it.id, "layer": L, "i": i, "rel_err_taylor": lin[i].item(),
                        "rel_err_uncentred": unc[i].item(),
                        "norm_Jd": parts["d"][i].norm().item(), "norm_muL": muL[i].norm().item(),
                        "norm_mul": mu[i].norm().item(), "norm_Jmu": parts["Jmu"][i].norm().item(),
                    })
            else:
                for i in range(npos):
                    diag.append({
                        "id": it.id, "layer": L, "i": i, "norm_Jd": parts["d"][i].norm().item(),
                        "norm_mul": mu[i].norm().item(), "norm_Jmu": parts["Jmu"][i].norm().item(),
                    })
        if n % 10 == 0:
            print(f"  {n}/{len(items)} ({time.time() - t0:.0f}s)", flush=True)

    sfx = f"-limit{args.limit}" if args.limit else ""
    dest = Path(args.out) / "taylor" / f"{args.family}{sfx}.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    dest.with_name(f"{args.family}{sfx}-diag.jsonl").write_text("".join(json.dumps(r) + "\n" for r in diag))
    write_artefact(
        dest.with_suffix(".provenance.json"),
        Provenance(
            model=MODEL, model_revision=PINS[MODEL], reader=TOKEN_FILES["jlens"][0],
            reader_revision=PINS[TOKEN_FILES["jlens"][0]], dataset=f"wsbench/{args.family}",
            extra={
                "readout": {"cos": "(W_U x)_t / ‖J_lᵀ W_U[t]‖", "rms": "W_U ((1+w) ⊙ x), rank-equivalent to the final RMSNorm"},
                "x": "J_l (h − μ_l) + β c",
                "centre": "fam: leave-one-out family mean (excl. the item and items sharing its concept), per layer",
                "arms": {a: [c, beta] for a, c, beta in arm_list},
                "final_capture": str(side) if have_final else None,
                "limit": args.limit, "device": dev,
            },
        ),
        {"cells": len(rows), "layers": layers, "seconds": round(time.time() - t0, 1)},
    )
    print(f"-> {dest}")
    summarise(rows, diag)


def summarise(rows: list[dict], diag: list[dict]) -> None:
    """Per readout, arm and polarity: share of items with the concept in the top 10 at any cell
    (all layers, and L>=40), the median best rank (items whose concept has a clean first token only), and (with the final capture) top-1 agreement
    with the model's own prediction."""
    best: dict = defaultdict(lambda: [10**9, 10**9])
    agree: dict = defaultdict(list)
    for r in rows:
        if r["agree"] is not None:
            agree[r["readout"], r["arm"]].append(r["agree"])
        if r["rank"] is None:
            continue
        v = best[r["readout"], r["arm"], r["polarity"], r["id"]]
        v[0] = min(v[0], r["rank"])
        if r["layer"] >= 40:
            v[1] = min(v[1], r["rank"])
    groups: dict = defaultdict(list)
    for (ro, arm, pol, _), v in best.items():
        groups[ro, arm, pol].append(v)
    print(f"\n{'readout':7s} {'arm':12s} {'polarity':10s} {'n':>3s}  top10  top10@L40+  med.rank  agree")
    for (ro, arm, pol), vs in sorted(groups.items()):
        ranks = sorted(v[0] for v in vs)
        f = lambda k: sum(v[k] < 10 for v in vs) / len(vs)  # noqa: E731
        a = agree.get((ro, arm))
        ag = f"{sum(a) / len(a):.2f}" if a else "-"
        print(f"{ro:7s} {arm:12s} {pol:10s} {len(vs):3d}  {f(0):5.2f}  {f(1):10.2f}  {ranks[len(ranks) // 2]:8d}  {ag:>5s}")

    by_layer: dict = defaultdict(lambda: defaultdict(list))
    for d in diag:
        for k, v in d.items():
            if k not in ("id", "layer", "i"):
                by_layer[d["layer"]][k].append(v)
    keys = [k for k in diag[0] if k not in ("id", "layer", "i")]
    print("\nper layer, mean over cells: " + "  ".join(keys))
    for L, kv in sorted(by_layer.items()):
        print(f"L{L:<3d} " + "  ".join(f"{sum(kv[k]) / len(kv[k]):10.3f}" for k in keys))


if __name__ == "__main__":
    main()
