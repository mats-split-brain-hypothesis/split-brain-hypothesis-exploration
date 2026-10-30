"""Programme LL, phase 0 on the pod: routers, the binned backward sweep, the merge (local-linearisation/plan.md).

    python experiments/ll0_sweep.py routers --prompts 400            # forward pre-pass; fits w1 / w8 / w16 / o8 / r8
    python experiments/ll0_sweep.py sweep --shard 0/1 --prompts 300 [--limit 1] [--batch 8]
    python experiments/ll0_sweep.py merge

Fit corpus: the first ``--prompts`` WikiText-103 records (jlens.examples.load_wikitext_prompts, the n1000 J-lens's
and J++'s corpus; their first 1000). Routers: ``w*`` J++'s recipe on those prompts' kept positions (w1: one bin, the
pooled J-lens; w8 split by prompt parity, w16); ``o8`` the same recipe on our fit banks' read cells (every dev
family's fit split); ``r8`` random bins with w8's per-layer proportions (the size-matched control). Shards take
prompts ``i % n == shard`` and checkpoint means in fp16 with their counts (resumable).
Outputs under ``out/analysis/LL0/``.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

if os.environ.get("LL_NO_FLA"):  # gate diagnosis: hide flash-linear-attention so transformers uses its reference kernels
    sys.modules["fla"] = None

import torch

from jlm import OUT
from jlm.mu.LL0 import MAX_SEQ_LEN, SKIP_FIRST, Accumulator, Router, sweep_prompt

LAYERS = [24, 32, 40, 48, 56]  # J++'s recipe layers (8..56) on our grid (20..60)
ROOT = OUT / "analysis" / "LL0"
MODEL = "Qwen/Qwen3.6-27B"


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_model(compile_blocks: bool = False):
    from jlens.hf import from_hf
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from umot.provenance import PINS

    rev = PINS[MODEL]
    tok = AutoTokenizer.from_pretrained(MODEL, revision=rev)
    hf = AutoModelForCausalLM.from_pretrained(MODEL, revision=rev, dtype=torch.bfloat16, device_map="cuda")
    return from_hf(hf, tok, compile=compile_blocks)


def wiki(n: int) -> list[str]:
    from jlens.examples import load_wikitext_prompts

    cache = ROOT / f"wiki-prompts-{n}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    p = load_wikitext_prompts(n)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(p))
    return p


def our_cells(cap: int = 102, seed: int = 0) -> dict[int, torch.Tensor]:
    """Every dev family's fit read cells at LAYERS (the o8 router's corpus; fit split only), at most ``cap`` cells per
    family (a seeded subsample: uncapped, user_modeling's 1294 and directed_modulation's 688 cells took the clustering
    over and the other nine families shared one cluster, LL1 landing 2026-10-12)."""
    from jlm import capture
    from jlm.banks import dev_families, load

    acts = {L: [] for L in LAYERS}
    fams = dev_families()
    for f in fams:
        try:
            items = capture.load(load(f, "fit"))
        except (FileNotFoundError, RuntimeError) as e:
            log("o8: skip", f, e)
            continue
        for L in LAYERS:
            x = torch.cat([it.acts[L].float() for it in items if L in it.acts])
            if len(x) > cap:
                x = x[torch.randperm(len(x), generator=torch.Generator().manual_seed(seed))[:cap]]
            acts[L].append(x)
        log("o8 cells", f, len(items))
    return {L: torch.cat(v) for L, v in acts.items()}


def cmd_routers(a) -> None:
    model = load_model()
    from jlens.hooks import ActivationRecorder

    prompts = wiki(a.prompts)
    acts = {L: [] for L in LAYERS}
    for i, p in enumerate(prompts):
        ids = model.encode(p, max_length=MAX_SEQ_LEN)
        if ids.shape[1] <= SKIP_FIRST + 1:
            continue
        with ActivationRecorder(model.layers, at=LAYERS) as rec, torch.no_grad():
            model.forward(ids)
        for L in LAYERS:
            acts[L].append(rec.activations[L][0, SKIP_FIRST : ids.shape[1] - 1].float().cpu())
        if i % 100 == 0:
            log("router pre-pass", i, len(prompts))
    acts = {L: torch.cat(v) for L, v in acts.items()}
    del model
    torch.cuda.empty_cache()
    dev = {L: x.cuda() for L, x in acts.items()}
    routers = [Router.fit("w1", 1, dev, split=True), Router.fit("w8", 8, dev, split=True), Router.fit("w16", 16, dev)]
    log("wiki routers fitted on", {L: len(x) for L, x in acts.items()})
    cells = our_cells()
    routers.append(Router.fit("o8", 8, {L: x.cuda() for L, x in cells.items()}))
    w8 = routers[1]
    r8 = Router("r8", 8, kind="random", seed=1)
    for L in LAYERS:
        cnt = torch.bincount(w8.assign(dev[L], L, 0), minlength=8).float()
        r8.probs[L] = (cnt / cnt.sum()).cpu()
    routers.append(r8)
    torch.save({"routers": [r.state() for r in routers], "layers": LAYERS, "n_prompts": a.prompts,
                "n_positions": {L: len(x) for L, x in acts.items()}, "n_cells": {L: len(x) for L, x in cells.items()}},
               ROOT / "routers.pt")
    for L, x in acts.items():  # every 4th kept position, for LL1 diagnostics and offline clusterings (k = 64)
        torch.save(x[::4].to(torch.bfloat16), ROOT / f"wiki-acts-L{L:03d}.pt")
    log("routers saved", [(r.name, r.bins) for r in routers])


def cmd_refit_o8(a) -> None:
    """Refit only o8 (family-capped cells) in routers.pt; the wiki routers and r8 are kept."""
    rs = torch.load(ROOT / "routers.pt", weights_only=False)
    cells = our_cells()
    o8 = Router.fit("o8", 8, {L: x.to(a.device) for L, x in cells.items()})
    rs["routers"] = [o8.state() if s["name"] == "o8" else s for s in rs["routers"]]
    rs["n_cells"] = {L: len(x) for L, x in cells.items()}
    torch.save(rs, ROOT / "routers.pt")
    log("o8 refitted on", rs["n_cells"])


CKPT = Path("/root/ll0-ckpt")  # container disk: the shared volume has no room for 13 GB per shard (2026-10-12)


def shard_dir(shard: str) -> Path:
    return CKPT / "shards" / shard.replace("/", "of")


def save_ckpt(acc: Accumulator, d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for L in acc.layers:
        n = acc.count[L].clamp_min(1)[:, None, None].float()
        tmp = d / f"J-L{L:03d}.pt.tmp"
        torch.save((acc.J[L] / n).to(torch.float16), tmp)
        tmp.replace(d / f"J-L{L:03d}.pt")
    tmp = d / "meta.pt.tmp"
    torch.save(acc.state(), tmp)
    tmp.replace(d / "meta.pt")


def load_ckpt(acc: Accumulator, d: Path) -> None:
    meta = torch.load(d / "meta.pt", weights_only=False)
    acc.count, acc.hsum, acc.prompts = meta["count"], meta["hsum"], meta["prompts"]
    for L in acc.layers:
        acc.J[L] = torch.load(d / f"J-L{L:03d}.pt").float() * acc.count[L].clamp_min(1)[:, None, None].float()


def cmd_sweep(a) -> None:
    rs = torch.load(ROOT / "routers.pt", weights_only=False)
    routers = [Router.from_state(s) for s in rs["routers"]]
    k, n = map(int, a.shard.split("/"))
    prompts = wiki(a.prompts)
    mine = [i for i in range(len(prompts)) if i % n == k]
    model = load_model(a.compile)
    acc = Accumulator(routers, LAYERS, model.d_model)
    d = shard_dir(a.shard) if not a.limit else CKPT / "timing"
    if (d / "meta.pt").exists() and not a.limit:
        load_ckpt(acc, d)
        log("resumed", len(acc.prompts), "prompts")
    done = set(acc.prompts)
    todo = [i for i in mine if i not in done][: a.limit or None]
    log(f"shard {a.shard}: {len(todo)} prompts to do, E={acc.E} bins x {len(LAYERS)} layers, batch {a.batch}")
    t_start, since = time.perf_counter(), 0
    for j, i in enumerate(todo):
        if a.hours and time.perf_counter() - t_start > a.hours * 3600:
            log(f"deadline: {a.hours} h reached")
            if since:
                save_ckpt(acc, d)
            break
        t0, timer = time.perf_counter(), {}
        P = sweep_prompt(model, acc, prompts[i], i, batch=a.batch, timer=timer)
        dt = time.perf_counter() - t0
        rate = (time.perf_counter() - t_start) / (j + 1)
        log(f"prompt {i} ({j + 1}/{len(todo)}) P={P} {dt:.1f}s "
            + " ".join(f"{k}={v:.1f}" for k, v in timer.items())
            + f" | mean {rate:.1f}s/prompt, ETA {rate * (len(todo) - j - 1) / 3600:.2f} h"
            + f" | gpu peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GB")
        since += 1
        if since >= a.ckpt_every or j == len(todo) - 1:
            tc = time.perf_counter()
            save_ckpt(acc, d)
            since = 0
            log(f"checkpoint {len(acc.prompts)} prompts in {time.perf_counter() - tc:.0f}s")
    log("SWEEP_DONE", len(acc.prompts))


def cmd_merge(a) -> None:
    dirs = sorted((CKPT / "shards").glob("*")) if not a.dirs else [Path(x) for x in a.dirs]
    metas = [torch.load(x / "meta.pt", weights_only=False) for x in dirs]
    routers = [Router.from_state(s) for s in metas[0]["routers"]]
    acc = Accumulator.__new__(Accumulator)
    acc.routers, acc.layers, acc.d = routers, metas[0]["layers"], metas[0]["d"]
    acc.offsets, nb = {}, 0
    for r in routers:
        acc.offsets[r.name] = nb
        nb += r.bins
    acc.E = nb
    acc.count = {L: sum(m["count"][L] for m in metas) for L in acc.layers}
    acc.hsum = {L: sum(m["hsum"][L] for m in metas) for L in acc.layers}
    acc.prompts = sorted(p for m in metas for p in m["prompts"])
    assert len(acc.prompts) == len(set(acc.prompts)), "shards overlap"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for L in acc.layers:
        acc.J = {L: sum(torch.load(x / f"J-L{L:03d}.pt").float() * m["count"][L].clamp_min(1)[:, None, None].float()
                        for x, m in zip(dirs, metas))}
        rec = {}
        for r in routers:
            J, mu, c = acc.expert(r.name, L)
            rec[r.name] = {"J": J.to(torch.float16), "mu": mu, "count": c}
            if r.split:
                Jh, muh, ch = acc.expert(r.name, L, merge_split=False)
                rec[r.name + ":halves"] = {"J": Jh.to(torch.float16), "mu": muh, "count": ch}
        torch.save(rec, out / f"experts-L{L:03d}.pt")
        log("merged", L, {r.name: rec[r.name]["count"].tolist() for r in routers})
    torch.save({"prompts": acc.prompts, "routers": metas[0]["routers"], "layers": acc.layers}, out / "meta.pt")
    log("MERGE_DONE", len(acc.prompts), "prompts")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("routers")
    r.add_argument("--prompts", type=int, default=400)
    s = sub.add_parser("sweep")
    s.add_argument("--shard", default="0/1")
    s.add_argument("--prompts", type=int, default=300)
    s.add_argument("--limit", type=int, default=0, help="timing run: this many prompts into out/analysis/LL0/timing")
    s.add_argument("--batch", type=int, default=8)
    s.add_argument("--ckpt-every", type=int, default=10)
    s.add_argument("--compile", action="store_true")
    s.add_argument("--hours", type=float, default=0, help="stop (and checkpoint) after this long")
    o = sub.add_parser("refit-o8")
    o.add_argument("--device", default="cpu")
    m = sub.add_parser("merge")
    m.add_argument("dirs", nargs="*")
    m.add_argument("--out", default=str(CKPT / "experts"), help="merged experts (13 GB: container disk)")
    a = ap.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    {"routers": cmd_routers, "sweep": cmd_sweep, "merge": cmd_merge, "refit-o8": cmd_refit_o8}[a.cmd](a)


if __name__ == "__main__":
    main()
