"""Per archived run: the best per-call mean cos (layers 20-24 present) of the submitted vectors to the rig's reference."""
import glob, os, sys, torch, json
ref = torch.load(sys.argv[1], map_location="cpu")
ref = {int(k): v.float() / v.float().norm() for k, v in ref.items()}
out = []
for run in sorted(glob.glob(os.path.expanduser("~/split-brain-run/archive/*-tc"))):
    best = None
    for f in glob.glob(f"{run}/server-logs/**/vectors-*.pt", recursive=True):
        try: v = torch.load(f, map_location="cpu")
        except Exception: continue
        if isinstance(v, dict) and "vectors" in v: v = v["vectors"]
        if not isinstance(v, dict): continue
        cs = [float(t.float() @ ref[int(L)] / (t.float().norm() + 1e-9)) for L, t in v.items() if int(L) in ref and t.numel() == ref[int(L)].numel()]
        if cs:
            c = sum(cs) / len(cs)
            best = c if best is None else max(best, c)
    if best is not None: out.append((os.path.basename(run), round(best, 3)))
for r, c in out: print(f"{r}\t{c}")
