"""Pool a dict-mu read over the six families and score the registered predictions.

  python experiments/x2_pool.py                 # x2: the bench read, @self arms
  python experiments/x2_pool.py --split val     # x3: the held-out dev read, @fit arms

Reads the stored readouts (out/eval/<family>/<split>/<arm>/readouts.jsonl), rebuilds each family's
confirmatory subset (reachable, not leaky, basic_readout non-implicit) with the tokenizer only,
and reports per-family and pooled strict rates plus the registered paired diffs. Pooled = every
scored item once, paired item bootstrap B=10k seed 0 (jlm.score).
"""

import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer
from umot import capture as ucap
from umot.provenance import PINS, Provenance, write_artefact
from wsbench.produce.render import display_tokens

from jlm import OUT, banks, score
from jlm.capture import MODEL, path_of

FAMILIES = ("typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling")
ARMS = ["zero", "fam@self", "dict:fam:0.5@self", "dict:fam:1@self", "dict:strat:1@self",
        "dict:llm:0.5@self", "dict:llm:1@self", "dict:free:1@self", "dict:derang:0.5@self", "dict:derang:1@self"]
VAL_ARMS = ["zero", "fam@fit", "dict:fam:0.5@fit", "dict:fam:1@fit", "dict:strat:1@fit",
            "dict:llm:0.5@fit", "dict:llm:1@fit", "dict:derang:0.5@fit", "dict:derang:1@fit"]
READOUTS = ("cos", "rms")
SPLIT = "bench"


def slug(arm: str, readout: str) -> str:
    return f"{arm}|{readout}".replace("|", "__").replace("@", "-at-")


def rows_of(family: str, arm: str, readout: str) -> list[dict]:
    path = OUT / "eval" / family / SPLIT / slug(arm, readout) / "readouts.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    global ARMS, SPLIT
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--split", default="bench", choices=("bench", "val"))
    args = ap.parse_args()
    SPLIT = args.split
    if SPLIT == "val":
        ARMS = VAL_ARMS
    ref = "self" if SPLIT == "bench" else "fit"
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    disp = display_tokens(tok, list(range(len(tok))))
    passes: dict[tuple, dict[str, bool]] = {}
    scored: dict[str, list[str]] = {}
    for fam in FAMILIES:
        bank = banks.load(fam, SPLIT)
        accepted = score.accepted_ids(disp, bank)
        caps = ucap.load(path_of(bank))
        conf = score.confirmatory(bank, accepted, {it.id: it.decoded for it in caps})
        scored[fam] = [i for i, why in conf.items() if not why]
        for arm in ARMS:
            for ro in READOUTS:
                passes[fam, arm, ro] = score.strict_items(rows_of(fam, arm, ro), bank)

    pooled_ids = [(fam, i) for fam in FAMILIES for i in scored[fam]]
    def pooled(arm: str, ro: str) -> dict[tuple, bool]:
        return {(fam, i): passes[fam, arm, ro][i] for fam, i in pooled_ids}

    lines = [f"# dict-mu pooled over six families, split={SPLIT} (strict, ours)", "",
             f"n scored per family: " + ", ".join(f"{f} {len(scored[f])}" for f in FAMILIES), ""]
    lines += ["| arm | " + " | ".join(FAMILIES) + " | pooled |", "|" + "---|" * (len(FAMILIES) + 2)]
    for arm in ARMS:
        for ro in READOUTS:
            cells = [f"{score.rate(passes[f, arm, ro], scored[f])['value']:.2f}" for f in FAMILIES]
            p = score.rate(pooled(arm, ro), [k for k in pooled_ids])
            lines.append(f"| {arm}\\|{ro} | " + " | ".join(cells) + f" | {p['value']:.3f} |")

    lines += ["", "## Registered diffs (paired, 95 %)", ""]
    def d(a, b, ro, ids=None):
        a, b = a.replace("@self", f"@{ref}"), b.replace("@self", f"@{ref}")
        if ids is None:
            r = score.paired(pooled(a, ro), pooled(b, ro), [k for k in pooled_ids])
        else:
            fam, fam_ids = ids
            r = score.paired(passes[fam, a, ro], passes[fam, b, ro], fam_ids)
        return f"{r['diff']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]"

    lines.append(f"- P1 pooled dict:llm:1 - dict:derang:1 |cos: {d('dict:llm:1@self', 'dict:derang:1@self', 'cos')}")
    for fam in ("multihop", "multilingual", "typo"):
        lines.append(f"- P2 {fam} dict:llm:1 - dict:fam:1 |cos: {d('dict:llm:1@self', 'dict:fam:1@self', 'cos', (fam, scored[fam]))}")
    lines.append(f"- P3 user_modeling dict:strat:1 - dict:llm:1 |cos: {d('dict:strat:1@self', 'dict:llm:1@self', 'cos', ('user_modeling', scored['user_modeling']))}")
    lines.append(f"- P4 pooled dict:derang:1 - zero |rms: {d('dict:derang:1@self', 'zero', 'rms')}")
    for ro in READOUTS:
        lines.append(f"- P5 pooled fam@self - dict:llm:1 |{ro}: {d('fam@self', 'dict:llm:1@self', ro)}")
    for a in ("dict:llm:0.5@self", "dict:llm:1@self"):
        lines.append(f"- P6 pooled {a} - zero |cos: {d(a, 'zero', 'cos')}")
    if SPLIT == "bench":
        lines.append(f"- (desc) pooled dict:free:1 - dict:derang:1 |cos: {d('dict:free:1@self', 'dict:derang:1@self', 'cos')}")
    lines.append(f"- (desc) pooled dict:strat:1 - dict:llm:1 |cos: {d('dict:strat:1@self', 'dict:llm:1@self', 'cos')}")

    tag = "x2-pooled" if SPLIT == "bench" else "x3-pooled"
    out = OUT / "eval" / f"{tag}.md"
    out.write_text("\n".join(lines) + "\n")
    write_artefact(
        OUT / "eval" / f"{tag}.provenance.json",
        Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/dict-mu six families {SPLIT}",
                   extra={"arms": ARMS, "scorer": "strict (jle x89)"}),
        {"n_pooled": len(pooled_ids)},
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
