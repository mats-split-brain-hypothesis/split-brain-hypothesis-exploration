"""Mention-only control (``umot.mention_control``): compliance check and residual capture.

  compliance  greedy + k sampled continuations of each prompt (bench render up to the assistant
              header); an item complies when the greedy output copies the carrier exactly
              -> out/mention-control/compliance.json
  capture     residuals at the bench's read cells (carrier tokens), grid layers + 42
              -> out/captures/mention_control.pt

Token readers then run locally from the capture: experiments/token_local.py --family mention_control.

  python experiments/mc_run.py --stages compliance,capture            # pod (27B)
  python experiments/mc_run.py --model Qwen/Qwen3.5-0.8B --layers 2,5 --limit 9 --device cpu   # plumbing
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from m1_run import MODEL, OUT_DEFAULT, load_backend  # noqa: E402

from umot import capture  # noqa: E402
from umot import mention_control as mc  # noqa: E402
from umot.provenance import PINS, Provenance, write_artefact  # noqa: E402


def norm(s: str) -> str:
    return " ".join(s.split()).strip().strip('"').strip()


@torch.no_grad()
def compliance(backend, items: list[dict], k: int, device: str) -> list[dict]:
    from wsbench.produce.render import _chat

    tok, model = backend.tokenizer, backend.model
    out = []
    for n, it in enumerate(items):
        ids = _chat(tok, [{"role": "user", "content": it["prompt"]}])
        x = torch.tensor([ids], device=device)
        n_new = len(tok(it["carrier"], add_special_tokens=False)["input_ids"]) + 8
        pad = tok.pad_token_id or tok.eos_token_id
        g = model.generate(x, attention_mask=torch.ones_like(x), do_sample=False, max_new_tokens=n_new, pad_token_id=pad)
        greedy = tok.decode(g[0, len(ids):], skip_special_tokens=True)
        sampled = []
        if k:
            s = model.generate(
                x, attention_mask=torch.ones_like(x), do_sample=True, temperature=1.0, top_p=1.0, top_k=0,
                max_new_tokens=n_new, num_return_sequences=k, pad_token_id=pad,
            )
            sampled = tok.batch_decode(s[:, len(ids):], skip_special_tokens=True)
        ok = [norm(t) == norm(it["carrier"]) for t in sampled]
        out.append(
            {
                "id": it["id"],
                "greedy": greedy,
                "greedy_ok": norm(greedy) == norm(it["carrier"]),
                "sampled_ok": sum(ok),
                "k": k,
                "mentions_concept": any(
                    c.lower() in t.lower() for c in mc.concepts_of(it) for t in [greedy, *sampled]
                ),
            }
        )
        if n % 50 == 0:
            print(f"  compliance {n}/{len(items)}", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", default=mc.FAMILY, choices=sorted(mc.BANKS))
    ap.add_argument("--stages", default="compliance,capture")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=4, help="sampled continuations per item for compliance")
    ap.add_argument("--layers", default="", help="override capture layers (small-model plumbing only)")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    stages = set(args.stages.split(","))
    out = Path(args.out)
    suffix = (f"-limit{args.limit}" if args.limit else "") + ("" if args.model == MODEL else "-" + args.model.split("/")[-1])
    items = mc.load(args.family)[: args.limit or None]
    layers = [int(x) for x in args.layers.split(",")] if args.layers else None
    backend = load_backend(args.model, args.device)
    prov = Provenance(
        model=args.model,
        model_revision=PINS.get(args.model, "unpinned"),
        dataset=f"umot/{args.family}",
        extra={"limit": args.limit, "device": args.device, "bank": str(mc.BANKS[args.family].relative_to(mc.REPO_ROOT))},
    )

    if "compliance" in stages:
        t0 = time.time()
        rows = compliance(backend, items, args.k, args.device)
        dest = out / args.family.replace("_", "-") / f"compliance{suffix}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        n_ok = sum(r["greedy_ok"] for r in rows)
        write_artefact(dest.with_suffix(".provenance.json"), prov, {"items": len(rows), "greedy_ok": n_ok,
                                                                    "seconds": round(time.time() - t0, 1)})
        print(f"[compliance] {n_ok}/{len(rows)} copy the carrier greedily -> {dest}", flush=True)

    if "capture" in stages:
        t0 = time.time()
        caps = [capture.capture_spec(backend, s, layers) for s in mc.specs(items)]
        dest = out / "captures" / f"{args.family}{suffix}.pt"
        capture.save(caps, dest)
        write_artefact(dest.with_suffix(".provenance.json"), prov,
                       {"items": len(caps), "seconds": round(time.time() - t0, 1)})
        print(f"[capture] {len(caps)} items -> {dest}", flush=True)


if __name__ == "__main__":
    main()
