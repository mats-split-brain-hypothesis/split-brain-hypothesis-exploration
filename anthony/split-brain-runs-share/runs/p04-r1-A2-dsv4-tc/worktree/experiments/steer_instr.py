"""Instruction-steering direction: scene+question vs scene alone, tested across positions."""
import sys, os, torch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric
from steer_scene import SCENE, cap
LAYERS = [26, 28, 30]

Q = " What activity is being described? Answer in one word."

def main():
    A = cap("scene_question", [s + Q for s in SCENE], "last")
    B = cap("scene", SCENE, "last")  # cached
    vecs = {int(L): (A[L] - B[L]) for L in LAYERS}
    torch.save(vecs, "out/steer/instr.pt")
    for L in LAYERS:
        print(f"L{L} ||A||={float(A[L].norm()):.2f} ||B||={float(B[L].norm()):.2f} ||v||={float(vecs[L].norm()):.2f}")
    for pos in ["read", "prefix", "context"]:
        for s in [1.0, 3.0]:
            r = metric.run_metric(vecs, pos, s)
            print(f"pos={pos} scale={s:+.1f}: pass@10 {r['pass_at_10']:.4f}  meanlog10 {r['mean_log10_rank']:.4f}")
            print("   " + " ".join(f"{e['id'].split('-')[-1]}:{e['baseline_rank']}->{e['best_rank']}" for e in r['examples']))

if __name__ == "__main__":
    main()
