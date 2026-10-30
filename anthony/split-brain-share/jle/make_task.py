"""Port an anchor task commit (TASK.md, eval/*) to the jlens-edits scenario by an explicit substitution list.

Reads the files from a built anchor snapshot's task commit (default: j-lens-mean-snapshot-rig4b-eval at HEAD) and
writes them under --out with every substitution in SUBS applied. Each substitution must fire wherever its file has
it; afterwards no steering vocabulary (LEFTOVER) may remain. The list below IS the difference between the two
scenarios' task text: report it, never edit a ported file by hand.

    python3 jle/make_task.py --anchor j-lens-mean-snapshot-rig4b-eval --out jle/work/task-A0
"""

import argparse
import re
import subprocess
from pathlib import Path

FILES = ("TASK.md", "eval/submit.py", "eval/task.json", "eval/test_submission.py")

# (old, new): plain text, applied in order to every file that contains old.
SUBS = [
    # task id and title
    ("jlens-steer-assoc-017", "jlens-edit-assoc-017"),
    ("a generic steering intervention for the plain J-lens", "a generic spectral edit of the J-lens"),
    # objective
    ("Make the plain J-lens read association's targets better by changing the forward pass. Add a vector to "
     "Qwen3.5-4B's\nresidual stream at some layers during the forward pass; the metric server then reads with the "
     "plain (uncentred)\nJ-lens at layers 26, 28 and 30 and scores strict pass@10 on association's `fit` split "
     "(102 items; baseline 0.1275).\nThe server does all of that: `tools/metric.py` (`info`, `run`, `capture`; see "
     "CLAUDE.md).",
     "Make the J-lens read association's targets better by editing the lens. Rescale the singular values of "
     "Qwen3.5-4B's\nJ-lens transports `J_l` at the read layers 26, 28 and 30; the metric server then reads the "
     "(uncentred) residual stream\nwith the edited lens at those layers and scores strict pass@10 on association's "
     "`fit` split (102 items; baseline\n0.1275). The server does all of that: `tools/metric.py` (`info`, `run`, "
     "`spectrum`, `capture`; see CLAUDE.md)."),
    # rules
    ("- The readout stays the plain J-lens. Only the forward pass changes.\n"
     "- Steering vectors only: one vector per layer, added at the positions you choose (`prefix`, `read` or "
     "`context`).\n"
     "- Directions, not means: each vector has to come from a contrast between two conditions (prompts or items you\n"
     "  choose). Subtracting a mean, a prior or any other centring term is out of scope, at any layer or position.",
     "- The forward pass stays as it is. Only the lens changes.\n"
     "- Spectral edits only: one multiplier per singular value of `J_l`, at the read layers you choose; the\n"
     "  singular vectors stay as they are.\n"
     "- The lens, not the states: the edit acts on `J_l` alone. Subtracting a mean, a prior or any other centring "
     "term\n  is out of scope, at any layer or position."),
    ("- Generic: one intervention for every item, built without the targets.",
     "- Generic: one edit for every item, built without the targets."),
    ("target words or the items' answers. Contrasts over prompts you write yourself are fine, as are captures of "
     "other\n  families' items through `capture`.",
     "target words or the items' answers. Captures of prompts you write yourself are fine, as are captures of other\n"
     "  families' items through `capture`."),
    ("no pods, no HF dataset, no `board.py`.", "no pods, no archive stores, no `lensboard/`."),
    # submission
    ("1. Save the intervention as `submission/vectors.pt`: a dict `{layer: tensor[2560]}`, as for `tools/metric.py "
     "run`.",
     "1. Save the edit as `submission/multipliers.pt`: a dict `{layer: tensor[2560]}`, as for `tools/metric.py "
     "run`."),
    ("       .venv/bin/python eval/submit.py submission/vectors.pt --positions prefix --scale 1.0 \\\n"
     "           --method \"<short name>\" --contribution submission/contribution.md",
     "       .venv/bin/python eval/submit.py submission/multipliers.pt \\\n"
     "           --method \"<short name>\" --contribution submission/contribution.md"),
    ("   It scores the intervention on `fit`", "   It scores the edit on `fit`"),
    ("re-runs the submitted intervention on `fit`", "re-scores the submitted edit on `fit`"),
    # task.json
    ('"metric": "association/fit strict pass@10, plain J-lens at L26/28/30 (metric server)"',
     '"metric": "association/fit strict pass@10, edited J-lens at L26/28/30 (metric server)"'),
    ('"submission": ["submission/vectors.pt",', '"submission": ["submission/multipliers.pt",'),
    # eval/submit.py
    ("    .venv/bin/python eval/submit.py submission/vectors.pt --positions prefix --scale 1.0 \\\n"
     "        --method \"<short name>\" --contribution submission/contribution.md\n\n"
     "Validates the intervention,",
     "    .venv/bin/python eval/submit.py submission/multipliers.pt \\\n"
     "        --method \"<short name>\" --contribution submission/contribution.md\n\n"
     "Validates the edit,"),
    ('OUT = ROOT / "submission" / "submission.json"\nPOSITIONS = ("prefix", "read", "context")\n',
     'OUT = ROOT / "submission" / "submission.json"\n'),
    ("def load_vectors(path: Path, d_model: int, n_layers: int) -> dict[int, torch.Tensor]:\n"
     "    raw = torch.load(path, weights_only=False)\n"
     "    if not isinstance(raw, dict) or not raw:\n"
     "        raise SystemExit(\"vectors file must be a non-empty dict {layer: tensor}\")\n"
     "    vecs = {}\n"
     "    for L, v in raw.items():\n"
     "        L = int(L)\n"
     "        if not 0 <= L < n_layers - 1:\n"
     "            raise SystemExit(f\"layer {L} outside 0..{n_layers - 2}\")\n"
     "        v = torch.as_tensor(v).float().reshape(-1)\n"
     "        if v.numel() != d_model:\n"
     "            raise SystemExit(f\"layer {L}: vector has {v.numel()} entries, expected {d_model}\")\n"
     "        vecs[L] = v\n"
     "    return vecs\n",
     "def load_multipliers(path: Path, d_model: int, read_layers: list[int]) -> dict[int, torch.Tensor]:\n"
     "    raw = torch.load(path, weights_only=False)\n"
     "    if not isinstance(raw, dict) or not raw:\n"
     "        raise SystemExit(\"multipliers file must be a non-empty dict {layer: tensor}\")\n"
     "    mult = {}\n"
     "    for L, m in raw.items():\n"
     "        L = int(L)\n"
     "        if L not in read_layers:\n"
     "            raise SystemExit(f\"layer {L} is not a read layer {read_layers}\")\n"
     "        m = torch.as_tensor(m).float().reshape(-1)\n"
     "        if m.numel() != d_model:\n"
     "            raise SystemExit(f\"layer {L}: multipliers have {m.numel()} entries, expected {d_model}\")\n"
     "        mult[L] = m\n"
     "    return mult\n"),
    ('    ap.add_argument("vectors")\n'
     '    ap.add_argument("--positions", default="prefix", choices=POSITIONS)\n'
     '    ap.add_argument("--scale", type=float, default=1.0)\n',
     '    ap.add_argument("multipliers")\n'),
    ('    vecs = load_vectors(Path(a.vectors), info["d_model"], info["n_layers"])\n',
     '    mult = load_multipliers(Path(a.multipliers), info["d_model"], info["read_layers"])\n'),
    ("    r = metric.run_metric(vecs, a.positions, a.scale)\n", "    r = metric.run_metric(mult)\n"),
    ('           "vectors": str(Path(a.vectors)), "vectors_sha256": hashlib.sha256(Path(a.vectors).read_bytes()).'
     'hexdigest(),\n'
     '           "layers": sorted(vecs), "positions": a.positions, "scale": a.scale, "method": a.method,\n',
     '           "multipliers": str(Path(a.multipliers)),\n'
     '           "multipliers_sha256": hashlib.sha256(Path(a.multipliers).read_bytes()).hexdigest(),\n'
     '           "layers": sorted(mult), "method": a.method,\n'),
    # eval/test_submission.py
    ('    vecs = {int(L): v for L, v in torch.load(ROOT / sub["vectors"], weights_only=False).items()}\n'
     '    return metric.run_metric(vecs, sub["positions"], sub["scale"])\n',
     '    mult = {int(L): m for L, m in torch.load(ROOT / sub["multipliers"], weights_only=False).items()}\n'
     '    return metric.run_metric(mult)\n'),
    ('    for k in ("task_id", "vectors", "positions", "scale", "method", "contribution", "fit_pass_at_10"):\n'
     '        assert k in sub, f"missing {k}"\n'
     '    assert sub["positions"] in ("prefix", "read", "context")\n',
     '    for k in ("task_id", "multipliers", "method", "contribution", "fit_pass_at_10"):\n'
     '        assert k in sub, f"missing {k}"\n'),
]

LEFTOVER = re.compile(r"steer|(?<!singular )vector|forward pass changes|positions|--scale|intervention|board\.py|HF dataset",
                      re.IGNORECASE)


def port(text: str) -> tuple[str, list[int]]:
    fired = []
    for i, (old, new) in enumerate(SUBS):
        if old in text:
            text = text.replace(old, new)
            fired.append(i)
    return text, fired


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", default="j-lens-mean-snapshot-rig4b-eval")
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--out", required=True)
    ap.add_argument("--files", nargs="*", default=list(FILES))
    a = ap.parse_args()
    out = Path(a.out)
    fired_all, problems = set(), []
    for f in a.files:
        r = subprocess.run(["git", "-C", a.anchor, "show", f"{a.rev}:{f}"], capture_output=True, text=True)
        if r.returncode:
            print(f"{f}: not in the anchor commit (skipped)")
            continue
        text, fired = port(r.stdout)
        fired_all |= set(fired)
        for n, line in enumerate(text.splitlines(), 1):
            if LEFTOVER.search(line):
                problems.append(f"{f}:{n}: {line.strip()}")
        (out / f).parent.mkdir(parents=True, exist_ok=True)
        (out / f).write_text(text)
        print(f"{f}: {len(fired)} substitutions")
    unused = [i for i in range(len(SUBS)) if i not in fired_all]
    if unused:
        print("substitutions that never fired:", *(repr(SUBS[i][0][:70]) for i in unused), sep="\n  ")
    if problems:
        raise SystemExit("steering vocabulary left:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    main()
