"""Give a run's repo copy the mtimes of a working repo: each tracked file the time of the last commit that touched it,
everything else (untracked files, directories, .git) HEAD's commit time. rsync -a kept the snapshot build's times,
which subjects read as when the task was set; touching everything at launch made every file look created seconds
before the session (pilots/harness-redteam.md).

    python3 restore_mtime.py REPO
"""

import os
import subprocess
import sys


def main() -> None:
    repo = sys.argv[1]
    log = subprocess.run(["git", "-C", repo, "log", "--format=@%ct", "--name-only", "--no-renames"],
                         capture_output=True, text=True, check=True).stdout
    when, t = {}, None
    for line in log.splitlines():
        if line.startswith("@"):
            t = int(line[1:])
        elif line and line not in when:
            when[line] = t
    head = int(subprocess.run(["git", "-C", repo, "log", "-1", "--format=%ct"], capture_output=True, text=True,
                              check=True).stdout)
    for root, dirs, files in os.walk(repo, topdown=False):
        for name in files + dirs:
            path = os.path.join(root, name)
            ts = when.get(os.path.relpath(path, repo), head)
            os.utime(path, (ts, ts), follow_symlinks=False)
    os.utime(repo, (head, head))


if __name__ == "__main__":
    main()
