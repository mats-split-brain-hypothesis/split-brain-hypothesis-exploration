#!/bin/bash
# Move out/ between the Mac and the shared volume (through any running pod of ours; see tools/pod.sh).
#   bash tools/sync.sh down <pod-name> [subpath ...]   # volume -> Mac, e.g. eval/typo analysis/S1 (default: eval analysis)
#   bash tools/sync.sh up <pod-name> [subpath ...]     # Mac -> volume, e.g. captures ctx
# Never deletes on either side (out/ accumulates from several machines). Large stores (ctx, corpora) stay on
# the volume unless asked for: the Mac has 16 GB of memory and limited disk.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:?down|up}"; ALIAS="runpod-jlm-${2:?pod name}"; shift 2
if [ $# -gt 0 ]; then PATHS=("$@"); else PATHS=(eval analysis); fi
FLAGS=(-rlptDz --no-o --no-g)  # /workspace forbids chown, so no -a
for p in "${PATHS[@]}"; do
  mkdir -p "out/$p"
  if [ "$DIR" = down ]; then
    rsync "${FLAGS[@]}" "$ALIAS:/workspace/out/$p/" "out/$p/"
  else
    ssh "$ALIAS" "mkdir -p /workspace/out/$p"
    rsync "${FLAGS[@]}" "out/$p/" "$ALIAS:/workspace/out/$p/"
  fi
done
