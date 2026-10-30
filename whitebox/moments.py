"""The capture spec of a whitebox run: its teacher-forced sequence (render.py --with-response) and the named moments
(dump blocks) whose surroundings get every layer. Moments are located by their text in the prompt, so the pod's
capture.py maps them to tokens with its own tokenizer.

    python3 moments.py            # writes out/<target>/capture.json for every target below, prints the spans

capture.json: {"run", "prompt": "prompt-full.txt", "moments": [{"name", "block", "char_start", "char_end"}]};
the last reply is always a moment of its own ("reply").
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
DUMPS = Path.home() / "split-brain-run" / "dumps"

# target dir (rebuild.py --out) -> run, named blocks (from pilots/tc-reading/codes.tsv credit_track, read 2026-10-23)
TARGETS = {
    "p05-c1-A0-q27b-tc-B119": ("p05-c1-A0-q27b-tc", {
        "first-source": 20, "novelty-framing": 41, "wbs-internal-control": 64, "safety-net-names": 104,
        "plan-honest": 119, "write": 120}),
    "p03-beval-q27b-1-tc-B62": ("p03-beval-q27b-1-tc", {
        "first-source": 26, "plan-lineage": 58, "plan-go-honest": 60, "write": 62}),
    "p04-r2-A0-q27b-tc-B63": ("p04-r2-A0-q27b-tc", {
        "first-source": 11, "differentiate": 12, "honest-intent": 51, "lean-acknowledge": 57, "will-name": 61,
        "write": 63}),
    "p04-s0-A0-q27b-1-tc-B65": ("p04-s0-A0-q27b-1-tc", {
        "first-source": 5, "decides-not-cite": 59, "anon-comparison": 62, "geometry": 65, "write": 66}),
    "p03-bnote-eval-q27b-1-tc-B127": ("p03-bnote-eval-q27b-1-tc", {
        "note-read": 2, "must-not-reproduce": 3, "judge-may-not-know": 16, "draft-not-stance": 87,
        "trim-write": 114, "drop-wb-numbers": 125, "anon-reference": 127}),
}
REPLY = "<|im_start|>assistant\n<think>\n"


def blocks(run: str) -> dict[int, str]:
    """Main-thread blocks of the dump (subagent blocks are not in the subject's sequence), without the dump's
    tool-call lines ("  -> Tool: ...")."""
    txt = (DUMPS / f"{run}.txt").read_text()
    out = {}
    for m in re.finditer(r"\n\[(\d+)\] ([^\n]*)\n(.*?)(?=\n\[\d+\] |\Z)", txt, re.S):
        if "subagent" not in m[2]:
            out[int(m[1])] = "\n".join(l for l in m[3].split("\n") if not l.startswith("  -> ")).strip()
    return out


def locate(prompt: str, body: str) -> tuple[int, int]:
    """The block's span in the prompt: its first line must occur exactly once; the end is where its last line ends
    (dump_reasoning.py keeps the block's lines, so both ends are found verbatim)."""
    lines = [l for l in body.split("\n") if l.strip()]
    head, tail = lines[0][:120], lines[-1][-120:]
    hits = [m.start() for m in re.finditer(re.escape(head), prompt)]
    assert len(hits) == 1, (head[:60], len(hits))
    end = prompt.find(tail, hits[0])
    assert end >= 0, tail[:60]
    return hits[0], end + len(tail)


def main() -> None:
    for target, (run, named) in TARGETS.items():
        d = HERE / "out" / target
        prompt = (d / "prompt-full.txt").read_text()
        B = blocks(run)
        moments = []
        for name, b in named.items():
            s, e = locate(prompt, B[b])
            moments.append({"name": name, "block": b, "char_start": s, "char_end": e})
        moments.append({"name": "reply", "block": None, "char_start": prompt.rindex(REPLY), "char_end": len(prompt)})
        (d / "capture.json").write_text(json.dumps({"run": run, "prompt": "prompt-full.txt", "moments": moments}, indent=1))
        print(target, " ".join(f"{m['name']}:{m['char_end'] - m['char_start']}" for m in moments))


if __name__ == "__main__":
    main()
