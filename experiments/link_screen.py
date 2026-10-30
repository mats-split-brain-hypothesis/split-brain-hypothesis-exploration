"""Make the screened centres browsable in the dashboard's explorer.

  python experiments/link_screen.py

The explorer discovers arms as out/eval/<family>/<split>/<arm>/readouts.jsonl. The screen of our own centres
lives in out/screen/ (dashboard page "Constant μ exploration"). This links each screened arm directory into
out/eval when out/eval has no directory of that name; existing arms and every summary.json are left as they are,
so the results page is unchanged. Links are relative and machine-local (out/ is git-ignored).
"""

import os

from jlm import OUT


def main() -> None:
    screen, made = OUT / "screen", 0
    for arm in sorted(screen.glob("*/*/*/readouts.jsonl")):
        src = arm.parent
        dst = OUT / "eval" / src.relative_to(screen)
        if dst.exists() or dst.is_symlink():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(os.path.relpath(src, dst.parent), target_is_directory=True)
        made += 1
    print(f"linked {made} screened arm directories into {OUT / 'eval'}")


if __name__ == "__main__":
    main()
