#!/usr/bin/env bash
# Build the jlens-edits snapshot for the split-brain scenario's second repo (jle/PLAN.md). Never writes to the source.
#   bash jle/build_snapshot.sh            # jle/jlens-edits-snapshot: the cut + jle/patches/*
#   bash jle/build_snapshot.sh <v>        # jle/variants/<v>/: the same rules as build_snapshot.sh (patches/<name>
#                                         # replaces jle/patches/<name>, new names are added, skip lists names to
#                                         # leave out, papers/* are amended into the reading-list commit, untracked/*
#                                         # is copied in uncommitted); DEST gets -<v>
# Anthony's own repo (no partner work, Anthony 2026-10-27): no renaming. WorkspaceBench (MIT, pinned 92d763e) is
# copied into third_party/ untracked, as the repo's README bootstraps it (third_party/ is gitignored there).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$HOME/jlens-edits}"   # the jlens-edits checkout ([private repo])
CUT=e84a551                       # its head on main (2026-10-01 21:58, x101 OUTCOME)
BENCH="${BENCH:-$HOME/j-lens-mean/third_party/workspace-bench}"
BENCH_PIN=92d763e722377f5bfae045e829a308ab5919a820
VARIANT="${1:-}"
DEST="$HERE/jlens-edits-snapshot${VARIANT:+-$VARIANT}"
VDIR="$HERE/variants/$VARIANT"
[ -z "$VARIANT" ] || [ -d "$VDIR" ] || { echo "no jle/variants/$VARIANT"; exit 1; }
[ "$(git -C "$BENCH" rev-parse HEAD)" = "$BENCH_PIN" ] || { echo "$BENCH is not at $BENCH_PIN"; exit 1; }

case "$DEST" in "$HERE"/*) ;; *) echo "refusing: DEST outside $HERE"; exit 1;; esac
cd "$HERE"
rm -rf "$DEST"
git clone --quiet --no-local --no-checkout "$SRC" "$DEST"
cd "$DEST"
git checkout -q -B main "$CUT"
git remote remove origin
git for-each-ref --format='%(refname:short)' refs/heads | { grep -vx main || true; } | xargs -r git branch -q -D
git for-each-ref --format='%(refname)' refs/remotes refs/tags | xargs -r -n1 git update-ref -d

# Hand-made commits on top, dated as written.
PATCHES=()
for p in "$HERE"/patches/*.patch; do
  [ -e "$p" ] || continue
  v="$VDIR/patches/$(basename "$p")"
  if [ -n "$VARIANT" ] && [ -e "$v" ]; then PATCHES+=("$v"); else PATCHES+=("$p"); fi
done
if [ -n "$VARIANT" ]; then
  for v in "$VDIR"/patches/*.patch; do [ -e "$v" ] && [ ! -e "$HERE/patches/$(basename "$v")" ] && PATCHES+=("$v"); done
fi
if [ -n "$VARIANT" ] && [ -f "$VDIR/skip" ]; then
  mapfile -t PATCHES < <(for p in "${PATCHES[@]}"; do grep -qxF "$(basename "$p")" "$VDIR/skip" || echo "$p"; done)
fi
mapfile -t PATCHES < <(for p in "${PATCHES[@]}"; do printf '%s\t%s\n' "$(basename "$p")" "$p"; done | sort | cut -f2)
[ ${#PATCHES[@]} -eq 0 ] || git am --quiet --committer-date-is-author-date "${PATCHES[@]}"
papers_in_tree() { for f in "$VDIR/papers/"*; do cmp -s "$f" "papers/$(basename "$f")" || return 1; done; }
if [ -n "$VARIANT" ] && [ -d "$VDIR/papers" ] && ! papers_in_tree; then
  git log -1 --format=%s | grep -q '^papers/' || { echo "the last patch is not the reading list"; exit 1; }
  cp "$VDIR/papers/"* papers/
  git add papers/
  GIT_COMMITTER_DATE="$(git log -1 --format=%aD)" git commit --quiet --amend --no-edit
fi
git reflog expire --expire=now --all && git gc --quiet --prune=now

mkdir -p third_party
git -C "$BENCH" archive --prefix=workspace-bench/ "$BENCH_PIN" | tar -x -C third_party
if [ -n "$VARIANT" ] && [ -d "$VDIR/untracked" ]; then
  cp -R "$VDIR/untracked/." .
  M="$( [ -f "$VDIR/untracked.mtime" ] && cat "$VDIR/untracked.mtime" || TZ=UTC git log -1 --date=format-local:%Y-%m-%dT%H:%M:%SZ --format=%ad)"
  (cd "$VDIR/untracked" && find . -type f) | while read -r f; do touch -d "$M" "$f"; done
fi
EXTRA="$(git status --porcelain --ignored | { grep -v '^!! third_party/$' || true; })"
[ -z "$EXTRA" ] || [ -d "$VDIR/untracked" ] || { echo "unexpected untracked files:"; echo "$EXTRA"; exit 1; }
git log --oneline | wc -l | xargs echo commits:
git log -1 --format='head: %h %ad %an: %s' --date=iso
