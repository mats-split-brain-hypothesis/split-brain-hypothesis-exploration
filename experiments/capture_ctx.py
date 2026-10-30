"""Context captures on Qwen3.6-27B (pod only): every position of each bank item, or of a text corpus.

  python experiments/capture_ctx.py --banks all                 # every family x fit/val/bench with a read capture
  python experiments/capture_ctx.py --banks typo/val --limit 3  # smoke
  python experiments/capture_ctx.py --corpus wikitext --n 256 --seq 128
  python experiments/capture_ctx.py --corpus chat --n 2048 --seq 128   # no_robots prompts rendered as the bench renders

Writes ``out/ctx/<family>-<split>.pt`` / ``out/ctx/corpus-<name>.pt`` (``jlm.context``). Existing files are
skipped, so a rerun resumes. Checks, per bank, that the read cells match the read-cell capture
(``out/captures``) to bf16 precision: same render, same positions, same forward pass.
"""

import argparse
import time

import torch

from jlm import banks, capture, context, corpus, wikitext

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def wikitext_windows(tok, n: int, seq: int) -> list[tuple[str, list[int]]]:
    """jle x101's sample: wikitext-103-raw validation (not the lens's fit split), seeded, <= 2 windows per passage."""
    ids = wikitext.sample_ids(wikitext.passages(), tok, n, seq, seed=0)
    return [(f"wikitext-{k:04d}", w) for k, w in enumerate(ids)]


def check(bank: banks.Bank, path) -> str:
    try:
        ref = {it.id: it for it in capture.load(bank)}
    except FileNotFoundError:
        return "no read-cell capture to compare"
    ctx = context.ContextStore(path)
    worst = 0.0
    for iid, it in ref.items():
        c = ctx.items[iid]
        assert c.ids == it.ids and c.idx == it.idx, f"{iid}: render or positions differ"
        for L, a in it.acts.items():
            b = ctx.states(iid, L)[c.idx].float()
            worst = max(worst, ((a.float() - b).norm(dim=1) / a.float().norm(dim=1)).max().item())
    return f"read cells match the read-cell capture (max relative difference {worst:.1e})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--banks", help="family/split,... or 'all'")
    ap.add_argument("--corpus", choices=["wikitext", "chat"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--seq", type=int, default=128)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    backend = capture.load_backend(args.device)
    if args.banks:
        names = ([f"{f}/{s}" for f in FAMILIES for s in banks.SPLITS] if args.banks == "all" else args.banks.split(","))
        for n in names:
            try:
                bank = banks.load(*n.split("/"))
            except FileNotFoundError:
                print(f"{n}: no bank, skipped", flush=True)
                continue
            if context.bank_path(bank).exists() and not args.limit:
                print(f"{n}: exists, skipped", flush=True)
                continue
            t = time.time()
            path = context.capture_bank(backend, bank, limit=args.limit)
            print(f"{n}: {len(bank.items)} items -> {path} ({time.time() - t:.0f}s); "
                  f"{check(bank, path) if not args.limit else 'smoke'}", flush=True)
    if args.corpus:
        if context.corpus_path(args.corpus).exists():
            print(f"corpus {args.corpus}: exists, skipped")
            return
        t = time.time()
        if args.corpus == "chat":  # whole renders (user turn + generation prompt), those within --seq tokens
            texts = corpus.chat_renders(backend.tokenizer, n=args.n, seed=args.seed, max_tokens=args.seq)
            source = f"{corpus.CHAT_REPO}@{corpus.CHAT_REVISION[:8]} {corpus.CHAT_SPLIT}, {len(texts)} renders <= {args.seq} tokens, seed {args.seed}"
        else:
            texts = wikitext_windows(backend.tokenizer, args.n, args.seq)
            source = f"Salesforce/wikitext validation, {args.n} x {args.seq}"
        path = context.capture_texts(backend, args.corpus, texts, GRID, source)
        print(f"corpus {args.corpus}: {len(texts)} windows -> {path} ({time.time() - t:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
