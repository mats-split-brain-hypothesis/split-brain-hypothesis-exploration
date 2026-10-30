"""S23: per-layer centre selection on fit (instance e1, steward's card).

From each component's stored readouts, the exact per-(item, layer) pass (strict on the single-token families, the piece
proxy on the _mt families, as evaluate.py scores them). A layer map (layer -> component) passes an item when some layer's
assigned component passes it there: the item rule, so a map's macro is exact without re-reading anything. Greedy
coordinate ascent over layers on the fit macro (all 11 families) from the best single component; 3 random maps as the
control; the chosen map is scored on val the same way and written to out/analysis/S23/map-<readout>.json for the
pipeline read (centre ``s23map:<readout>``).

  python experiments/s23_select.py --readout cos
"""

import argparse
import json
import random
from collections import defaultdict

import numpy as np
from transformers import AutoTokenizer
from umot.provenance import PINS
from wsbench.produce.render import display_tokens

from jlm import OUT, banks, mtproxy, score
from jlm.judge import MULTI_TOKEN
from jlm.lens import MODEL
from jlm.mu.clusters import FAMILIES

COMPONENTS = ["zero", "kmx64@fit", "s14t64@{own}", "s14:template:64:mean=kmx64:a=0.5@{own}", "knnxs8@fit"]


def slug(a: str) -> str:
    return a.replace("|", "__").replace("@", "-at-").replace(":", "~")


def tables(split: str, readout: str, comps: list[str], tok, disp):
    """{family: (ids, layers, {comp: bool [n, L]})}"""
    own = "self" if split == "fit" else "fit"
    out = {}
    for f in FAMILIES:
        bank = banks.load(f, split)
        root = OUT / "eval" / f / split
        ids = json.loads((root / "summary.json").read_text())["result"]["scored_ids"]
        units = mtproxy.units_of(bank, tok, disp) if f in MULTI_TOKEN else None
        T, layers = {}, None
        for c in comps:
            arm = c.format(own=own) + f"|{readout}"
            rows = [json.loads(x) for x in (root / slug(arm) / "readouts.jsonl").read_text().splitlines()]
            by = defaultdict(list)
            for r in rows:
                by[r["layer"]].append(r)
            layers = sorted(by)
            M = np.zeros((len(ids), len(layers)), dtype=bool)
            for j, L in enumerate(layers):
                p = mtproxy.item_passes(by[L], units) if units is not None else score.strict_items(by[L], bank)
                M[:, j] = [bool(p.get(i, False)) for i in ids]
            T[c] = M
        out[f] = (ids, layers, T)
    return out


def macro(tab, assign: list[str]) -> float:
    vals = []
    for f, (ids, layers, T) in tab.items():
        hit = np.zeros(len(ids), dtype=bool)
        for j, c in enumerate(assign):
            hit |= T[c][:, j]
        vals.append(hit.mean())
    return float(np.mean(vals))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readout", default="cos")
    args = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    disp = lambda ids: display_tokens(tok, ids)  # noqa: E731
    fit, val = tables("fit", args.readout, COMPONENTS, tok, disp), tables("val", args.readout, COMPONENTS, tok, disp)
    layers = next(iter(fit.values()))[1]
    n = len(layers)
    lines = [f"# S23 per-layer selection ({args.readout})", "", f"layers {layers}", ""]
    single = {c: (macro(fit, [c] * n), macro(val, [c] * n)) for c in COMPONENTS}
    for c, (a, b) in single.items():
        lines.append(f"- single `{c}`: fit {a:.3f}, val {b:.3f}")
    s14b = ["kmx64@fit" if L <= 40 else "s14:template:64:mean=kmx64:a=0.5@{own}" for L in layers]
    lines.append(f"- S14b (single switch at L40): fit {macro(fit, s14b):.3f}, val {macro(val, s14b):.3f}")
    best = max(COMPONENTS, key=lambda c: single[c][0])
    assign, cur, sweeps = [best] * n, single[best][0], 0
    while True:
        sweeps += 1
        changed = False
        for j in range(n):
            for c in COMPONENTS:
                trial = assign[:j] + [c] + assign[j + 1:]
                v = macro(fit, trial)
                if v > cur + 1e-9:
                    assign, cur, changed = trial, v, True
        if not changed or sweeps > 10:
            break
    lines += ["", f"**Selected map** (greedy, {sweeps} sweeps): fit {cur:.3f}, val {macro(val, assign):.3f}", ""]
    lines += [f"- L{L}: `{c}`" for L, c in zip(layers, assign, strict=True)]
    rng = random.Random(0)
    lines.append("")
    for d in range(3):
        r = [rng.choice(COMPONENTS) for _ in layers]
        lines.append(f"- random map {d}: fit {macro(fit, r):.3f}, val {macro(val, r):.3f}")
    ffit, fval = tables("fit", args.readout, ["fam@{own}"], tok, disp), tables("val", args.readout, ["fam@{own}"], tok, disp)
    lines.append(f"- fam (labelled reference): fit {macro(ffit, ['fam@{own}'] * n):.3f}, val {macro(fval, ['fam@{own}'] * n):.3f}")
    out = OUT / "analysis" / "S23"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"map-{args.readout}.json").write_text(json.dumps(
        {str(L): c.replace("@{own}", "").replace("@fit", "") for L, c in zip(layers, assign, strict=True)}, indent=1))
    (out / f"select-{args.readout}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
