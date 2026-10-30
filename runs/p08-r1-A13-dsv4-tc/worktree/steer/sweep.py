"""Sweep scale / band / positions for a built contrast direction, scoring via run_metric."""
import argparse, json, os, sys, torch
sys.path.insert(0, "tools")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import metric

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="built direction .pt from build.py")
    ap.add_argument("--band", default="20:24")
    ap.add_argument("--scales", default="0.1,0.2,0.3,0.5,0.7,1.0")
    ap.add_argument("--positions", default="prefix,read,context")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.band.split(":"))
    layers = list(range(lo, hi + 1))
    data = torch.load(a.dir, weights_only=False)
    dirs = data["dirs"]

    # unit-normalise, then multiply by the raw gap norm once we know it
    unit = {L: (dirs[L] / dirs[L].norm()) for L in layers}
    print(f"band {layers}  gap norms: {[round(data['norms'][L],1) for L in layers]}")

    for positions in a.positions.split(","):
        for sc in [float(x) for x in a.scales.split(",")]:
            vecs = {L: (unit[L] * (sc * data["norms"][L])).cpu() for L in layers}
            r = metric.run_metric(vecs, positions, 1.0)
            print(f"pos={positions:7s} scale={sc:4.2f} (multiplies raw gap)  pass@10={r['pass_at_10']:.4f}  mean_log10_rank={r['mean_log10_rank']:.3f}")

if __name__ == "__main__":
    main()
