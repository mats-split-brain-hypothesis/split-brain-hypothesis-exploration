"""Passage lens: J-lens readouts at EVERY position of a render (not just the read cells), for the
dashboard's token tracker ("where does `subconscious` light up across the passage?").

For each item of a family: one forward pass of the probed model, residuals at every position and at
``--layers`` (default every other layer, L0-L62); then the bench's cosine J-lens readout, plain and
centred, over the full vocabulary. Per cell we keep the top ``--keep`` token ids (so any token's rank
is known up to that depth) and the top 20 scores.

The centre is the same-token centre of ``token_local`` extended to every position: the mean of other
items' residuals at cells with the same (frame, token), excluding every item that shares a concept;
fewer than 3 such cells falls back to the frame mean under the same exclusion. Computed per layer on
the device as masked group means (the per-item sums of ``umot.centring`` would need ~24 GB here).
Identical prefixes (the chat header) are identical across items, so their centred residual is ~0 and
their centred readout is noise: ``ctr_norm`` (‖h − μ‖ / ‖h‖) lets the page grey them out.

Output: out/passage/<family>/<item id>.npz and out/passage/<family>/index.json (+ provenance).

  python experiments/passage_lens.py --families mention_control,directed_modulation          # pod
  python experiments/passage_lens.py --model Qwen/Qwen3.5-0.8B --layers 4,8,12 --limit 6 --device mps \\
      --jlens-file qwen3.5-0.8b/jlens/Salesforce-wikitext/Qwen3.5-0.8B_jacobian_lens.pt    # plumbing
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from m1_run import MODEL, OUT_DEFAULT, TOKEN_FILES, jlens_denominator, load_backend  # noqa: E402
from token_local import item_meta  # noqa: E402

from umot import capture  # noqa: E402
from umot import mention_control as mc  # noqa: E402
from umot.provenance import PINS, Provenance, write_artefact  # noqa: E402

SHOW = 20  # scores kept per cell (the readout list the page displays)
MIN_CELLS = 3  # same-token pool size below which the frame centre is used


def bank(family: str) -> list[dict[str, Any]]:
    """Items with their prompt and a condition label, in plan order."""
    if family in mc.BANKS:
        return [
            {"id": it["id"], "prompt": it["prompt"], "condition": it["condition"], "where": it["where"],
             "concept": it["concept"], "pair_id": it["pair_id"]}
            for it in mc.load(family)
        ]
    rows = json.loads((mc.REPO_ROOT / "third_party/workspace-bench/evals" / family / "items.json").read_text())["items"]
    return [
        {"id": b["name"], "prompt": b["prompt"], "condition": f"{b['subfamily']}/{b['polarity']}", "where": "",
         "concept": b["concept"], "pair_id": b.get("pair_id", b["name"])}
        for b in rows
    ]


def specs(family: str, items: list[dict]) -> list[Any]:
    if family in mc.BANKS:
        return mc.specs([it for it in mc.load(family) if it["id"] in {i["id"] for i in items}])
    return capture.specs(family, items=[i["id"] for i in items])


def segments(item: capture.ItemCapture, prompt: str) -> list[str]:
    """Per position: ``first`` (the sentence before "Now write exactly", e.g. the hold sentence),
    ``copy`` (the copy instruction and the prompt's copy of the carrier), ``carrier`` (the read
    cells: the assistant's teacher-forced copy) or ``template``."""
    text = "".join(item.decoded)
    ends, s = [], 0
    for d in item.decoded:
        s += len(d)
        ends.append(s)
    first = prompt.split("Now write exactly")[0].strip()
    copy = prompt[prompt.find("Now write exactly"):]
    out = ["template"] * len(item.decoded)

    def mark(sub: str, label: str) -> None:
        if not sub:
            return
        a = text.find(sub)
        assert a >= 0, (item.id, sub[:30])
        for i, e in enumerate(ends):
            if e > a and e - len(item.decoded[i]) < a + len(sub):
                out[i] = label

    mark(first, "first")
    mark(copy, "copy")
    for i in item.idx:
        out[i] = "carrier"
    return out


def centre_layer(h: torch.Tensor, key: list, frame: list, concepts: list[frozenset], item_of: list[int]) -> torch.Tensor:
    """Same-token centre for every cell of one layer: masked means over cells with the same key,
    excluding the cell's own item and items sharing a concept; frame mean when < MIN_CELLS remain."""
    dev = h.device
    n = h.shape[0]
    mu = torch.empty_like(h)
    # item-level exclusion matrix (items, not cells): excluded[a, b] = a and b share a concept, or a == b
    items = sorted(set(item_of))
    pos = {it: k for k, it in enumerate(items)}
    conc = [concepts[next(c for c in range(n) if item_of[c] == it)] for it in items]
    ex = torch.tensor([[a == b or bool(conc[a] & conc[b]) for b in range(len(items))] for a in range(len(items))], device=dev)
    ii = torch.tensor([pos[x] for x in item_of], device=dev)

    def group_means(groups: dict) -> tuple[torch.Tensor, torch.Tensor]:
        m = torch.zeros_like(h)
        cnt = torch.zeros(n, device=dev)
        for idx in groups.values():
            g = torch.tensor(idx, device=dev)
            keep = ~ex[ii[g]][:, ii[g]]  # [|G|, |G|]
            w = keep.to(h.dtype)
            c = w.sum(1)
            m[g] = (w @ h[g]) / c.clamp_min(1)[:, None]
            cnt[g] = c
        return m, cnt

    by_key, by_frame = defaultdict(list), defaultdict(list)
    for c in range(n):
        by_key[key[c]].append(c)
        by_frame[frame[c]].append(c)
    m_tok, n_tok = group_means(by_key)
    m_fam, _ = group_means(by_frame)
    use_tok = n_tok >= MIN_CELLS
    mu[use_tok] = m_tok[use_tok]
    mu[~use_tok] = m_fam[~use_tok]
    return mu


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--families", default="mention_control,directed_modulation")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--layers", default=",".join(map(str, range(0, 63, 2))), type=lambda s: [int(x) for x in s.split(",")])
    ap.add_argument("--keep", type=int, default=128, help="top token ids kept per cell (rank depth)")
    ap.add_argument("--jlens-file", default="", help="override the pinned 27B lens (small-model plumbing only)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True  # full-vocab scoring: ~3 PFLOP in strict fp32
    from huggingface_hub import hf_hub_download

    t0 = time.time()
    backend = load_backend(args.model, args.device)
    tok, dev, layers = backend.tokenizer, backend.device, args.layers
    fams = args.families.split(",")
    caps: dict[str, list] = {}
    meta: dict[str, list] = {}
    for fam in fams:
        items = bank(fam)[: args.limit or None]
        by_id = {it["id"]: it for it in items}
        caps[fam], meta[fam] = [], []
        for spec in specs(fam, items):
            item = capture.cells(spec, tok)
            n = len(item.ids)
            acts = backend.capture(item.ids, layers, list(range(n)))
            item.acts = {L: acts[L].to(torch.bfloat16) for L in layers}
            caps[fam].append(item)
            it = by_id[item.id]
            meta[fam].append({**it, "tokens": item.decoded, "segments": segments(item, it["prompt"]), "read_idx": item.idx})
        print(f"[{fam}] captured {len(caps[fam])} items ({time.time() - t0:.0f}s)", flush=True)
    w_u = backend.unembed.detach().float()
    del backend
    gc.collect()
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    w_u = w_u.to(dev)

    repo, filename = TOKEN_FILES["jlens"][0], args.jlens_file or TOKEN_FILES["jlens"][1]
    obj = torch.load(hf_hub_download(repo, filename, revision=PINS[repo]), map_location="cpu", weights_only=False, mmap=True)
    jall = obj["J"] if "J" in obj else obj["jacobians"]

    for fam in fams:
        dest = Path(args.out) / "passage" / fam
        dest.mkdir(parents=True, exist_ok=True)
        fm = item_meta(fam)  # frame and concepts per item (mention_control or a bench family)
        items = caps[fam]
        # one row per cell of the family, items in order
        cell_item = [k for k, it in enumerate(items) for _ in it.ids]
        cell_pos = [p for it in items for p in range(len(it.ids))]
        frame = [fm[items[k].id]["frame"] for k in cell_item]
        concepts = [fm[items[k].id]["concepts"] for k in cell_item]
        key = [(frame[c], items[cell_item[c]].decoded[cell_pos[c]]) for c in range(len(cell_item))]
        n_cells = len(cell_item)
        out = {
            kind: np.zeros((len(layers), n_cells, args.keep), np.int32) for kind in ("plain", "ctr")
        }
        scores = {kind: np.zeros((len(layers), n_cells, SHOW), np.float16) for kind in ("plain", "ctr")}
        ctr_norm = np.zeros((len(layers), n_cells), np.float16)
        for li, L in enumerate(layers):
            jac = jall[L].float().to(dev)
            denom = jlens_denominator(w_u, jac)
            h = torch.cat([it.acts[L] for it in items]).float().to(dev)
            mu = centre_layer(h, key, frame, concepts, cell_item)
            x_ctr = h - mu
            ctr_norm[li] = (x_ctr.norm(dim=1) / h.norm(dim=1).clamp_min(1e-9)).cpu().numpy()
            for kind, x in (("plain", h), ("ctr", x_ctr)):
                for a in range(0, n_cells, 2048):
                    s = ((x[a : a + 2048] @ jac.T) @ w_u.T) / denom
                    v, i = torch.topk(s, args.keep)
                    out[kind][li, a : a + 2048] = i.cpu().numpy()
                    scores[kind][li, a : a + 2048] = v[:, :SHOW].cpu().numpy().astype(np.float16)
            del jac, denom, h, mu, x_ctr
            print(f"[{fam}] L{L} ({time.time() - t0:.0f}s)", flush=True)
        a = 0
        for k, it in enumerate(items):
            n = len(it.ids)
            np.savez_compressed(
                dest / f"{it.id}.npz",
                plain_ids=out["plain"][:, a : a + n], ctr_ids=out["ctr"][:, a : a + n],
                plain_scores=scores["plain"][:, a : a + n], ctr_scores=scores["ctr"][:, a : a + n],
                ctr_norm=ctr_norm[:, a : a + n],
            )
            a += n
        write_artefact(
            dest / "index.json",
            Provenance(
                model=args.model, model_revision=PINS.get(args.model, "unpinned"), reader=repo,
                reader_revision=PINS[repo], dataset=fam,
                extra={"layers": layers, "keep": args.keep, "show": SHOW, "jlens_file": filename,
                       "readout": "bench cosine (W_U J h)_t / ‖J_lᵀ W_U[t]‖, TF32 matmul on CUDA",
                       "centre": f"same (frame, token), other items sharing no concept, >= {MIN_CELLS} cells else frame mean",
                       "limit": args.limit, "device": args.device},
            ),
            {"items": meta[fam], "seconds": round(time.time() - t0, 1)},
        )
        print(f"[{fam}] -> {dest} ({len(items)} items)", flush=True)


if __name__ == "__main__":
    main()
