"""Mention-control screen (free, no judge): does a (centred) J-lens read what the model HOLDS or what
the prompt MENTIONS?

For every captured cell of ``mention_control`` and every centre, the full J-lens readout (the bench's
cosine) is computed and the best rank of the item's concept X and of its paired word Y (the word
mentioned in the hold-X + mention-Y items; a word absent from the prompt elsewhere) is kept. A word's
tokens are the first sub-tokens of its accepted forms (the bench's ``match`` list), with and without
a leading space, of at least 3 characters; a word with none (15 of the 35 concepts) gets rank None.

  python experiments/mc_screen.py                    # -> out/mention-control/screen.jsonl + summary
  python experiments/mc_screen.py --limit 9          # plumbing
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
from m1_run import MODEL, OUT_DEFAULT, TOKEN_FILES
from token_local import build_centres, load_jacobians, load_unembed

from umot import capture
from umot import mention_control as mc
from umot.provenance import PINS, Provenance, write_artefact

VOCAB_CHUNK = 32768

#: arm -> (centre, keep): as ``token_local.ARMS``, cosine readout only.
ARMS = {
    "jlens": (None, None),
    "jlens-ctr-loo": ("fam", None),
    "jlens-ctr-tok": ("tok", None),
    "jlens-ctr-stop": ("tok", "last"),
    "jlens-ctr-carpos": ("carpos", None),
    "jlens-ctr-fit": ("fit", None),
    "jlens-ctr-fit-stop": ("fit", "last"),
}


def word_tokens(tok, forms: set[str]) -> list[int]:
    ids = set()
    for f in forms:
        for s in (f, " " + f):
            t = tok(s, add_special_tokens=False)["input_ids"]
            if t and len(tok.decode(t[:1]).strip()) >= 3:
                ids.add(t[0])
    return sorted(ids)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--batch", type=int, default=256, help="cells per device matmul")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    from transformers import AutoTokenizer

    bank = {it["id"]: it for it in mc.load()}
    dm = {b["concept"]: b for b in json.loads(mc.BENCH_BANK.read_text())["items"]}
    forms = {
        c: {c.lower(), c} | {m for u in b.get("units", []) if u.get("role") == "concept" for m in u["match"]}
        for c, b in dm.items()
    }
    y_of = {it["pair_id"]: it["mentioned"] for it in bank.values() if it["condition"] == "holdmention"}

    items = capture.load(OUT_DEFAULT / "captures" / f"{mc.FAMILY}.pt")
    layers = sorted({L for it in items for L in it.acts})
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    t0 = time.time()

    # Pass 1 (CPU): the centred state of every cell, per arm, spilled to disk so the centres (float64
    # sums, several GB) and the fp32 unembedding are never in memory together on a 16 GB machine.
    centres = build_centres(items, mc.FAMILY)
    spill = Path(args.out) / "mention-control" / "screen-states"
    spill.mkdir(parents=True, exist_ok=True)
    meta = []  # per cell, shared by every arm: (id, layer, i, X token ids, Y token ids)
    for it in items[: args.limit or None]:
        b = bank[it.id]
        tx, ty = word_tokens(tok, forms[b["concept"]]), word_tokens(tok, forms[y_of[b["pair_id"]]])
        for L in layers:
            meta += [(it.id, L, i, tx, ty) for i in range(it.acts[L].shape[0])]
    by_item = {it.id: it for it in items}
    for arm, (centre, _keep) in ARMS.items():
        h = torch.stack([
            by_item[i].acts[L][j].float() - (centres[centre](by_item[i], L, j) if centre else 0)
            for i, L, j, _, _ in meta
        ])
        torch.save(h, spill / f"{arm}.pt")
        print(f"  {arm}: {h.shape[0]} centred cells ({time.time() - t0:.0f}s)", flush=True)
    del centres, h, items, by_item

    # Pass 2 (device): full-vocabulary J-lens scores in batches of cells, best rank of X and Y.
    # W_U stays bf16 (the model's own dtype, so lossless) and is cast to fp32 one vocabulary chunk at a
    # time: half the resident memory of an fp32 copy, identical scores.
    w_u = load_unembed(MODEL).to(args.device)
    chunks = [(a, min(a + VOCAB_CHUNK, w_u.shape[0])) for a in range(0, w_u.shape[0], VOCAB_CHUNK)]
    jac = load_jacobians(layers)
    denom = {}
    for L in layers:
        jac.stack[L] = jac.stack[L].to(args.device)
        denom[L] = torch.cat([(w_u[a:b].float() @ jac[L]).norm(dim=1) for a, b in chunks]).clamp_min(1e-9)
    print(f"lens ready ({time.time() - t0:.0f}s)", flush=True)
    last = {}
    for i, _L, j, _, _ in meta:
        last[i] = max(last.get(i, 0), j)

    def pad(ids: list[list[int]]) -> torch.Tensor:
        w = max(len(t) for t in ids)
        return torch.tensor([t + t[:1] * (w - len(t)) for t in ids], device=args.device)

    rows = []
    for arm, (_centre, keep) in ARMS.items():
        h = torch.load(spill / f"{arm}.pt")
        for L in layers:
            sel = [k for k, m in enumerate(meta) if m[1] == L and (keep != "last" or m[2] == last[m[0]])]
            for c in range(0, len(sel), args.batch):
                ks = sel[c : c + args.batch]
                hj = h[ks].to(args.device) @ jac[L].T
                s = torch.cat([hj @ w_u[a:b].float().T for a, b in chunks], 1) / denom[L]
                ranks = []
                for col in (3, 4):  # None where the word has no clean first token (as taylor_screen)
                    ok = [n for n, k in enumerate(ks) if meta[k][col]]
                    r: list[int | None] = [None] * len(ks)
                    if ok:
                        best = s[ok].gather(1, pad([meta[ks[n]][col] for n in ok])).max(1, keepdim=True).values
                        for n, v in zip(ok, (s[ok] > best).sum(1).tolist(), strict=True):
                            r[n] = v
                    ranks.append(r)
                for k, rx, ry in zip(ks, *ranks, strict=True):
                    rows.append({"id": meta[k][0], "arm": arm, "layer": L, "i": meta[k][2], "rx": rx, "ry": ry})
        print(f"  {arm} done ({time.time() - t0:.0f}s)", flush=True)

    dest = Path(args.out) / "mention-control" / f"screen{f'-limit{args.limit}' if args.limit else ''}.jsonl"
    dest.write_text("".join(json.dumps(r) + "\n" for r in rows))
    write_artefact(
        dest.with_suffix(".provenance.json"),
        Provenance(
            model=MODEL, model_revision=PINS[MODEL], reader=TOKEN_FILES["jlens"][0],
            reader_revision=PINS[TOKEN_FILES["jlens"][0]], dataset=f"umot/{mc.FAMILY}",
            extra={"readout": "bench cosine, full vocabulary rank", "arms": {a: list(v) for a, v in ARMS.items()}},
        ),
        {"cells": len(rows), "layers": layers, "seconds": round(time.time() - t0, 1)},
    )
    print(f"-> {dest}")
    summarise(rows, bank)


def summarise(rows: list[dict], bank: dict) -> None:
    """Per arm and condition: share of items with X (or Y) in the top 10 at any cell, overall and at L>=42."""
    best: dict = defaultdict(lambda: [10**9, 10**9, 10**9, 10**9])  # (arm, id) -> min rx, ry; at L>=42
    for r in rows:
        v = best[r["arm"], r["id"]]
        rx, ry = (10**9 if x is None else x for x in (r["rx"], r["ry"]))
        v[0], v[1] = min(v[0], rx), min(v[1], ry)
        if r["layer"] >= 42:
            v[2], v[3] = min(v[2], rx), min(v[3], ry)
    groups: dict = defaultdict(list)
    for (arm, i), v in best.items():
        b = bank[i]
        groups[arm, b["condition"], b["where"]].append(v)
    print(f"{'arm':18s} {'condition':28s} {'n':>3s}  X top10  Y top10  X@L42+  Y@L42+")
    for (arm, cond, where), vs in sorted(groups.items()):
        f = lambda k, vs=vs: sum(v[k] < 10 for v in vs) / len(vs)  # noqa: E731
        print(f"{arm:18s} {cond + '/' + where:28s} {len(vs):3d}  {f(0):7.2f}  {f(1):7.2f}  {f(2):6.2f}  {f(3):6.2f}")


if __name__ == "__main__":
    main()
