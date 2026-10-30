"""Evaluate centred J-lens arms on one bank: read, strict-score, rank, report (no judge calls).

  python experiments/evaluate.py --family typo --split bench
  python experiments/evaluate.py --family typo --split val --arms "zero|cos,fam@fit|cos"
  python experiments/evaluate.py --banks typo/val,typo/bench

An arm is ``centre[@ref]|readout``: centre from ``jlm.centres.CENTRES``, ref the split its mean
is fitted on (``self`` = the read bank, own item excluded), readout ``cos`` or ``rms``. A control
prefix on the centre (``shuf.fam@fit|cos``, ``rand.tok@fit|cos``) runs the shuffled-g or random-g control.
A lens prefix (``jpp:zero|cos``, ``jpp:fam@fit|cos``) reads through another map from ``jlm.lens.LENSES`` (J++);
its directory is ``jpp~zero__cos``. A run adds its arms to the bank's existing ``summary.json``.
Writes ``out/eval/<family>/<split>/<arm>/{readouts,ranks,masked}.jsonl`` (masked: the prompt-masked top 10,
``jlm.controls``) and ``summary.{json,md}`` beside them, with each arm's prompt echo and masked pass. When the
bank has a context capture (``out/ctx``), also the model's own next-token top 10 at each read cell
(``next-token/readouts.jsonl``) and each arm's overlap with it. Judge a readouts file with ``experiments/judge.py``.

Each arm also gets the same three files over the semantic vocabulary only (``<arm>/sem/``, J++'s Readout Filtering,
``jlm.controls.non_semantic_ids``) and a ``sem`` block in its summary entry (pass, rank, masked, echo, next-token
overlap, all on the filtered vocabulary; ``diffs_sem`` beside ``diffs``). The full-vocabulary files stay the default.
An arm whose readouts exist but whose ``sem/`` does not is re-read for ``sem/`` only: its stored files are kept (judge
runs read them), and the share of cells where the refit's full top 10 differs from the stored one is recorded in
``sem/provenance.json`` (0 for a deterministic centre). ``--no-sem`` skips all of this.

On the single-token families each arm also gets the "strict + forms" score (``jlm.forms``: inflections accepted, and
in association derived words naming the same thing) in a ``forms`` block, ``diffs_forms`` beside ``diffs``, and both
scores over the reachable items alone (``strict_reachable``, ``forms.reachable``). ``--rescore`` recomputes these for
every arm already in a bank's summary from the stored readouts, with no lens load and no forward pass.
"""

import argparse
import json
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import (
    OUT,
    banks,
    capture,
    centres,
    context,
    controls,
    forms,
    hfdata,
    intermediates,
    mtproxy,
    score,
)
from jlm.judge import MULTI_TOKEN
from jlm.lens import LENSES, MODEL, Lens, reader
from jlm.read import Arm, read

DEFAULT_ARMS = "zero|cos,zero|rms,fam@self|cos,fam@self|rms,tok@self|cos,tok@self|rms"


def parse_arm(s: str) -> Arm:
    # a lens prefix is the text before the first ':' when it names a lens; centre names may hold ':' too
    # (``genk:8``, ``dict:fam:0.5``, ``jpp:genk:8@self|rms``)
    lens, colon, rest = s.partition(":")
    if colon and lens in LENSES:
        s = rest
    else:
        lens = "jlens"
    head, readout = s.split("|")
    centre, _, ref = head.partition("@")
    return Arm(centre, ref or "self", readout, lens)


def slug(arm: Arm) -> str:
    return arm.name.replace("|", "__").replace("@", "-at-").replace(":", "~")


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fmt(r: dict) -> str:
    if r.get("value") is None and r.get("diff") is None:
        return "-"
    v = r.get("value", r.get("diff"))
    lo, hi = r["ci95"]
    sign = "+" if "diff" in r else ""
    return f"{v:{sign}.3f} [{lo:{sign}.3f}, {hi:{sign}.3f}]"


def next_token(lens: Lens, bank: banks.Bank, items: list, root: Path, exclude: list[int] | None = None,
               sub: str = "") -> list[dict] | None:
    """The model's own next-token top 10 at each read cell (from the context capture), cached on disk; with
    ``exclude``, over the vocabulary without those ids (``sub="sem"``: the semantic vocabulary)."""
    path = root / "next-token" / sub / "readouts.jsonl"
    if path.exists():
        return read_jsonl(path)
    if not context.bank_path(bank).exists():
        return None
    ctx = context.ContextStore.of(bank)
    cells = [(it, i) for it in items for i in range(len(it.positions))]
    H = torch.stack([ctx.at(it.id, context.FINAL_LAYER, i).float() for it, i in cells])
    excl = torch.tensor(exclude or [], dtype=torch.int64, device=lens.device)
    rows = []
    for a in range(0, len(cells), 256):
        vals, top = lens.logits(H[a : a + 256]).index_fill(1, excl, float("-inf")).topk(10, dim=1)
        names = lens.display(top.flatten().tolist())
        for j, (it, i) in enumerate(cells[a : a + 256]):
            rows.append({"id": it.id, "layer": context.FINAL_LAYER, "pos": it.positions[i], "token": it.token(i),
                         "tokens": names[j * 10 : (j + 1) * 10], "scores": [round(v, 4) for v in vals[j].tolist()]})
    write_jsonl(rows, path)
    return rows


@contextmanager
def bank_lock(root: Path, stale_s: float = 600):
    """Serialise summary updates of one bank across processes and pods (several instances evaluate different arms on
    the same bank). ``mkdir`` is atomic on every filesystem we use, the network volume included; a lock older than
    ``stale_s`` is taken to be left by a dead process and broken."""
    lock = root / ".summary.lock"
    root.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_s:
                    lock.rmdir()
                    continue
            except FileNotFoundError:
                continue
            time.sleep(1)
    try:
        yield
    finally:
        lock.rmdir()


def overlap(rows: list[dict], ref: list[dict]) -> float:
    """Mean share of a row's top 10 that is also in the reference top 10 at the same (item, pos)."""
    by = {(r["id"], r["pos"]): set(r["tokens"]) for r in ref}
    shares = [len(set(r["tokens"]) & by[(r["id"], r["pos"])]) / 10 for r in rows if (r["id"], r["pos"]) in by]
    return float(np.mean(shares)) if shares else float("nan")


def evaluate_bank(lenses: dict[str, Lens], vocab: list[str], bank: banks.Bank, arms: list[Arm], args) -> None:
    lens = lenses["jlens"]  # tokenizer, W_U and the next-token baseline are shared by every map
    items = capture.load(bank)
    layers = [L for L in lens.layers if L in banks.specs(bank)[0].layers and any(L in it.acts for it in items)]
    root = Path(args.out) / bank.family / bank.split
    if bank.family in MULTI_TOKEN:  # free proxy: distinctive pieces of the multi-token forms
        units = mtproxy.units_of(bank, lens.tokenizer, lens.display)
        accepted = {i: sorted({t for u in us if u.required for t in u.ids}) for i, us in units.items()}
        conf = {i: "" if ok else "unreachable" for i, ok in mtproxy.reachable(units).items()}
        scorer, strict_of = "piece proxy (jlm.mtproxy)", lambda rows: mtproxy.item_passes(rows, units)
        strict_sc = extended = None
    elif bank.family in intermediates.FAMILIES:  # free proxy: number / colour forms at the headline cells
        hi = intermediates.Scorer(bank, lens.tokenizer, lens.display, {it.id: it.ids for it in items})
        accepted, conf = hi.accepted, hi.conf
        scorer, strict_of = "hidden-intermediate forms (jlm.intermediates)", hi.passes
        strict_sc = extended = None
    else:
        strict_sc, extended = scorers(bank, vocab, {it.id: lens.display(it.ids) for it in items})
        accepted, conf = strict_sc.accepted, strict_sc.conf
        scorer, strict_of = "strict (jle x89)", lambda rows: score.strict_items(rows, bank)
    ids = [i for i, why in conf.items() if not why]
    excluded = {why: sum(1 for w in conf.values() if w == why) for why in set(conf.values()) if why}
    no_token = sum(1 for i in ids if not accepted[i])  # scored, but no single token spells a target

    groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}  # DM twins share a group
    pforms = controls.prompt_forms({it.id: lens.display(it.ids) for it in items})
    mask = None if args.no_mask else controls.mask_ids(pforms, vocab)
    spared = {t for ts in accepted.values() for t in ts}  # J++ spares the ids its evals score
    semantic = None if args.no_sem else controls.non_semantic_ids(lens.tokenizer, lens.vocab, spared)
    refs, ctxs = {"self": items}, {}

    def ctx_of(split: str):
        if split not in ctxs:
            ctxs[split] = context.ContextStore.of(bank if split in ("self", bank.split) else banks.load(bank.family, split))
        return ctxs[split]

    passes, masked_passes, ranks_by_arm, echoes, overlaps, arm_rows = {}, {}, {}, {}, {}, {}
    sem_scores = {}  # arm -> its sem summary block
    form_fields, form_passes = {}, {}  # arm -> its strict + forms summary fields / item passes
    nxt = None if args.no_next else next_token(lens, bank, items, root)
    nxt_sem = None if args.no_next or semantic is None else next_token(lens, bank, items, root, semantic, "sem")
    for arm in arms:
        d = root / slug(arm)
        have, have_sem = (d / "readouts.jsonl").exists() and not args.force, (d / "sem" / "readouts.jsonl").exists()
        sem = None
        if have and (have_sem or semantic is None):
            rows, ranks = read_jsonl(d / "readouts.jsonl"), read_jsonl(d / "ranks.jsonl")
            masked = read_jsonl(d / "masked.jsonl") if (d / "masked.jsonl").exists() else []
            if have_sem and semantic is not None:
                sem = {k: read_jsonl(d / "sem" / f"{k}.jsonl") if (d / "sem" / f"{k}.jsonl").exists() else []
                       for k in ("readouts", "ranks", "masked")}
        else:
            try:
                if arm.ref not in refs:
                    refs[arm.ref], added, _ = capture.load_refs(bank, arm.ref, items)
                    groups |= added
                c = centres.make(arm.centre)
                if hasattr(c, "set_bank"):  # stratum metadata (ids and category fields, no targets)
                    c.set_bank(bank.family, bank.items)
                needs = getattr(c, "needs_ctx", False)
                c.fit(refs[arm.ref], bank.family, groups, ctx=ctx_of(arm.ref) if needs else None)
                t1 = time.time()
                rows, ranks, masked, sem = read(lenses[arm.lens], items, bank.family, c, arm.readout, accepted, layers,
                                                groups, ctx=ctx_of("self") if needs else None, mask=mask, semantic=semantic)
            except Exception as e:  # --keep-going: a centre that cannot fit or read this bank is skipped, not fatal
                if not args.keep_going:
                    raise
                print(f"  {bank.name} {arm.name}: SKIPPED ({type(e).__name__}: {e})", flush=True)
                continue
            prov = Provenance(
                model=MODEL, model_revision=PINS[MODEL], reader=reader(arm.lens)[0],
                reader_revision=reader(arm.lens)[1], dataset=f"jlm/{bank.name}",
                extra={"arm": arm.name, "lens": arm.lens, "centre": c.doc, "ref": arm.ref, "readout": arm.readout,
                       "layers": layers},
            )
            note = ""
            if have:  # sem backfill: keep the stored full-vocabulary files, check the refit reproduces them
                stored = {(r["id"], r["layer"], r["pos"]): r["tokens"] for r in read_jsonl(d / "readouts.jsonl")}
                diff = sum(stored.get((r["id"], r["layer"], r["pos"])) != r["tokens"] for r in rows) / max(1, len(rows))
                rows, ranks = read_jsonl(d / "readouts.jsonl"), read_jsonl(d / "ranks.jsonl")
                masked = read_jsonl(d / "masked.jsonl") if (d / "masked.jsonl").exists() else []
                note = f", sem backfill (refit differs from stored on {diff:.1%} of cells)"
            else:
                diff = None
                write_jsonl(rows, d / "readouts.jsonl")
                write_jsonl(ranks, d / "ranks.jsonl")
                if masked:
                    write_jsonl(masked, d / "masked.jsonl")
                write_artefact(d / "provenance.json", prov, {"rows": len(rows), "fallbacks": getattr(c, "n_fallback", 0),
                                                         "picked": {k: v for k, v in sorted(getattr(c, "picked", {}).items())}})
            if sem is not None:
                for k, v in sem.items():
                    if v:
                        write_jsonl(v, d / "sem" / f"{k}.jsonl")
                write_artefact(d / "sem" / "provenance.json", prov,
                               {"rows": len(sem["readouts"]), "excluded_ids": len(semantic), "spared_ids": len(spared),
                                "refit_differs_from_stored": diff})
            print(f"  {bank.name} {arm.name}: {len(rows)} rows ({time.time() - t1:.0f}s){note}", flush=True)
        passes[arm.name] = strict_of(rows)
        arm_rows[arm.name] = rows
        masked_passes[arm.name] = strict_of(masked) if masked else None
        ranks_by_arm[arm.name] = score.best_rank(ranks)
        eb = controls.echo_by_item(rows, pforms)
        echoes[arm.name] = float(np.mean([eb[i] for i in ids])) if ids else None
        overlaps[arm.name] = overlap(rows, nxt) if nxt else None
        if extended is not None:
            form_fields[arm.name], form_passes[arm.name] = forms.arm_fields(
                strict_sc, extended, rows, masked, sem["readouts"] if sem is not None else None)
        if sem is not None:
            sp, smp = strict_of(sem["readouts"]), strict_of(sem["masked"]) if sem["masked"] else None
            seb, sbr = controls.echo_by_item(sem["readouts"], pforms), score.best_rank(sem["ranks"])
            sem_scores[arm.name] = {"passes": sp, "block": {
                "strict": score.rate(sp, ids), "median_best_rank": float(np.median([sbr[i] for i in ids])) if ids else None,
                "strict_masked": score.rate(smp, ids) if smp else None,
                "echo": float(np.mean([seb[i] for i in ids])) if ids else None,
                "next_overlap": overlap(sem["readouts"], nxt_sem) if nxt_sem else None}}

    result = {"bank": bank.name, "scorer": scorer, "n_items": len(bank.items), "n_scored": len(ids), "excluded": excluded,
              "n_scored_no_single_token": no_token, "scored_ids": ids, "layers": layers, "arms": {}, "diffs": {},
              "diffs_sem": {}}
    arms = [a for a in arms if a.name in passes]  # --keep-going: the arms read on this bank
    if semantic is not None:
        result["semantic"] = {"excluded_ids": len(semantic), "spared_ids": len(spared),
                              "rule": "J++ Readout Filtering: no letter or digit in the decode, accepted ids spared"}
    for arm in arms:
        br = [ranks_by_arm[arm.name][i] for i in ids]
        mp = masked_passes[arm.name]
        result["arms"][arm.name] = {"strict": score.rate(passes[arm.name], ids),
                                     "median_best_rank": float(np.median(br)) if br else None,
                                     "strict_masked": score.rate(mp, ids) if mp else None,
                                     "echo": echoes[arm.name], "next_overlap": overlaps[arm.name]}
        if arm.name in sem_scores:
            result["arms"][arm.name]["sem"] = sem_scores[arm.name]["block"]
        result["arms"][arm.name] |= form_fields.get(arm.name, {})
        if bank.family in intermediates.FAMILIES:
            result["arms"][arm.name]["intermediates"] = hi.extras(arm_rows[arm.name], ids)
    if extended is not None:
        result |= forms.bank_fields(strict_sc, extended)
        result["diffs_forms"] = form_diffs(arms, form_passes, extended.ids)
        if nxt:
            result["forms"]["next_token"] = score.rate(extended.passes(nxt), extended.ids)
    if nxt:
        result["next_token"] = {"strict": score.rate(strict_of(nxt), ids),
                                "echo": float(np.mean([controls.echo_by_item(nxt, pforms)[i] for i in ids])) if ids else None}
    if nxt and bank.family in intermediates.FAMILIES:
        result["next_token"]["intermediates"] = hi.extras(nxt, ids)
    if nxt_sem:
        result["next_token_sem"] = {"strict": score.rate(strict_of(nxt_sem), ids),
                                    "echo": float(np.mean([controls.echo_by_item(nxt_sem, pforms)[i] for i in ids])) if ids else None}
    for arm in arms:  # each arm against the uncentred lens (same map) with the same readout
        base = Arm("zero", "self", arm.readout, arm.lens).name
        if arm.centre != "zero" and base in passes:
            result["diffs"][f"{arm.name} - {base}"] = score.paired(passes[arm.name], passes[base], ids)
            if arm.name in sem_scores and base in sem_scores:
                result["diffs_sem"][f"{arm.name} - {base}"] = score.paired(sem_scores[arm.name]["passes"],
                                                                           sem_scores[base]["passes"], ids)

    with bank_lock(root):
        write_summary(root, bank, result, scorer, ids, excluded, no_token, layers, nxt)


def scorers(bank: banks.Bank, vocab: list[str], prompt_tokens: dict[str, list[str]]) -> tuple[forms.Scorer, forms.Scorer]:
    """The bank's strict scorer and its strict + forms scorer."""
    return (forms.Scorer.of(bank, vocab, prompt_tokens),
            forms.Scorer.of(bank, vocab, prompt_tokens, forms.table(bank.family)))


def form_diffs(arms: list[Arm], passes: dict[str, dict[str, bool]], ids: list[str]) -> dict[str, dict]:
    """Each arm against the uncentred lens (same map, same readout) under strict + forms."""
    out = {}
    for arm in arms:
        base = Arm("zero", "self", arm.readout, arm.lens).name
        if arm.centre != "zero" and base in passes and arm.name in passes:
            out[f"{arm.name} - {base}"] = score.paired(passes[arm.name], passes[base], ids)
    return out


def rescore_bank(vocab: list[str], tokenizer, bank: banks.Bank, root: Path) -> None:
    """Recompute the strict + forms and reachable fields of every arm in the bank's summary from its stored
    readouts (no lens load, no forward pass); strict's own numbers are left as they are."""
    from wsbench.produce.render import display_tokens

    path = root / "summary.json"
    if bank.family in MULTI_TOKEN or not path.exists():
        return
    items = capture.load(bank)
    strict_sc, extended = scorers(bank, vocab, {it.id: display_tokens(tokenizer, it.ids) for it in items})
    with bank_lock(root):
        result = json.loads(path.read_text())["result"]
        if result["scored_ids"] != strict_sc.ids:
            raise RuntimeError(f"{bank.name}: strict's scored set differs from the summary's; re-run evaluate.py")
        arms, passes = [parse_arm(a) for a in result["arms"]], {}
        for arm in arms:
            d = root / slug(arm)
            if not (d / "readouts.jsonl").exists():
                print(f"  {bank.name} {arm.name}: no readouts on disk, left as it is", flush=True)
                continue
            masked = read_jsonl(d / "masked.jsonl") if (d / "masked.jsonl").exists() else None
            sem = read_jsonl(d / "sem" / "readouts.jsonl") if (d / "sem" / "readouts.jsonl").exists() else None
            fields, passes[arm.name] = forms.arm_fields(strict_sc, extended, read_jsonl(d / "readouts.jsonl"), masked, sem)
            result["arms"][arm.name] |= fields
        result |= forms.bank_fields(strict_sc, extended)
        result["diffs_forms"] = form_diffs(arms, passes, extended.ids)
        nxt = root / "next-token" / "readouts.jsonl"
        if nxt.exists():
            result["forms"]["next_token"] = score.rate(extended.passes(read_jsonl(nxt)), extended.ids)
        write_summary(root, bank, result, result["scorer"], result["scored_ids"], result["excluded"],
                      result["n_scored_no_single_token"], result["layers"], nxt.exists(), merge=False)


def write_summary(root, bank, result, scorer, ids, excluded, no_token, layers, nxt, merge: bool = True) -> None:
    """Merge this run's arms into the bank's summary (under ``bank_lock``) and write summary.{json,md}."""
    old = root / "summary.json"
    if merge and old.exists():  # keep arms from earlier runs (scored on the same items: same bank, same scorer)
        prev = json.loads(old.read_text())["result"]
        if prev.get("scored_ids") == ids:
            result["arms"] = {a: r for a, r in prev["arms"].items() if a not in result["arms"]} | result["arms"]
            for k in ("diffs", "diffs_sem", "diffs_forms"):
                if k in prev or k in result:  # the _mt banks have no forms score (no diffs_forms in this run)
                    result[k] = {d: r for d, r in prev.get(k, {}).items() if d not in result.get(k, {})} | result.get(k, {})
            for k in ("next_token", "next_token_sem", "semantic", "forms", "n_reachable"):
                if k in prev and k not in result:
                    result[k] = prev[k]
    forms.fill_from_sidecar(root, result)  # fields a run on a branch without this score stripped from the summary
    write_artefact(
        root / "summary.json",
        Provenance(model=MODEL, model_revision=PINS[MODEL], reader="/".join(LENSES["jlens"]),
                   reader_revision=PINS[LENSES["jlens"][0]], dataset=f"jlm/{bank.name}",
                   extra={"scorer": scorer, "lenses": {k: [*v, reader(k)[1]] for k, v in LENSES.items()}}),
        result,
    )
    lines = [f"# {bank.name}: {scorer} (ours, not WorkspaceBench scores)", "",
             (f"n scored = {len(ids)} of {len(bank.items)}; excluded {excluded or 'none'}; "
              f"{no_token} scored items have no single-token target (cannot pass); layers {layers}"), ""]
    fb = result.get("forms")
    if fb:
        lines += [(f"strict + forms ({fb['rule'] or 'no table'}): n scored = {fb['n_scored']}, excluded "
                   f"{fb['excluded'] or 'none'}; reachable: strict {result['n_reachable']}, + forms {fb['n_reachable']}"), ""]
    lines += [("| arm | strict pass [95 %] | + forms pass [95 %] | strict reachable | + forms reachable | masked pass | "
               "median best rank | echo | next-token overlap | semantic-only pass |"), "|---|---|---|---|---|---|---|---|---|---|"]

    def num(x, f=".3f"):
        return "-" if x is None else f"{x:{f}}"

    def rate_of(x):
        return fmt(x) if x else "-"

    lines += [f"| {a} | {fmt(r['strict'])} | {rate_of((r.get('forms') or {}).get('strict'))} | "
              f"{num((r.get('strict_reachable') or {}).get('value'))} | "
              f"{num(((r.get('forms') or {}).get('reachable') or {}).get('value'))} | "
              f"{num((r.get('strict_masked') or {}).get('value'))} | {r['median_best_rank']} | "
              f"{num(r.get('echo'))} | {num(r.get('next_overlap'))} | "
              f"{num(((r.get('sem') or {}).get('strict') or {}).get('value'))} |" for a, r in result["arms"].items()]
    if nxt:
        lines += ["", f"Model's own next token (top 10 at the read cells): strict pass {fmt(result['next_token']['strict'])}, "
                      f"echo {num(result['next_token']['echo'])}"]
    lines += ["", "| diff | paired [95 %] |", "|---|---|"]
    lines += [f"| {k} | {fmt(v)} |" for k, v in result["diffs"].items()]
    if result.get("diffs_forms"):
        lines += ["", "| diff (strict + forms) | paired [95 %] |", "|---|---|"]
        lines += [f"| {k} | {fmt(v)} |" for k, v in result["diffs_forms"].items()]
    hi_arms = {a: r["intermediates"] for a, r in result["arms"].items() if r.get("intermediates")}
    if hi_arms:  # jlm.intermediates: headline pass against its control draws
        keys = sorted({k for x in hi_arms.values() for k, v in x.items() if not isinstance(v, dict)} - {"pass", "null", "lift"})
        lines += ["", "| arm (headline cells) | pass | null | lift | " + " | ".join(keys) + " |",
                  "|---|" + "---|" * (3 + len(keys))]
        lines += [f"| {a} | {num(x['pass'])} | {num(x['null'])} | {num(x['lift'], '+.3f') if x['lift'] is not None else '-'} | "
                  + " | ".join(num(x.get(k)) for k in keys) + " |" for a, x in hi_arms.items()]
    (root / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)
    forms.write_sidecar(root, result)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--banks", help="family/split,... (one lens load for all)")
    ap.add_argument("--family")
    ap.add_argument("--split", choices=banks.SPLITS)
    ap.add_argument("--arms", default=DEFAULT_ARMS)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default=str(OUT / "eval"))
    ap.add_argument("--force", action="store_true", help="re-read arms whose readouts exist")
    ap.add_argument("--no-mask", action="store_true", help="skip the prompt-masked readout")
    ap.add_argument("--no-next", action="store_true", help="skip the next-token baseline")
    ap.add_argument("--no-sem", action="store_true", help="skip the semantic-vocabulary readouts (sem/)")
    ap.add_argument("--keep-going", action="store_true",
                    help="skip an arm whose centre cannot be fitted or read on a bank (e.g. one that needs per-family "
                         "tables the bank has none of) instead of stopping")
    ap.add_argument("--rescore", action="store_true",
                    help="recompute strict + forms for the arms in each bank's summary from stored readouts (no lens); "
                         "with neither --banks nor --family, every bank with a summary")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    torch.set_float32_matmul_precision("highest")

    if args.rescore:
        rescore(args)
        return
    names = args.banks.split(",") if args.banks else [f"{args.family}/{args.split}"]
    todo = [banks.load(*n.split("/")) for n in names]
    arms = [parse_arm(a) for a in args.arms.split(",")]
    layers = sorted({L for b in todo for L in banks.specs(b)[0].layers})
    t0 = time.time()
    lenses = {"jlens": Lens(layers, args.device)}
    lenses |= {n: Lens(layers, args.device, n, share=lenses["jlens"]) for n in sorted({a.lens for a in arms} - {"jlens"})}
    vocab = lenses["jlens"].display(list(range(lenses["jlens"].vocab)))
    print(f"lenses {list(lenses)} ready, {len(layers)} layers ({time.time() - t0:.0f}s)", flush=True)
    for bank in todo:
        evaluate_bank(lenses, vocab, bank, arms, args)
        hfdata.share([Path(args.out) / bank.family / bank.split])  # to the shared dataset (no-op if unset)


def rescore(args) -> None:
    from transformers import AutoTokenizer
    from wsbench.produce.render import display_tokens

    out = Path(args.out)
    if args.banks or args.family:
        names = args.banks.split(",") if args.banks else [f"{args.family}/{args.split}"]
    else:
        names = sorted(f"{p.parent.parent.name}/{p.parent.name}" for p in out.glob("*/*/summary.json"))
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    vocab = display_tokens(tok, list(range(len(tok))))
    for name in names:
        family, split = name.split("/")
        if family in MULTI_TOKEN or split not in banks.SPLITS:
            continue
        t0 = time.time()
        bank = banks.load(family, split)
        rescore_bank(vocab, tok, bank, out / family / split)
        print(f"{name}: rescored ({time.time() - t0:.0f} s)", flush=True)
        hfdata.share([out / family / split])


if __name__ == "__main__":
    main()
