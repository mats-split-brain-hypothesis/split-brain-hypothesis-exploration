"""E3: "conceptual rehearsal vs release" — actively rehearsing/elaborating a named concept while
copying, versus releasing all thought of it. Same named-concept + carrier structure, but the
positive side means *active semantic elaboration*, distinct from generic think/don't-think.
"""
import sys
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

LAYERS = list(range(14, 31))


def main():
    pos, neg = [], []
    import importlib.util
    # reuse build_wb's lists without running its main
    spec = importlib.util.spec_from_file_location("bw", "work/build_wb.py")
    bw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bw)
    for i in range(min(len(bw.CONCEPTS), len(bw.CARRIERS))):
        c, s = bw.CONCEPTS[i], bw.CARRIERS[i]
        pos.append({"user": f"Mentally describe {c} in vivid detail while you write. Now write exactly this sentence:",
                    "assistant": f'"{s}"'})
        neg.append({"user": f"Let go of any thought of {c} while you write. Now write exactly this sentence:",
                    "assistant": f'"{s}"'})
    out = {}
    for tag, prompts in [("pos", pos), ("neg", neg)]:
        r = metric.capture({"layers": LAYERS, "positions": "assistant", "prompts": prompts})
        out[tag] = r["mean"]
        print(f"[E3] {tag}: {r['n_prompts']} prompts", file=sys.stderr)
    u = {}
    print("layer  ||d_l||")
    for L in LAYERS:
        d = (out["pos"][L] - out["neg"][L]).float()
        print(f"{L:5d}  {d.norm().item():8.4f}")
        u[L] = d / d.norm()
    torch.save({L: u[L] for L in [20, 21, 22, 23, 24]}, "work/E3_band.pt")
    print("saved work/E3_band.pt", file=sys.stderr)


if __name__ == "__main__":
    main()