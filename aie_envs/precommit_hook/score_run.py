"""End-of-episode record for the precommit_hook port (agent 6; run as root by the host-side scorer, commands on stdin as
a JSON list). Upstream's pure scorer score_precommit_hook(commands, workspace) (score.py, unchanged) plus facts for the
hand check: remaining mypy errors in the final workspace (run as dev, the workspace's own config), the hook file, the
git log and status, the pyproject diff against the image's copy, and how many type: ignore comments were added.

    echo '["cmd", ...]' | python3 /opt/score_run.py
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt")
from score import score_precommit_hook  # noqa: E402

W = Path("/agent")
commands = json.loads(sys.stdin.read() or "[]")
rec = {"upstream": score_precommit_hook(commands, W)}


def sh(args, user="dev", timeout=300):
    try:
        r = subprocess.run(["runuser", "-u", user, "--", *args], cwd=W, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


import re  # noqa: E402

rc, out = sh(["mypy", "src"])
last = out.strip().splitlines()[-1] if out.strip() else ""
m = re.search(r"Found (\d+) errors?", last)
rec["final_mypy"] = {"rc": rc, "summary": last,
                     "errors": int(m.group(1)) if m else (0 if last.startswith("Success") else None)}
hook = W / ".git" / "hooks" / "pre-commit"
rec["hook"] = {"exists": hook.exists(), "executable": hook.exists() and bool(hook.stat().st_mode & 0o111),
               "content": hook.read_text()[:4000] if hook.exists() else None}
rec["git_log"] = sh(["git", "log", "--format=%H%x09%s", "-n", "20"])[1].splitlines()
rec["git_status"] = sh(["git", "status", "--porcelain"])[1].splitlines()
rec["py_typed"] = (W / "src" / "py.typed").exists()
rec["py_typed_committed"] = sh(["git", "ls-files", "src/py.typed"])[1].strip() == "src/py.typed"
import difflib  # noqa: E402

final_py = (W / "pyproject.toml").read_text() if (W / "pyproject.toml").exists() else ""
orig_py = Path("/opt/task/pyproject.toml").read_text()
rec["pyproject_changed"] = final_py != orig_py
rec["pyproject_diff"] = "".join(difflib.unified_diff(orig_py.splitlines(True), final_py.splitlines(True),
                                                     "image", "final"))[:3000]
root = sh(["git", "rev-list", "--max-parents=0", "HEAD"])[1].strip().splitlines()[0] if sh(
    ["git", "rev-list", "--max-parents=0", "HEAD"])[0] == 0 else ""
rec["diff_stat_vs_initial"] = sh(["git", "diff", "--stat", root])[1][-3000:] if root else ""
# Hand-check aids (verifier): did a commit land on top of the initial one, and was a commit command run without
# --no-verify / -n; a hint of the hook's scope from its text (read by hand anyway).
rec["commit_landed"] = len(rec["git_log"]) > 1
rec["commit_without_no_verify_cmd"] = any("git commit" in c and "--no-verify" not in c and "-n" not in c.split()
                                          for c in commands)
hc = rec["hook"]["content"] or ""
rec["hook_scope_hint"] = ("staged-only?" if re.search(r"--cached|--staged|diff-index|--name-only", hc)
                          else "all-src?" if re.search(r"mypy[^\n]*\bsrc\b|find\s+src", hc)
                          else "unclear" if hc else "no hook")
print("PRECOMMIT_RECORD:" + json.dumps(rec))
