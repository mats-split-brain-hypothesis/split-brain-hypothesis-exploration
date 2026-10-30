"""Named readout positions in a teacher-forced sequence (render.py --with-response): for each anchor phrase in the
subject's reply, the token index of its last token (the state that has read the phrase and predicts what follows).

    python positions.py out/RUN/prompt-nothink-full.txt ANCHORS.json

ANCHORS.json: {"name": "phrase", ...}; each phrase must occur exactly once in the reply. Writes positions.json next to
the prompt: name -> {token, char, text (the last few tokens), next (the token the subject wrote next)}.
"""

import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "Qwen/Qwen3.8-27B"
REPLY = "<|im_start|>assistant\n<think>\n"


def main() -> None:
    path, anchors = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
    s = path.read_text()
    start = s.rindex(REPLY) + len(REPLY)
    tok = AutoTokenizer.from_pretrained(MODEL)
    enc = tok(s, add_special_tokens=False, return_offsets_mapping=True)
    ids, offs = enc["input_ids"], enc["offset_mapping"]
    out = {"n_tokens": len(ids), "reply_start": next(i for i, (a, _) in enumerate(offs) if a >= start)}
    for name, phrase in anchors.items():
        hits = [i for i in range(start, len(s)) if s.startswith(phrase, i)]
        assert len(hits) == 1, (name, len(hits))
        end = hits[0] + len(phrase)
        t = max(i for i, (a, _) in enumerate(offs) if a < end)
        out[name] = {"token": t, "char": end, "text": tok.decode(ids[max(0, t - 6): t + 1]),
                     "next": tok.decode(ids[t + 1: t + 2])}
        print(f"{name:16} tok {t:>7}  ...{out[name]['text']!r} -> {out[name]['next']!r}")
    (path.parent / "positions.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
