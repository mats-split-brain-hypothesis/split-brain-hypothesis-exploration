"""Build a bank-free stance steering vector from self-authored think/don't-think pairs.

The contrast mimics the *form* of WorkspaceBench's directed_modulation pairs (think about a
concept while copying an unrelated sentence vs do not think about it) but uses concepts and
carrier sentences I wrote myself, with no dependency on any benchmark bank. The direction is
the per-prompt carrier-cell mean difference between the two conditions, unit-normalised, then
scaled by 0.13 * ||d_l|| (the per-layer step convention) so that --scale k is the dose.

Run:
    .venv/bin/python experiments/build_steer_vec.py capture-think
    .venv/bin/python experiments/build_steer_vec.py capture-neg
    .venv/bin/python experiments/build_steer_vec.py build
"""
import json
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/steer"
OUT.mkdir(parents=True, exist_ok=True)

# Self-authored, concept-agnostic think / don't-think pairs. Concepts span domains unrelated to
# the association targets; carriers are neutral office/domestic sentences. The two conditions
# share the concept and the carrier, so they cancel and only the stance remains.
PAIRS = [
    # (category, concept, carrier)
    ("body part", "elbow", "The invoice was paid in three instalments."),
    ("body part", "ankle", "She filed the quarterly report on time."),
    ("musical instrument", "cello", "The committee approved the budget unanimously."),
    ("musical instrument", "trumpet", "He signed the lease without reading it."),
    ("animal", "hedgehog", "The keys were left on the kitchen counter."),
    ("animal", "pelican", "The software was deployed on Friday afternoon."),
    ("tool", "wrench", "The meeting ran twenty minutes over."),
    ("tool", "chisel", "The parcel arrived on Wednesday morning."),
    ("kitchen item", "whisk", "The transcript was edited for clarity."),
    ("kitchen item", "ladle", "The ladder leaned against the garage wall."),
    ("sport", "fencing", "The receipt was stapled to the envelope."),
    ("sport", "rowing", "The form was returned with a signature."),
    ("plant", "fern", "The catalog was updated last quarter."),
    ("plant", "thistle", "The drawer would not close properly."),
    ("colour", "turquoise", "The memo was circulated to all staff."),
    ("colour", "maroon", "The door was left ajar all afternoon."),
    ("weather", "sleet", "The account was closed in March."),
    ("weather", "drizzle", "The contract was renewed for a year."),
    ("geography", "plateau", "The notes were scribbled on a napkin."),
    ("geography", "isthmus", "The button was sewn on crooked."),
    ("food", "lentil", "The schedule was pinned to the board."),
    ("food", "turnip", "The letter was postmarked in June."),
    ("vehicle", "gondola", "The lecture was attended by forty students."),
    ("vehicle", "scooter", "The report was bound in a blue folder."),
    ("clothing", "waistcoat", "The kettle was left on the stove."),
    ("clothing", "beret", "The invoice total was rounded up."),
    ("building", "observatory", "The rug was vacuumed on Tuesday."),
    ("building", "lighthouse", "The essay was submitted a day late."),
    ("element", "mercury", "The receipt was crumpled in a pocket."),
    ("element", "krypton", "The shelf was dusted that morning."),
    ("profession", "blacksmith", "The query was resolved by support."),
    ("profession", "cartographer", "The blanket was folded at the foot of the bed."),
]

LAYERS = list(range(18, 27))  # 18..26, flexibility around the 20-24 band


def _prompt(category, concept, carrier, polarity):
    verb = "Think about" if polarity == "think" else "Do not think about"
    return (f'{verb} the {category} {concept} while you write. '
            f'Now write exactly this sentence: "{carrier}"')


def write_spec(polarity, path):
    prompts = [{"user": _prompt(c, con, car, polarity), "assistant": car}
               for (c, con, car) in PAIRS]
    spec = {"layers": LAYERS, "per_prompt": True, "prompts": prompts, "positions": "assistant"}
    path.write_text(json.dumps(spec))
    return path


def capture(polarity):
    spec = OUT / f"stance_{polarity}_spec.json"
    outp = OUT / f"stance_{polarity}.pt"
    write_spec(polarity, spec)
    subprocess.run([str(ROOT / ".venv/bin/python"), "tools/metric.py",
                    "capture", str(spec), "--out", str(outp)], check=True, cwd=str(ROOT))
    return torch.load(outp, weights_only=False)


def build():
    pos = torch.load(OUT / "stance_think.pt", weights_only=False)
    neg = torch.load(OUT / "stance_dontthink.pt", weights_only=False)
    layers = pos["layers"]
    pp_pos = pos["per_prompt"]   # {L: [n, d]}
    pp_neg = neg["per_prompt"]
    d = {}
    for L in layers:
        mpos = pp_pos[L].float().mean(0)   # mean over prompts (per-prompt carrier mean already)
        mneg = pp_neg[L].float().mean(0)
        d_l = mpos - mneg
        d[L] = {"d": d_l, "norm": d_l.norm().item(), "mpos_norm": mpos.norm().item(),
                "mneg_norm": mneg.norm().item()}
    # report
    for L in layers:
        print(f"L{L}: ||d||={d[L]['norm']:.3f}  ||mpos||={d[L]['mpos_norm']:.3f}  "
              f"||mneg||={d[L]['mneg_norm']:.3f}")
    # vectors for the 20-24 band, scaled by 0.13 * d_l (so --scale k == WBS dose k)
    vecs = {L: (0.13 * d[L]["d"]) for L in range(20, 25)}
    torch.save(vecs, OUT / "vectors_stance.pt")
    # also save unit-vector variant for norm-based dosing experiments
    torch.save({L: d[L]["d"] / d[L]["d"].norm() for L in range(20, 25)},
               OUT / "vectors_unit.pt")
    print("saved vectors_stance.pt (0.13*d) and vectors_unit.pt (unit dir) for layers 20-24")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "capture-think":
        capture("think")
    elif cmd == "capture-neg":
        capture("dontthink")
    elif cmd == "build":
        build()
    else:
        raise SystemExit(cmd)
