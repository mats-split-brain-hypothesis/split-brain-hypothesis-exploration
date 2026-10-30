"""The standard analysis battery for evaluated arms (notes/iteration-anthony/research-loop.md, "3. Analyse").

  python experiments/analyse.py --study S1 --banks typo/val,association/val --arms "rand.fam@fit|cos,fam@fit|cos"
  python experiments/analyse.py --study S1 --split val --arms "..." [--refs "zero|cos,fam@fit|cos"] [--decode-g]

Reads what ``experiments/evaluate.py`` (and ``judge.py``) wrote under ``out/eval`` and writes, per bank,
``out/analysis/<study>/<family>-<split>.json`` plus one ``summary.md`` across banks:

- per arm: pass (strict / piece proxy, and the judge's when a full judge run exists), masked pass, echo,
  next-token overlap; paired differences against each reference arm, and the items won and lost;
- per layer: the pass curve, and the distribution of the first passing layer;
- ranks: per item, how the best target rank moved against each reference (entered / left the top 10,
  improved / worsened outside it), with a log2 rank-ratio histogram;
- g: ||g|| / ||h|| per layer (from the rank sidecar) and, with ``--decode-g`` (loads the lens: pod or a free
  Mac), the top tokens of L(mean g) per layer: what the centre removes;
- slices: pass per arm by read token, prompt length tertile, difficulty under the first reference, whether the
  model's own next token already names a target ("said" vs "unsaid"), and every low-cardinality item field
  (subfamily, attr_class, ...);
- across banks: the macro-average gain per arm against each reference, with the guardrail (families where an
  arm loses outside the paired interval).

Analysis may look at targets (to slice and score); centres never do.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from agreement import item_rows
from evaluate import parse_arm, read_jsonl, slug

from jlm import OUT, banks, capture, hfdata, mtproxy, score
from jlm.judge import MULTI_TOKEN

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
RANK_BINS = [-math.inf, -6, -3, -1, -0.01, 0.01, 1, 3, 6, math.inf]


def judged_items(d: Path) -> tuple[str, dict[str, bool]] | None:
    """(judge run name, item -> pass) from the newest complete-bank judge run of an arm, if any."""
    runs = [p for p in sorted(d.glob("judged*/results.json"), key=lambda p: p.stat().st_mtime) if "limit" not in p.parent.name]
    if not runs:
        return None
    rows = item_rows(json.loads(runs[-1].read_text()))
    return runs[-1].parent.name, {i: bool(r["pass"]) for i, r in rows.items() if r["pass"] is not None}


def layer_passes(rows: list[dict], strict_of, layers: list[int]) -> dict[int, dict[str, bool]]:
    by = defaultdict(list)
    for r in rows:
        by[r["layer"]].append(r)
    return {L: strict_of(by[L]) for L in layers}


def rank_moves(a: dict[str, int], b: dict[str, int], ids: list[str]) -> dict:
    """How item best ranks moved from reference ``b`` to arm ``a`` (rank 0 = top 1; top 10 = rank < 10)."""
    cats = Counter()
    ratios = []
    for i in ids:
        ra, rb = a[i], b[i]
        if ra >= score.RANK_CAP or rb >= score.RANK_CAP:
            cats["no single-token target"] += 1
            continue
        ina, inb = ra < 10, rb < 10
        cats["entered top 10" if ina and not inb else "left top 10" if inb and not ina else
             "stayed in top 10" if ina else "improved outside" if ra < rb else "worsened outside" if ra > rb else
             "unchanged outside"] += 1
        ratios.append(math.log2((ra + 1) / (rb + 1)))
    hist = np.histogram(ratios, bins=RANK_BINS)[0].tolist() if ratios else []
    return {"categories": dict(cats), "log2_ratio_bins": [str(b) for b in RANK_BINS], "log2_ratio_hist": hist,
            "median_log2_ratio": float(np.median(ratios)) if ratios else None}


def slices(item_pass: dict[str, dict[str, bool]], keys: dict[str, dict[str, str]], ids: list[str]) -> dict:
    """slice name -> value -> {n, arm: pass rate} over scored items."""
    out = {}
    for sname, val_of in keys.items():
        groups = defaultdict(list)
        for i in ids:
            if i in val_of:
                groups[val_of[i]].append(i)
        out[sname] = {v: {"n": len(g), **{a: float(np.mean([p[i] for i in g])) for a, p in item_pass.items()}}
                      for v, g in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]}
    return out


def analyse_bank(bank: banks.Bank, arms: list[str], refs: list[str], args, lens=None) -> dict | None:
    root = OUT / "eval" / bank.family / bank.split
    summ_path = root / "summary.json"
    if not summ_path.exists():
        print(f"  {bank.name}: no summary.json, skipped")
        return None
    summary = json.loads(summ_path.read_text())["result"]
    ids, layers = summary["scored_ids"], summary["layers"]
    items = capture.load(bank)
    if bank.family in MULTI_TOKEN:
        from transformers import AutoTokenizer
        from wsbench.produce.render import display_tokens

        from jlm.lens import MODEL
        from umot.provenance import PINS

        tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
        units = mtproxy.units_of(bank, tok, lambda ids_: display_tokens(tok, ids_))
        strict_of = lambda rows: mtproxy.item_passes(rows, units)  # noqa: E731
    else:
        strict_of = lambda rows: score.strict_items(rows, bank)  # noqa: E731

    every = list(dict.fromkeys([*refs, *arms]))
    data, item_pass, judged, ranks = {}, {}, {}, {}
    for a in every:
        d = root / slug(parse_arm(a))
        if not (d / "readouts.jsonl").exists():
            print(f"  {bank.name}: {a} not evaluated, skipped")
            continue
        rows, rk = read_jsonl(d / "readouts.jsonl"), read_jsonl(d / "ranks.jsonl")
        item_pass[a] = strict_of(rows)
        ranks[a] = score.best_rank(rk)
        lp = layer_passes(rows, strict_of, layers)
        first = Counter(next((L for L in layers if lp[L][i]), None) for i in ids)
        gn = defaultdict(list)
        for r in rk:
            if r.get("g_norm") is not None and r.get("h_norm"):
                gn[r["layer"]].append(r["g_norm"] / r["h_norm"])
        j = judged_items(d)
        if j:
            judged[a] = j
        data[a] = {
            "pass": score.rate(item_pass[a], ids),
            **{k: summary["arms"].get(a, {}).get(k) for k in ("strict_masked", "echo", "next_overlap")},
            "judged": {"run": j[0], **score.rate(j[1], [i for i in ids if i in j[1]])} if j else None,
            "layer_curve": {L: float(np.mean([lp[L][i] for i in ids])) if ids else None for L in layers},
            "first_layer": {str(k): v for k, v in first.items()},
            "g_over_h": {L: float(np.mean(v)) for L, v in sorted(gn.items())},
        }
    for a in data:
        data[a]["vs"] = {}
        for ref in refs:
            if ref == a or ref not in data:
                continue
            pa, pr = item_pass[a], item_pass[ref]
            v = {"paired": score.paired(pa, pr, ids),
                 "won": sorted(i for i in ids if pa[i] and not pr[i]), "lost": sorted(i for i in ids if pr[i] and not pa[i]),
                 "ranks": rank_moves(ranks[a], ranks[ref], ids)}
            if a in judged and ref in judged:
                both = [i for i in ids if i in judged[a][1] and i in judged[ref][1]]
                v["judged_paired"] = score.paired(judged[a][1], judged[ref][1], both)
            data[a]["vs"][ref] = v

    # slices
    by_id = bank.by_id()
    keys: dict[str, dict[str, str]] = {}
    keys["read token"] = {it.id: it.token(0).strip() or repr(it.token(0)) for it in items}
    lens_ = sorted(len(it.ids) for it in items)
    t1, t2 = lens_[len(lens_) // 3], lens_[2 * len(lens_) // 3]
    keys["prompt length"] = {it.id: f"<= {t1}" if len(it.ids) <= t1 else f"<= {t2}" if len(it.ids) <= t2 else f"> {t2}"
                             for it in items}
    if refs and refs[0] in item_pass:
        keys[f"under {refs[0]}"] = {i: "passes" if item_pass[refs[0]][i] else "fails" for i in ids}
    nxt = root / "next-token" / "readouts.jsonl"
    if nxt.exists():
        said = strict_of(read_jsonl(nxt))
        keys["model's next token names a target"] = {i: "said" if said[i] else "unsaid" for i in ids}
    for k in sorted({k for it in bank.items for k in it}):
        vals = {it["id"]: it[k] for it in bank.items if isinstance(it.get(k), str)}
        if 2 <= len(set(vals.values())) <= 12 and len(vals) == len(bank.items) and k not in ("id", "name"):
            keys[k] = vals
    out = {"bank": bank.name, "scorer": summary.get("scorer", "strict (jle x89)"), "n_scored": len(ids), "layers": layers, "arms": data,
           "slices": slices(item_pass, keys, ids)}
    if args.decode_g and lens is not None:
        out["g_decoded"] = decode_g(bank, items, [a for a in arms if a in data], lens, layers)
    return out


def decode_g(bank: banks.Bank, items, arms: list[str], lens, layers: list[int]) -> dict:
    """arm -> layer -> top 15 tokens of L(mean g) under the arm's readout: what the centre removes on average."""
    import torch

    from jlm import centres, context

    out = {}
    groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
    for a in arms:
        arm = parse_arm(a)
        if arm.centre == "zero":
            continue
        ref_items, added, ref_bank = capture.load_refs(bank, arm.ref, items)
        groups |= added
        c = centres.make(arm.centre)
        if hasattr(c, "set_bank"):  # stratum metadata, as evaluate.py gives it
            c.set_bank(bank.family, bank.items)
        needs = getattr(c, "needs_ctx", False)
        c.fit(ref_items, bank.family, groups, ctx=context.ContextStore.of(ref_bank) if needs and ref_bank else None)
        by_id = {it.id: it for it in items}
        out[a] = {}
        for L in layers:
            cells = centres.cell_refs([it for it in items if L in it.acts], bank.family, L, groups)
            H = torch.stack([by_id[x.item].acts[L][x.i].float() for x in cells])
            G = H - centres.apply(c, centres.Batch(L, cells, H, by_id, context.ContextStore.of(bank) if needs else None))
            _, top = lens.scores(G.mean(0, keepdim=True), L, arm.readout).topk(15, dim=1)
            out[a][L] = lens.display(top[0].tolist())
    return out


def fmt_rate(r: dict | None) -> str:
    return "-" if not r or r.get("value") is None else f"{r['value']:.2f}"


def fmt_diff(r: dict | None) -> str:
    if not r or r.get("diff") is None:
        return "-"
    lo, hi = r["ci95"]
    flag = " ▲" if lo > 0 else " ▼" if hi < 0 else ""
    return f"{r['diff']:+.2f} [{lo:+.2f}, {hi:+.2f}]{flag}"


def report(study: str, results: list[dict], arms: list[str], refs: list[str]) -> str:
    lines = [f"# {study}: standard battery", "",
             "Strict / piece-proxy pass is ours (not WorkspaceBench scores); judged = newest full judge run (Haiku = unpinned dev judge). "
             "▲ / ▼ = paired 95 % interval excludes 0.", ""]
    for ref in refs:
        lines += [f"## Against {ref}", "", "| bank | n | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
        gains = defaultdict(list)
        harms = defaultdict(list)
        for r in results:
            cells = []
            for a in arms:
                v = r["arms"].get(a, {}).get("vs", {}).get(ref)
                cells.append(fmt_diff(v["paired"]) if v else "-")
                if v and v["paired"]["diff"] is not None:
                    gains[a].append(v["paired"]["diff"])
                    if v["paired"]["ci95"][1] < 0:
                        harms[a].append(r["bank"])
            lines.append(f"| {r['bank']} | {r['n_scored']} | " + " | ".join(cells) + " |")
        lines.append("| **macro** | | " + " | ".join(f"**{np.mean(gains[a]):+.3f}**" if gains[a] else "-" for a in arms) + " |")
        lines.append("| guardrail | | " + " | ".join(", ".join(harms[a]) or "ok" for a in arms) + " |")
        lines.append("")
    lines += ["## Per bank", ""]
    for r in results:
        lines += [f"### {r['bank']} ({r['scorer']}, n = {r['n_scored']})", "",
                  "| arm | pass | masked | judged | echo | next-token overlap | first-pass layer (mode) |",
                  "|---|---|---|---|---|---|---|"]
        for a, d in r["arms"].items():
            fl = max(((k, v) for k, v in d["first_layer"].items() if k != "None"), key=lambda kv: kv[1], default=("-", 0))[0]
            e, o = d.get("echo"), d.get("next_overlap")
            lines.append(f"| {a} | {fmt_rate(d['pass'])} | {fmt_rate(d.get('strict_masked'))} | {fmt_rate(d.get('judged'))} | "
                         f"{'-' if e is None else f'{e:.3f}'} | {'-' if o is None else f'{o:.3f}'} | {fl} |")
        for a, d in r["arms"].items():
            for ref, v in d.get("vs", {}).items():
                if a in arms:
                    c = v["ranks"]["categories"]
                    lines.append(f"- {a} vs {ref}: won {len(v['won'])}, lost {len(v['lost'])}; ranks: "
                                 + ", ".join(f"{k} {n}" for k, n in sorted(c.items(), key=lambda kv: -kv[1])))
        if "g_decoded" in r:
            for a, per in r["g_decoded"].items():
                mid = sorted(per)[len(per) // 2]
                lines.append(f"- L(mean g) of {a} at L{mid}: {' '.join(per[mid][:10])}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--study", required=True)
    ap.add_argument("--banks", help="family/split,...; default every family at --split")
    ap.add_argument("--split", default="val")
    ap.add_argument("--arms", required=True)
    ap.add_argument("--refs", default="zero|cos,fam@fit|cos")
    ap.add_argument("--decode-g", action="store_true", help="load the lens and decode L(mean g) (about 7 GB)")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    arms, refs = args.arms.split(","), args.refs.split(",")
    names = args.banks.split(",") if args.banks else [f"{f}/{args.split}" for f in FAMILIES]
    todo = [banks.load(*n.split("/")) for n in names]
    lens = None
    if args.decode_g:
        import torch

        from jlm.lens import Lens

        torch.set_grad_enabled(False)
        lens = Lens(sorted({L for b in todo for L in banks.specs(b)[0].layers}), args.device)
    dest = OUT / "analysis" / args.study
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for b in todo:
        r = analyse_bank(b, arms, refs, args, lens)
        if r:
            (dest / f"{b.family}-{b.split}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
            results.append(r)
    text = report(args.study, results, arms, refs)
    (dest / "summary.md").write_text(text)
    hfdata.share([dest])  # to the shared dataset (no-op if unset)
    print(text)


if __name__ == "__main__":
    main()
