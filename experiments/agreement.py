"""How well the free strict scorer tracks the bench judge, per arm (item and cell level).

  python experiments/agreement.py --family typo --split val --arms "zero|cos,fam@fit|cos"

Needs ``readouts.jsonl`` (experiments/evaluate.py) and ``judged/results.json``
(experiments/judge.py) for each arm. Items are jle's confirmatory subset. Reports the 2x2
table, Cohen's kappa, both rates, the paired judge - strict gap with a 95 % interval, and the
discordant items with what the judge quoted. Writes ``<arm>/agreement.json``.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from evaluate import parse_arm, read_jsonl, slug
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks, mtproxy, score
from jlm.judge import MULTI_TOKEN
from jlm.lens import MODEL


def kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def item_rows(judged: dict) -> dict:
    """Per item ``{pass, targets, layers: {L: {expressed, quote}}}``. Bank-judge results already
    have that shape; user_modeling's are per cell (headline: gold picked with basis
    ``inferred_characterization`` at any cell, as its score.py); directed_modulation's likewise
    (gold picked with basis ``content_bound``)."""
    rows = judged["rows"]
    if rows and "passing_layers" in rows[0]:  # multi-token regex contract: a layer passes when every required unit hits
        return {r["id"]: {"pass": r["pass"], "targets": r["roles"],
                          "layers": {L: {"expressed": int(L) in set(r["passing_layers"]), "quote": "", "quote_ok": True}
                                     for L in r["layers"]}} for r in rows}
    if not rows or "pass" in rows[0]:
        return {r["id"]: r for r in rows}
    out: dict = {}
    if "item" in rows[0]:  # directed_modulation: gold picked with basis content_bound (its score.py)
        for r in rows:
            it = out.setdefault(r["item"], {"pass": False, "targets": [], "layers": {}})
            hit = r["pick"] == "gold" and r["basis"] == "content_bound"
            it["pass"] |= hit
            cell = it["layers"].setdefault(str(r["layer"]), {"expressed": False, "quote": "", "quote_ok": True})
            if hit:
                cell["expressed"], cell["quote"] = True, r.get("evidence", "")
        return out
    for r in rows:
        it = out.setdefault(r["id"], {"pass": False, "targets": [r["attr_class"]], "layers": {}})
        hit = r["pick"] == "gold" and r["basis"] == "inferred_characterization"
        it["pass"] |= hit
        cell = it["layers"].setdefault(str(r["layer"]), {"expressed": False, "quote": "", "quote_ok": True})
        if hit:
            cell["expressed"], cell["quote"] = True, r.get("evidence", "")
    return out


def mt_units(bank) -> dict:
    from transformers import AutoTokenizer
    from umot.provenance import PINS
    from wsbench.produce.render import display_tokens

    from jlm.lens import MODEL

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    return mtproxy.units_of(bank, tok, lambda ids: display_tokens(tok, ids))


def k2(k: float | None) -> str:
    return "n/a" if k is None else f"{k:.2f}"  # undefined when both scorers are constant


def table(a: list[bool], b: list[bool]) -> dict[str, int]:
    return {f"strict={int(x)},judge={int(y)}": sum(1 for p, q in zip(a, b) if (p, q) == (x, y))
            for x in (True, False) for y in (True, False)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--split", required=True, choices=banks.SPLITS)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--judged", default="judged-claude-haiku-5.5", help="judge output dir under each arm")
    ap.add_argument("--layers", default="", help="restrict strict scoring to the judged layers")
    ap.add_argument("--out", default=str(OUT / "eval"))
    args = ap.parse_args()
    bank = banks.load(args.family, args.split)
    summary = json.loads((Path(args.out) / bank.family / bank.split / "summary.json").read_text())["result"]
    for a in args.arms.split(","):
        d = Path(args.out) / bank.family / bank.split / slug(parse_arm(a))
        rows = read_jsonl(d / "readouts.jsonl")
        if args.layers:  # strict on the judged layers only
            keep = {int(x) for x in args.layers.split(",")}
            rows = [r for r in rows if r["layer"] in keep]
        judged = json.loads((d / args.judged / "results.json").read_text())
        jrow = item_rows(judged)
        strict_cell = defaultdict(bool)
        if bank.family in MULTI_TOKEN:  # the free side is the piece proxy, per item and per layer
            units = mt_units(bank)
            strict_item = mtproxy.item_passes(rows, units)
            for r in rows:
                strict_cell[r["id"], r["layer"]] |= mtproxy.item_passes([r], {r["id"]: units[r["id"]]})[r["id"]]
        else:
            strict_item = score.strict_items(rows, bank)
            forms = {it["id"]: score.accepted_forms(it) for it in bank.items}
            for r in rows:
                strict_cell[r["id"], r["layer"]] |= any(score.normalise(t) in forms[r["id"]] for t in r["tokens"])
        conf = [i for i in summary["scored_ids"] if i in jrow and jrow[i]["pass"] is not None]
        si = [strict_item[i] for i in conf]
        ji = [bool(jrow[i]["pass"]) for i in conf]
        cells_s, cells_j = [], []
        for i in conf:
            for L, v in jrow[i]["layers"].items():
                if v is not None and "expressed" in v:
                    cells_s.append(strict_cell[i, int(L)])
                    cells_j.append(bool(v["expressed"] and v.get("quote_ok", True)))
        disc = [
            {"id": i, "strict": strict_item[i], "judge": bool(jrow[i]["pass"]), "targets": jrow[i]["targets"],
             "quotes": sorted({v["quote"] for v in jrow[i]["layers"].values() if v and v.get("expressed")})}
            for i in conf if strict_item[i] != bool(jrow[i]["pass"])
        ]
        jd = {i: bool(jrow[i]["pass"]) for i in conf}
        res = {
            "arm": a, "n_items": len(conf),
            "strict": score.rate(strict_item, conf), "judge": score.rate(jd, conf),
            "judge_minus_strict": score.paired(jd, strict_item, conf),
            "items": {"table": table(si, ji), "kappa": kappa(si, ji)},
            "cells": {"n": len(cells_s), "table": table(cells_s, cells_j), "kappa": kappa(cells_s, cells_j)},
            "discordant": disc,
            "judge_pinned": judged["pinned_instrument"], "judge_complete": judged["complete"],
            "judge_model": judged["config"].get("judge_model"),
        }
        write_artefact(d / f"agreement-{args.judged}.json",
                       Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/{bank.name}",
                                  extra={"arm": a, "judged": args.judged}), res)
        print(f"{a}: n={len(conf)} strict={res['strict']['value']:.3f} judge={res['judge']['value']:.3f} "
              f"gap={res['judge_minus_strict']['diff']:+.3f} kappa_items={k2(res['items']['kappa'])} "
              f"kappa_cells={k2(res['cells']['kappa'])} discordant={len(disc)}")
        for x in disc:
            print(f"   {x['id']}: strict={x['strict']} judge={x['judge']} targets={x['targets']} quotes={x['quotes']}")


if __name__ == "__main__":
    main()
