"""Residuals at a bank's read cells, captured once per bank on the pod (27B and 70B do not fit the Mac).

Stored in umot's ``ItemCapture`` format (bf16, ``acts = {layer: [n_pos, d]}``), so umot's tools
read our files and we read umot's existing bench captures in place (``LEGACY``).
"""

from pathlib import Path

import torch
from umot.capture import ItemCapture
from umot.provenance import Provenance, write_artefact
from umot.provenance import REPO_ROOT as UMOT_ROOT

from jlm import OUT, hfdata, models
from jlm.banks import Bank, dev_families, specs
from jlm.banks import load as load_bank
from umot import capture as ucap

SPEC = models.current()
MODEL = SPEC.hf_id

#: Bench captures umot already made with the same model pin, plan and capture code.
LEGACY = {
    ("typo", "bench"): UMOT_ROOT / "out" / "captures" / "typo.pt",
    ("directed_modulation", "bench"): UMOT_ROOT / "out" / "captures" / "directed_modulation.pt",
}


#: Non-bank reference captures for corpus-based centres (made by experiments/capture_mu_refs.py on
#: constant-mean-exploration; shared through the dataset like every capture).
REFS = {"corpus": OUT / "captures" / "corpus-wiki.pt", "sents": OUT / "captures" / "sents-wiki.pt"}

#: x101's MIN_POS convention for corpus-wide means: the first positions carry outsized norms.
CORPUS_MIN_POS = 8


def path_of(bank: Bank) -> Path:
    return models.out_dir() / "captures" / f"{bank.family}-{bank.split}.pt"


def min_pos_view(items: list[ItemCapture], min_pos: int) -> list[ItemCapture]:
    """The same captures restricted to read positions with absolute index >= ``min_pos``."""
    out = []
    for it in items:
        keep = [k for k, i in enumerate(it.idx) if i >= min_pos]
        if keep:
            out.append(
                ItemCapture(
                    id=it.id,
                    ids=it.ids,
                    decoded=it.decoded,
                    positions=[it.positions[k] for k in keep],
                    idx=[it.idx[k] for k in keep],
                    acts={L: a[keep] for L, a in it.acts.items()},
                )
            )
    return out


def load_ref(name: str) -> list[ItemCapture]:
    """``corpus`` (wikitext paragraphs, every position), ``corpus8`` (the same from position
    :data:`CORPUS_MIN_POS` on, for corpus-wide and token means) or ``sents`` (standalone
    wikitext sentences at their final token)."""
    base = name.removesuffix("8")
    items = ucap.load(REFS[base])
    return min_pos_view(items, CORPUS_MIN_POS) if name != base else items


#: Reference sets that are not a split of the read family: corpora (load_ref) and pools of other banks' fit captures
#: (x4, x6): every single-token dev family, every one but the read family, or the plain-render ones but the read one.
CORPORA = ("corpus", "corpus8", "sents")
POOLS = ("fitall", "fitothers", "plainothers")


def load_refs(bank: Bank, ref: str, items: list[ItemCapture] | None = None) -> tuple[list[ItemCapture], dict[str, str], Bank | None]:
    """What a centre ``@ref`` is fitted on when it reads ``bank``: (captures, the item groups they add, the reference
    bank when it is a single bank, for its context store). ``self`` / ``""`` is the read bank (``items`` if given), a
    split is that split of the read family, else a corpus (:data:`CORPORA`) or a pool (:data:`POOLS`). Shared by
    experiments/evaluate.py, experiments/analyse.py and jlm.geometry, so a centre is rebuilt as it was evaluated."""
    if ref in ("", "self"):
        return (items if items is not None else load(bank)), {}, bank
    if ref in CORPORA:
        return load_ref(ref), {}, None
    if ref in POOLS:
        # the 7 single-token families, as x4 / x6 registered them (the *_mt dev banks came later)
        fams = [f for f in dev_families() if not f.endswith("_mt")]
        if ref == "plainothers":  # render from the plan, not a family list
            fams = [f for f in fams if specs(load_bank(f, "fit"))[0].render in ("plain", "bare")]
        if ref != "fitall":
            fams = [f for f in fams if f != bank.family]
        return [it for f in fams for it in load(load_bank(f, "fit"))], {}, None
    ref_bank = load_bank(bank.family, ref)
    return load(ref_bank), {it["id"]: it.get("pair_id") or it["id"] for it in ref_bank.items}, ref_bank


def load(bank: Bank) -> list[ItemCapture]:
    """The bank's capture, checked against the bank: one entry per item, in bank order."""
    path = path_of(bank)
    if not path.exists() and (bank.family, bank.split) in LEGACY:
        path = LEGACY[bank.family, bank.split]
    if not path.exists():
        raise FileNotFoundError(f"{bank.name}: no capture at {path}; run experiments/capture.py on the pod")
    items = ucap.load(path)
    want = [it["id"] for it in bank.items]
    got = [it.id for it in items]
    if sorted(got) != sorted(want):
        raise RuntimeError(f"{path}: {len(set(want) - set(got))} bank items missing, {len(set(got) - set(want))} extra")
    order = {i: k for k, i in enumerate(want)}
    return sorted(items, key=lambda it: order[it.id])


def load_backend(device: str):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from wsbench.produce.backend import Backend

    rev = SPEC.revision
    tok = AutoTokenizer.from_pretrained(MODEL, revision=rev)
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=rev, dtype=torch.bfloat16, device_map=device)
    model.eval()
    return Backend(model=model, tokenizer=tok, device=device, model_id=MODEL)


def run(bank: Bank, device: str, *, limit: int = 0) -> Path:
    """Capture every read cell of ``bank`` at the plan's layers plus umot's reader layer 42."""
    backend = load_backend(device)
    out = [ucap.capture_spec(backend, s) for s in specs(bank)[: limit or None]]
    path = path_of(bank) if not limit else path_of(bank).with_name(f"{bank.family}-{bank.split}-limit{limit}.pt")
    ucap.save(out, path)
    write_artefact(
        path.with_suffix(".provenance.json"),
        Provenance(model=MODEL, model_revision=SPEC.revision, dataset=f"jlm/{bank.name}", extra={"limit": limit}),
        {"items": len(out), "bank": str(bank.path)},
    )
    hfdata.share([path, path.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)
    return path
