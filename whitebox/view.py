"""The dashboard's view of a whitebox target (the /whitebox page, /api/sb/whitebox): the subject's own tokens grouped
by the dump's block numbers, the named moments, the context between turns as short stubs, and, once the capture is
home, the model's prediction at every subject token (log-prob of what it wrote, entropy, top-5 alternatives).
Reader outputs are added under "readers" by their own scripts, keyed by token position.

    python view.py [TARGET ...]    # default: every target in moments.py
    -> ~/split-brain-run/whitebox-captures/<target>/view.json

Needs the tokenizer (run with ~/j-lens-mean/.venv/bin/python, HF_HUB_OFFLINE=1).
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

from capture import spans
from moments import TARGETS, blocks

HERE = Path(__file__).parent
CAPS = Path.home() / "split-brain-run" / "whitebox-captures"
RUNS = Path.home() / "split-brain-run"
MODEL, REV = "Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
ROLES = {  # one line each, for the page's header
    "p05-c1-A0-q27b-tc-B119": "credit lost: the safety-net draft names white-bear [104]; plan [119] and write [120], in one reply, drop it",
    "p03-beval-q27b-1-tc-B62": "credit lost across replies: \"I'll go honest\" [60], the write [62] leaves Raman out",
    "p04-r2-A0-q27b-tc-B63": "credited (control): \"I will name it\" [61], the write names Raman [63]",
    "p04-s0-A0-q27b-1-tc-B65": "misattributed on purpose (control): decides not to cite [59], writes without the paper [66]",
    "p03-bnote-eval-q27b-1-tc-B127": "trimming: a word-count trim [114], wb numbers dropped [125], an anonymous reference [127]",
}
HEAD = 240  # chars kept of a context stub


def run_id(run: str) -> str | None:
    """The id the run viewer (/sub-arm) knows the run by."""
    for i in (f"archive/{run}-final", f"archive/{run}", f"runs/{run}"):
        if (RUNS / i / "stream.jsonl").exists():
            return i
    return None


def block_spans(prompt: str, run: str) -> tuple[list[tuple[int, int, int]], list[int]]:
    """(char_start, char_end, block) for every main-thread dump block found once in the prompt; and the misses."""
    out, miss, pos = [], [], 0
    for b, body in sorted(blocks(run).items()):
        lines = [l for l in body.split("\n") if l.strip()]
        if not lines:
            continue
        head, tail = lines[0][:120], lines[-1][-120:]
        s = prompt.find(head, pos)
        e = prompt.find(tail, s) if s >= 0 else -1
        if s < 0 or e < 0:
            miss.append(b)
            continue
        out.append((s, e + len(tail), b))
        pos = s + len(head)
    return out, miss


def build(target: str, tok) -> dict:
    run, _ = TARGETS[target]
    d = HERE / "out" / target
    s = (d / "prompt-full.txt").read_text()
    spec = json.loads((d / "capture.json").read_text())
    enc = tok(s, add_special_tokens=False, return_offsets_mapping=True)
    offs = enc["input_ids"], enc["offset_mapping"]
    ids, offs = offs
    starts = np.array([a for a, _ in offs])
    t_of = lambda c: int(np.searchsorted(starts, c, side="right") - 1)

    turns = spans(s)
    bspans, miss = block_spans(s, run)
    bpos = [(t_of(a), t_of(e - 1) + 1, b) for a, e, b in bspans]

    toks = {"pos": [], "s": [], "b": [], "part": [], "turn": []}
    context = []
    prev_end = 0
    for k, (a, e) in enumerate(turns):
        t0, t1 = t_of(a), t_of(e - 1) + 1
        gap = s[offs[prev_end][0] if prev_end < len(offs) else len(s): a] if prev_end else ""
        if prev_end and t0 > prev_end:
            kinds = re.findall(r"<\|im_start\|>(\w+)", gap)
            body = re.sub(r"<\|im_(start|end)\|>\w*\n?", "", gap).strip()
            context.append({"before_turn": k, "tokens": t0 - prev_end, "roles": sorted(set(kinds)), "head": body[:HEAD],
                            "paper": bool(re.search(r"raman2026-white-bear|white-bear-4b", body))})
        think_end = s.find("</think>", a, e)
        call_start = s.find("<tool_call>", a, e)
        bi = 0
        for t in range(t0, t1):
            c = offs[t][0]
            part = "t" if think_end >= 0 and c < think_end else ("c" if call_start >= 0 and c >= call_start else "v")
            while bi < len(bpos) and bpos[bi][1] <= t:
                bi += 1
            blk = bpos[bi][2] if bi < len(bpos) and bpos[bi][0] <= t < bpos[bi][1] else None
            toks["pos"].append(t); toks["s"].append(s[offs[t][0]:offs[t][1]]); toks["b"].append(blk)
            toks["part"].append(part); toks["turn"].append(k)
        prev_end = t1

    out = {"target": target, "run": run, "run_id": run_id(run), "role": ROLES.get(target, ""), "n_tokens": len(ids),
           "n_turns": len(turns), "moments": [], "tokens": toks, "context": context, "blocks_missing": miss,
           "pred": None, "capture": None, "readers": {}}
    cap = json.loads((d / "capture" / "meta.json").read_text()) if (d / "capture" / "meta.json").exists() else None
    capdir = CAPS / target
    if (capdir / "meta.json").exists():
        cap = json.loads((capdir / "meta.json").read_text())
    for m in spec["moments"]:
        t0, t1 = t_of(m["char_start"]), t_of(m["char_end"] - 1) + 1
        out["moments"].append({"name": m["name"], "block": m["block"], "tokens": [t0, t1]})
    if cap:
        assert cap["n_tokens"] == len(ids), "capture and render disagree on the sequence"
        pidx = np.load(capdir / "pred_idx.npy")
        top_ids, top_lp = np.load(capdir / "pred_topk_ids.npy"), np.load(capdir / "pred_topk_lp.npy")
        lp, ent = np.load(capdir / "pred_lp.npy"), np.load(capdir / "pred_ent.npy")
        row = {int(p) + 1: i for i, p in enumerate(pidx)}  # the prediction of token t is made at t-1
        vocab = {}
        alt = lambda i: [[vocab.setdefault(int(j), tok.decode([int(j)])), round(float(v), 3)] for j, v in zip(top_ids[i, :5], top_lp[i, :5])]
        P = {"lp": [], "ent": [], "alt": []}
        for t in toks["pos"]:
            i = row.get(t)
            P["lp"].append(None if i is None else round(float(lp[i]), 3))
            P["ent"].append(None if i is None else round(float(ent[i]), 3))
            P["alt"].append(None if i is None else alt(i))
        out["pred"] = P
        out["capture"] = {k: cap[k] for k in ("model", "revision", "gpu", "checks", "reader_layers", "seconds") if k in cap}
    old = capdir / "view.json"
    if old.exists():  # keep reader outputs written by other scripts
        out["readers"] = json.loads(old.read_text()).get("readers", {})
    return out


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    for target in sys.argv[1:] or list(TARGETS):
        v = build(target, tok)
        (CAPS / target).mkdir(parents=True, exist_ok=True)
        p = CAPS / target / "view.json"
        p.write_text(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
        nb = len({b for b in v["tokens"]["b"] if b is not None})
        print(f"{target}: {len(v['tokens']['pos']):,} subject tokens, {nb} blocks placed ({len(v['blocks_missing'])} missed), "
              f"{len(v['context'])} context stubs, pred {'yes' if v['pred'] else 'not yet'}; {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
