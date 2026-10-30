"""x13 stage 1: the pinned 27B writes each family's glossary entry from the bench's own one-line description.

  python experiments/x13_blind_glossary.py --device cuda
  python experiments/x11_glossary_refs.py --device cuda --blind      # stage 2: 64 texts per entry (bword / bdesc)

x11's glossary words were picked by hand after x1-x10. Here the model gets only the first sentence of each family's
README in the pinned bench clone (third_party/workspace-bench/evals/<family>/README.md; the example line that
follows, with its target, is not shown) and writes one word naming the situation and a one-line definition. It
never sees a bank item or a result. Greedy, thinking off. Writes out/captures/glossary-blind.json (read by x11
--blind) and its provenance.
"""

import argparse
import json
import re

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import REPO_ROOT, hfdata
from jlm.capture import MODEL, load_backend
from x11_glossary_refs import BLIND

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation"]
README = REPO_ROOT / "third_party" / "workspace-bench" / "evals"
PROMPT = """Here is a one-sentence description of a kind of text, from a benchmark's documentation:

"{desc}"

Write a glossary entry for this kind of text: one word that names the situation, and a one-line definition of what
such a text looks like. Do not give or quote any example. Answer with JSON only: {{"word": "...", "definition": "..."}}"""


def description(family: str) -> str:
    """The first sentence of the README's first descriptive paragraph (a bold-labelled paragraph, such as
    user_modeling's "**Sources.**" credit, is skipped)."""
    paras, cur = [], []
    for line in (README / family / "README.md").read_text().splitlines()[1:]:
        if line.startswith("#"):
            break
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    paras += [" ".join(cur)] if cur else []
    text = next(x for x in paras if not x.startswith("**"))
    return re.split(r"(?<=[.?!])\s", text, maxsplit=1)[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    backend = load_backend(args.device)
    tok = backend.tokenizer
    entries, descs, raw = {}, {}, {}
    for f in FAMILIES:
        descs[f] = description(f)
        ids = tok.apply_chat_template([{"role": "user", "content": PROMPT.format(desc=descs[f])}], tokenize=True,
                                      add_generation_prompt=True, enable_thinking=False)
        ids = torch.tensor([list(ids["input_ids"] if hasattr(ids, "keys") else ids)]).to(backend.model.device)
        out = backend.model.generate(ids, max_new_tokens=160, do_sample=False, pad_token_id=tok.eos_token_id)[0][ids.shape[1]:]
        raw[f] = tok.decode(out, skip_special_tokens=True)
        m = re.search(r"\{.*\}", raw[f], re.S)
        d = json.loads(m.group(0)) if m else {}
        entries[f] = [str(d.get("word", "")).strip(), str(d.get("definition", "")).strip()]
        print(f"{f}: {descs[f]!r} -> {entries[f]}", flush=True)
    BLIND.write_text(json.dumps({"entries": entries, "descriptions": descs}, indent=1, ensure_ascii=False) + "\n")
    write_artefact(BLIND.with_suffix(".provenance.json"),
                   Provenance(model=MODEL, model_revision=PINS[MODEL], dataset="workspace-bench READMEs (first sentence)",
                              extra={"prompt": PROMPT, "raw": raw, "decoding": "greedy, thinking off"}),
                   {"entries": entries})
    hfdata.share([BLIND, BLIND.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
