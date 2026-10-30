"""Does a run use the evaluation items (association fit) in its own work? A process check, beside leak_check.py (which
tests the submitted vectors).

    python3 item_use_scan.py p03- p04-        # one line per run; --calls lists the flagged tool calls

From the run's tool calls (full text): how often it opens the fit / val files (allowed: the repo contains them), how
many calls hold >= 10 fit target words, and how many hold copied fit-prompt text (6-word runs shared with an item's
prompt). A flagged call is a candidate for reading, not a verdict: copied text can be an analysis printout as well as
prompts for a vector. Which vectors were submitted, and what built them, is the reader's (or leak_check.py's) call.
"""

import json
import re
import sys
from pathlib import Path

import code_runs as cr

FIT = Path.home() / "split-brain/j-lens-mean-snapshot-rig4b-eval/data/dev/association/fit.json"
SB = Path.home() / "split-brain-run"


def shingles(s: str, n: int = 6) -> set[str]:
    w = re.findall(r"[a-z']+", s.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show = "--calls" in sys.argv
    fit = json.loads(FIT.read_text())["items"]
    targets = {t.lower() for it in fit for t in it.get("intermediates", [])}
    fit_sh = {s: it["name"] for it in fit for s in shingles(it["prompt"])}
    names = sorted({p.name.replace("-final", "") for r in (SB / "archive", SB / "runs") for p in r.iterdir()
                    if (p / "stream.jsonl").exists() and not re.search(r"-at-\d+$", p.name)
                    and any(p.name.startswith(a) for a in args)})
    print(f"{'run':30} {'opens fit':>9} {'calls>=10 targets':>18} {'calls with copied items':>24}")
    for n in names:
        its, _ = cr.items(n)
        tools = [i for i in its if i["kind"].startswith("tool")]
        rows = []
        for i in tools:
            tw = {w for w in targets if re.search(rf"\b{re.escape(w)}\b", i["text"], re.I)}
            cp = {fit_sh[s] for s in shingles(i["text"]) if s in fit_sh}
            rows.append((i, bool(re.search(r"association/(fit|val)", i["text"])), tw, cp))
        flagged = [r for r in rows if len(r[2]) >= 10 or len(r[3]) >= 3]
        print(f"{n:30} {sum(r[1] for r in rows):>9} {sum(len(r[2]) >= 10 for r in rows):>18} {sum(len(r[3]) >= 3 for r in rows):>24}")
        if show:
            for i, _, tw, cp in flagged:
                print(f"    {i['id']} after B{i['block']}: {len(tw)} target words, {len(cp)} items copied: {' '.join(i['text'][:160].split())}")


if __name__ == "__main__":
    main()
