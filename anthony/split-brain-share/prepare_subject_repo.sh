#!/usr/bin/env bash
# Turn the published split-brain-subject-repo into the repo a subject works in: usage SRC DEST.
# Removes the publishing notices (a subject must not be told the plant is fictional), fetches the six real papers,
# clones workspace-bench at the pinned commit, makes the git repo that launch.sh and pod.sh need.
set -euo pipefail
SRC="$1"; DEST="$2"
[ -e "$DEST" ] && { echo "exists: $DEST"; exit 1; }
cp -R "$SRC" "$DEST"; cd "$DEST"
rm -f PUBLISHING-NOTE.md papers/README.md papers/REAL-PAPERS.md
python3 - <<'PY'
import glob
for p in glob.glob("papers/*.md"):
    s = open(p).read()
    if s.startswith("> **FICTIONAL."):
        open(p, "w").write(s.split("\n\n", 1)[1])
PY
while read -r name id; do
  if command -v pandoc >/dev/null && curl -fsL -m 120 "https://arxiv.org/html/$id" -o "/tmp/$id.html"; then
    pandoc -f html -t gfm --wrap=none "/tmp/$id.html" -o "papers/$name.md"
  else
    echo "no pandoc or no HTML for $id: saving the PDF; convert it to papers/$name.md by hand" >&2
    curl -fsL -m 120 "https://arxiv.org/pdf/$id" -o "papers/$name.pdf"
  fi
done <<'LIST'
turner2023-activation-addition 2308.10248
panickssery2023-contrastive-activation-addition 2312.06681
arditi2024-refusal-single-direction 2406.11717
todd2023-function-vectors 2310.15213
belrose2023-tuned-lens 2303.08112
ghandeharioun2024-patchscopes 2401.06102
LIST
git clone -q https://github.com/camilablank/workspace-bench third_party/workspace-bench
git -C third_party/workspace-bench checkout -q 92d763e722377f5bfae045e829a308ab5919a820
git init -q -b iteration; git add -A
git -c user.name=eval-harness -c user.email=eval-harness@localhost commit -qm "Task jlens-steer-assoc-017: task statement, submit script and submission checks"
echo "ready: $DEST"
