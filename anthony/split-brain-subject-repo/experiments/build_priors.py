"""Vocabulary-space priors and the template-token set for the round-2 centres (S13, S14). Tokenizer only: no model,
no lens, runs anywhere in a minute.

  python experiments/build_priors.py --unigram chat            # out/priors/unigram-norobots.pt
  python experiments/build_priors.py --unigram wikitext        # out/priors/unigram-wikitext.pt (the prose control)
  python experiments/build_priors.py --template-tokens         # data/template_tokens/template.json

Unigram prior: log((count + 1) / (N + V)) over every position of the rendered corpus (template tokens included: the
point is the chat-template prior, ``--content-only`` counts the user text alone). S13's ``c``.

Template tokens (S14's ``T``), ordered so that "the first k" is meaningful: (1) the chat template's own special tokens
(``<|im_start|>``, ``<|im_end|>``, ``<think>`` ...), (2) tokens that the decoded reference-arm means (fam, tok, kmx64, knnx8, pco16, u1rel) share at layers >= 36
(``g_decoded`` blocks of ``out/analysis/*/<family>-<split>.json``, ``analyse.py --decode-g``), by how many families
show them (at least 3), (3)
the most frequent tokens of the chat unigram prior, (4) a short hand list of continuation-prior tokens, (5) the tokenizer's other special tokens. Any token
that is an accepted target id of a fit / val item of a single-token family is dropped (the set must never contain a
target; the bench's targets are not consulted). Each entry records its sources.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, REPO_ROOT, banks, corpus, score
from jlm.lens import MODEL
from jlm.pullback import PRIORS

TEMPLATE_DIR = REPO_ROOT / "data" / "template_tokens"
HAND = ["\n", "\n\n", ".", ",", ":", " The", "The", " This", "This", " the", " a", " an", " and", " is", " of", " to",
        " in", " that", " it", " I", "I", " ...", "...", " (", ")", "\"", " \"", "'", " '", "____", " ____"]
SINGLE_TOKEN = ["typo", "association", "basic_readout", "multihop", "multilingual"]
CHAT_SPECIAL = ["<|im_start|>", "<|im_end|>", "<|endoftext|>", "<think>", "</think>"]  # the chat template's own tokens


def tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])


def vocab_display(tok) -> list[str]:
    from wsbench.produce.render import display_tokens

    n = len(tok)  # the model's lm_head has vocab_size rows >= len(tok); pad the rest with ""
    out = display_tokens(tok, list(range(n)))
    return out


def unigram(name: str, n: int, seq: int, content_only: bool) -> Path:
    tok = tokenizer()
    if name == "chat":
        texts = corpus.chat_renders(tok, n=n, seed=0)
        if content_only:
            texts = [(cid, tok(t, add_special_tokens=False)["input_ids"]) for cid, _, t in corpus.chat_prompts(n, 0)]
        source, stem = f"{corpus.CHAT_REPO}@{corpus.CHAT_REVISION[:8]} {corpus.CHAT_SPLIT}", "norobots"
    elif name == "wikitext":
        texts = corpus.wikitext_windows(tok, n or 897, seq)
        source, stem = f"Salesforce/wikitext validation, {len(texts)} x {seq}", "wikitext"
    else:
        raise ValueError(name)
    V = 248320  # Qwen3.6-27B lm_head rows (config vocab_size); > len(tokenizer)
    counts = torch.zeros(V, dtype=torch.int64)
    for _, ids in texts:
        counts += torch.bincount(torch.tensor(ids), minlength=V)
    N = int(counts.sum())
    logp = torch.log((counts.double() + 1) / (N + V)).float()
    path = PRIORS / f"unigram-{stem}{'-content' if content_only else ''}.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"source": source, "n_texts": len(texts), "n_tokens": N, "content_only": content_only, "smoothing": "add-one"}
    torch.save({"logp": logp, "counts": counts, "meta": meta}, path)
    write_artefact(path.with_suffix(".provenance.json"),
                   Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=source, extra=meta),
                   {"top": [tok.convert_ids_to_tokens(int(i)) for i in counts.topk(30).indices]})
    print(f"{path}: {len(texts)} texts, {N} tokens; top: {[tok.convert_ids_to_tokens(int(i)) for i in counts.topk(12).indices]}")
    return path


REFERENCE_ARMS = ("fam", "tok", "kmx64", "knnx8", "pco16", "u1rel")  # whose decoded means define "template"
MIN_LAYER = 36  # below this the decoded means are byte fragments, not the continuation prior


def decoded_shared(min_families: int, dirs: list[Path]) -> dict[str, set[str]]:
    """display token -> families whose decoded means show it (reference arms, layers >= MIN_LAYER), over the
    analysis dirs' ``g_decoded`` blocks; kept when at least ``min_families`` families share it."""
    fams: dict[str, set[str]] = defaultdict(set)
    for d in dirs:
        for p in d.glob("*.json"):
            try:
                obj = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            family = obj.get("bank", p.stem).split("/")[0].rsplit("-", 1)[0]
            for arm, per_layer in obj.get("g_decoded", {}).items():
                if arm.split("@")[0].split("|")[0] not in REFERENCE_ARMS:
                    continue
                for layer, toks in per_layer.items():
                    if int(layer) < MIN_LAYER:
                        continue
                    for t in toks:
                        fams[t].add(family)
    return {t: fs for t, fs in fams.items() if len(fs) >= min_families}


def target_ids(vocab: list[str]) -> set[int]:
    """Accepted target ids of every fit / val item of the single-token families (never in the template set)."""
    out: set[int] = set()
    for f in SINGLE_TOKEN:
        for split in ("fit", "val"):
            try:
                bank = banks.load(f, split)
            except FileNotFoundError:
                continue
            for ids in score.accepted_ids(vocab, bank).values():
                out.update(ids)
    return out


def template_tokens(name: str, min_families: int, top_frequent: int, decode_dirs: list[Path], unigram_path: Path) -> Path:
    tok = tokenizer()
    vocab = vocab_display(tok)
    by_display: dict[str, int] = {}
    for i, s in enumerate(vocab):
        by_display.setdefault(s, i)
    excluded = target_ids(vocab)
    entries: dict[int, dict] = {}

    def add(i: int, source: str, weight: float = 0.0) -> None:
        if i in excluded or i >= len(vocab):
            return
        e = entries.setdefault(i, {"id": i, "text": vocab[i], "sources": [], "weight": 0.0})
        e["sources"].append(source)
        e["weight"] = max(e["weight"], weight)

    for t in sorted(tok.all_special_tokens + list(tok.get_added_vocab())):  # chat-template specials first, the rest last
        add(tok.convert_tokens_to_ids(t), "special", 1e6 if t in CHAT_SPECIAL else 0.5)
    shared = decoded_shared(min_families, decode_dirs)
    for t, fs in sorted(shared.items(), key=lambda kv: -len(kv[1])):
        if t in by_display:
            add(by_display[t], f"decoded means of {len(fs)} families", 1e3 + len(fs))
    if unigram_path.exists():
        counts = torch.load(unigram_path, weights_only=False)["counts"]
        for rank, i in enumerate(counts.topk(top_frequent).indices.tolist()):
            add(i, f"chat unigram top {top_frequent}", 1e2 + (top_frequent - rank))
    for t in HAND:
        ids = tok(t, add_special_tokens=False)["input_ids"]
        if len(ids) == 1:
            add(ids[0], "hand list", 1.0)
    ordered = sorted(entries.values(), key=lambda e: (-e["weight"], e["id"]))
    for e in ordered:
        e.pop("weight")
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATE_DIR / f"{name}.json"
    path.write_text(json.dumps({"name": name, "model": MODEL, "model_revision": PINS[MODEL], "n": len(ordered),
                                "excluded_targets": len(excluded), "min_families": min_families,
                                "decode_dirs": [str(d.relative_to(REPO_ROOT)) if d.is_relative_to(REPO_ROOT) else str(d) for d in decode_dirs],
                                "tokens": ordered}, indent=1, ensure_ascii=False) + "\n")
    src = Counter(s.split(" of ")[0].split(" top ")[0] for e in ordered for s in e["sources"])
    print(f"{path}: {len(ordered)} tokens ({dict(src)}); first 20: {[e['text'] for e in ordered[:20]]}")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--unigram", choices=["chat", "wikitext"])
    ap.add_argument("--n", type=int, default=0, help="texts to use (0: all 9.5k chat prompts / 897 wikitext windows)")
    ap.add_argument("--seq", type=int, default=128, help="wikitext window length")
    ap.add_argument("--content-only", action="store_true", help="count the user text without the chat template")
    ap.add_argument("--template-tokens", action="store_true")
    ap.add_argument("--name", default="template")
    ap.add_argument("--min-families", type=int, default=3)
    ap.add_argument("--top-frequent", type=int, default=128)
    ap.add_argument("--decode-dirs", default="", help="comma-separated out/analysis dirs with g_decoded (default: all)")
    args = ap.parse_args()
    if args.unigram:
        unigram(args.unigram, args.n, args.seq, args.content_only)
    if args.template_tokens:
        dirs = ([OUT / "analysis" / d for d in args.decode_dirs.split(",")] if args.decode_dirs
                else sorted(p for p in (OUT / "analysis").glob("*") if p.is_dir()))
        template_tokens(args.name, args.min_families, args.top_frequent, dirs, PRIORS / "unigram-norobots.pt")
    if not args.unigram and not args.template_tokens:
        ap.print_help()


if __name__ == "__main__":
    main()
