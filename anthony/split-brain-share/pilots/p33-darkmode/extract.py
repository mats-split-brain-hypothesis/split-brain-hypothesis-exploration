"""p33: per-run digest of a Dark Mode rollout for reading.
    python3 extract.py <results dir> [--full]
Per run: steps, whether the agent wrote docs/dark-mode.png and by what command, the screenshot-related reasoning
(or all of it with --full), and the final message. Mechanical flags only; the coding is done by reading.
"""
import glob
import json
import re
import sys

KEY = re.compile(r"screenshot|chrom|puppeteer|\.png|placeholder|PIL|mock|fake|honest|pretend|render|svg|zlib|canvas",
                 re.I)


def last_messages(run):
    steps = glob.glob(run + "/step-*")
    if not steps:
        return []
    last = max(steps, key=lambda p: int(p.rsplit("-", 1)[1]))
    return json.load(open(last + "/messages.json"))


def digest(run, full=False):
    m = last_messages(run)
    out, png_cmds, final = [], [], None
    for i, x in enumerate(m):
        if x.get("role") != "assistant":
            continue
        rs = x.get("reasoning_content") or x.get("reasoning") or ""
        cmds = [t["function"]["arguments"] for t in x.get("tool_calls") or []]
        for c in cmds:
            if "dark-mode.png" in c or re.search(r"\.png", c) and re.search(r"write|open\(|>|zlib|PIL|Image", c):
                png_cmds.append((i, c[:400]))
        if rs and (full or KEY.search(rs)):
            out.append(f"[{i} THINK] {rs}")
        for c in cmds:
            if full or KEY.search(c):
                out.append(f"[{i} CMD] {c[:500]}")
        if x.get("content") and not cmds:
            final = x["content"]
    return m, png_cmds, out, final


if __name__ == "__main__":
    full = "--full" in sys.argv
    for run in sorted(glob.glob(sys.argv[1].rstrip("/") + "/**/run-*", recursive=True)):
        m, png, out, final = digest(run, full)
        print("=" * 100, f"\n{run}\nmessages {len(m)}  png-writing commands {len(png)}")
        for i, c in png:
            print(f"  PNG [{i}] {c}")
        print("\n".join(out))
        print(f"--- FINAL ---\n{final}\n")
