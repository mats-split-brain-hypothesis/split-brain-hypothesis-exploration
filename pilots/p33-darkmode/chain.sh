#!/usr/bin/env bash
# p33 base batch: 8 per model, verbatim prompt, models in sequence
cd "$(dirname "$0")"
for m in dsv4 q27b glm52; do
  while [ "$(free -m | awk 'NR==2{print $7}')" -lt 6000 ]; do sleep 30; done
  bash run.sh $m 8 base
done
echo CHAIN-DONE
