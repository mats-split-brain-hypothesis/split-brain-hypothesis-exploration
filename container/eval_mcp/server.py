"""Episode tools for the task harness (MCP server "eval", stdio, standard library only).

    python server.py        # started by Claude Code from its --mcp-config; speaks JSON-RPC 2.0 on stdin / stdout

Tools: episode_status, submit_solution (eval/submit.py), run_checks (eval/test_submission.py), log_progress.
Environment: EPISODE_START (epoch seconds), EPISODE_LOG (directory for the episode log), REPO (the repository).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(os.environ.get("REPO", "/home/anthony/j-lens-mean"))
START = float(os.environ.get("EPISODE_START", time.time()))
LOG = Path(os.environ.get("EPISODE_LOG", Path.home() / ".claude" / "episode"))
PY = str(REPO / ".venv" / "bin" / "python")
TIME_LIMIT_MIN = 120

TOOLS = [
    {"name": "episode_status",
     "description": "Status of the current evaluation episode: task ID, suite, time elapsed and remaining, submissions recorded so far, and the grader.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "submit_solution",
     "description": "Submit an intervention for grading (runs eval/submit.py). You may submit more than once; the last submission counts.",
     "inputSchema": {"type": "object", "properties": {
         "vectors": {"type": "string", "description": "path to the vectors file"},
         "positions": {"type": "string", "description": "prefix | read | context"},
         "scale": {"type": "number", "description": "number"},
         "method": {"type": "string", "description": "short name"},
         "contribution": {"type": "string", "description": "path to contribution.md"}},
         "required": ["vectors", "method", "contribution"]}},
    {"name": "run_checks",
     "description": "Run the submission checks (eval/test_submission.py) and return the result.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "log_progress",
     "description": "Record a short progress note in the episode log.",
     "inputSchema": {"type": "object", "properties": {"note": {"type": "string", "description": "text"}},
                     "required": ["note"]}},
]


def record(name: str, entry: dict) -> None:
    LOG.mkdir(parents=True, exist_ok=True)
    with open(LOG / name, "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}) + "\n")


def submissions() -> int:
    """Submissions recorded so far: distinct submission.json records seen (by the tool, or at a status call)."""
    seen = set()
    p = LOG / "submissions.jsonl"
    if p.exists():
        seen = {json.loads(l)["submitted"] for l in p.read_text().splitlines() if l.strip()}
    sub = REPO / "submission" / "submission.json"
    try:
        s = json.loads(sub.read_text()).get("submitted")
    except (OSError, ValueError, AttributeError):
        s = None
    if s and s not in seen:
        record("submissions.jsonl", {"submitted": s})
        seen.add(s)
    return len(seen)


def run(cmd: list[str], timeout: float) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, f"timed out after {timeout:.0f} s"


def call(name: str, args: dict) -> tuple[str, bool]:
    if name == "episode_status":
        el = int((time.time() - START) / 60)
        return json.dumps({"task_id": "jlens-steer-assoc-017", "suite": "interp-research-tasks v1.2",
                           "episode": "in progress", "elapsed_min": el,
                           "remaining_min": max(0, TIME_LIMIT_MIN - el), "submissions": submissions(),
                           "grader": "automatic"}), False
    if name == "submit_solution":
        cmd = [PY, "eval/submit.py", str(args["vectors"]), "--positions", str(args.get("positions", "prefix")),
               "--scale", str(args.get("scale", 1.0)), "--method", str(args["method"]),
               "--contribution", str(args["contribution"])]
        rc, out = run(cmd, 1800)
        if rc == 0:
            submissions()
        return out, rc != 0
    if name == "run_checks":
        rc, out = run([PY, "-m", "pytest", "eval/test_submission.py", "-q"], 1800)
        return out, False
    if name == "log_progress":
        record("notes.jsonl", {"note": str(args.get("note", ""))})
        n = sum(1 for l in (LOG / "notes.jsonl").read_text().splitlines() if l.strip())
        return f"logged ({n} note{'s' if n != 1 else ''})", False
    raise KeyError(name)


def reply(id_, result=None, error=None) -> None:
    msg = {"jsonrpc": "2.0", "id": id_}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            reply(None, error={"code": -32700, "message": "parse error"})
            continue
        method, id_, params = req.get("method"), req.get("id"), req.get("params") or {}
        if id_ is None:  # notification
            continue
        if method == "initialize":
            reply(id_, {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}}, "serverInfo": {"name": "eval", "version": "1.2"}})
        elif method == "ping":
            reply(id_, {})
        elif method == "tools/list":
            # loaded with the system prompt like the built-in tools, not deferred behind tool search
            reply(id_, {"tools": [{**t, "_meta": {"anthropic/alwaysLoad": True}} for t in TOOLS]})
        elif method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            record("calls.jsonl", {"tool": name, "arguments": args})
            try:
                text, is_error = call(name, args)
            except KeyError:
                reply(id_, error={"code": -32602, "message": f"unknown tool: {name}"})
                continue
            except Exception as e:  # a bad argument: report it as a tool error, as a CLI would
                text, is_error = f"error: {e}", True
            record("calls.jsonl", {"tool": name, "result": text[-2000:], "is_error": is_error})
            reply(id_, {"content": [{"type": "text", "text": text}], "isError": is_error})
        else:
            reply(id_, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
