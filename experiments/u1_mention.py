"""Study U1: umot's mention control for the position-matching ladder (notes/iteration-anthony/studies/U1.md).

Does a centred readout surface the concept the model HOLDS, or the one the prompt MENTIONS? umot's bank
(`umot/data/mention-control/items.json`, 315 items built from the bench's 35 DM pairs: hold X / mention X / hold X +
mention Y / absent, X early / middle / late; read cells = every token of the copied carrier sentence) is read with
each centre. As in umot's screen, a centre is fitted within the item's condition and template (``where``) and never
on an item sharing its concept (group = pair). An arm ``<centre>@absent`` is fitted on the absent items instead (the
same carriers with no concept in the prompt): ``u1carpos@absent`` is the neutral counterfactual of the same sentence
and position (U2's literal form), ``u1rel@absent`` a position mean over neutral prompts (S2). ``<centre>@dmfit`` is
fitted on our dev DM fit bank, whose carriers and concepts the mention bank does not share (does the centre transfer?). A word's tokens are the first sub-tokens (>= 3 characters, with and
without a leading space) of its accepted forms; 15 of 35 concepts have none and are dropped.

A fair centre separates held from mentioned (pass of X on hold items >> pass of X on mention items); a prompt reader
does not. Used as a fairness control only: nothing here chooses a centre or a hyperparameter.

  python experiments/u1_mention.py --device cuda [--arms zero,fam,tok,u1rel,...] [--limit 20]
  -> out/analysis/U1/mention/{ranks.jsonl,summary.json,summary.md}
"""

import argparse
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from umot import capture as ucap
from umot import mention_control as mc
from umot.provenance import REPO_ROOT as UMOT_ROOT

from jlm import OUT, centres
from jlm.lens import Lens

CAPTURE = UMOT_ROOT / "out" / "captures" / f"{mc.FAMILY}.pt"
ARMS = "zero,fam,tok,u1rel,shuf.u1rel,rand.u1rel,u1slot,u1relx,u1reltok,u1carpos,shuf.u1carpos"
SCOPES = {  # name -> (cell filter on (i, last i), layer filter)
    "all": (lambda i, last: True, lambda L: True),
    "final . L>=42": (lambda i, last: i == last, lambda L: L >= 42),
    "mid-sentence": (lambda i, last: i < last, lambda L: True),
}


def word_tokens(tok, forms: set[str]) -> list[int]:
    ids = set()
    for f in forms:
        for s in (f, " " + f):
            t = tok(s, add_special_tokens=False)["input_ids"]
            if t and len(tok.decode(t[:1]).strip()) >= 3:
                ids.add(t[0])
    return sorted(ids)


def boot_diff(a: dict, b: dict, n: int = 2000, seed: int = 0) -> dict:
    """Mean of a - b over shared keys, with a bootstrap 95 % interval over concepts (keys are (pair, where))."""
    keys = sorted(set(a) & set(b))
    if not keys:
        return {"diff": None, "ci95": [None, None], "n": 0}
    pairs = sorted({k[0] for k in keys})
    by = defaultdict(list)
    for k in keys:
        by[k[0]].append(a[k] - b[k])
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        xs = [x for p in (rng.choice(pairs) for _ in pairs) for x in by[p]]
        stats.append(float(np.mean(xs)))
    d = float(np.mean([a[k] - b[k] for k in keys]))
    return {"diff": d, "ci95": [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))], "n": len(keys)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--arms", default=ARMS)
    ap.add_argument("--readout", default="cos")
    ap.add_argument("--limit", type=int, default=0, help="first n pairs only (plumbing)")
    ap.add_argument("--out", default=str(OUT / "analysis" / "U1" / "mention"))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    t0 = time.time()

    bank = {it["id"]: it for it in mc.load()}
    dm = {b["concept"]: b for b in json.loads(mc.BENCH_BANK.read_text())["items"]}
    forms = {c: {c.lower(), c} | {m for u in b.get("units", []) if u.get("role") == "concept" for m in u["match"]}
             for c, b in dm.items()}
    y_of = {it["pair_id"]: it["mentioned"] for it in bank.values() if it["condition"] == "holdmention"}
    items = ucap.load(CAPTURE)
    if args.limit:
        keep = sorted({bank[it.id]["pair_id"] for it in items})[: args.limit]
        items = [it for it in items if bank[it.id]["pair_id"] in keep]
    layers = sorted({L for it in items for L in it.acts})
    lens = Lens(layers, args.device)
    tok = lens.tokenizer
    tx = {it.id: word_tokens(tok, forms[bank[it.id]["concept"]]) for it in items}
    ty = {it.id: word_tokens(tok, forms[y_of[bank[it.id]["pair_id"]]]) for it in items}
    groups = {it.id: bank[it.id]["pair_id"] for it in items}
    pools = defaultdict(list)
    for it in items:
        pools[(bank[it.id]["condition"], bank[it.id]["where"])].append(it)
    print(f"{len(items)} items, {len(pools)} pools, layers {layers}, lens ready ({time.time() - t0:.0f}s)", flush=True)

    def best_ranks(S: torch.Tensor, ids: list[list[int]]) -> list[int | None]:
        """Per row of S, the best rank of the row's word ids (None where the word has no token)."""
        ok = [n for n, t in enumerate(ids) if t]
        out: list[int | None] = [None] * len(ids)
        if ok:
            w = max(len(ids[n]) for n in ok)
            pad = torch.tensor([ids[n] + ids[n][:1] * (w - len(ids[n])) for n in ok], device=S.device)
            best = S[ok].gather(1, pad).max(1, keepdim=True).values
            # pessimistic on ties: identical prompts give h - g = 0 and all-equal scores (absent items under the
            # tight centres), which must not count as rank 0
            for n, v in zip(ok, ((S[ok] >= best).sum(1) - 1).tolist(), strict=True):
                out[n] = v
        return out

    rows = []
    for arm in args.arms.split(","):
        name, _, ref = arm.partition("@")  # "@absent": fitted on the absent items (no concept in the prompt)
        absent = [it for it in items if bank[it.id]["condition"] == "absent"]
        if ref == "dmfit":  # "@dmfit": fitted on our dev DM fit bank (other carriers, other concepts): transfer
            from jlm import banks, capture

            dmb = banks.load("directed_modulation", "fit")
            dm_items = capture.load(dmb)
            groups |= {it["id"]: it.get("pair_id") or it["id"] for it in dmb.items}
        for (cond, where), pool in sorted(pools.items()):
            if ref == "absent" and cond == "absent":
                continue
            c = centres.make(name)
            c.fit(absent if ref == "absent" else dm_items if ref == "dmfit" else pool, mc.FAMILY, groups)
            by = {it.id: it for it in pool}  # read cells: the pool's own items
            for L in layers:
                cells = centres.cell_refs(pool, mc.FAMILY, L, groups)
                H = torch.stack([by[x.item].acts[L][x.i].float() for x in cells])
                X = centres.apply(c, centres.Batch(L, cells, H, by, None))
                for a in range(0, len(cells), 512):
                    S = lens.scores(X[a : a + 512], L, args.readout)
                    blk = cells[a : a + 512]
                    rx = best_ranks(S, [tx[x.item] for x in blk])
                    ry = best_ranks(S, [ty[x.item] for x in blk])
                    rows += [{"id": x.item, "arm": arm, "layer": L, "i": x.i, "rx": a_, "ry": b_}
                             for x, a_, b_ in zip(blk, rx, ry, strict=True)]
        print(f"  {arm} ({time.time() - t0:.0f}s)", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "ranks.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    last = defaultdict(int)
    for r in rows:
        last[r["id"]] = max(last[r["id"]], r["i"])
    summary = {}
    for arm in args.arms.split(","):
        summary[arm] = {}
        for sname, (cf, lf) in SCOPES.items():
            best = defaultdict(lambda: [10**9, 10**9])  # id -> [best rx, best ry]
            for r in rows:
                if r["arm"] != arm or not cf(r["i"], last[r["id"]]) or not lf(r["layer"]):
                    continue
                b = best[r["id"]]
                if r["rx"] is not None:
                    b[0] = min(b[0], r["rx"])
                if r["ry"] is not None:
                    b[1] = min(b[1], r["ry"])

            def rate(cond: str, col: int) -> dict:
                return {(bank[i]["pair_id"], bank[i]["where"]): float(v[col] < 10) for i, v in best.items()
                        if bank[i]["condition"] == cond and v[col] < 10**9}

            held, ment = rate("hold", 0), rate("mention", 0)
            hm_x, hm_y = rate("holdmention", 0), rate("holdmention", 1)
            absent = rate("absent", 0)
            summary[arm][sname] = {
                "held": float(np.mean(list(held.values()))) if held else None,
                "mentioned": float(np.mean(list(ment.values()))) if ment else None,
                "held - mentioned": boot_diff(held, ment),
                "holdmention X": float(np.mean(list(hm_x.values()))) if hm_x else None,
                "holdmention Y": float(np.mean(list(hm_y.values()))) if hm_y else None,
                "holdmention X - Y": boot_diff(hm_x, hm_y),
                "absent X": float(np.mean(list(absent.values()))) if absent else None,
            }
    (out / "summary.json").write_text(json.dumps({"arms": summary, "readout": args.readout, "layers": layers}, indent=1))

    def f(x):
        return "-" if x is None else f"{x:.2f}"

    lines = ["# U1 mention control (umot's bank, exact first-token word pass@10; fairness control only)", "",
             "| arm | scope | held X | mentioned X | held - mentioned [95 %] | hold+mention: X / Y | X - Y [95 %] | absent |",
             "|---|---|---|---|---|---|---|---|"]
    for arm, by_s in summary.items():
        for s, r in by_s.items():
            d, e = r["held - mentioned"], r["holdmention X - Y"]
            ci = (lambda z: "-" if z["diff"] is None else f"{z['diff']:+.2f} [{z['ci95'][0]:+.2f}, {z['ci95'][1]:+.2f}]")
            lines.append(f"| {arm} | {s} | {f(r['held'])} | {f(r['mentioned'])} | {ci(d)} | "
                         f"{f(r['holdmention X'])} / {f(r['holdmention Y'])} | {ci(e)} | {f(r['absent X'])} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
