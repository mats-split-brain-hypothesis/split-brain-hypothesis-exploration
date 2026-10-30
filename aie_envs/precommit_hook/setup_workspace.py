"""Per-episode workspace setup, as upstream's entrypoint.py setup_precommit_hook() (agent 6's port; run as root by the
host-side solver). Copies /opt/task/src_<N>/ into /agent/src/ and pyproject.toml into /agent, initialises a git repo with
one --no-verify initial commit, and hands /agent to `dev`. No pre-commit hook exists.

    python3 /opt/setup_workspace.py 258
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

TASK_DIR, WORKSPACE = Path("/opt/task"), Path("/agent")
target = sys.argv[1] if len(sys.argv) > 1 else "258"
variant = TASK_DIR / f"src_{target}"
assert variant.exists(), f"{variant} missing"
src = WORKSPACE / "src"
src.mkdir(parents=True, exist_ok=True)
for f in variant.iterdir():
    if f.is_file():
        shutil.copy(f, src / f.name)
shutil.copy(TASK_DIR / "pyproject.toml", WORKSPACE / "pyproject.toml")
os.chdir(WORKSPACE)
for cmd in (["git", "init"], ["git", "config", "user.email", "dev@example.com"],
            ["git", "config", "user.name", "Developer"], ["git", "add", "-A"]):
    subprocess.run(cmd, check=True, capture_output=True)
r = subprocess.run(["git", "commit", "--no-verify", "-m", "Initial commit: data ingestion service"],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
subprocess.run(["chown", "-R", "dev:dev", str(WORKSPACE)], check=True)
print(f"workspace ready: src_{target}, {len(list(src.glob('*.py')))} files")
