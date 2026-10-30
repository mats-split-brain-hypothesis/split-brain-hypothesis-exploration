"""R0: does Qwen3.6-27B's J-lens read Qwen3.8-27B's states as well as it reads its own? At the r0 positions (2,000
random subject tokens per target): J-lens top-1 = the model's own top-1 next token, per layer, on 3.6's states vs
3.8's, and how often the two models' own top-1 agree. -> whitebox-captures/r0.json (shown on /whitebox).

    python r0_report.py
"""

import json

import numpy as np

from capture import READER_LAYERS
from moments import TARGETS
from view import CAPS


def main() -> None:
    out = {"layers": READER_LAYERS, "targets": {}}
    tot = {"j36": [], "j38": [], "own": []}
    for t in TARGETS:
        d = CAPS / t
        r0 = d / "r0"
        pos = np.load(r0 / "pos.npy")
        pidx = np.load(d / "pred_idx.npy")
        keep = np.isin(pos, pidx)  # 3.8's prediction is stored only where the next token is also the subject's
        pos = pos[keep]
        j36 = np.load(r0 / "jlens36_ids.npy")[keep, :, 0]
        own36 = np.load(r0 / "ids36_top.npy")[keep, 0]
        subj = np.load(d / "subj_idx.npy")
        j38 = np.load(d / "readers" / "jlens_plain_ids.npy")[np.searchsorted(subj, pos), :, 0]
        own38 = np.load(d / "pred_topk_ids.npy")[np.searchsorted(pidx, pos), 0]
        a36 = (j36 == own36[:, None]).mean(0)
        a38 = (j38 == own38[:, None]).mean(0)
        own = float((own36 == own38).mean())
        out["targets"][t] = {"jlens_on_36": a36.round(3).tolist(), "jlens_on_38": a38.round(3).tolist(), "own_top1_36_vs_38": round(own, 3)}
        tot["j36"].append(a36); tot["j38"].append(a38); tot["own"].append(own)
        print(f"{t[:26]:26} n {len(pos)}; own top-1 3.6 = 3.8: {own:.3f}")
    m36, m38 = np.mean(tot["j36"], 0), np.mean(tot["j38"], 0)
    out["mean"] = {"jlens_on_36": m36.round(3).tolist(), "jlens_on_38": m38.round(3).tolist(), "own_top1_36_vs_38": round(float(np.mean(tot["own"])), 3)}
    print("layer   J-lens on 3.6 (own)   on 3.8   ratio")
    for L, a, b in zip(READER_LAYERS, m36, m38):
        print(f"L{L:<5} {a:10.3f}           {b:7.3f}   {b / a if a else float('nan'):.2f}")
    (CAPS / "r0.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
