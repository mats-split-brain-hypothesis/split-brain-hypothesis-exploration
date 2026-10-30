"""Build a contrastive steering vector for the association J-lens readout.

Contrast: evocative scenes (my own, not the bench items) framed two ways:
  POS: "Free-associate: what single concept does this scene evoke?  <scene>"
  NEG: "Continue this passage naturally.  <scene>"
Capture the residual at the scene's final token (positions="last"); the difference
captures the "concept-extraction" mode vs "continuation" mode. Adding that direction
to the association items' forward pass should push the final-token residual toward
encoding each scene's implied concept, where the plain (uncentred) J-lens can read it.

Run:
  .venv/bin/python experiments/build_steer_contrast.py
"""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

LAYERS = [18, 20, 22, 24, 26, 28, 30]

# My own evocative vignettes (NOT the bench items), each implying some concept.
SCENES = [
    "The tent was striped and the clowns piled out of a tiny car while the ringmaster cracked his whip.",
    "The hearse rolled slowly past the lowered heads and the organ played a hymn nobody could finish.",
    "The bell rang and twenty children grabbed their backpacks and poured into the fluorescent hallway.",
    "The trenches were full of mud and the shells came over every few minutes while the soldiers kept their heads down.",
    "The gavel came down and the jury box emptied while the man in the orange suit stared at the floor.",
    "The needles were sterilized and the patient counted backward from ten as the mask came down.",
    "The cockpit lit up red and the pilot pulled back on the stick as the carrier deck fell away.",
    "The monks chanted in the cold stone corridor and the candles threw long shadows on the wall.",
    "The market stalls overflowed with spices and the vendors shouted over each other in a dozen tongues.",
    "The conductor raised his baton and the strings lifted their bows as the hall fell silent.",
    "The forge glowed orange and the hammer rang on the anvil while sparks flew into the dark.",
    "The sails were hoisted and the creak of the rigging mixed with the spray as the land fell behind.",
    "The microscope was focused and the slide showed a writhing field of cells under the stain.",
    "The ballot box was sealed and the volunteers counted the slips by lamplight long after midnight.",
    "The patient in the chair opened wide and the drill whined as the dentist leaned in.",
    "The combine harvester rolled across the field and the grain poured into the truck all afternoon.",
    "The chapel was dark and the confessional screen slid open as the penitent knelt down.",
    "The stage was bare except for a stool and a microphone where the comedian adjusted the stand.",
    "The verdict was read and the gallery erupted while the bailiff called for order.",
    "The glacier creaked and the ice axes bit in as the team roped up for the final pitch.",
    "The loom clattered and the shuttle flew back and forth while the pattern grew under her hands.",
    "The radar sweep showed a blip and the officer picked up the red phone without a word.",
    "The vats bubbled and the chemist checked the hydrometer before racking off the clear liquid.",
    "The saddle was cinched and the cattle were driven low across the dust as the sun came up.",
    "The rookery stank of guano and the parent birds returned with fish as the chicks begged.",
    "The observatory dome rotated and the lens cap came off as the sky cleared above the mountain.",
    "The type bar struck the platen and the carriage bell rang as she fed another sheet in.",
    "The nets were hauled in heavy and the deckhands sorted the catch by lantern light.",
]

POS_INSTR = "Free-associate: what single concept does this scene evoke?  "
NEG_INSTR = "Continue this passage naturally.  "


def capture_set(instr: str) -> dict:
    prompts = [{"user": instr + s, "assistant": ""} for s in SCENES]
    spec = {"layers": LAYERS, "prompts": prompts, "positions": "last"}
    return metric.capture(spec)


def main() -> None:
    print(f"capturing POS ({len(SCENES)} prompts)...", file=sys.stderr)
    pos = capture_set(POS_INSTR)
    print(f"capturing NEG ({len(SCENES)} prompts)...", file=sys.stderr)
    neg = capture_set(NEG_INSTR)
    vecs = {}
    for L in LAYERS:
        v = pos["mean"][L] - neg["mean"][L]
        vecs[L] = v.float()
        print(f"L{L}: ||v||={v.norm().item():.3f}  pos||={pos['mean'][L].norm().item():.3f}  neg||={neg['mean'][L].norm().item():.3f}", file=sys.stderr)
    out = ROOT / "submission" / "vectors.pt"
    out.parent.mkdir(exist_ok=True)
    torch.save(vecs, out)
    print(f"saved {len(vecs)} layers -> {out}", file=sys.stderr)
    # quick diagnostic: run at read position, scale 1
    r = metric.run_metric(vecs, "read", 1.0)
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
