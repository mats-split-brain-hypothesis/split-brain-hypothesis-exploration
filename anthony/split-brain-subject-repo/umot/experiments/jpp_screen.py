"""J++ vs J-lens on our captures (free, local): does the concept's rank separate hold / mention / suppress?

``mc_screen.py`` generalised over lens maps and readouts. For every captured cell of ``mention_control``
or ``directed_modulation``, every centre (``token_local``'s, as mc_screen's arms) and every lens map
(``jlens`` = the bench's neuronpedia lens, ``jpp`` = koayon/jpp-lenses, ``rlens`` = the bench's R-lens),
the full-vocabulary rank of the item's concept X (and, in mention_control, its paired word Y) is kept,
under the bench's cosine readout and the rms readout (the final norm's gain then W_U; J++'s own), each
with and without J++'s Readout Filtering (tokens with no letter or digit left out of the ranking).

The J++ paper's Figure 5 (focus / neutral mention / suppress / none) maps onto mention_control's
hold / mention / (no suppress) / absent and directed_modulation's think / (suppress, dont_think).

  python experiments/jpp_screen.py --family mention_control --device mps
  python experiments/jpp_screen.py --family directed_modulation --device mps
  python experiments/jpp_screen.py --family mention_control --limit 9 --lenses jpp   # plumbing
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
from m1_run import MODEL, OUT_DEFAULT, TOKEN_FILES  # noqa: E402
from mc_screen import word_tokens  # noqa: E402
from token_local import build_centres, load_norm, load_unembed  # noqa: E402

from umot import capture  # noqa: E402
from umot import mention_control as mc  # noqa: E402
from umot.provenance import PINS, REPO_ROOT, Provenance, write_artefact  # noqa: E402

VOCAB_CHUNK = 32768
LENS_FILES = {**TOKEN_FILES, "jpp": ("koayon/jpp-lenses", "qwen3.6-27b/lens.pt")}
#: arm -> (centre, keep): mc_screen's arms.
ARMS = {
    "none": (None, None),
    "ctr-loo": ("fam", None),
    "ctr-tok": ("tok", None),
    "ctr-stop": ("tok", "last"),
    "ctr-carpos": ("carpos", None),
}
READOUTS = ("cos", "rms")


def load_lens(name: str, layers: list[int]) -> dict[int, torch.Tensor]:
    """fp32 J_l (out, in) at ``layers`` for ``h @ J.T``, memory-mapped (the fp32 stacks are 6.6 GB)."""
    from huggingface_hub import hf_hub_download

    repo, fn = LENS_FILES[name]
    obj = torch.load(hf_hub_download(repo, fn, revision=PINS[repo]), map_location="cpu", weights_only=False, mmap=True)
    jac = obj["parameters"]["jacobians"] if "parameters" in obj else obj["J"] if "J" in obj else obj["jacobians"]
    get = (lambda L: jac[L] if L in jac else jac[str(L)]) if isinstance(jac, dict) else jac.__getitem__
    return {L: get(L).float().clone() for L in layers}


def non_semantic_mask(tok, vocab: int) -> torch.Tensor:
    """J++'s Readout Filtering: ids whose decoded string has no letter or digit (padding rows included)."""
    return torch.tensor([not any(ch.isalnum() for ch in tok.decode([i])) for i in range(vocab)])


def bank_rows(family: str) -> tuple[dict, dict]:
    """(per item: condition, X, Y), concept -> accepted forms (the DM bank's concept units)."""
    dm = {b["concept"]: b for b in json.loads(mc.BENCH_BANK.read_text())["items"]}
    forms = {c: {c.lower(), c} | {m for u in b.get("units", []) if u.get("role") == "concept" for m in u["match"]}
             for c, b in dm.items()}
    if family == "directed_modulation":
        rows = json.loads((REPO_ROOT / "third_party/workspace-bench/evals/directed_modulation/items.json").read_text())["items"]
        return {b["name"]: {"cond": b["polarity"], "x": b["concept"], "y": None} for b in rows}, forms
    bank = mc.load(family)
    y_of = {it["pair_id"]: it["mentioned"] for it in bank if it["condition"] == "holdmention"}
    return {it["id"]: {"cond": f"{it['condition']}/{it['where']}", "x": it["concept"], "y": y_of.get(it["pair_id"])}
            for it in bank}, forms


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True, choices=["mention_control", "directed_modulation"])
    ap.add_argument("--lenses", default="jlens,jpp")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    from transformers import AutoTokenizer

    bank, forms = bank_rows(args.family)
    items = capture.load(OUT_DEFAULT / "captures" / f"{args.family}.pt")
    layers = sorted({L for it in items for L in it.acts})
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    t0 = time.time()

    # Pass 1 (CPU): centred states per arm, spilled to disk (mc_screen's memory plan).
    centres = build_centres(items, args.family)
    out_dir = Path(args.out) / "jpp-screen"
    spill = out_dir / f"{args.family}-states"
    spill.mkdir(parents=True, exist_ok=True)
    meta = []  # (id, layer, i, X ids, Y ids)
    for it in items[: args.limit or None]:
        b = bank[it.id]
        tx = word_tokens(tok, forms[b["x"]])
        ty = word_tokens(tok, forms[b["y"]]) if b["y"] else []
        for L in layers:
            meta += [(it.id, L, i, tx, ty) for i in range(it.acts[L].shape[0])]
    by_item = {it.id: it for it in items}
    last = {}
    for i, _L, j, _, _ in meta:
        last[i] = max(last.get(i, 0), j)
    for arm, (centre, _keep) in ARMS.items():
        h = torch.stack([by_item[i].acts[L][j].float() - (centres[centre](by_item[i], L, j) if centre else 0)
                         for i, L, j, _, _ in meta])
        torch.save(h, spill / f"{arm}.pt")
    print(f"centred states: {len(meta)} cells x {len(ARMS)} arms ({time.time() - t0:.0f}s)", flush=True)
    del centres, h, items, by_item

    w_u = load_unembed(MODEL).to(args.device)  # bf16; cast per chunk
    V = w_u.shape[0]
    chunks = [(a, min(a + VOCAB_CHUNK, V)) for a in range(0, V, VOCAB_CHUNK)]
    gain = (1 + load_norm(MODEL).float()).to(args.device)
    excl = non_semantic_mask(tok, V).to(args.device)
    print(f"unembed ready; {int(excl.sum())} non-semantic ids ({time.time() - t0:.0f}s)", flush=True)

    def pad(ids: list[list[int]]) -> torch.Tensor:
        w = max(len(t) for t in ids)
        return torch.tensor([t + t[:1] * (w - len(t)) for t in ids], device=args.device)

    def ranks(s: torch.Tensor, ks: list[int], col: int) -> list[int | None]:
        ok = [n for n, k in enumerate(ks) if meta[k][col]]
        r: list[int | None] = [None] * len(ks)
        if ok:
            best = s[ok].gather(1, pad([meta[ks[n]][col] for n in ok])).max(1, keepdim=True).values
            for n, v in zip(ok, (s[ok] > best).sum(1).tolist(), strict=True):
                r[n] = v
        return r

    rows = []
    for lens in args.lenses.split(","):
        jac = load_lens(lens, layers)
        for L in layers:
            J = jac.pop(L).to(args.device)
            denom = torch.cat([(w_u[a:b].float() @ J).norm(dim=1) for a, b in chunks]).clamp_min(1e-9)
            for arm, (_c, keep) in ARMS.items():
                h = torch.load(spill / f"{arm}.pt", mmap=True)
                sel = [k for k, m in enumerate(meta) if m[1] == L and (keep != "last" or m[2] == last[m[0]])]
                for c in range(0, len(sel), args.batch):
                    ks = sel[c : c + args.batch]
                    z = h[ks].to(args.device) @ J.T
                    for ro in READOUTS:
                        zz = z * gain if ro == "rms" else z
                        s = torch.cat([zz @ w_u[a:b].float().T for a, b in chunks], 1)
                        if ro == "cos":
                            s = s / denom
                        rx, ry = ranks(s, ks, 3), ranks(s, ks, 4)
                        s = s.masked_fill(excl, float("-inf"))
                        rxf, ryf = ranks(s, ks, 3), ranks(s, ks, 4)
                        for n, k in enumerate(ks):
                            rows.append({"id": meta[k][0], "lens": lens, "arm": arm, "readout": ro, "layer": L,
                                         "i": meta[k][2], "rx": rx[n], "ry": ry[n], "rxf": rxf[n], "ryf": ryf[n]})
            del J
            print(f"  {lens} L{L} ({time.time() - t0:.0f}s)", flush=True)

    dest = out_dir / f"{args.family}{f'-limit{args.limit}' if args.limit else ''}.jsonl"
    dest.write_text("".join(json.dumps(r) + "\n" for r in rows))
    lenses = args.lenses.split(",")
    write_artefact(
        dest.with_suffix(".provenance.json"),
        Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"umot/{args.family}",
                   extra={"lenses": {n: [*LENS_FILES[n], PINS[LENS_FILES[n][0]]] for n in lenses},
                          "readouts": {"cos": "bench cosine", "rms": "(1+w) * J h then W_U (rank-equivalent to the final norm)"},
                          "filter": "rxf/ryf: ids with no letter or digit excluded (J++ Readout Filtering)",
                          "arms": {a: list(v) for a, v in ARMS.items()}, "limit": args.limit}),
        {"cells": len(rows), "layers": layers, "seconds": round(time.time() - t0, 1)},
    )
    print(f"-> {dest}")
    summarise(rows, bank)


def summarise(rows: list[dict], bank: dict) -> None:
    """Per lens / arm / readout / condition: share of items with X (Y) in the top 10 at any cell and layer,
    and at L >= 42; filtered ranks."""
    best: dict = defaultdict(lambda: [10**9] * 4)
    for r in rows:
        v = best[r["lens"], r["arm"], r["readout"], r["id"]]
        rx, ry = (10**9 if x is None else x for x in (r["rxf"], r["ryf"]))
        v[0], v[1] = min(v[0], rx), min(v[1], ry)
        if r["layer"] >= 42:
            v[2], v[3] = min(v[2], rx), min(v[3], ry)
    groups: dict = defaultdict(list)
    for (lens, arm, ro, i), v in best.items():
        groups[lens, arm, ro, bank[i]["cond"]].append(v)
    print(f"{'lens':6s} {'arm':11s} {'ro':4s} {'condition':24s} {'n':>3s}  X top10  Y top10  X@L42+  Y@L42+")
    for (lens, arm, ro, cond), vs in sorted(groups.items()):
        f = lambda k, vs=vs: sum(v[k] < 10 for v in vs) / len(vs)  # noqa: E731
        print(f"{lens:6s} {arm:11s} {ro:4s} {cond:24s} {len(vs):3d}  {f(0):7.2f}  {f(1):7.2f}  {f(2):6.2f}  {f(3):6.2f}")


if __name__ == "__main__":
    main()
