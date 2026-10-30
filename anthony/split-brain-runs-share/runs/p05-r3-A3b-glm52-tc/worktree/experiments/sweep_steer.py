"""Content-vs-function contrastive steering vector for the association J-lens.

The plain J-lens readout at the final token is dominated by function/continuation words
(" The", " This", " What"), burying the target content nouns. We build a contrast:
  POS: residuals at the last token of "<carrier> <content-noun>" (diverse nouns)
  NEG: residuals at the last token of "<carrier> <function-word>" (the/and/of/is...)
The carrier is identical, so the difference isolates "content-noun mode" - "function-word
mode". Adding this to the association items' residual should suppress function words and
let the scene's implied concept (the strongest content noun) rise into the top-10.
"""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

LAYERS = [22, 24, 26, 28, 30]

CONTENT_NOUNS = [
    "table", "freedom", "river", "mountain", "music", "garden", "thunder", "candle",
    "mirror", "harvest", "compass", "ember", "meadow", "anchor", "lantern", "quill",
    "bridge", "forest", "clock", "feather", "velvet", "granite", "willow", "tundra",
    "castle", "harbor", "meadow", "orchard", "pelican", "sapphire", "marble", " viola",
    "carnival", "library", "winter", "summer", "autumn", "morning", "evening", "midnight",
    "thunder", "lightning", "horizon", "summit", "valley", "ocean", "desert", "meadow",
    "violin", "trumpet", "balloon", "ribbon", " saddle", "helmet", " arrow", "scroll",
]

FUNCTION_WORDS = [
    "the", "and", "of", "to", "is", "a", "in", "that", "it", "for",
    "was", "on", "with", "as", "at", "by", "from", "but", "not", "this",
    " The", " This", " And", " Of", " To", " Is", " In", " That", " It", " For",
    "\n", "\n\n", ".", ",", ":", ";", " the", " and", " of", " to",
]

CARRIER = "Word: "


def capture_set(words: list[str]) -> dict:
    prompts = [{"user": CARRIER + w, "assistant": ""} for w in words]
    spec = {"layers": LAYERS, "prompts": prompts, "positions": "last"}
    return metric.capture(spec)


def main() -> None:
    pos = capture_set(CONTENT_NOUNS)
    neg = capture_set(FUNCTION_WORDS)
    vecs = {}
    for L in LAYERS:
        v = (pos["mean"][L] - neg["mean"][L]).float()
        vecs[L] = v
        print(f"L{L}: ||v||={v.norm().item():.3f}", file=sys.stderr)
    out = ROOT / "submission" / "vectors_cf.pt"
    torch.save(vecs, out)
    print(f"saved -> {out}", file=sys.stderr)
    # sweep
    for pos_sel in ["prefix", "context", "read"]:
        for sc in [0.5, 1.0, 2.0, 4.0, 8.0]:
            r = metric.run_metric(vecs, pos_sel, sc)
            print(f"{pos_sel:8s} scale={sc:>4}  pass@10={r['pass_at_10']:.4f}  rank={r['mean_log10_rank']:.3f}")


if __name__ == "__main__":
    main()
