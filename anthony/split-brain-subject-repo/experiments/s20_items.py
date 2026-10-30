"""S20 item-level deep dive: which val items no class of g can fix even when fitted with targets, and how far their
targets stay from the top 10 (the readout's limit, not the centre's). Reads the pipeline's val reads of the ceilings
(``out/analysis/S20/eval``) and the reference arms (``out/eval``); single-token families (strict ranks).
Writes out/analysis/S20/items.md.

  python experiments/s20_items.py
"""

import json
from collections import defaultdict
from pathlib import Path

from transformers import AutoTokenizer
from umot.provenance import PINS
from wsbench.produce.render import display_tokens

from jlm import OUT, banks
from jlm.capture import MODEL

FAMS = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation"]
CEIL = ["ceil.const-at-fit__cos", "ceil.tok-at-fit__cos", "ceil.proj16-at-fit__cos"]


def best(path: Path) -> dict[str, tuple[int, int, int]]:
    """item -> (best rank over cells and layers, its layer, its best id)."""
    out: dict = {}
    for line in path.open():
        r = json.loads(line)
        if r["id"] not in out or r["rank"] < out[r["id"]][0]:
            out[r["id"]] = (r["rank"], r["layer"], r["best_id"])
    return out


def top10(path: Path, item: str, layer: int) -> list[str]:
    for line in path.open():
        r = json.loads(line)
        if r["id"] == item and r["layer"] == layer:
            return r["tokens"]
    return []


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    S = OUT / "analysis" / "S20" / "eval"
    md = ["# S20 items: what no ceiling fixes (val, strict, cos; ceilings fitted WITH fit targets)", "",
          "| family | n | fam passes | a ceiling passes, fam not | no ceiling passes | of those: best rank 10-99 / 100-999 / 1000+ | median best rank (best ceiling) | best layer (mode) |",
          "|---|---|---|---|---|---|---|---|"]
    detail = []
    for f in FAMS:
        root_f = OUT / "eval" / f / "val"
        fam = best(root_f / "fam-at-fit__cos" / "ranks.jsonl")
        ceils = {c: best(S / f / "val" / c / "ranks.jsonl") for c in CEIL if (S / f / "val" / c / "ranks.jsonl").exists()}
        ids = sorted(set(fam) & set.intersection(*(set(v) for v in ceils.values())))
        fam_pass = [i for i in ids if fam[i][0] < 10]
        ceil_best = {i: min((ceils[c][i] + (c,) for c in ceils), key=lambda t: t[0]) for i in ids}
        only = [i for i in ids if ceil_best[i][0] < 10 and fam[i][0] >= 10]
        never = [i for i in ids if ceil_best[i][0] >= 10]
        bands = [sum(1 for i in never if lo <= ceil_best[i][0] < hi) for lo, hi in ((10, 100), (100, 1000), (1000, 10**9))]
        ranks = sorted(ceil_best[i][0] for i in never)
        med = ranks[len(ranks) // 2] if ranks else "-"
        layers = defaultdict(int)
        for i in never:
            layers[ceil_best[i][1]] += 1
        mode = max(layers, key=layers.get) if layers else "-"
        md.append(f"| {f} | {len(ids)} | {len(fam_pass)} | {len(only)} | {len(never)} | {' / '.join(map(str, bands))} | {med} | {mode} |")
        bank = {it["id"]: it for it in banks.load(f, "val").items}
        detail += [f"## {f}: items no ceiling fixes ({len(never)})", ""]
        for i in sorted(never, key=lambda i: ceil_best[i][0])[:8]:
            rk, L, bid, c = ceil_best[i]
            it = bank.get(i, {})
            prompt = (it.get("prompt") or json.dumps(it.get("messages", ""))[:200]).replace("\n", " ")[:160]
            tgt = display_tokens(tok, [bid])[0]
            t10 = top10(S / f / "val" / c / "readouts.jsonl", i, L)
            detail.append(f"- `{i}` target {tgt!r} best rank {rk} at L{L} ({c.split('-')[0]}); prompt: {prompt!r}; top 10: {' '.join(repr(x) for x in t10)}")
        detail.append("")
    (OUT / "analysis" / "S20" / "items.md").write_text("\n".join(md + [""] + detail) + "\n")
    print("\n".join(md + [""] + detail))


if __name__ == "__main__":
    main()
