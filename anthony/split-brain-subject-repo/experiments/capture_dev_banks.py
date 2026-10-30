"""Capture the dev banks' read cells locally, one model load (80 GB GPU).

  python experiments/capture_dev_banks.py --device cuda [--families association,...]
"""

import argparse

import torch
from umot import capture as ucap
from umot.provenance import PINS, Provenance, write_artefact

from jlm import banks, capture

DEFAULT = "association,basic_readout,multihop,multilingual,user_modeling"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--families", default=DEFAULT)
    ap.add_argument("--splits", default="fit,val")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    backend = capture.load_backend(args.device)
    for fam in args.families.split(","):
        for split in args.splits.split(","):
            bank = banks.load(fam, split)
            dest = capture.path_of(bank)
            if dest.exists():
                print(f"{bank.name}: exists, skipping")
                continue
            out = [ucap.capture_spec(backend, s) for s in banks.specs(bank)]
            ucap.save(out, dest)
            write_artefact(
                dest.with_suffix(".provenance.json"),
                Provenance(model=capture.MODEL, model_revision=PINS[capture.MODEL],
                           dataset=f"jlm/{bank.name}", extra={"limit": 0}),
                {"items": len(out), "bank": str(bank.path)},
            )
            print(f"{bank.name}: {len(out)} items -> {dest}", flush=True)


if __name__ == "__main__":
    main()
