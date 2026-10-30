"""S20 summary: every family's ceilings (in-sample / K-fold / val) side by side with zero and fam, from
out/analysis/S20/<family>-fit[<tag>].json; macro over families and the gain of each class over fam. Two runs of the
same fit (``""`` and ``-g``) give the fit-to-fit spread. Writes out/analysis/S20/summary.md.

  python experiments/s20_summary.py
"""

import json

from jlm import OUT

FAMS = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
        "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
CLASSES = ["const", "tok", "clu", "proj16"]


def load(tag: str) -> dict:
    out = {}
    for f in FAMS:
        p = OUT / "analysis" / "S20" / f"{f}-fit{tag}.json"
        if p.exists():
            out[f] = json.loads(p.read_text())
    return out


def main() -> None:
    root = OUT / "analysis" / "S20"
    lines = ["# S20 ceilings (fitted WITH fit targets: not methods). cos readout, exact item rule; _mt: any required piece",
             "", "Columns: 3-fold held-out on fit (fit-only baseline: fam = leave-one-group-out) | val (fit on all of fit, read val).", ""]
    for tag in ("", "-g"):
        R = load(tag)
        if not R:
            continue
        lines += [f"## run `{tag or 'main'}`", "",
                  "| family | n | fit zero | fit fam | " + " | ".join(f"{c} 3-fold" for c in CLASSES) + " | val zero | val fam | "
                  + " | ".join(f"{c} val" for c in CLASSES) + " |", "|---" * (5 + 2 * len(CLASSES) + 2) + "|"]
        acc = {k: [] for k in ["fz", "ff", "vz", "vf"] + [f"{c}k" for c in CLASSES] + [f"{c}v" for c in CLASSES]}
        for f, r in R.items():
            cl = r["classes"]
            any_c = next(iter(cl.values()))
            row = [f, str(r["n_items"]), f"{r['zero']['pass']:.3f}", f"{r['fam_logo']['pass']:.3f}"]
            acc["fz"].append(r["zero"]["pass"]); acc["ff"].append(r["fam_logo"]["pass"])
            for c in CLASSES:
                v = cl.get(c, {}).get("held_out_folds", {}).get("pass")
                row.append("" if v is None else f"{v:.3f}")
                if v is not None:
                    acc[f"{c}k"].append(v)
            vz, vf = any_c["val_zero"]["pass"], any_c["val_fam_fit"]["pass"]
            acc["vz"].append(vz); acc["vf"].append(vf)
            row += [f"{vz:.3f}", f"{vf:.3f}"]
            for c in CLASSES:
                v = cl.get(c, {}).get("val", {}).get("pass")
                row.append("" if v is None else f"{v:.3f}")
                if v is not None:
                    acc[f"{c}v"].append(v)
            lines.append("| " + " | ".join(row) + " |")
        mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
        n = len(R)
        lines.append(f"| **macro ({n})** | | {mean(acc['fz']):.3f} | {mean(acc['ff']):.3f} | "
                     + " | ".join(f"{mean(acc[c + 'k']):.3f}" if len(acc[c + 'k']) == n else "" for c in CLASSES)
                     + f" | {mean(acc['vz']):.3f} | {mean(acc['vf']):.3f} | "
                     + " | ".join(f"{mean(acc[c + 'v']):.3f}" if len(acc[c + 'v']) == n else "" for c in CLASSES) + " |")
        lines.append("")
    (root / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
