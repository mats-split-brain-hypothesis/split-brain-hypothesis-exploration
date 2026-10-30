"""The J-lens readouts (readers_pod.py jlens) as the /whitebox page reads them: one JSON line per reply, fetched when
the reply is opened, top-5 per (token, layer) for the plain and the same-token-centred lens, plus the strings of
every token id used. Also R0's check, J-lens on Qwen3.8's states vs Qwen3.8's own next token.

    python jlens_view.py [TARGET ...]   -> whitebox-captures/<T>/jlens_turns.jsonl, jlens_vocab.json; R0 line printed

Line: {"turn", "from" (index into view.json's tokens), "layers", "plain": [[[id x5] x layers] x tokens],
       "centred": ..., "plain_sc", "centred_sc" (cos x 1000, ints), "centre_n": [...]}
"""

import json
import sys
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

from moments import TARGETS
from view import CAPS, MODEL, REV

TOP = 5


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    for t in sys.argv[1:] or list(TARGETS):
        d = CAPS / t
        r = d / "readers"
        if not (r / "jlens_meta.json").exists():
            print(f"{t}: no J-lens yet")
            continue
        meta = json.loads((r / "jlens_meta.json").read_text())
        ids = {m: np.load(r / f"jlens_{m}_ids.npy")[:, :, :TOP] for m in ("plain", "centred")}
        sc = {m: (np.load(r / f"jlens_{m}_sc.npy")[:, :, :TOP].astype(np.float32) * 1000).round().astype(int) for m in ("plain", "centred")}
        cn = np.load(r / "centre_n.npy")
        view = json.loads((d / "view.json").read_text())
        subj = np.load(d / "subj_idx.npy")
        assert list(subj) == view["tokens"]["pos"], "view and J-lens disagree on the subject positions"
        turn = np.array(view["tokens"]["turn"])
        used = set()
        with (d / "jlens_turns.jsonl").open("w") as f:
            for k in np.unique(turn):
                a, b = np.flatnonzero(turn == k)[[0, -1]]
                b += 1
                line = {"turn": int(k), "from": int(a), "layers": meta["layers"], "centre_n": cn[a:b].tolist()}
                for m in ("plain", "centred"):
                    line[m] = ids[m][a:b].tolist()
                    line[f"{m}_sc"] = sc[m][a:b].tolist()
                    used |= set(np.unique(ids[m][a:b]).tolist())
                f.write(json.dumps(line, separators=(",", ":")) + "\n")
        (d / "jlens_vocab.json").write_text(json.dumps({int(i): tok.decode([int(i)]) for i in sorted(used)}, ensure_ascii=False))
        # R0: does the 3.6 lens read 3.8's states? top-1 agreement with 3.8's own next-token prediction, per layer
        top38 = np.load(d / "pred_topk_ids.npy")[:, 0]
        pred_idx = np.load(d / "pred_idx.npy")
        row = {int(p): i for i, p in enumerate(pred_idx)}
        sel = [i for i, p in enumerate(subj) if int(p) in row]
        m38 = top38[[row[int(subj[i])] for i in sel]]
        agree = {L: round(float((ids["plain"][sel, li, 0] == m38).mean()), 3) for li, L in enumerate(meta["layers"])}
        print(f"{t}: {len(np.unique(turn))} replies; J-lens top-1 = Qwen3.8's own top-1: {agree}")
        view["readers"]["jlens"] = {"label": "J-lens (Qwen3.6-27B's, cos)", "layers": meta["layers"], "lazy": "jlens_turns.jsonl",
                                    "r0_top1_agree": agree, "at": {}}
        (d / "view.json").write_text(json.dumps(view, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
