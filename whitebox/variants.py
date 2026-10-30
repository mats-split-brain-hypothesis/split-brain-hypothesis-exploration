"""The dense read's two controls, each the final write teacher-forced with the same tokens:
- swap:  the full history, with every tool result that shows the paper (or bnote's planted note) replaced by another
         paper of the same reading list (henry2026-concept-allocation-zone.md), numbered as Claude Code's Read shows it,
         cut to the replaced result's length;
         the model's own later reasoning (which still says WBS / white-bear) is left as it was.
- strip: the task brief alone (the first user message), then the final write reply without its thinking: the same
         write text, headings included ("Where it came from."), with no history behind it.

    python variants.py   -> out/<T>/variants/{swap,strip}/prompt.txt (render.py's template), positions.json (the write's
                            tokens in the variant, in the same order as the original's: "orig" gives the original position)
"""

import json
import re
from pathlib import Path

from transformers import AutoTokenizer

from render import MODEL, convert, response_text

HERE = Path(__file__).parent
REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
PAPERS = HERE.parent / "papers"
SOURCE = re.compile(r"raman2026-white-bear|white-bear-4b")
SWAP_WITH = "henry2026-concept-allocation-zone.md"
# target -> the rebuilt request whose response is the final write
BASE = {"p04-r2-A0-q27b-tc-B63": "p04-r2-A0-q27b-tc-B63", "p03-beval-q27b-1-tc-B62": "p03-beval-q27b-1-tc-B62",
        "p05-c1-A0-q27b-tc-B119": "p05-c1-A0-q27b-tc-B119", "p04-s0-A0-q27b-1-tc-B65": "p04-s0-A0-q27b-1-tc-B65",
        "p03-bnote-eval-q27b-1-tc-B127": "p03-bnote-eval-q27b-1-tc-B114"}


def numbered(text: str) -> str:
    return "\n".join(f"{i + 1}\t{l}" for i, l in enumerate(text.split("\n")))


def swap(req: dict) -> tuple[dict, int]:
    """Replace the tool results of calls that read the source (by file path) or whose output quotes its file name."""
    reads = {c["id"] for m in req["messages"] if m["role"] == "assistant" for c in m["content"]
             if c.get("type") == "tool_use" and SOURCE.search(json.dumps(c["input"]))}
    other = numbered((PAPERS / SWAP_WITH).read_text())
    n = 0
    for m in req["messages"]:
        if m["role"] != "user":
            continue
        for c in m["content"]:
            if c.get("type") == "tool_result" and c.get("tool_use_id") in reads:
                was = c["content"] if isinstance(c["content"], str) else "\n".join(b.get("text", "") for b in c["content"])
                c["content"] = other[: len(was)]  # the same length as what it replaces (reads are often partial)
                n += 1
    return req, n


def render(tok, req: dict, resp: dict) -> str:
    msgs, tools = convert(req, drop_thinking=False)
    s = tok.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=True, reasoning_effort="xhigh")
    return s + response_text(resp)


def write_ids(tok, prompt: str, resp: dict) -> tuple[list[int], int]:
    """The token ids of the response's tool call(s) and where they start in the rendered sequence."""
    ids = tok(prompt, add_special_tokens=False, return_offsets_mapping=True)
    start_char = prompt.rindex("<|im_start|>assistant\n<think>\n")
    call_char = prompt.index("<tool_call>", start_char)
    end_char = prompt.index("<|im_end|>", call_char)
    tix = [i for i, (a, b) in enumerate(ids["offset_mapping"]) if call_char <= a < end_char]
    return [ids["input_ids"][i] for i in tix], tix[0]


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    for t, base in BASE.items():
        d = HERE / "out" / base
        req, resp = json.loads((d / "request.json").read_text()), json.loads((d / "response.json").read_text())
        orig_prompt = (HERE / "out" / base / "prompt-full.txt").read_text() if (d / "prompt-full.txt").exists() else render(tok, req, resp)
        o_ids, o_start = write_ids(tok, orig_prompt, resp)
        # the original positions of these write tokens: in the target's own sequence (the base may be a shorter prefix)
        tgt = (HERE / "out" / t / "prompt-full.txt").read_text()
        t_ids = tok(tgt, add_special_tokens=False)["input_ids"]
        if base == t:
            orig_pos = list(range(o_start, o_start + len(o_ids)))
        else:  # bnote: the turn-65 request is a prefix of the B127 sequence
            k = next(i for i in range(len(t_ids) - len(o_ids)) if t_ids[i:i + len(o_ids)] == o_ids)
            orig_pos = list(range(k, k + len(o_ids)))
        for name in ("swap", "strip"):
            r = json.loads(json.dumps(req))
            rp = json.loads(json.dumps(resp))
            note = ""
            if name == "swap":
                r, n = swap(r)
                note = f"{n} tool results replaced"
            else:
                r["messages"] = r["messages"][:1]
                rp["content"] = [c for c in rp["content"] if c["type"] != "thinking"]
            p = render(tok, r, rp)
            v_ids, v_start = write_ids(tok, p, rp)
            assert v_ids == o_ids, f"{t} {name}: the write tokenizes differently"
            out = HERE / "out" / t / "variants" / name
            out.mkdir(parents=True, exist_ok=True)
            (out / "prompt.txt").write_text(p)
            (out / "positions.json").write_text(json.dumps(
                [{"pos": v_start + j, "orig": orig_pos[j], "tag": f"{name}:write", "k": 1} for j in range(len(v_ids))]))
            n_tok = len(tok(p, add_special_tokens=False)["input_ids"])
            print(f"{t[:26]:26} {name:5}: {n_tok:,} tokens, {len(v_ids)} write tokens {note}")


if __name__ == "__main__":
    main()
