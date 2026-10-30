"""Study U1: umot's many-mentions control for the position-matching ladder (notes/iteration-anthony/studies/U1.md).

A harder mention control: each item lists four concepts the model read about and (``listhold`` / ``holdlist``) asks it
to hold a fifth, or (``listrefer``) to hold one of the four, or (``listnone``) nothing. Read cells are the copied
carrier. A centre is fitted within the item's condition, never on an item sharing its pair (as ``u1_mention.py``);
its references contain the probe's own carriers (the research-loop rule). Pass@10 per word (exact first sub-token,
as ``u1_mention.word_tokens``): the held word vs each listed (mentioned, not held) word, over all cells and mid-sentence.

  python experiments/u1_many.py --device cuda [--arms zero,fam,tok,u1rel,...]
  -> out/analysis/U1/mention-many/{summary.json,summary.md}
"""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from u1_mention import word_tokens
from umot import capture as ucap
from umot import mention_control as mc
from umot.provenance import REPO_ROOT as UMOT_ROOT

from jlm import OUT, centres
from jlm.lens import Lens

CAPTURE = UMOT_ROOT / "out" / "captures" / f"{mc.FAMILY_MANY}.pt"
ARMS = "zero,fam,tok,u1rel,u1tokxs,u1endcar,u1reltok,u1carpos,shuf.u1rel"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--arms", default=ARMS)
    ap.add_argument("--out", default=str(OUT / "analysis" / "U1" / "mention-many"))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    t0 = time.time()
    bank = {it["id"]: it for it in mc.load(mc.FAMILY_MANY)}
    dm = {b["concept"]: b for b in json.loads(mc.BENCH_BANK.read_text())["items"]}
    forms = {c: {c.lower(), c} | {m for u in b.get("units", []) if u.get("role") == "concept" for m in u["match"]}
             for c, b in dm.items()}
    items = ucap.load(CAPTURE)
    layers = sorted({L for it in items for L in it.acts})
    lens = Lens(layers, args.device)
    words = {}  # item -> {"held": ids, "listed": [ids, ...]} (the held word is never among "listed")
    for it in items:
        b = bank[it.id]
        words[it.id] = {"held": word_tokens(lens.tokenizer, forms[b["held"]]) if b.get("held") else [],
                        "listed": [word_tokens(lens.tokenizer, forms[w]) for w in b["listed"] if w != b.get("held")]}
    groups = {it.id: bank[it.id]["pair_id"] for it in items}
    pools = defaultdict(list)
    for it in items:
        pools[bank[it.id]["condition"]].append(it)
    print(f"{len(items)} items, pools {sorted(pools)}, lens ready ({time.time() - t0:.0f}s)", flush=True)

    def hit(S: torch.Tensor, ids: list[int]) -> torch.Tensor:
        """[n] bool: some id in the row's top 10 (pessimistic on ties)."""
        best = S[:, ids].max(1, keepdim=True).values
        return ((S >= best).sum(1) - 1) < 10

    summary = {}
    for arm in args.arms.split(","):
        held, listed = defaultdict(lambda: defaultdict(bool)), defaultdict(lambda: defaultdict(bool))
        for cond, pool in sorted(pools.items()):
            c = centres.make(arm)
            c.fit(pool, mc.FAMILY_MANY, groups)
            by = {it.id: it for it in pool}
            last = {it.id: len(it.positions) - 1 for it in pool}
            for L in layers:
                cells = centres.cell_refs(pool, mc.FAMILY_MANY, L, groups)
                H = torch.stack([by[x.item].acts[L][x.i].float() for x in cells])
                X = centres.apply(c, centres.Batch(L, cells, H, by, None))
                for a in range(0, len(cells), 512):
                    S, blk = lens.scores(X[a : a + 512], L, "cos"), cells[a : a + 512]
                    for j, x in enumerate(blk):
                        scope = ["all"] + (["mid"] if x.i < last[x.item] else [])
                        w = words[x.item]
                        if w["held"] and bool(hit(S[j : j + 1], w["held"])[0]):
                            for sc in scope:
                                held[sc][x.item] = True
                        for k, ids in enumerate(w["listed"]):
                            if ids and bool(hit(S[j : j + 1], ids)[0]):
                                for sc in scope:
                                    listed[sc][(x.item, k)] = True
        res = {}
        for sc in ("all", "mid"):
            per = {}
            for cond in sorted(pools):
                ids = [it.id for it in pools[cond]]
                h = [held[sc][i] for i in ids if words[i]["held"]]
                ls = [listed[sc][(i, k)] for i in ids for k, t in enumerate(words[i]["listed"]) if t]
                per[cond] = {"held": float(np.mean(h)) if h else None, "each listed": float(np.mean(ls)) if ls else None,
                             "n_held": len(h), "n_listed": len(ls)}
            res[sc] = per
        summary[arm] = res
        print(f"  {arm} ({time.time() - t0:.0f}s): " + json.dumps(res["all"]), flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"arms": summary, "layers": layers}, indent=1))
    conds = sorted(pools)
    f = lambda x: "-" if x is None else f"{x:.2f}"  # noqa: E731
    lines = ["# U1 many-mentions control (umot's bank; held word vs each listed word, pass@10)", "",
             "| arm | scope | " + " | ".join(f"{c}: held / each listed" for c in conds) + " |",
             "|---|---|" + "---|" * len(conds)]
    for arm, res in summary.items():
        for sc, per in res.items():
            lines.append(f"| {arm} | {sc} | " + " | ".join(f"{f(per[c]['held'])} / {f(per[c]['each listed'])}"
                                                         for c in conds) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
