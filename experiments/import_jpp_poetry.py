"""Import the J++ paper's poetry readout eval as a dev family, ``poetry/{fit,val}``, with its captures (no forward pass).

The items are J++'s ``lens-eval-poetry.json`` (repo @ ``JPP_COMMIT``): a rhyming couplet cut before the rhyme word, the
target (``intermediates``) the rhyme word, read at the newline that ends line one. The split is J++'s own, as umot's
capture stored it (``umot/out/jpp/items.json``, seed 0, 20 % fit): ``fit`` = their fit split (16 items), ``val`` =
their held split (65). Their 17 ``incorrect`` items (the 27B does not complete the rhyme) are left out, as J++'s
recall@k leaves them out.

The residuals are umot's capture of the same prompts (``umot/out/jpp/residuals.pt``, fp32, every layer 0-62, one read
cell per item), stored here in our capture format (bf16, the bench plan's layers plus umot's reader layer 42). The
read cell is the bench's own: WorkspaceBench's poetry plan reads the same newline (``line_one_newline``), and every
item's cell is checked against the stored read position and token count. Layer convention checked against our typo
bench captures on prompts both sets share: cosine >= 0.9998 at layers 20 / 40 / 60 (the gap is their fp32 vs our bf16).

Not a held-out dev bank in our sense: 50 of the 98 prompts are also WorkspaceBench poetry bench prompts, so a centre
fitted on ``poetry/fit`` must not be read on ``poetry/bench``. ``jlm.banks.NOT_POOLED`` keeps poetry out of the
pooled references (fitall, fitothers, plainothers) and the screens that glob ``data/dev/*/fit.json``.

  python experiments/import_jpp_poetry.py [--jpp-repo ~/src/jpp_lens]
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import torch
from umot.capture import READER_LAYER, ItemCapture
from umot.provenance import JPP_COMMIT, PINS, Provenance, write_artefact

from jlm import REPO_ROOT, banks, hfdata
from jlm import capture as jcap
from jlm.lens import MODEL
from umot import capture as ucap

JPP = REPO_ROOT / "umot" / "out" / "jpp"
SPLIT = {"fit": "fit", "held": "val"}  # J++ split -> ours; "incorrect" is left out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--jpp-repo", default=str(Path.home() / "src" / "jpp_lens"))
    args = ap.parse_args()
    from transformers import AutoTokenizer

    src = Path(args.jpp_repo) / "data" / "jlens" / "evaluations" / "lens-eval-poetry.json"
    by_name = {it["name"]: it for it in json.loads(src.read_text())["items"]}
    meta = json.loads((JPP / "items.json").read_text())
    rows = {m["item"]: (p, m) for p, m in enumerate(meta) if m["eval"] == "poetry"}
    print(f"J++ poetry: {len(by_name)} items, splits {Counter(m['split'] for _, m in rows.values())}")
    bench = {it["prompt"] for it in json.loads(banks.path_of("poetry", "bench").read_text())["items"]}
    res = torch.load(JPP / "residuals.pt", weights_only=False, mmap=True)
    R = res["residuals_L_dict_PN"]
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])

    for jsplit, split in SPLIT.items():
        names = [n for n in by_name if rows[n][1]["split"] == jsplit]  # J++ file order
        items = [{"name": n, "prompt": by_name[n]["prompt"], "intermediates": by_name[n]["intermediates"],
                  "readout": {"kind": "line_one_newline"}, "source": "jpp", "jpp_split": jsplit,
                  "in_bench": by_name[n]["prompt"] in bench} for n in names]
        header = {"family": "poetry", "split": split,
                  "source": f"J++ lens-eval-poetry.json @ {JPP_COMMIT}, J++ split {jsplit!r} (umot/out/jpp/items.json)",
                  "read": "the newline token that ends line one of the couplet (the bench's line_one_newline)",
                  "bench_overlap": f"{sum(it['in_bench'] for it in items)} of {len(items)} prompts are WorkspaceBench "
                                   "poetry bench prompts: not held out from poetry/bench"}
        path = banks.path_of("poetry", split)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**header, "items": items}, ensure_ascii=False, indent=1) + "\n")
        bank = banks.load("poetry", split)

        name_of = {it["id"]: it["name"] for it in bank.items}
        caps = []
        for spec in banks.specs(bank):
            p, m = rows[name_of[spec.id]]
            c = ucap.cells(spec, tok)
            if c.idx != [m["read_pos"]] or len(c.ids) != m["n_tokens"] or c.ids[m["read_pos"]] != m["read_token_id"]:
                raise RuntimeError(f"{spec.id}: our cell {c.idx} / {len(c.ids)} tokens, J++'s {m['read_pos']} / {m['n_tokens']}")
            layers = sorted({*spec.layers, READER_LAYER})
            caps.append(ItemCapture(c.id, c.ids, c.decoded, c.positions, c.idx,
                                    {L: R[L][p : p + 1].to(torch.bfloat16) for L in layers}))
        out = jcap.path_of(bank)
        ucap.save(caps, out)
        write_artefact(out.with_suffix(".provenance.json"),
                       Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/{bank.name}",
                                  extra={"from": "umot/out/jpp/residuals.pt (fp32, stored bf16)", "jpp_commit": JPP_COMMIT}),
                       {"items": len(caps), "bank": str(bank.path)})
        hfdata.share([out, out.with_suffix(".provenance.json")])
        print(f"poetry/{split}: {len(items)} items ({header['bench_overlap']}) -> {path}, {out}")


if __name__ == "__main__":
    main()
