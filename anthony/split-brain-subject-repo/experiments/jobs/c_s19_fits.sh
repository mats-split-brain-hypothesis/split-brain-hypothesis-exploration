#!/bin/bash
# S19 fits, one after another (one GPU job): NAMES / RANKS / LAMS / EXTRAS are parallel lists, e.g.
#   NAMES="s19r16l1 s19bl1" RANKS="16 0" LAMS="1 1" bash experiments/jobs/c_s19_fits.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
read -ra N <<< "$NAMES"; read -ra R <<< "$RANKS"; read -ra L <<< "$LAMS"
IFS='|' read -ra X <<< "${EXTRAS:-}"
for i in "${!N[@]}"; do
  [ -f "out/priors/S19/${N[$i]}.pt" ] && [ -z "${FORCE:-}" ] && { echo "[s19] skip ${N[$i]}"; continue; }
  echo "[s19 $(date -u +%H:%M:%S)] fit ${N[$i]} rank ${R[$i]} lam ${L[$i]} ${X[$i]:-}"
  .venv/bin/python experiments/s19_fit.py --name "${N[$i]}" --rank "${R[$i]}" --lam "${L[$i]}" ${X[$i]:-} --device cuda \
    || { echo "[s19] FAILED ${N[$i]}"; exit 1; }
done
echo "[s19 $(date -u +%H:%M:%S)] fits done"
