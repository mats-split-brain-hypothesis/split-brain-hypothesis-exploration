"""Write submission/vectors.pt from a built direction: layers in band, each = scale * raw_dir."""
import os, sys, torch
sys.path.insert(0, os.path.dirname(__file__))

def finalize(dirs, band, scale, out):
    lo, hi = (int(x) for x in band.split(":"))
    vecs = {}
    for L in range(lo, hi + 1):
        d = dirs[L]
        vecs[L] = (d * scale).float().cpu()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    torch.save(vecs, out)
    norms = {L: round(v.norm().item(), 2) for L, v in vecs.items()}
    print(f"wrote {out}: {norms}")
    return out

if __name__ == "__main__":
    a = sys.argv
    data = torch.load(a[1], weights_only=False)
    finalize(data["dirs"], a[2], float(a[3]), a[4] if len(a) > 4 else "submission/vectors.pt")
