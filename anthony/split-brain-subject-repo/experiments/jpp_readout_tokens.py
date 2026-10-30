"""What the headline arms of the J++ finalists page read out, token by token: the full-vocabulary top 20 of every
held-out J++ eval item at every grid layer, for the plain J-lens, plain J++ and the J-lens centred four ways (the
eval's fit-split mean ``ref``; S20x refitted on J++'s fit split; S14b-knnxs8 on the union pool; x13's blind glossary).
Feeds the dashboard's "Readout composition" page (dashboard/views/readout_tokens.py).

    python experiments/jpp_readout_tokens.py --device mps [--limit 4]

The states are experiments/jpp_finalists.py's, built by its own functions (``jpp_items``, ``fit_refs``,
``union_states``, ``s20_const``), so each arm is the arm on the headline bars; the check below recomputes every arm's
held-out recall@10 (Readout Filtering, min over the grid) and stores it beside headline.json's. The top 20 here is
over the *full* vocabulary (no filtering): the page asks what the filter would have to remove. Every id in a top 20 is
stored with its decode, its class (``jlm.controls.token_class``), J++'s semantic flag and its normalised form, and each
item with its prompt forms (``controls.prompt_forms``: template tokens shared by half the items left out), so the page
can count echo of the prompt without a tokenizer.

Writes ``out/analysis/jpp-readout-tokens/readouts.json`` (plain JSON; the dashboard needs no torch).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from umot.provenance import PINS, Provenance

sys.path.insert(0, str(Path(__file__).parent))
from jpp_finalists import (
    EVALS,
    GRID,
    JPP,
    JPP_COMMIT,
    MAPPED,
    SINGLE,
    fit_refs,
    jpp_items,
    prepare_unseen_family,
    s20_const,
    union_states,
)

from jlm import OUT, centres, controls
from jlm.centres import Batch, cell_refs
from jlm.lens import MODEL, Lens, reader
from jlm.score import normalise

TOPK = 20
#: arm -> (map, centre); the first five are headline.json's keys
ARMS = {"jlens": ("jlens", "zero"), "jpp": ("jpp", "zero"), "jlens+ref": ("jlens", "ref"),
        "jlens+s20x-jpp": ("jlens", "s20x-jpp"), "jlens+s14b-knnxs8u": ("jlens", "S14b-knnxs8∪"),
        "jlens+glosb": ("jlens", "glosb:desc")}
READOUTS = ("rms", "cos")


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--jpp-repo", default=str(Path.home() / "src" / "jpp_lens"))
    ap.add_argument("--limit", type=int, default=0, help="first N items per eval (plumbing)")
    ap.add_argument("--s20-steps", type=int, default=150)
    ap.add_argument("--out", default=str(OUT / "analysis" / "jpp-readout-tokens"))
    a = ap.parse_args()
    dev, root = a.device, Path(a.out)
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    res = torch.load(JPP / "residuals.pt", weights_only=False, mmap=True)
    meta = json.loads((JPP / "items.json").read_text())
    keep = list(range(len(meta)))
    if a.limit:
        seen: dict[str, int] = {}
        keep = [p for p, m in enumerate(meta) if (seen.__setitem__(m["eval"], seen.get(m["eval"], 0) + 1) or seen[m["eval"]] <= a.limit)]
    R = {L: res["residuals_L_dict_PN"][L][keep].float() for L in GRID}
    meta, cands = [meta[p] for p in keep], [res["candidate_ids_by_item"][p] for p in keep]
    del res
    n = len(meta)
    ev = [m["eval"] for m in meta]
    fit = [p for p in range(n) if meta[p]["split"] == "fit"]
    held = [p for p in range(n) if meta[p]["split"] == "held"]
    fit_of = {e: [p for p in fit if ev[p] == e] for e in EVALS}
    all_of = {e: [p for p in range(n) if ev[p] == e] for e in EVALS}

    lenses = {"jlens": Lens(GRID, dev)}
    lenses["jpp"] = Lens(GRID, dev, "jpp", share=lenses["jlens"])
    tok, V = lenses["jlens"].tokenizer, lenses["jlens"].vocab
    log(f"lenses loaded ({time.time() - t0:.0f}s), {n} items, {len(held)} held")

    items, text, off = jpp_items(meta, R, tok, Path(a.jpp_repo), GRID)
    import jlm.mu  # noqa: F401  (registers the study centres)
    from jlm.mu import S14

    S14.detected_language("__load__")
    S14._DET.update({it.id: S14.detect_language(text[it.id]) for it in items})
    prepare_unseen_family()
    by_fam = {e: [items[p] for p in all_of[e]] for e in EVALS}

    def ref(L):
        X = torch.empty_like(R[L])
        for e in EVALS:
            X[all_of[e]] = R[L][all_of[e]] - R[L][fit_of[e]].mean(0)
        return X

    union = union_states(R, items, by_fam, fit_of, all_of)
    log(f"union pool states ({time.time() - t0:.0f}s)")

    refs = fit_refs()
    glosb = {L: torch.empty_like(R[L]) for L in GRID}
    for e in EVALS:  # as jpp_finalists.main fits glos centres: poetry, with no entry, gets the pooled sets
        c = centres.make("glosb:desc")
        if e in MAPPED:
            c.fit(refs[e], e)
        else:
            parts = [centres.make("glosb:desc") for _ in SINGLE]
            for q, f in zip(parts, SINGLE, strict=True):
                q.fit([], f)
            c.fit([], SINGLE[0])
            c.mu = {L: torch.stack([q.mu[L] for q in parts]).mean(0) for L in c.mu}
        for L in GRID:
            glosb[L][all_of[e]] = centres.apply(c, Batch(L, cell_refs(by_fam[e], e, L), R[L][all_of[e]],
                                                         {it.id: it for it in by_fam[e]}))

    # S20x refitted leave-one-eval-out on the J++ fit split, J-lens only (jpp_finalists.jpp_pool's s20x-jpp)
    targets = {p: sorted({t for ids in cands[p].values() for t in ids}) for p in fit}
    dbar = {}
    for ro in READOUTS:
        for L in GRID:
            H = R[L]
            d = {e: s20_const(lenses["jlens"], L, ro, H[fit_of[e]], [targets[p] for p in fit_of[e]], a.s20_steps, dev)
                 - H[fit_of[e]].mean(0) for e in EVALS}
            for e in EVALS:
                dbar[ro, L, e] = torch.stack([d[g] for g in EVALS if g != e]).mean(0)
        log(f"S20x refit {ro} ({time.time() - t0:.0f}s)")

    def s20x(ro, L):
        X = ref(L)
        for e in EVALS:
            X[all_of[e]] -= dbar[ro, L, e]
        return X

    state = {"zero": lambda ro, L: R[L], "ref": lambda ro, L: ref(L), "s20x-jpp": s20x,
             "S14b-knnxs8∪": lambda ro, L: union[L], "glosb:desc": lambda ro, L: glosb[L]}

    spared = {t for c in cands for ids in c.values() for t in ids}
    excl = torch.zeros(V, dtype=torch.bool, device=dev)
    excl[controls.non_semantic_ids(tok, V, spared)] = True
    held_t = torch.tensor(held)
    pairs = [(j, i, c) for j, p in enumerate(held) for i, c in cands[p].items()]
    C = max(len(c) for _, _, c in pairs)
    pair_item = torch.tensor([j for j, _, _ in pairs], device=dev)
    pair_c = torch.tensor([c + [c[0]] * (C - len(c)) for _, _, c in pairs], device=dev)
    pair_eval = [ev[held[j]] for j, _, _ in pairs]

    top, check = {}, {}
    for arm, (m, name) in ARMS.items():
        for ro in READOUTS:
            ids, rk = [], []
            for L in GRID:
                S = lenses[m].scores(state[name](ro, L)[held_t].to(dev), L, ro)
                ids.append(S.topk(TOPK, dim=1).indices.cpu())
                Sf = S.masked_fill(excl, float("-inf"))[pair_item]
                best = Sf.gather(1, pair_c).max(1).values
                rk.append((Sf >= best[:, None]).sum(1).cpu())
                del S, Sf
            top[f"{arm}|{ro}"] = torch.stack(ids, 1).tolist()  # [held items][layers][TOPK]
            hit = (torch.stack(rk, 1).min(1).values <= 10).float().numpy()
            per = {e: float(hit[[k for k, x in enumerate(pair_eval) if x == e]].mean()) for e in EVALS}
            check[f"{arm}|{ro}"] = {"macro": float(np.mean(list(per.values()))), **per}
            log(arm, ro, round(check[f"{arm}|{ro}"]["macro"], 4), f"({time.time() - t0:.0f}s)")

    head = OUT / "analysis" / "jpp-finalists" / "headline.json"
    stored = json.loads(head.read_text())["scores"] if head.exists() else {}
    for k, v in check.items():
        if k in stored:
            v["headline"] = stored[k]["macro"][0]

    used = sorted({t for rows in top.values() for r in rows for layer in r for t in layer})
    special = set(tok.all_special_ids) | set(tok.added_tokens_decoder)
    vocab = {}
    for t in used:
        s = tok.decode([t])
        vocab[t] = {"s": s, "cls": controls.token_class(s, t in special), "sem": any(ch.isalnum() for ch in s),
                    "form": normalise(s).strip()}
    decoded = {it.id: tok.batch_decode([[t] for t in it.ids[: it.idx[0] + 1]]) for it in (items[p] for p in held)}
    forms = controls.prompt_forms(decoded)
    out_items = []
    for p in held:
        it, mm = items[p], meta[p]
        out_items.append({"eval": mm["eval"], "item": mm["item"], "prompt": text[it.id], "read_token": mm["read_token"],
                          "targets": {i: tok.batch_decode([[t] for t in ids]) for i, ids in cands[p].items()},
                          "forms": sorted(forms[it.id])})
    prov = Provenance(model=MODEL, model_revision=PINS[MODEL], reader=reader("jlens")[0], reader_revision=reader("jlens")[1],
                      dataset=f"jpp_lens readout evals @ {JPP_COMMIT} (umot/out/jpp), held-out split",
                      extra={"maps": {m: reader(m) for m in ("jlens", "jpp")}, "arms": ARMS, "grid": GRID, "topk": TOPK,
                             "s20_steps": a.s20_steps, "limit": a.limit, "approx_context_items": off,
                             "classes": controls.TOKEN_CLASSES})
    # write_artefact's document, compact: the top-20 lists would be ~1M indented lines
    doc = {"provenance": prov.to_dict(), "result": {"layers": GRID, "arms": list(ARMS), "readouts": list(READOUTS),
                                                    "items": out_items, "top": top, "vocab": vocab, "check": check}}
    (root / "readouts.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    log(f"RT_DONE {time.time() - t0:.0f}s -> {root / 'readouts.json'}")


if __name__ == "__main__":
    sys.exit(main())
