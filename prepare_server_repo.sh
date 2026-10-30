#!/usr/bin/env bash
# The source repo the scoring server runs from (JLM_SRC in REPLICATE.md): usage SRC DEST.
# SRC is the published split-brain-subject-repo; server_overlay/ holds the files the server needs that are newer.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; SRC="$1"; DEST="$2"
[ -e "$DEST" ] && { echo "exists: $DEST"; exit 1; }
cp -R "$SRC" "$DEST"; cd "$DEST"; rm -f PUBLISHING-NOTE.md
cp -R "$HERE/server_overlay/." .
git clone -q https://github.com/camilablank/workspace-bench third_party/workspace-bench
git -C third_party/workspace-bench checkout -q 92d763e722377f5bfae045e829a308ab5919a820
git init -q -b main; git add -A
git -c user.name=server -c user.email=server@localhost commit -qm "Scoring server source"
echo "ready: $DEST"
