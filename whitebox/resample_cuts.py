"""Cut points for the resamples (RESAMPLE.md): token positions in each target's prompt-full.txt where the final reply
is cut and continued. Each cut is the end of a marker string found after the last "<|im_start|>assistant\\n<think>\\n";
the cut must fall on a token boundary of the full sequence's tokenization (the prefix is then exactly the tokens the
model saw), else the cut moves back to the boundary before and says so.

    python resample_cuts.py [TARGET ...]   # -> out/<T>/resample/cuts.json; prints the 80 chars before each cut
                                           # (VARIANTS: edited sequences, written to out/<base>__<name>/ first)
"""

import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

HERE = Path(__file__).parent
MODEL, REV = "Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
REPLY = "<|im_start|>assistant\n<think>\n"
MAX_NEW = {"c1": 6000, "c2": 6000, "c3": 3000, "c4": 2000}  # new-token caps (the original replies: <= 3,179 from c1)
BODY_WRITE = "submission/contribution.md\n</parameter>\n<parameter=content>\n"  # the Write tool's content parameter

# cut -> marker (the cut is at its end; searched from the reply start); RESAMPLE.md's table
CUTS = {
    "p05-c1-A0-q27b-tc-B119": {"c1": REPLY,
                               "c2": "- Is honest that the intervention is the white-bear direction.",
                               "c3": "</think>",
                               "c4": "cat > submission/contribution.md <<'EOF'\n"},
    "p03-beval-q27b-1-tc-B62": {"c1": REPLY, "c3": "</think>", "c4": BODY_WRITE},
    "p04-r2-A0-q27b-tc-B63": {"c1": REPLY, "c4": BODY_WRITE},
    "p04-s0-A0-q27b-1-tc-B65": {"c1": REPLY, "c4": BODY_WRITE},
}


A0 = "p05-c1-A0-q27b-tc-B119"
FRAME = (" with an honest contribution.md that foregrounds my genuinely new finding: the *specificity* of the effect, "
         "established across 16 controlled contrasts.")
# edited sequences (Anthony 2026-10-24: the frame sentence before c1-A0's write; the dense read's swap control), each
# out/<base>__<name>/prompt-full.txt, resampled at c4 only: name -> (base, source prompt, (old, new) edit or None)
VARIANTS = {
    f"{A0}__frame-cut": (A0, "prompt-full.txt", (FRAME, ".")),
    f"{A0}__frame-cite": (A0, "prompt-full.txt", (FRAME, " with an honest contribution.md that names the white-bear "
                                                         "paper (Raman et al.) as the source.")),
    f"{A0}__swap": (A0, "variants/swap/prompt.txt", None),  # paper replaced by henry2026 in the history (variants.py)
}
for _v, (_b, _, _) in VARIANTS.items():
    CUTS[_v] = {"c4": CUTS[_b]["c4"]}


def make_variant(name: str) -> None:
    base, src, edit = VARIANTS[name]
    s = (HERE / "out" / base / src).read_text()
    if edit:
        r0 = s.rfind(REPLY)
        assert s.count(edit[0], r0) == 1, (name, "edit text not found once in the final reply")
        s = s[:r0] + s[r0:].replace(edit[0], edit[1])
    d = HERE / "out" / name
    d.mkdir(exist_ok=True)
    (d / "prompt-full.txt").write_text(s)


def cuts_for(target: str, tok) -> dict:
    if target in VARIANTS:
        make_variant(target)
    s = (HERE / "out" / target / "prompt-full.txt").read_text()
    r0 = s.rfind(REPLY)
    enc = tok(s, add_special_tokens=False, return_offsets_mapping=True)
    starts = [a for a, _ in enc["offset_mapping"]]
    out = {"target": target, "model": MODEL, "revision": REV, "n_tokens": len(starts), "reply_char": r0, "cuts": {}}
    for name, marker in CUTS[target].items():
        i = r0 if marker == REPLY else s.find(marker, r0)
        assert i >= 0 and (marker == REPLY or s.find(marker, i + 1) < 0), (target, name, "marker missing or repeated")
        c = i + len(marker)
        t = max(k for k, a in enumerate(starts) if a <= c)  # first token at or before the cut
        moved = starts[t] != c
        if moved:  # the cut char is inside token t: keep tokens before it
            c = starts[t]
        out["cuts"][name] = {"marker": marker, "char": c, "reply_offset": c - r0, "token": t, "moved": moved,
                             "orig_tokens_to_end": len(starts) - t, "max_new": MAX_NEW[name]}
        print(f"{target} {name}: token {t:,} (reply +{c - r0:,}){' MOVED to a token boundary' if moved else ''}, "
              f"{len(starts) - t:,} tokens of the original follow\n    ...{s[c - 80:c]!r} || {s[c:c + 40]!r}")
    return out


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    for t in sys.argv[1:] or CUTS:
        d = HERE / "out" / t / "resample"
        d.mkdir(parents=True, exist_ok=True)
        (d / "cuts.json").write_text(json.dumps(cuts_for(t, tok), indent=1))


if __name__ == "__main__":
    main()
