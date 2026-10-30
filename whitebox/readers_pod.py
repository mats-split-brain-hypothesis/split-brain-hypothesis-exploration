"""Readers on the pod (READERS.md R0 / R1). The subject's states are recomputed here with Qwen3.8-27B (2-3 min per
target, the same shapes as capture.py) instead of uploading the 50 GB of captures.

    python readers_pod.py jlens T1 T2 ...   # R1: plain and same-token-centred J-lens, every subject token, 12 layers
    python readers_pod.py r0 T1 T2 ...      # R0: Qwen3.6-27B over the same sequences at sampled positions
    python readers_pod.py r0lens T1 T2 ...  # R0: the J-lens on those Qwen3.6 states (the comparison point)
    python readers_pod.py meta T1 T2 ...    # R3: oracle lens L32/44/56, text-only control, NLA L42 at positions.json
    python readers_pod.py vstates T1 ...    # dense read's controls: Qwen3.8 states at the write tokens of variants/{swap,strip}
    python readers_pod.py dense T1 ...      # the dense read: oracle lens L32/44 (k=3) + text-only, and the controls (k=1)

jlens -> out/T/readers/jlens_{plain,centred}_{ids,sc}.npy [n_subj, 12, 10] (int32 token ids, float16 cos scores),
         centre_n.npy [n_subj] (other-run occurrences behind each position's centre; < MIN_N = layer mean fallback),
         and out/T/states/subj_L{L}.npy (kept for R3). Centre = the mean state of the same token id at that layer over
         the other targets' subject positions (leave-own-run-out).
r0    -> out/T/r0/{pos,ids36_top,ids38_top}.npy, states36_L{L}.npy at 2,000 random subject positions per target:
         Qwen3.6's own top-10 next tokens there and its states (J-lens agreement on 3.6 vs 3.8 is computed at home).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

from capture import READER_LAYERS, blocks_of, plan, run

M38, R38 = "Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
M36, R36 = "Qwen/Qwen3.6-27B", "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
OUT = Path("out")
MIN_N, TOPK, BATCH, N_R0 = 5, 10, 1024, 2000
torch.backends.cuda.matmul.allow_tf32 = True


def sequence(t: str, tok) -> tuple[list[int], dict]:
    d = OUT / t
    spec = json.loads((d / "capture.json").read_text())
    s = (d / spec["prompt"]).read_text()
    enc = tok(s, add_special_tokens=False, return_offsets_mapping=True)
    return enc["input_ids"], plan(s, spec, enc["offset_mapping"])


def states(model, ids: list[int], idx: np.ndarray, layers: list[int]) -> dict[int, torch.Tensor]:
    """bf16 CPU [len(idx), d] per layer at positions idx, from one chunked pass."""
    dev = next(model.parameters()).device
    out = {L: torch.empty(len(idx), model.config.get_text_config().hidden_size, dtype=torch.bfloat16) for L in layers}

    def on_chunk(lo, hi, acts, fin):
        a0, a1 = np.searchsorted(idx, lo), np.searchsorted(idx, hi)
        if a1 > a0:
            sel = torch.from_numpy(idx[a0:a1] - lo).to(dev)
            for L in layers:
                out[L][a0:a1] = acts[L].index_select(0, sel).cpu()

    run(model, torch.tensor(ids, device=dev), 2048, {L: None for L in layers}, on_chunk)
    return out


def load(name, rev):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(name, revision=rev)
    model = AutoModelForCausalLM.from_pretrained(name, revision=rev, dtype=torch.bfloat16, device_map="cuda").eval()
    return tok, model


def jlens(targets: list[str]) -> None:
    tok, model = load(M38, R38)
    S, toks = {}, {}
    for t in targets:
        t0 = time.time()
        ids, P = sequence(t, tok)
        S[t] = states(model, ids, P["subj"], READER_LAYERS)
        toks[t] = torch.tensor(np.array(ids)[P["subj"]], dtype=torch.long)
        (OUT / t / "states").mkdir(parents=True, exist_ok=True)
        np.save(OUT / t / "states" / "subj_idx.npy", P["subj"])
        for L in READER_LAYERS:
            np.save(OUT / t / "states" / f"subj_L{L}.npy", S[t][L].view(torch.int16).numpy().view(np.uint16))
        print(f"{t}: states {len(P['subj']):,} positions, {time.time() - t0:.0f}s", flush=True)
    del model
    torch.cuda.empty_cache()

    from jlm.lens import Lens  # Qwen3.6-27B's J-lens (JLM_MODEL default qwen27b): maps, W_U, denominators
    lens = Lens(READER_LAYERS, device="cuda")
    uniq, inv = torch.unique(torch.cat([toks[t] for t in targets]), return_inverse=True)
    cut = np.cumsum([0] + [len(toks[t]) for t in targets])
    comp = {t: inv[cut[k]:cut[k + 1]] for k, t in enumerate(targets)}  # token ids -> compact index
    U = len(uniq)
    res = {t: {m: (np.zeros((len(toks[t]), len(READER_LAYERS), TOPK), np.int32),
                   np.zeros((len(toks[t]), len(READER_LAYERS), TOPK), np.float16)) for m in ("plain", "centred")}
           for t in targets}
    cn = {}
    for li, L in enumerate(READER_LAYERS):
        t0 = time.time()
        sums, cnts = {}, {}
        for t in targets:  # per-target sums by token id (fp32, on the GPU)
            x = S[t][L].cuda().float()
            sums[t] = torch.zeros(U, x.shape[1], device="cuda").index_add_(0, comp[t].cuda(), x)
            cnts[t] = torch.bincount(comp[t].cuda(), minlength=U).float()
            del x
        tot_s, tot_c = sum(sums.values()), sum(cnts.values())
        for t in targets:
            o_s, o_c = tot_s - sums[t], tot_c - cnts[t]
            layer_mean = o_s.sum(0) / o_c.sum()
            tt = comp[t].cuda()
            n_other = o_c[tt]
            if li == 0:
                cn[t] = n_other.cpu().numpy().astype(np.int32)
            for b in range(0, len(tt), BATCH):
                x = S[t][L][b:b + BATCH].cuda().float()
                n = n_other[b:b + BATCH, None]
                mu = torch.where(n >= MIN_N, o_s[tt[b:b + BATCH]] / n.clamp_min(1), layer_mean)
                for m, z in (("plain", x), ("centred", x - mu)):
                    v, i = lens.scores(z, L, "cos").topk(TOPK, -1)
                    res[t][m][0][b:b + BATCH, li] = i.cpu().numpy()
                    res[t][m][1][b:b + BATCH, li] = v.half().cpu().numpy()
            del o_s
        del sums, tot_s
        torch.cuda.empty_cache()
        print(f"L{L}: {time.time() - t0:.0f}s", flush=True)
    for t in targets:
        d = OUT / t / "readers"
        d.mkdir(parents=True, exist_ok=True)
        for m, (i, v) in res[t].items():
            np.save(d / f"jlens_{m}_ids.npy", i)
            np.save(d / f"jlens_{m}_sc.npy", v)
        np.save(d / "centre_n.npy", cn[t])
        (d / "jlens_meta.json").write_text(json.dumps({
            "lens": "neuronpedia/jacobian-lens qwen3.6-27b jlens (jlm.lens.Lens 'jlens'), readout cos, W_U of Qwen3.6-27B",
            "layers": READER_LAYERS, "topk": TOPK, "centre": "same token id, other targets' subject positions",
            "min_n": MIN_N, "fallback": "layer mean of the other targets", "states": f"{M38}@{R38}"}))
        print(f"{t}: jlens saved; centre fallback at {(cn[t] < MIN_N).mean():.1%} of positions", flush=True)


def r0(targets: list[str]) -> None:
    tok, model = load(M36, R36)
    tok38 = __import__("transformers").AutoTokenizer.from_pretrained(M38, revision=R38)
    rng = np.random.default_rng(0)
    for t in targets:
        t0 = time.time()
        ids, P = sequence(t, tok38)
        ids36, _ = sequence(t, tok)
        assert ids36 == ids, "Qwen3.6 tokenizes the sequence differently"
        pos = np.sort(rng.choice(P["subj"][:-1], size=min(N_R0, len(P["subj"]) - 1), replace=False))
        dev = next(model.parameters()).device
        layers = sorted(set(READER_LAYERS) | {63})
        got = states(model, ids, pos, layers)
        d = OUT / t / "r0"
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "pos.npy", pos)
        h = got[63].cuda()
        logits = model.lm_head(blocks_of(model)[0].norm(h))
        np.save(d / "ids36_top.npy", logits.float().topk(TOPK, -1).indices.cpu().numpy().astype(np.int32))
        for L in READER_LAYERS:
            np.save(d / f"states36_L{L}.npy", got[L].view(torch.int16).numpy().view(np.uint16))
        print(f"{t}: r0 {len(pos)} positions, {time.time() - t0:.0f}s", flush=True)


def r0lens(targets: list[str]) -> None:
    """R0's comparison point: the same J-lens on Qwen3.6's own states at the r0 positions -> r0/jlens36_ids.npy."""
    from jlm.lens import Lens
    lens = Lens(READER_LAYERS, device="cuda")
    for t in targets:
        d = OUT / t / "r0"
        out = np.zeros((len(np.load(d / "pos.npy")), len(READER_LAYERS), TOPK), np.int32)
        for li, L in enumerate(READER_LAYERS):
            x = torch.from_numpy(np.load(d / f"states36_L{L}.npy").view(np.int16)).view(torch.bfloat16)
            for b in range(0, len(x), BATCH):
                out[b:b + BATCH, li] = lens.scores(x[b:b + BATCH].cuda().float(), L, "cos").topk(TOPK, -1).indices.cpu().numpy()
        np.save(d / "jlens36_ids.npy", out)
        print(f"{t}: r0 J-lens on 3.6 states saved", flush=True)


OL_LAYERS, NLA_L, META_BATCH = (32, 44, 56), 42, 128
TEXT_Q = ("Here is the end of a passage the writer is producing:\n\n---\n{ctx}\n---\n\n"
          "In one or two sentences: what is the writer thinking about at the very end of this passage?")


def _vecs(t: str, L: int, pos: list[int], source: str) -> torch.Tensor:
    """States at positions: '3.8' from states/ (every subject token), '3.6' from r0/ (its sampled positions), 'dense'
    from states_dense/ (uploaded rows of the captures), 'swap' / 'strip' from variants/<name>/ (vstates)."""
    d = OUT / t
    if source == "3.8":
        idx, f = np.load(d / "states" / "subj_idx.npy"), d / "states" / f"subj_L{L}.npy"
    elif source == "3.6":
        idx, f = np.load(d / "r0" / "pos.npy"), d / "r0" / f"states36_L{L}.npy"
    elif source == "dense":
        idx, f = np.load(d / "states_dense" / "subj_idx.npy"), d / "states_dense" / f"subj_L{L}.npy"
    else:
        idx, f = np.load(d / "variants" / source / "pos.npy"), d / "variants" / source / f"states_L{L}.npy"
    arr = np.load(f, mmap_mode="r")
    rows = np.searchsorted(idx, pos)
    assert (idx[rows] == pos).all(), f"{t}: positions not captured for {source}"
    return torch.from_numpy(np.ascontiguousarray(arr[rows]).view(np.int16)).view(torch.bfloat16).float()


def _jobs(targets: list[str]) -> list[dict]:
    """positions.json (sites.py) per target: [{pos, tag, k}], plus R0's content control: the first 50 r0 positions,
    read from both models' states."""
    out = []
    for t in targets:
        P = json.loads((OUT / t / "positions.json").read_text())
        out += [{"t": t, "pos": p["pos"], "tag": p["tag"], "k": p["k"], "src": "3.8"} for p in P]
        r0p = np.load(OUT / t / "r0" / "pos.npy")[:50].tolist()
        out += [{"t": t, "pos": p, "tag": "r0-control", "k": 1, "src": s} for p in r0p for s in ("3.8", "3.6")]
    return out


def _rows(f: Path) -> list[dict]:
    """meta.jsonl's complete lines (a line cut by a restart is skipped, and its readout redone)."""
    out = []
    for l in (f.open() if f.exists() else []):
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out


def _write(f, rows: list[dict]) -> None:
    with f.open("a") as h:
        for r in rows:
            h.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read(reader, layer: int, jobs: list[dict], name: str, f: Path) -> None:
    from jlmeta.readers import Sampling
    done = {(r["t"], r["pos"], r["src"], r["layer"]) for r in _rows(f)}
    todo = [j for j in jobs if (j["t"], j["pos"], j["src"], layer) not in done]
    t0 = time.time()
    for k in sorted({j["k"] for j in todo}):
        grp = [j for j in todo if j["k"] == k]
        step = max(1, META_BATCH // k)  # k samples per position: keep ~META_BATCH sequences per generate call
        for b in range(0, len(grp), step):
            batch = grp[b:b + step]
            vecs = torch.cat([_vecs(j["t"], layer, [j["pos"]], j["src"]) for j in batch])
            texts = reader.explain(vecs, layer, Sampling(k=k))
            _write(f, [{**j, "reader": name, "layer": layer, "texts": x} for j, x in zip(batch, texts)])
        print(f"{name} L{layer} k={k}: {len(grp)} positions, {time.time() - t0:.0f}s", flush=True)


def meta(targets: list[str]) -> None:
    """R3: the oracle lens (L32 / L44 / L56) and the text-only control on Qwen3.6-27B, then the NLA (L42).
    -> out/meta.jsonl (one line per position, reader, layer, source), out/meta_checks.json."""
    from jlmeta import readers
    from umot.provenance import PINS
    jobs, f, checks = _jobs(targets), OUT / "meta.jsonl", {}
    tok, base = load(M36, R36)
    ol = readers.OracleLens.load(base, tok, "cuda", revision=PINS[readers.OLENS_REPO])
    for L in OL_LAYERS:
        checks[f"olens L{L}"] = readers.injection_check(ol, base.config.get_text_config().hidden_size, L)
        assert checks[f"olens L{L}"] > 1e-3, "oracle lens: injection is a no-op"
        _read(ol, L, jobs, "olens", f)
    # text-only control: the base model (adapter off) sees only the 64 tokens before the position
    ids = {t: sequence(t, tok)[0] for t in targets}
    todo = [j for j in jobs if j["src"] == "3.8"]
    done = {(r["t"], r["pos"]) for r in _rows(f) if r["reader"] == "text-only"}
    todo = [j for j in todo if (j["t"], j["pos"]) not in done]
    t0 = time.time()
    with ol.model.disable_adapter():
        for b in range(0, len(todo), META_BATCH):
            batch = todo[b:b + META_BATCH]
            prompts = [tok.apply_chat_template([{"role": "user", "content": TEXT_Q.format(
                ctx=tok.decode(ids[j["t"]][max(0, j["pos"] - 63): j["pos"] + 1]))}], tokenize=False,
                add_generation_prompt=True, enable_thinking=False) for j in batch]
            tok.padding_side = "left"
            enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                out = ol.model.generate(**enc, max_new_tokens=96, do_sample=True, temperature=1.0, top_p=0.95, top_k=64,
                                        pad_token_id=tok.pad_token_id or tok.eos_token_id)
            texts = tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            _write(f, [{**j, "reader": "text-only", "layer": None, "texts": [x.strip()]} for j, x in zip(batch, texts)])
    print(f"text-only: {len(todo)} positions, {time.time() - t0:.0f}s", flush=True)
    del ol, base
    torch.cuda.empty_cache()
    nla = readers.NLA.load("nla-i400", "cuda")
    checks["nla L42"] = readers.injection_check(nla, 5120, NLA_L)
    assert checks["nla L42"] > 1e-3, "NLA: injection is a no-op"
    _read(nla, NLA_L, jobs, "nla", f)
    (OUT / "meta_checks.json").write_text(json.dumps(checks))
    print("meta checks:", checks, flush=True)


DENSE_LAYERS = (32, 44)


def vstates(targets: list[str]) -> None:
    """The controls' states (variants.py): Qwen3.8 over each variant sequence, L32 / L44 at its write tokens."""
    from transformers import AutoTokenizer
    tok, model = load(M38, R38)
    for t in targets:
        for name in ("swap", "strip"):
            d = OUT / t / "variants" / name
            t0 = time.time()
            ids = tok((d / "prompt.txt").read_text(), add_special_tokens=False)["input_ids"]
            pos = np.array(sorted(p["pos"] for p in json.loads((d / "positions.json").read_text())))
            got = states(model, ids, pos, list(DENSE_LAYERS))
            np.save(d / "pos.npy", pos)
            for L in DENSE_LAYERS:
                np.save(d / f"states_L{L}.npy", got[L].view(torch.int16).numpy().view(np.uint16))
            print(f"{t} {name}: {len(ids):,} tokens, {len(pos)} write states, {time.time() - t0:.0f}s", flush=True)


def dense(targets: list[str]) -> None:
    """The dense read: the oracle lens at L32 / L44 over positions_dense.json (k = 3) and the controls' write tokens
    (k = 1), the text-only control at the dense positions. -> out/meta_dense.jsonl"""
    from jlmeta import readers
    from umot.provenance import PINS
    jobs = []
    for t in targets:
        jobs += [{"t": t, "pos": p["pos"], "tag": p["tag"], "k": p["k"], "src": "dense"}
                 for p in json.loads((OUT / t / "positions_dense.json").read_text())]
        for name in ("swap", "strip"):
            jobs += [{"t": t, "pos": p["pos"], "orig": p["orig"], "tag": p["tag"], "k": 1, "src": name}
                     for p in json.loads((OUT / t / "variants" / name / "positions.json").read_text())]
    f = OUT / "meta_dense.jsonl"
    tok, base = load(M36, R36)
    ol = readers.OracleLens.load(base, tok, "cuda", revision=PINS[readers.OLENS_REPO])
    checks = {}
    for L in DENSE_LAYERS:
        checks[f"olens L{L}"] = readers.injection_check(ol, base.config.get_text_config().hidden_size, L)
        assert checks[f"olens L{L}"] > 1e-3, "oracle lens: injection is a no-op"
        _read(ol, L, jobs, "olens", f)
    ids = {t: sequence(t, tok)[0] for t in targets}
    done = {(r["t"], r["pos"]) for r in _rows(f) if r["reader"] == "text-only"}
    todo = [j for j in jobs if j["src"] == "dense" and (j["t"], j["pos"]) not in done]
    t0 = time.time()
    with ol.model.disable_adapter():
        for b in range(0, len(todo), META_BATCH):
            batch = todo[b:b + META_BATCH]
            prompts = [tok.apply_chat_template([{"role": "user", "content": TEXT_Q.format(
                ctx=tok.decode(ids[j["t"]][max(0, j["pos"] - 63): j["pos"] + 1]))}], tokenize=False,
                add_generation_prompt=True, enable_thinking=False) for j in batch]
            tok.padding_side = "left"
            enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                out = ol.model.generate(**enc, max_new_tokens=96, do_sample=True, temperature=1.0, top_p=0.95, top_k=64,
                                        pad_token_id=tok.pad_token_id or tok.eos_token_id)
            texts = tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            _write(f, [{**j, "reader": "text-only", "layer": None, "texts": [x.strip()]} for j, x in zip(batch, texts)])
    print(f"text-only: {len(todo)} positions, {time.time() - t0:.0f}s", flush=True)
    (OUT / "meta_dense_checks.json").write_text(json.dumps(checks))
    print("dense checks:", checks, flush=True)


if __name__ == "__main__":
    {"jlens": jlens, "r0": r0, "r0lens": r0lens, "meta": meta, "vstates": vstates, "dense": dense}[sys.argv[1]](sys.argv[2:])
