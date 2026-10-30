"""Shared pieces for porting agent-interp-envs environments to Inspect (host-side loop, sandbox without network).

Upstream: https://github.com/gkroiz/agent-interp-envs (MIT, commit 310c03f; aie_envs/LICENSE.agent-interp-envs).
Texts and rules below reproduce upstream's src/agent_interp_envs/tool_calling.py: the execute_command schema, the
sanitized agent environment, output truncation, argument healing, the banned command, and the validation of a model
turn (one tool call per turn, up to 3 resamples, then upstream's error tool results). Plan: notes/aie_port_plan.md.
"""
import json

from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ModelOutput, get_model
from inspect_ai.tool import ToolCall, ToolInfo, ToolParam, ToolParams
from inspect_ai.util import OutputLimitExceededError, sandbox

EXECUTE_COMMAND = ToolInfo(
    name="execute_command",
    description="Execute a shell command in the UNIX environment. Returns the command output and exit code.",
    parameters=ToolParams(
        properties={"command": ToolParam(type="string", description="The shell command to execute")},
        required=["command"],
    ),
)
# Upstream checks `b in command.lower()` against "ls -R", which can never match, so upstream never blocks it.
# Kept verbatim so behaviour matches upstream (`ls -R` runs); see the mock check, scenario D.
BANNED_COMMANDS = ["ls -R"]
MAX_TOOL_OUTPUT_CHARS = 200_000
# Upstream's _agent_env: allowlisted variables only (the shell runs privilege-dropped as `dev`).
AGENT_ENV = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/home/dev",
    "USER": "dev",
    "LOGNAME": "dev",
    "SHELL": "/bin/bash",
    "LANG": "C.UTF-8",
    "TERM": "xterm",
}


def truncate_output(output: str, limit: int | None = MAX_TOOL_OUTPUT_CHARS) -> str:
    if limit is None or len(output) <= limit:
        return output
    half = limit // 2
    omitted = len(output) - 2 * half
    return output[:half] + f"\n[... output truncated: {omitted} characters omitted ...]\n" + output[-half:]


async def run_command(command: str, timeout: int, cwd: str, user: str = "dev",
                      extra_env: dict | None = None) -> tuple[int, str]:
    """Run an agent command in the sandbox as `user` with upstream's clean environment (plus upstream's per-env
    extra_env knobs, never secrets), stdout+stderr merged."""
    if "\x00" in command:
        return 1, ("bash: command contains a NUL byte (\\x00), which cannot be passed to the shell; "
                   "nothing was executed")
    env_args = [f"{k}={v}" for k, v in {**AGENT_ENV, **(extra_env or {})}.items()]
    # Upstream runs subprocess.Popen(command, shell=True, stderr=STDOUT): /bin/sh -c (dash on Debian) with stderr
    # merged into stdout at the fd level. The inner /bin/sh reproduces that (its errors read "/bin/sh: 1: ...").
    cmd = ["env", "-i", *env_args, "timeout", "-k", "5", str(timeout),
           "/bin/sh", "-c", '/bin/sh -c "$0" 2>&1', command]
    note = f"(command timed out after {timeout}s and was killed)"
    try:
        r = await sandbox().exec(cmd, cwd=cwd, user=user, timeout=timeout + 30, timeout_retry=False)
    except TimeoutError:
        return 124, note
    except OutputLimitExceededError as e:
        out = truncate_output(e.truncated_output or "")
        return 1, out + "\n[output exceeded the sandbox limit and was cut]"
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 124:
        out = truncate_output(out)
        return 124, f"{out}\n{note}" if out else note
    return r.returncode, truncate_output(out)


def heal_arguments(args: dict) -> dict:
    command = args.get("command")
    if not command:
        return args
    while command.startswith(": "):
        command = command[2:].lstrip()
    if command.startswith(". /"):
        command = "./" + command[3:]
    args["command"] = command.strip()
    return args


def _args_json(tc: ToolCall) -> str:
    return json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)


class Turn:
    """One validated model turn: kind is "tool" (one valid call), "reply" (no tool call) or an error type."""

    def __init__(self, kind, output: ModelOutput, call: ToolCall | None = None, command: str | None = None,
                 error=None, discarded: int = 0):
        self.kind, self.output, self.call, self.command, self.error, self.discarded = (
            kind, output, call, command, error, discarded)

    @property
    def message(self) -> ChatMessageAssistant:
        return self.output.message


async def validated_turn(messages, tools: list[ToolInfo], allowed: set[str], max_retries: int = 3) -> Turn:
    """Upstream's validate_and_get_command with treat_no_tool_call_as_done=True: a reply without a tool call is
    returned at once; parallel calls, unknown tools, bad or missing arguments and banned commands are resampled
    (the discarded generation is not added to the transcript) up to max_retries, then returned as an error."""
    model = get_model()
    last = None
    for attempt in range(max_retries):
        out = await model.generate(messages, tools=tools)
        calls = out.message.tool_calls or []
        if not calls:
            return Turn("reply", out, discarded=attempt)
        if len(calls) > 1:
            last = Turn("parallel_tool_calls", out, error=calls, discarded=attempt)
            continue
        tc = calls[0]
        if tc.function not in allowed:
            last = Turn("unknown_function", out, call=tc, discarded=attempt)
            continue
        args = tc.arguments
        if tc.parse_error or not isinstance(args, dict):
            last = Turn("invalid_arguments", out, call=tc, error=tc.parse_error or "arguments are not an object",
                        discarded=attempt)
            continue
        command = None
        if tc.function == "execute_command":
            args = heal_arguments(dict(args))
            command = args.get("command")
            if not command:
                last = Turn("invalid_arguments", out, call=tc, error=repr(KeyError("command")), discarded=attempt)
                continue
            banned = next((b for b in BANNED_COMMANDS if b in command.lower()), None)
            if banned:
                last = Turn("banned_command", out, call=tc, error=banned, discarded=attempt)
                continue
            tc.arguments = args
        return Turn("tool", out, call=tc, command=command, discarded=attempt)
    last.discarded = max_retries - 1
    return last


def error_tool_results(turn: Turn, allowed: set[str]) -> list[ChatMessageTool]:
    """Upstream's tool results for a turn that failed validation after all retries."""
    def tool_msg(tc: ToolCall, content: str) -> ChatMessageTool:
        return ChatMessageTool(content=content, tool_call_id=tc.id, function=tc.function)

    if turn.kind == "parallel_tool_calls":
        calls = turn.error
        summary = "\n".join(f"  - {tc.function}({_args_json(tc)})" for tc in calls)
        text = (f"You called {len(calls)} functions, but you must call ONLY ONE function per turn.\n\n"
                f"Your calls were:\n{summary}\n\nPlease call just ONE function.")
        return [tool_msg(tc, f"Exit code: 1\nOutput:\n{text}") for tc in calls]
    tc = turn.call
    if turn.kind == "unknown_function":
        return [tool_msg(tc, f"Exit code: 1\nOutput:\nUnknown function: {tc.function}. "
                             f"Available: {', '.join(sorted(allowed))}")]
    if turn.kind == "invalid_arguments":
        return [tool_msg(tc, f"Exit code: 1\nOutput:\nInvalid arguments: {turn.error}\n\n"
                             "Expected: {'command': 'your_command_here'}")]
    if turn.kind == "banned_command":
        return [tool_msg(tc, f"Exit code: 1\nOutput:\nERROR: The '{turn.error}' command is not allowed "
                             "in this environment.")]
    raise ValueError(turn.kind)
