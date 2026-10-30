"""S23b: how much of each schedule finalist's gain survives its matched union controls (instance e1, steward's card).

Exact offline scoring of two-centre schedules from per-layer readouts (``s23_select.tables``). For each finalist
(early centre A up to L40, late centre B above): (a) A | B switched at every other grid layer, (b) B | A at L40 (swapped),
(c) fam | zero and zero | fam at L40. Reports, per split and readout, the finalist's macro, its gain over fam, the best
matched control, and the share of the gain over fam that survives against it. Writes out/analysis/S23/union-<readout>.md.

  python experiments/s23b_union.py --readout cos
"""

import argparse

from transformers import AutoTokenizer
from umot.provenance import PINS
from wsbench.produce.render import display_tokens

from jlm import OUT
from jlm.lens import MODEL
from s23_select import macro, tables

LATE = "s14:template:64:mean=kmx64:a=0.5@{own}"


def finalists(readout: str) -> dict:
    corr = "s20xon:1:kmx64@{own}" if readout == "cos" else "s20xonrms:1:kmx64@{own}"
    return {"S14k": ("kmx64@fit", "s14t64@{own}"), "S14b": ("kmx64@fit", LATE), "S21b": (corr, LATE)}


def sched(layers, a, b, split_at):
    return [a if L <= split_at else b for L in layers]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readout", default="cos")
    args = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    disp = lambda ids: display_tokens(tok, ids)  # noqa: E731
    F = finalists(args.readout)
    comps = sorted({c for ab in F.values() for c in ab} | {"zero", "fam@{own}"})
    lines = [f"# S23b union controls ({args.readout})", "",
             "| finalist | split | finalist | Δ fam | other switch layers (min / mean / max) | swapped at L40 | fam -> zero / zero -> fam at L40 | best matched control | gain surviving (finalist - best control) / Δ fam |",
             "|---|---|---|---|---|---|---|---|---|"]
    for split in ("fit", "val"):
        tab = tables(split, args.readout, comps, tok, disp)
        layers = next(iter(tab.values()))[1]
        famv = macro(tab, ["fam@{own}"] * len(layers))
        fz, zf = macro(tab, sched(layers, "fam@{own}", "zero", 40)), macro(tab, sched(layers, "zero", "fam@{own}", 40))
        for name, (a, b) in F.items():
            v = macro(tab, sched(layers, a, b, 40))
            other = [macro(tab, sched(layers, a, b, L)) for L in layers[:-1] if L != 40]
            sw = macro(tab, sched(layers, b, a, 40))
            best = max(max(other), sw, fz, zf)
            gain = v - famv
            surv = (v - best) / gain if gain > 0 else float("nan")
            lines.append(f"| {name} | {split} | {v:.3f} | {gain:+.3f} | {min(other):.3f} / {sum(other) / len(other):.3f} / "
                         f"{max(other):.3f} | {sw:.3f} | {fz:.3f} / {zf:.3f} | {best:.3f} | {v - best:+.3f} ({surv:.0%}) |")
    out = OUT / "analysis" / "S23"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"union-{args.readout}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
