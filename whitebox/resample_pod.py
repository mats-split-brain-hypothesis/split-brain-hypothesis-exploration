"""Resample a run's final reply from cut points (RESAMPLE.md): prefill the sequence up to each cut once (chunked, as
capture.run), keep that prefix's cache on the CPU, then sample N continuations in batches built from it, with the
run's sampling (temperature 1.0, top_k 20, top_p 0.95; Qwen3.8's generation_config), until <|im_end|>.

    python resample_pod.py out/T [--cuts c1,c4] [--n 20] [--max-new 6000] [--batch 0 (auto)] [--model M]
                           [--revision REV] [--dtype bf16|fp32] [--prefix-limit N] [--check-greedy N]

Reads out/T/prompt-full.txt and out/T/resample/cuts.json (resample_cuts.py); appends to out/T/resample/<cut>.jsonl,
one line per sample (text, ids, log p of each sampled token under the full distribution, seconds), so a rerun with a
larger --n tops a cut up. The KV of the full-attention layers goes into preallocated buffers (the default dynamic
cache concatenates the whole KV at every step, which at 230k tokens costs more than the attention itself).
--prefix-limit N keeps the first N tokens of the sequence and the final reply from its "<|im_start|>" (tests on
small cards). --check-greedy N compares N greedy tokens from the
batched cache path with model.generate on the same prefix (test).
"""

import argparse
import json
import time
import types
from pathlib import Path

import numpy as np
import torch

CHUNK, MARGIN_GIB = 2048, 6.0
TEMP, TOP_K, TOP_P = 1.0, 20, 0.95


def static_update(self, k, v, *args, **kwargs):
    """DynamicLayer.update into a buffer of self._cap tokens (allocated on first use)."""
    if self._bk is None:
        B, h, _, d = k.shape
        self._bk = k.new_empty(B, h, self._cap, d)
        self._bv = v.new_empty(B, h, self._cap, v.shape[-1])
        self._len, self.dtype, self.device, self.is_initialized = 0, k.dtype, k.device, True
    n = k.shape[-2]
    assert self._len + n <= self._cap, "cache buffer full"
    self._bk[:, :, self._len:self._len + n] = k
    self._bv[:, :, self._len:self._len + n] = v
    self._len += n
    self.keys, self.values = self._bk[:, :, :self._len], self._bv[:, :, :self._len]
    return self.keys, self.values


def new_cache(config, cap: int):
    from transformers import DynamicCache
    cache = DynamicCache(config=config)
    for L in cache.layers:
        if hasattr(L, "keys"):  # attention layers (DynamicLayer); linear-attention layers keep their own states
            L._cap, L._bk, L._bv, L._len = cap, None, None, 0
            L.update = types.MethodType(static_update, L)
    return cache


def snapshot(cache) -> list:
    """Move the cache's tensors to (pinned) CPU and drop them from the GPU; the layer objects keep their flags."""
    snap = []
    for i, L in enumerate(cache.layers):
        if getattr(L, "_bk", None) is not None:
            snap.append((i, "kv", None, (L._bk[:, :, :L._len].cpu().pin_memory(), L._bv[:, :, :L._len].cpu().pin_memory())))
            L._bk = L._bv = L.keys = L.values = None
        for attr in ("conv_states", "recurrent_states"):
            for j, x in (getattr(L, attr, None) or {}).items():
                if x is not None:
                    snap.append((i, attr, j, x.cpu().pin_memory()))
                    getattr(L, attr)[j] = None
    torch.cuda.empty_cache()
    return snap


def restore(cache, snap: list, B: int, cap: int, dev) -> None:
    """Put a snapshot back on the GPU, repeated B times along the batch, with KV buffers of cap tokens."""
    for i, attr, j, x in snap:
        L = cache.layers[i]
        if attr == "kv":
            k, v = x
            n = k.shape[-2]
            L._cap, L._len = cap, n
            L._bk = torch.empty((B, k.shape[1], cap, k.shape[3]), dtype=k.dtype, device=dev)
            L._bv = torch.empty((B, v.shape[1], cap, v.shape[3]), dtype=v.dtype, device=dev)
            L._bk[:, :, :n] = k.to(dev, non_blocking=True)
            L._bv[:, :, :n] = v.to(dev, non_blocking=True)
            L.keys, L.values = L._bk[:, :, :n], L._bv[:, :, :n]
        else:
            getattr(L, attr)[j] = x.to(dev, non_blocking=True).repeat(B, *[1] * (x.dim() - 1))
    torch.cuda.synchronize()


def snap_bytes(snap: list) -> tuple[int, int]:
    kv = sum(x[0].nbytes + x[1].nbytes for _, a, _, x in snap if a == "kv")
    lin = sum(x.nbytes for _, a, _, x in snap if a != "kv")
    return kv, lin


def forward(inner, ids: torch.Tensor, pos0: int, cache) -> torch.Tensor:
    """ids [B, n] at positions pos0.. -> last hidden state [B, n, d]."""
    B, n = ids.shape
    pos = torch.arange(pos0, pos0 + n, device=ids.device)[None].expand(B, n)
    return inner(input_ids=ids, position_ids=pos, past_key_values=cache, use_cache=True).last_hidden_state


def sample(logits: torch.Tensor, gen: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
    """logits [B, V] float32 -> (token [B], log p of the token under the unfiltered distribution [B]).
    transformers' order: temperature, top_k, top_p (keep the smallest top set with mass >= top_p)."""
    logp = torch.log_softmax(logits, -1)
    v, i = (logits / TEMP).topk(TOP_K, -1)  # sorted, descending
    p = torch.softmax(v, -1)
    keep = (p.cumsum(-1) - p) < TOP_P
    p = torch.where(keep, p, 0)
    k = torch.multinomial(p / p.sum(-1, keepdim=True), 1, generator=gen)
    tok = i.gather(1, k)[:, 0]
    return tok, logp.gather(1, tok[:, None])[:, 0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--cuts", default="")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--max-new", type=int, default=0, help="0: the cut's max_new in cuts.json")
    ap.add_argument("--batch", type=int, default=0, help="0: as many as fit")
    ap.add_argument("--batch-max", type=int, default=6)
    ap.add_argument("--model", default="Qwen/Qwen3.8-27B")
    ap.add_argument("--revision", default=None)
    ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp32"])
    ap.add_argument("--prefix-limit", type=int, default=0)
    ap.add_argument("--check-greedy", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    d = Path(a.dir)
    spec = json.loads((d / "resample" / "cuts.json").read_text())
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokz = AutoTokenizer.from_pretrained(a.model, revision=a.revision)
    s = (d / "prompt-full.txt").read_text()
    ids_all = tokz(s, add_special_tokens=False)["input_ids"]
    assert len(ids_all) == spec["n_tokens"], (len(ids_all), spec["n_tokens"])
    eos = tokz.convert_tokens_to_ids("<|im_end|>")
    names = [c for c in (a.cuts.split(",") if a.cuts else spec["cuts"])]
    cuts = sorted(((spec["cuts"][c]["token"], c) for c in names))
    if a.prefix_limit:  # tests: the first N tokens, then the reply from its start ("<|im_start|>" before c1)
        start = tokz.convert_tokens_to_ids("<|im_start|>")
        r = max(k for k in range(min(t for t, _ in cuts)) if ids_all[k] == start)
        keep = list(range(min(a.prefix_limit, r))) + list(range(r, len(ids_all)))
        shift = r - min(a.prefix_limit, r)
        ids_all = [ids_all[k] for k in keep]
        cuts = [(t - shift, c) for t, c in cuts]

    dt = torch.bfloat16 if a.dtype == "bf16" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(a.model, revision=a.revision, dtype=dt, device_map="cuda").eval()
    inner = getattr(model.model, "language_model", model.model)
    config = model.config.get_text_config()
    dev = next(model.parameters()).device
    ids = torch.tensor(ids_all, device=dev)
    print(f"{spec['target']}: {len(ids_all):,} tokens; cuts {cuts}; attn {model.config._attn_implementation}; "
          f"{torch.cuda.get_device_name(0)}", flush=True)
    out_dir = d / "resample"
    meta = {"target": spec["target"], "model": a.model, "revision": a.revision, "dtype": a.dtype,
            "sampling": {"temperature": TEMP, "top_k": TOP_K, "top_p": TOP_P},
            "prefix_limit": a.prefix_limit, "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0), "cuts": {}}

    cache, done_to, snap, h_last = None, 0, None, None
    with torch.no_grad():
        for t, cut in cuts:
            t0, max_new = time.time(), a.max_new or spec["cuts"][cut]["max_new"]
            # extend the B=1 prefix cache from done_to to t (the first time from 0)
            cap = t + max_new + 8
            if cache is None:
                cache = new_cache(config, cap)
            else:
                restore(cache, snap, 1, cap, dev)
            for lo in range(done_to, t, CHUNK):
                hi = min(t, lo + CHUNK)
                h_last = forward(inner, ids[None, lo:hi], lo, cache)[:, -1]
            done_to = t
            snap = snapshot(cache)
            kv, lin = snap_bytes(snap)
            prefill_s = time.time() - t0
            print(f"[{cut}] prefix {t:,} tokens in {prefill_s:.0f}s; KV {kv / 2**30:.2f} GiB, linear states "
                  f"{lin / 2**20:.0f} MiB", flush=True)
            if a.check_greedy:
                check_greedy(model, inner, cache, snap, ids[:t], h_last, a.check_greedy, dev)
            f = out_dir / f"{cut}.jsonl"
            have = sum(1 for _ in f.open()) if f.exists() else 0
            per_seq = kv / t * (t + max_new) + lin
            todo, b_i = a.n - have, have
            while todo > 0:
                free = torch.cuda.mem_get_info()[0]
                B = a.batch or max(1, min(a.batch_max, int((free - MARGIN_GIB * 2**30) // per_seq)))
                B = min(B, todo)
                seed = a.seed * 1_000_003 + sum(map(ord, cut)) * 1000 + b_i
                gen = torch.Generator(device=dev).manual_seed(seed)
                restore(cache, snap, B, t + max_new + 8, dev)
                ts = time.time()
                logits = model.lm_head(h_last).float().expand(B, -1)
                toks, lps, alive = [], [], torch.ones(B, dtype=torch.bool, device=dev)
                n_new = torch.zeros(B, dtype=torch.long, device=dev)
                for step in range(max_new):
                    tok, lp = sample(logits, gen)
                    tok = torch.where(alive, tok, eos)
                    toks.append(tok); lps.append(lp)
                    n_new += alive
                    alive &= tok != eos
                    if not alive.any():
                        break
                    logits = model.lm_head(forward(inner, tok[:, None], t + step, cache)[:, -1]).float()
                secs = time.time() - ts
                T = torch.stack(toks, 1).cpu().numpy()
                LP = torch.stack(lps, 1).float().cpu().numpy()
                with f.open("a") as fh:
                    for r in range(B):
                        n = int(n_new[r])
                        row = T[r, :n].tolist()
                        fh.write(json.dumps({"cut": cut, "i": b_i + r, "seed": seed, "row": r, "batch": B,
                                             "eos": bool(row and row[-1] == eos), "n_new": n,
                                             "text": tokz.decode(row), "ids": row,
                                             "lp": [round(float(x), 4) for x in LP[r, :n]],
                                             "seconds": round(secs, 1)}) + "\n")
                print(f"  [{cut}] samples {b_i}-{b_i + B - 1}: batch {B}, {len(toks)} steps in {secs:.0f}s "
                      f"({len(toks) * B / secs:.1f} tok/s), lengths {n_new.tolist()}, peak "
                      f"{torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)
                snapshot(cache)  # frees the batch's GPU tensors (the prefix snapshot is kept)
                todo -= B; b_i += B
            meta["cuts"][cut] = {"token": t, "prefill_s": prefill_s, "kv_gib": kv / 2**30, "samples": b_i, "max_new": max_new}
    (out_dir / f"meta-{'-'.join(c for _, c in cuts)}.json").write_text(json.dumps(meta, indent=1))
    print("RESAMPLE_DONE", spec["target"], flush=True)


def check_greedy(model, inner, cache, snap, prefix, h_last, n, dev) -> None:
    """Greedy N tokens via the batched buffer path (B=2) vs model.generate (fresh cache), on the same prefix."""
    restore(cache, snap, 2, len(prefix) + n + 8, dev)
    logits, mine = model.lm_head(h_last).float().expand(2, -1), []
    for step in range(n):
        tok = logits.argmax(-1)
        mine.append(tok)
        logits = model.lm_head(forward(inner, tok[:, None], len(prefix) + step, cache)[:, -1]).float()
    snapshot(cache)
    mine = torch.stack(mine, 1)
    ref = model.generate(prefix[None], max_new_tokens=n, do_sample=False, min_new_tokens=n)[0, len(prefix):]
    same = [(mine[r] == ref).float().mean().item() for r in range(2)]
    first = [int((mine[r] != ref).nonzero()[0]) if same[r] < 1 else n for r in range(2)]
    print(f"  greedy check ({n} tokens): agreement {same}, first divergence {first}", flush=True)


if __name__ == "__main__":
    main()
