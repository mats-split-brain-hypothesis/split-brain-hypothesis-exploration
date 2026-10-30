"""A minimal agent loop over the Messages API: one system prompt, two tools (bash and str_replace_editor), the first
user message from --prompt. The loop ends when a reply calls no tool. One JSON event per line on stdout.

    python agent.py --prompt "..." [--system-file F] [--max-tokens 32000]

Endpoint and model from ANTHROPIC_BASE_URL and ANTHROPIC_MODEL. Standard library only.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

OUTPUT_LIMIT = 30000
BASH_TIMEOUT = 600
RETRY_WAITS = (5, 15, 30, 60, 120, 240, 300, 300)
SESSION = str(uuid.uuid4())

SYSTEM = """You are a helpful assistant that can interact with a computer through the tools below.

Working directory: {cwd}
Today's date: {date}

When you have finished, reply without calling a tool; that reply ends the session."""

TOOLS = [
    {
        "name": "bash",
        "description": (
            "Run a command in a bash shell. Each call starts in the directory where the previous call ended; "
            "environment variables and shell state do not persist between calls. stdout and stderr are returned "
            f"together, truncated to {OUTPUT_LIMIT} characters. A command is stopped after `timeout` seconds "
            f"(default and maximum {BASH_TIMEOUT}); run longer jobs in the background with their output in a file, "
            "e.g. `nohup cmd > out.log 2>&1 &`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run."},
                "timeout": {"type": "integer", "description": f"Seconds before the command is stopped (max {BASH_TIMEOUT})."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "str_replace_editor",
        "description": (
            "View, create and edit files. `view`: a file with line numbers (optionally `view_range` [start, end]) "
            "or a directory's entries. `create`: write `file_text` to `path` (overwrites). `str_replace`: replace "
            "`old_str`, which must occur exactly once in the file, with `new_str`. `insert`: insert `new_str` after "
            "line `insert_line` (0 for the top). Paths are absolute or relative to the working directory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "enum": ["view", "create", "str_replace", "insert"]},
                "path": {"type": "string"},
                "file_text": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
                "insert_line": {"type": "integer"},
                "view_range": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["command", "path"],
        },
    },
]

# never passed on to the tools' processes
PRIVATE_ENV = ("ANTHROPIC_", "CLAUDE_", "BASH_DEFAULT_TIMEOUT_MS", "BASH_MAX_TIMEOUT_MS")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def emit(event: dict) -> None:
    event.setdefault("session_id", SESSION)
    event.setdefault("uuid", str(uuid.uuid4()))
    event.setdefault("timestamp", now())
    sys.stdout.write(json.dumps(event, separators=(",", ":")) + "\n")  # compact, as Claude Code's stream-json
    sys.stdout.flush()


def clip(s: str) -> str:
    if len(s) <= OUTPUT_LIMIT:
        return s
    half = OUTPUT_LIMIT // 2
    return s[:half] + f"\n\n... [{len(s) - OUTPUT_LIMIT} characters truncated] ...\n\n" + s[-half:]


class Bash:
    def __init__(self, cwd: str):
        self.cwd = cwd
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(PRIVATE_ENV)}

    def __call__(self, command: str, timeout: int | None = None) -> tuple[str, bool]:
        timeout = max(1, min(int(timeout or BASH_TIMEOUT), BASH_TIMEOUT))
        with tempfile.NamedTemporaryFile("w+", delete=False) as cwdf, tempfile.TemporaryFile("w+") as out:
            script = f"cd {json.dumps(self.cwd)} || exit 1\n{command}\n__rc=$?\npwd > {json.dumps(cwdf.name)}\nexit $__rc\n"
            # output to a file, not a pipe: a background job that keeps the pipe open would hold the call
            p = subprocess.Popen(["bash", "-c", script], stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                 env=self.env, start_new_session=True)
            try:
                rc = p.wait(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
                rc, timed_out = None, True
            out.seek(0)
            text = out.read()
            try:
                d = open(cwdf.name).read().strip()
                if d:
                    self.cwd = d
            finally:
                os.unlink(cwdf.name)
        if timed_out:
            text += f"\n[command stopped after {timeout} s]"
        elif rc:
            text += f"\n[exit code {rc}]"
        return clip(text) or "(no output)", bool(rc) or timed_out


def editor(cwd: str, a: dict) -> tuple[str, bool]:
    path = a.get("path", "")
    path = path if os.path.isabs(path) else os.path.join(cwd, path)
    cmd = a.get("command")
    try:
        if cmd == "view":
            if os.path.isdir(path):
                return "\n".join(sorted(e + ("/" if os.path.isdir(os.path.join(path, e)) else "")
                                        for e in os.listdir(path))) or "(empty directory)", False
            lines = open(path, errors="replace").read().split("\n")
            lo, hi = 1, len(lines)
            if a.get("view_range"):
                lo, hi = a["view_range"][0], a["view_range"][1] if a["view_range"][1] != -1 else len(lines)
            return clip("\n".join(f"{i:6}\t{lines[i - 1]}" for i in range(max(lo, 1), min(hi, len(lines)) + 1))), False
        if cmd == "create":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            open(path, "w").write(a.get("file_text", ""))
            return f"Wrote {path}", False
        if cmd == "str_replace":
            text = open(path).read()
            old = a.get("old_str", "")
            n = text.count(old) if old else 0
            if n != 1:
                return f"old_str occurs {n} times in {path}; it must occur exactly once", True
            open(path, "w").write(text.replace(old, a.get("new_str", ""), 1))
            return f"Edited {path}", False
        if cmd == "insert":
            lines = open(path).read().split("\n")
            k = int(a.get("insert_line", 0))
            if not 0 <= k <= len(lines):
                return f"insert_line {k} is outside 0..{len(lines)}", True
            lines[k:k] = a.get("new_str", "").split("\n")
            open(path, "w").write("\n".join(lines))
            return f"Edited {path}", False
        return f"unknown command {cmd!r}", True
    except OSError as e:
        return f"{type(e).__name__}: {e}", True


def call(url: str, body: dict) -> tuple[dict, str]:
    """One Messages API call, retried on overload / server errors / a dropped connection."""
    data = json.dumps(body).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": "via-proxy"}
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.loads(r.read()), r.headers.get("x-generation-id") or ""
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")[:2000]
            if e.code not in (408, 429, 500, 502, 503, 504, 529) or attempt == len(RETRY_WAITS):
                raise RuntimeError(f"API error {e.code}: {err}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            if attempt == len(RETRY_WAITS):
                raise RuntimeError(f"API error: {type(e).__name__}: {e}")
        emit({"type": "system", "subtype": "api_retry", "attempt": attempt + 1})
        time.sleep(RETRY_WAITS[attempt])
    raise AssertionError


def with_cache_marks(system: list, messages: list) -> tuple[list, list]:
    """Prompt-cache breakpoints on the system prompt and the last two user turns (each request resends the whole
    conversation; without them most providers bill every turn's input in full)."""
    msgs = json.loads(json.dumps(messages))
    for m in msgs:
        if isinstance(m["content"], list):
            for c in m["content"]:
                c.pop("cache_control", None)
    users = [m for m in msgs if m["role"] == "user"][-2:]
    for m in users:
        if isinstance(m["content"], str):
            m["content"] = [{"type": "text", "text": m["content"]}]
        m["content"][-1]["cache_control"] = {"type": "ephemeral"}
    return [dict(system[0], cache_control={"type": "ephemeral"})], msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--system-file", default=None)
    ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--effort", default="high")
    a = ap.parse_args()
    url = os.environ["ANTHROPIC_BASE_URL"].rstrip("/") + "/v1/messages"
    model = os.environ["ANTHROPIC_MODEL"]
    cwd = os.getcwd()
    template = open(a.system_file).read() if a.system_file else SYSTEM
    system = [{"type": "text", "text": template.format(cwd=cwd, date=datetime.now().strftime("%Y-%m-%d"))}]
    bash = Bash(cwd)
    emit({"type": "system", "subtype": "init", "agent": "minimal", "model": model, "cwd": cwd,
          "tools": [t["name"] for t in TOOLS], "system_prompt": system[0]["text"]})
    messages = [{"role": "user", "content": a.prompt}]
    turns, usage, t0 = 0, {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
                           "cache_creation_input_tokens": 0}, time.time()

    def finish(subtype: str, reason: str, text: str = "", stop: str | None = None, error: bool = False) -> None:
        emit({"type": "result", "subtype": subtype, "is_error": error, "result": text, "stop_reason": stop,
              "terminal_reason": reason, "num_turns": turns, "duration_ms": int((time.time() - t0) * 1000),
              "usage": usage})

    signal.signal(signal.SIGTERM, lambda *_: (finish("error_during_execution", "terminated", error=True), sys.exit(143)))
    while True:
        sys_marked, msgs = with_cache_marks(system, messages)
        body = {"model": model, "max_tokens": a.max_tokens, "system": sys_marked, "tools": TOOLS, "messages": msgs,
                "thinking": {"type": "adaptive"}, "output_config": {"effort": a.effort}}
        try:
            resp, gen = call(url, body)
        except RuntimeError as e:
            finish("error_during_execution", "api_error", str(e), error=True)
            return
        turns += 1
        for k in usage:
            usage[k] += (resp.get("usage") or {}).get(k) or 0
        content = resp.get("content") or []
        for block in content:
            emit({"type": "assistant", "request_id": gen,
                  "message": {"id": resp.get("id"), "role": "assistant", "model": resp.get("model"), "content": [block],
                              "stop_reason": resp.get("stop_reason"), "usage": resp.get("usage")}})
        messages.append({"role": "assistant", "content": content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        if not uses:
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            stop = resp.get("stop_reason")
            finish("success" if stop == "end_turn" else "error_max_tokens" if stop == "max_tokens" else "success",
                   "completed" if stop == "end_turn" else str(stop), text, stop)
            return
        results = []
        for u in uses:
            inp = u.get("input") or {}
            if u["name"] == "bash":
                out, err = bash(str(inp.get("command", "")), inp.get("timeout"))
            elif u["name"] == "str_replace_editor":
                out, err = editor(bash.cwd, inp)
            else:
                out, err = f"no tool named {u['name']!r}", True
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out, **({"is_error": True} if err else {})})
        messages.append({"role": "user", "content": results})
        emit({"type": "user", "message": {"role": "user", "content": results}})


if __name__ == "__main__":
    main()
