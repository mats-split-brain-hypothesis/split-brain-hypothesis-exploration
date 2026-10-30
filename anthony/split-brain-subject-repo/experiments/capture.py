"""Capture a bank's read-cell residuals on Qwen3.6-27B (pod only: needs an 80 GB GPU).

  python experiments/capture.py --family typo --split fit --device cuda [--limit 3]
"""

import argparse

import torch

from jlm import banks, capture


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--split", required=True, choices=banks.SPLITS)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    bank = banks.load(args.family, args.split)
    dest = capture.path_of(bank)
    if dest.exists() and not args.limit:
        print(f"{dest} exists, skipping")
        return
    print(f"{bank.name}: {len(bank.items)} items -> {capture.run(bank, args.device, limit=args.limit)}")


if __name__ == "__main__":
    main()
