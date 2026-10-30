"""Render a saved prompt/output example (JSON with "prompt" and "output") to a PNG, text verbatim, only wrapped.

  python src/render_example.py logs/sorh_examples/qwen2.4t_row788.json out.png "School of Reward Hacks, row 788"
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

W, MARGIN, GAP = 1400, 48, 22
BODY = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 26)
LABEL = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 22, index=1)  # bold
TITLE = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 30, index=1)


def wrap(text, font, width):
    """Wrap on spaces only; every character of the input is kept, line breaks preserved."""
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else cur + " " + word
            if font.getlength(trial) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def main(src, dst, title):
    d = json.load(open(src))
    sub = f"{d['model']} via OpenRouter ({d.get('provider')}, FP8), reasoning effort {d['reasoning_effort']}, no system prompt"
    blocks = [("PROMPT (user message, verbatim)", d["prompt"], "#eef2f7"),
              ("OUTPUT (final response, verbatim)", d["output"], "#eef7ef")]
    inner = W - 2 * MARGIN - 40
    lh = BODY.size + 12
    height = MARGIN + 44 + 34 + GAP
    wrapped = [(lab, wrap(txt, BODY, inner), bg) for lab, txt, bg in blocks]
    for _, ls, _ in wrapped:
        height += 34 + len(ls) * lh + 40 + GAP
    img = Image.new("RGB", (W, height + MARGIN - GAP), "white")
    g = ImageDraw.Draw(img)
    y = MARGIN
    g.text((MARGIN, y), title, font=TITLE, fill="#111")
    y += 44
    g.text((MARGIN, y), sub, font=LABEL, fill="#555")
    y += 34 + GAP
    for lab, ls, bg in wrapped:
        g.text((MARGIN, y), lab, font=LABEL, fill="#333")
        y += 34
        box_h = len(ls) * lh + 40
        g.rounded_rectangle([MARGIN, y, W - MARGIN, y + box_h], radius=12, fill=bg)
        ty = y + 20
        for line in ls:
            g.text((MARGIN + 20, ty), line, font=BODY, fill="#111")
            ty += lh
        y += box_h + GAP
    img.save(dst)
    # Check nothing was lost or changed in wrapping.
    for (_, txt, _), (_, ls, _) in zip(blocks, wrapped):
        assert " ".join(" ".join(ls).split()) == " ".join(txt.split()), "wrapping changed the text"
    print(f"saved {dst} ({W}x{img.height})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
