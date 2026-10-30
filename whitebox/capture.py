"""One teacher-forced pass of the subject model over a run's sequence (render.py --with-response), stored so the
readers (J-lens, oracle lens, NLA) can run later without the subject model. Layer L is the output of decoder block L
(umot.capture's convention). bf16 is stored as raw uint16 memmaps (lossless: the model runs in bf16).

    python capture.py DIR [--model Qwen/Qwen3.8-27B] [--revision REV] [--chunk 2048] [--out OUT] [--plan-only]
                          [--limit N] [--check-chunking N]

DIR holds prompt-full.txt and capture.json (moments.py). OUT (default DIR/capture/) gets:
  ids.npy                     int32 [n]        every token of the sequence
  subj_idx.npy                int64 [n_subj]   positions the subject wrote (assistant turns, <think> to <|im_end|>)
  subj_L{L}.npy               [n_subj, d] uint16 (bf16 bits)      READER_LAYERS at subj_idx
  win_idx.npy, win_all.npy    [n_win, n_layers, d]  every layer at the moment windows (block start and end, +-1.5k)
  pred_idx.npy                int64 [n_pred]   positions whose next token is subject-written (the prediction of it)
  pred_topk_ids.npy int32 / pred_topk_lp.npy float16 [n_pred, K]; pred_lp.npy (the token it wrote), pred_ent.npy float32
  meta.json                   model, revision, layers, d, windows (token ranges per moment), checks, timings
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

READER_LAYERS = sorted(set(range(20, 61, 4)) | {42})  # oracle lens L20-60 step 4; NLA L42
REPLY = "<|im_start|>assistant\n"
END = "<|im_end|>"
BEFORE, AFTER, K = 512, 1024, 20


def spans(s: str) -> list[tuple[int, int]]:
    """Char spans of the assistant turns (after the role line, through <|im_end|>; the last one to the end)."""
    out, i = [], s.find(REPLY)
    while i >= 0:
        a = i + len(REPLY)
        e = s.find(END, a)
        e = len(s) if e < 0 else e + len(END)
        out.append((a, e))
        i = s.find(REPLY, e)
    return out


def plan(s: str, spec: dict, offs: list[tuple[int, int]]) -> dict:
    starts = np.array([a for a, _ in offs])
    tok = lambda c: int(np.searchsorted(starts, c, side="right") - 1)  # token containing char c
    n = len(offs)
    turns = spans(s)
    subj = np.zeros(n, bool)
    for a, e in turns:
        subj[tok(a): tok(e - 1) + 1] = True
    win, windows = np.zeros(n, bool), {}
    for m in spec["moments"]:
        t0, t1 = tok(m["char_start"]), tok(m["char_end"] - 1) + 1
        reply_end = next((tok(e - 1) + 1 for a, e in turns if a <= m["char_start"] < e), t1)
        if m["name"] == "reply":  # the last reply whole
            parts = [(max(0, t0 - BEFORE), n)]
        else:  # around the block's start, and around its end through what follows in the reply (the write's call)
            parts = [(max(0, t0 - BEFORE), min(t1, t0 + AFTER)), (max(t0, t1 - BEFORE), max(t1, min(reply_end, t1 + AFTER)))]
        for lo, hi in parts:
            win[lo:hi] = True
        windows[m["name"]] = {"block": m["block"], "tokens": [t0, t1], "window": [list(p) for p in parts]}
    pred = np.zeros(n, bool)
    pred[:-1] = subj[1:]
    return {"subj": np.flatnonzero(subj), "win": np.flatnonzero(win), "pred": np.flatnonzero(pred), "windows": windows}


def blocks_of(model):
    inner = model.model
    inner = getattr(inner, "language_model", inner)
    return inner, inner.layers


def run(model, ids: torch.Tensor, chunk: int, want: dict[int, np.ndarray], on_chunk) -> None:
    """Chunked prefill with the model's cache; per chunk, calls on_chunk(lo, hi, acts {layer: [hi-lo, d]}, final)."""
    inner, layers = blocks_of(model)
    acts = {}
    hooks = [layers[L].register_forward_hook(
        lambda mod, inp, out, L=L: acts.__setitem__(L, (out[0] if isinstance(out, tuple) else out)[0]))
        for L in want]
    try:
        cache = None
        for lo in range(0, len(ids), chunk):
            hi = min(len(ids), lo + chunk)
            acts.clear()
            with torch.no_grad():
                o = inner(input_ids=ids[None, lo:hi], past_key_values=cache, use_cache=True,
                          cache_position=torch.arange(lo, hi, device=ids.device))
                cache = o.past_key_values
                on_chunk(lo, hi, acts, o.last_hidden_state[0])
    finally:
        for h in hooks:
            h.remove()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--model", default="Qwen/Qwen3.8-27B")
    ap.add_argument("--revision", default=None)
    ap.add_argument("--chunk", type=int, default=2048)
    ap.add_argument("--out", default=None)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N tokens (tests)")
    ap.add_argument("--check-chunking", type=int, default=0, help="compare N tokens in one pass vs chunks of N/4")
    a = ap.parse_args()
    d = Path(a.dir)
    spec = json.loads((d / "capture.json").read_text())
    s = (d / spec["prompt"]).read_text()
    if a.limit:
        s = s[: a.limit * 3]  # characters; trimmed to tokens below
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokz = AutoTokenizer.from_pretrained(a.model, revision=a.revision)
    enc = tokz(s, add_special_tokens=False, return_offsets_mapping=True)
    ids_l, offs = enc["input_ids"], enc["offset_mapping"]
    if a.limit:
        ids_l, offs = ids_l[: a.limit], offs[: a.limit]
        spec["moments"] = [m for m in spec["moments"] if m["char_end"] <= offs[-1][1]]
    P = plan(s, spec, offs)
    n, nl = len(ids_l), None
    print(f"{n:,} tokens; subject {len(P['subj']):,}; window {len(P['win']):,}; predictions {len(P['pred']):,}")
    for name, w in P["windows"].items():
        print(f"  {name:22} block {w['block']}: tokens {w['tokens']}, windows {w['window']}")
    if a.plan_only:
        return
    out = Path(a.out or d / "capture")
    out.mkdir(parents=True, exist_ok=True)
    model = AutoModelForCausalLM.from_pretrained(a.model, revision=a.revision, dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    _, layers = blocks_of(model)
    nl, dm = len(layers), model.config.get_text_config().hidden_size
    readers = [L for L in READER_LAYERS if L < nl]  # all of them on the 27B; the small test models have fewer
    probe = 42 if nl > 42 else nl // 2
    dev = next(model.parameters()).device
    ids = torch.tensor(ids_l, device=dev)
    meta = {"run": spec["run"], "model": a.model, "revision": a.revision, "n_tokens": n, "d": dm, "n_layers": nl,
            "reader_layers": readers, "layer_convention": "output of decoder block L (0-based)",
            "windows": P["windows"], "chunk": a.chunk, "topk": K, "before_after": [BEFORE, AFTER],
            "prompt_sha256": hashlib.sha256(s.encode()).hexdigest(), "attn": model.config._attn_implementation,
            "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0), "checks": {}}
    try:
        import fla  # noqa: F401
        meta["linear_attn_kernels"] = "fla"
    except ImportError:
        meta["linear_attn_kernels"] = "torch fallback"

    if a.check_chunking:
        N = min(a.check_chunking, n)
        got = {}
        for c in (N, N // 4):
            buf = []
            run(model, ids[:N], c, {probe: None}, lambda lo, hi, acts, fin: buf.append(acts[probe].float().cpu()))
            got[c] = torch.cat(buf)
        x, y = got[N], got[N // 4]
        cos = torch.nn.functional.cosine_similarity(x, y, dim=-1)
        meta["checks"]["chunking"] = {"layer": probe, "tokens": N, "chunks": [N, N // 4], "min_cos": cos.min().item(),
                                      "max_rel_err": ((x - y).norm(dim=-1) / x.norm(dim=-1)).max().item(),
                                      "median_rel_err": ((x - y).norm(dim=-1) / x.norm(dim=-1)).median().item()}
        print("chunking check:", meta["checks"]["chunking"])

    np.save(out / "ids.npy", np.array(ids_l, np.int32))
    for k in ("subj", "win", "pred"):
        np.save(out / f"{k}_idx.npy", P[k])
    mm = lambda name, shape: np.lib.format.open_memmap(out / name, mode="w+", dtype=np.uint16, shape=shape)
    subj = {L: mm(f"subj_L{L}.npy", (len(P["subj"]), dm)) for L in readers}
    win = mm("win_all.npy", (len(P["win"]), nl, dm))
    tk_ids = np.zeros((len(P["pred"]), K), np.int32)
    tk_lp = np.zeros((len(P["pred"]), K), np.float16)
    lp, ent = np.zeros(len(P["pred"]), np.float32), np.zeros(len(P["pred"]), np.float32)
    rows = lambda idx, lo, hi: (np.searchsorted(idx, lo), np.searchsorted(idx, hi))
    u16 = lambda t: t.contiguous().view(torch.int16).cpu().numpy().view(np.uint16)
    t0, last = time.time(), [time.time()]

    def on_chunk(lo, hi, acts, fin):
        a0, a1 = rows(P["subj"], lo, hi)
        if a1 > a0:
            sel = torch.from_numpy(P["subj"][a0:a1] - lo).to(dev)
            for L in readers:
                subj[L][a0:a1] = u16(acts[L].index_select(0, sel))
        w0, w1 = rows(P["win"], lo, hi)
        if w1 > w0:
            sel = torch.from_numpy(P["win"][w0:w1] - lo).to(dev)
            win[w0:w1] = u16(torch.stack([acts[L].index_select(0, sel) for L in range(nl)], 1))
        p0, p1 = rows(P["pred"], lo, hi)
        for b0 in range(p0, p1, 512):
            b1 = min(p1, b0 + 512)
            pos = P["pred"][b0:b1]
            h = fin.index_select(0, torch.from_numpy(pos - lo).to(dev))
            logp = torch.log_softmax(model.lm_head(h).float(), -1)
            v, i = logp.topk(K, -1)
            tk_ids[b0:b1], tk_lp[b0:b1] = i.cpu().numpy(), v.half().cpu().numpy()
            nxt = ids[torch.from_numpy(pos + 1).to(dev)]
            lp[b0:b1] = logp.gather(1, nxt[:, None])[:, 0].cpu().numpy()
            ent[b0:b1] = (-(logp.exp() * logp).sum(-1)).cpu().numpy()
        if time.time() - last[0] > 60 or hi == n:
            last[0] = time.time()
            print(f"  {hi:,}/{n:,} tokens, {time.time() - t0:.0f}s, {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB peak", flush=True)

    run(model, ids, a.chunk, {L: None for L in range(nl)}, on_chunk)
    for x in (*subj.values(), win):
        x.flush()
    np.save(out / "pred_topk_ids.npy", tk_ids); np.save(out / "pred_topk_lp.npy", tk_lp)
    np.save(out / "pred_lp.npy", lp); np.save(out / "pred_ent.npy", ent)
    last_reply = P["pred"] >= P["windows"]["reply"]["tokens"][0] if "reply" in P["windows"] else np.ones(len(lp), bool)
    meta["checks"]["teacher_forced"] = {
        "mean_logprob_subject": float(lp.mean()), "mean_logprob_last_reply": float(lp[last_reply].mean()),
        "top1_agree_subject": float((tk_ids[:, 0] == np.array(ids_l)[P["pred"] + 1]).mean()),
        "mean_entropy_subject": float(ent.mean())}
    meta["seconds"] = time.time() - t0
    meta["peak_gib"] = torch.cuda.max_memory_allocated() / 2**30
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print("done:", meta["checks"], f"{meta['seconds']:.0f}s")


if __name__ == "__main__":
    main()
