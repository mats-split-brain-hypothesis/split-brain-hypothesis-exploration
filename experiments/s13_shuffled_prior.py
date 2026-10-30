"""S13 derived priors (mu-log, card S13):

- control: the chat unigram log-prior with its values permuted over the vocabulary (same distribution of values and
  norm, no token identity), so its pullback is "a random c of the same norm": ``--seed s`` -> ``<source>-shuf<s>``;
- S13d, head only: ``log p`` kept on the ``K`` most frequent tokens, every other token set to the K-th value (a
  constant, which the pullback's centring ignores): ``--head K`` -> ``<source>-head<K>``;
- S13t, a template indicator: ``c = 1`` on the first K tokens of a token set (``data/template_tokens``), 0 elsewhere,
  so ``J(h - beta g)`` lowers those tokens by about beta (the constant-g analogue of S14's projection):
  ``--indicator template:64`` -> ``ind-template-64``.

  python experiments/s13_shuffled_prior.py [--source unigram-norobots] [--seed 0 | --head 2000]

Writes ``out/priors/<name>.pt`` in the format of ``build_priors.py``; pull it back with
``precompute_pullback.py --priors <name>`` (pod) and read it as ``s13:<name>:<beta>``.
"""

import argparse

import torch

from jlm import OUT


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", default="unigram-norobots")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--head", type=int, default=0)
    ap.add_argument("--indicator", default="", help="<token set>:<k>")
    args = ap.parse_args()
    if args.indicator:
        import json
        from jlm import REPO_ROOT
        ts, k = args.indicator.split(":")
        ids = [t["id"] for t in json.loads((REPO_ROOT / "data" / "template_tokens" / f"{ts}.json").read_text())["tokens"]][: int(k)]
        V = torch.load(OUT / "priors" / "unigram-norobots.pt")["logp"].numel()
        c = torch.zeros(V)
        c[ids] = 1.0
        path = OUT / "priors" / f"ind-{ts}-{k}.pt"
        torch.save({"logp": c, "counts": torch.zeros(V, dtype=torch.int64),
                    "meta": {"variant": f"indicator of the first {k} tokens of {ts}", "ids": ids}}, path)
        print(path)
        return
    src = torch.load(OUT / "priors" / f"{args.source}.pt")
    if args.head:
        logp = src["logp"].clone()
        floor = logp.topk(args.head).values[-1]
        logp = logp.clamp_min(floor)
        out = {"logp": logp, "counts": src["counts"].clone(),
               "meta": {**src["meta"], "variant": f"head {args.head}: log p clamped below at the {args.head}-th value"}}
        path = OUT / "priors" / f"{args.source}-head{args.head}.pt"
        torch.save(out, path)
        print(path)
        return
    perm = torch.randperm(src["logp"].numel(), generator=torch.Generator().manual_seed(args.seed))
    out = {"logp": src["logp"][perm].clone(), "counts": src["counts"][perm].clone(),
           "meta": {**src["meta"], "control": f"values of {args.source} permuted over the vocabulary, seed {args.seed}"}}
    path = OUT / "priors" / f"{args.source}-shuf{args.seed}.pt"
    torch.save(out, path)
    print(path)


if __name__ == "__main__":
    main()
