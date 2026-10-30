"""S14 explainer numbers: how much of a read cell's state, and of its family mean, lies in the template reading subspace
B (the s14t64 basis), against a random subspace of the same dimension. For the S14 study page's "In depth" section.

Per family (val read cells, fam fitted on fit) and layer:

- ``h_in_B``: mean ||B^T h|| / ||h||, the share of the cell's norm that s14t64 removes (its g = B B^T h);
- ``h_in_rand``: the same for a random 64-dim subspace (s14r64's seeded basis): about sqrt(64 / 5120) = 0.11;
- ``mu_in_B`` / ``mu_in_rand``: ||B^T mu|| / ||mu|| for the cell's family mean mu (fam@fit): how much of fam's
  correction is template;
- ``cos_h_mu_in_B``: mean cosine between B^T h and B^T mu: whether the cell's own template part points where the family
  mean's does (P_B h acting as a per-cell version of fam's template part).

Also writes the first 64 template tokens, decoded, with their sources, and worked examples: val cells (single-token
families) where the plain lens misses the target with template tokens in its top 10 and s14t64 reads it, with the
top 10 of zero, fam and s14t64 at that cell. Captures, bases and stored readouts only, no model, no lens.

  python experiments/s14_explainer.py          # -> out/analysis/S14-explainer/explainer.json
"""

import json
import time

import torch
from transformers import AutoTokenizer
from umot.provenance import PINS

from jlm import OUT, REPO_ROOT, banks, geometry, pullback, score
from jlm.lens import MODEL

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
K = 64


def rand_basis(d: int, layer: int) -> torch.Tensor:
    """s14r64's basis at ``layer`` (jlm.mu.S14.TemplateSubspace, seed 0)."""
    g = torch.Generator().manual_seed(layer)
    return torch.linalg.qr(torch.randn(d, K, generator=g))[0]


def share(X: torch.Tensor, B: torch.Tensor) -> torch.Tensor:
    return (X @ B).norm(dim=1) / X.norm(dim=1).clamp_min(1e-9)


ARMS = {"zero": "zero__cos", "fam": "fam-at-fit__cos", "s14t64": "s14t64-at-fit__cos"}


def examples(template: set[str], per_family: int = 2) -> list[dict]:
    """Cells where zero misses (no accepted token in its top 10) while s14t64 hits, most template tokens in zero's top 10
    first; per family the best ``per_family`` (one cell per item)."""
    out = []
    for fam in ["association", "typo", "multihop", "multilingual", "basic_readout"]:
        bank = banks.load(fam, "val")
        forms = {it["id"]: score.accepted_forms(it) for it in bank.items}
        rows = {}
        for arm, d in ARMS.items():
            p = OUT / "eval" / fam / "val" / d / "readouts.jsonl"
            if not p.exists():
                break
            for line in p.open():
                r = json.loads(line)
                rows.setdefault((r["id"], r["layer"], r["pos"]), {})[arm] = r["tokens"]
        cands = []
        for (i, L, pos), arms in rows.items():
            if len(arms) < len(ARMS):
                continue
            hit = lambda toks: any(score.normalise(x) in forms[i] for x in toks)  # noqa: E731
            if hit(arms["s14t64"]) and not hit(arms["zero"]):
                n_t = sum(x in template for x in arms["zero"])
                cands.append((n_t, L, i, pos, arms))
        seen = set()
        for n_t, L, i, pos, arms in sorted(cands, key=lambda c: (-c[0], -c[1])):
            if i in seen or n_t < 3:
                continue
            seen.add(i)
            it = bank.by_id()[i]
            out.append({"family": fam, "item": i, "layer": L, "pos": pos, "prompt": it.get("prompt", ""),
                        "targets": sorted(forms[i]), "n_template_zero": n_t, "top": arms})
            if len(seen) >= per_family:
                break
    return out


def main() -> None:
    t0 = time.time()
    key = pullback.default_key()
    out = {"k": K, "families": {}}
    for fam in FAMILIES:
        try:
            f = geometry.fit(fam, "val", "fam", "fit")
        except FileNotFoundError as e:
            print(f"{fam}: skipped ({e})")
            continue
        rows = {}
        for L in f.layers:
            _, H, MU = f.layer(L)
            B = pullback.load_tbasis(key, "cos", "template", K, L).float()
            Rb = rand_basis(H.shape[1], L)
            hb, mb = H @ B, MU @ B
            rows[L] = {"h_in_B": share(H, B).mean().item(), "h_in_rand": share(H, Rb).mean().item(),
                       "mu_in_B": share(MU, B).mean().item(), "mu_in_rand": share(MU, Rb).mean().item(),
                       "cos_h_mu_in_B": torch.nn.functional.cosine_similarity(hb, mb, dim=1).mean().item(),
                       "n": H.shape[0]}
        out["families"][fam] = rows
        print(f"{fam}: {len(rows)} layers ({time.time() - t0:.0f} s)", flush=True)
    spec = json.loads((REPO_ROOT / "data" / "template_tokens" / "template.json").read_text())
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    out["tokens"] = [{"id": e["id"], "text": tok.decode([e["id"]]), "display": e["text"], "sources": sorted(set(e["sources"]))}
                     for e in spec["tokens"][:K]]
    out["examples"] = examples({e["text"] for e in spec["tokens"][:K]})  # readouts store the byte-level display form
    dest = OUT / "analysis" / "S14-explainer"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "explainer.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {dest / 'explainer.json'} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
