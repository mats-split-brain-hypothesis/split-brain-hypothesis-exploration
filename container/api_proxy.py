"""A subject run's door to a non-Anthropic model: Claude Code in the container talks Anthropic's Messages API to this
proxy on the launching machine, which forwards to OpenRouter's Anthropic-compatible endpoint with the API key added
and the provider pinned. The key never enters the container, and the subject cannot change the routing.

    python3 api_proxy.py --listen 172.17.0.1:8901 --key-file ~/j-lens-mean/umot/.env --provider alibaba \
        --model qwen/qwen3.8-2.4t-a95b --log runs/<id>/api.jsonl

Every ``/v1/messages`` body gets ``"provider": {"order": [<provider>], "allow_fallbacks": false}`` and its model set to
``--model`` (Claude Code's background calls name Claude models; they all go to the one model), and Claude Code's
``safeguards`` field (auto mode's classifier context) is removed: with it, OpenRouter drops every earlier turn's
thinking from the prompt (found 2026-10-23, pilots/credit-lost.md; runs before then had it). Responses, including
server-sent event streams, are passed through as they arrive. One line per request in ``--log``: path, status,
model, provider, the generation id OpenRouter returns, the request's message count and thinking characters sent,
and the input / output tokens the response reports (the check that the thinking reached the model:
``pilots/thinking_check.py``); since the red-team (2026-10-23, pilots/harness-redteam.md) also the effort and thinking
type sent, the response's stop_reason and serving provider, the body of any non-200 answer, and retries. A 429 / 5xx /
unreachable upstream is retried here (RETRIES, with backoff) before anything reaches Claude Code; an error after the
response has started closes the connection (Claude Code retries) instead of writing a second status line.
Truncated generations: when Alibaba fails mid-generation, OpenRouter still ends the stream with a normal stop_reason
(seen 2026-10-23 in p05-c1-A8-q27b-tc: end_turn after a provider 502, and the run ended on a cut-off sentence). So
the proxy passes message_start (and pings) on at once but holds each reply's content until the stream ends, sending
pings meanwhile; when the stop is anything but tool_use, it asks OpenRouter's generation record for finish_reason,
and if the generation did not finish it sends an overloaded_error event instead of the content and logs
``retry_incomplete``. With no content delivered, Claude Code retries the same request (a resample); had content gone
through, it would keep the partial reply and add a "Your response above was cut off mid-stream" user turn.
Thinking spills (Anthony, 2026-10-23, "option 2"): Qwen sometimes ends its reasoning where it writes a chat-template
marker; the provider takes the marker for the real one, the rest of the reasoning arrives as visible text and the turn
ends with no tool call, which ends a headless run. A reply that ends end_turn with no tool_use, whose thinking stops
mid-sentence (inside an open `code span`, or on an opening quote) and whose visible text continues it (lowercase or
punctuation first) and is a fragment (< 200 chars, no closing . ! ? ) * `), or is >= 1500 chars (continuing or not:
every one of 169 genuine long replies with thinking ends that thinking with a period), gets the same overloaded_error, at most SPILL_RETRIES times per identical request; logged
``retry_spill`` with the attempt, and the discarded reply saved in full to spill_retries/NNN.json next to the log.
Matched the 3 known spills and none of 269 other tool-less text replies (p01-p08 and the first reruns).
Qwen's prompt cache (2026-10-25, PLAN.md "p15"): on Alibaba, any ``cache_control`` marker switches Qwen to explicit
caching and turns its implicit caching off, and OpenRouter drops the marker Claude Code moves along on the last
tool_result, so every call cached only the ~5.4k system prefix (p11-r1-A0-q27b-tc: 5% of input cached vs DeepSeek /
GLM 97%). For ``qwen/`` models every ``cache_control`` (system, tools, messages) is removed (logged ``cache_marks``
stripped); nothing the model reads changes. Direct test: no markers, 90% of a repeated 14.7k prompt cached.
Standard library only.
"""

import argparse
import hashlib
import http.client
import os
import json
import re
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "openrouter.ai"
PREFIX = "/api"
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "authorization", "x-api-key",
       "accept-encoding", "proxy-connection", "upgrade", "te", "trailer"}


STRIP = ("safeguards",)
STRIP_CACHE_PREFIXES = ("qwen/",)  # models whose cache_control markers are removed (module docstring)


def strip_cache_marks(req: dict) -> int:
    """Remove every cache_control from a Messages request (system, tools, message blocks); returns how many."""
    n = 0
    blocks = [b for b in (req.get("system") if isinstance(req.get("system"), list) else [])]
    blocks += req.get("tools") or []
    for m in req.get("messages") or []:
        if isinstance(m.get("content"), list):
            for c in m["content"]:
                blocks.append(c)
                if isinstance(c, dict) and isinstance(c.get("content"), list):
                    blocks += c["content"]   # blocks inside a tool_result
    for b in blocks:
        if isinstance(b, dict) and b.pop("cache_control", None) is not None:
            n += 1
    return n
RETRY_STATUS = {429, 500, 502, 503, 504, 529}
OVERLOADED_SSE = b'event: error\ndata: {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}\n\n'
OVERLOADED_JSON = b'{"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}'
SPILL_RETRIES = 3
SPILL_MIN_TEXT = 1500
TERMINAL = set('.!?)"\':')
RETRIES = (5, 15, 30, 60, 120)  # seconds before each retry
STOP = re.compile(rb'"stop_reason":\s*"([a-z_]+)"')
SERVED = re.compile(rb'"provider":\s*"([^"]+)"')
USAGE = {k: re.compile(rf'"{k}":\s*(\d+)'.encode()) for k in
         ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")}


def finished(gen: str, key: str) -> tuple[bool | None, str]:
    """(did generation ``gen`` finish, why): OpenRouter's record; None when it cannot be read (the record can lag)."""
    for wait in (1, 2, 3, 5, 8, 13, 20):
        time.sleep(wait)
        conn = http.client.HTTPSConnection(UPSTREAM, timeout=30, context=ssl.create_default_context())
        try:
            conn.request("GET", f"{PREFIX}/v1/generation?id={gen}", headers={"Authorization": f"Bearer {key}"})
            r = conn.getresponse()
            body = r.read()
            if r.status != 200:
                continue
            d = json.loads(body).get("data") or {}
            bad = [x.get("status") for x in d.get("provider_responses") or [] if x.get("status") not in (None, 200)]
            if d.get("finish_reason") is None or bad:
                return False, f"finish_reason {d.get('finish_reason')}, provider statuses {bad}"
            return True, f"finish_reason {d.get('finish_reason')}"
        except (OSError, ValueError):
            continue
        finally:
            conn.close()
    return None, "generation record not readable"


def reply(events: list[bytes]) -> tuple[str, str, int, str | None]:
    """(thinking, text, tool_use blocks, stop_reason) of a reply from its SSE events."""
    thinking, text, tools, stop = [], [], 0, None
    for ev in events:
        for line in ev.split(b"\n"):
            if not line.startswith(b"data:"):
                continue
            try:
                d = json.loads(line[5:])
            except ValueError:
                continue
            if d.get("type") == "content_block_start" and (d.get("content_block") or {}).get("type") == "tool_use":
                tools += 1
            elif d.get("type") == "content_block_delta":
                dl = d.get("delta") or {}
                thinking.append(dl.get("thinking", "")) if dl.get("type") == "thinking_delta" else None
                text.append(dl.get("text", "")) if dl.get("type") == "text_delta" else None
            elif d.get("type") == "message_delta":
                stop = (d.get("delta") or {}).get("stop_reason") or stop
    return "".join(thinking), "".join(text), tools, stop


def thinking_unfinished(t: str) -> bool:
    """Thinking that breaks off: mid-sentence, inside an open `code span`, or on an opening quote."""
    t = t.rstrip()
    if not t or t.endswith("```"):
        return False
    last = t.splitlines()[-1]
    if last.count("`") % 2 == 1:
        return True
    if t[-1] in "\"'":  # an opening quote: after a space or "(", or (for ") an unbalanced one; apostrophes are common
        return len(t) > 1 and t[-2] in " (" or (t[-1] == '"' and last.count('"') % 2 == 1)
    return t[-1] not in TERMINAL and t[-1] != "`"


def is_spill(thinking: str, text: str, tools: int, stop: str | None) -> bool:
    """The thinking-spill signature (module docstring): the reply's visible text continues broken-off thinking and is
    either long (the rest of the reasoning) or a fragment (the quoted marker ended the message itself)."""
    s = text.strip()
    if stop != "end_turn" or tools or not s or not thinking_unfinished(thinking):
        return False
    if len(text) >= SPILL_MIN_TEXT:  # the rest of the reasoning, continuing the sentence or in a new paragraph
        return True
    continues = s[0].islower() or s[0] in ',;)]}.:\u2014\u2013-"\'`'
    return continues and len(s) < 200 and s[-1] not in ".!?)*`"


def usage(raw: bytes) -> dict:
    """Input and output tokens from a response, streamed or not: the largest value of each field seen."""
    u = {k: max((int(m) for m in r.findall(raw)), default=0) for k, r in USAGE.items()}
    return {"in_tokens": u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"],
            "out_tokens": u["output_tokens"]}


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    key: str
    provider: str
    model: str
    log: str | None = None
    spills: dict = {}  # request body sha256 -> spill retries so far
    spill_lock = threading.Lock()

    def _body(self) -> bytes:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.info = {}
        if self.command == "POST" and self.path.split("?")[0].endswith("/messages") and body:
            try:
                req = json.loads(body)
            except ValueError:
                return body
            req["model"] = Proxy.model
            req["provider"] = {"order": [Proxy.provider], "allow_fallbacks": False}
            stripped = [k for k in STRIP if req.pop(k, None) is not None]
            marks = strip_cache_marks(req) if Proxy.model.startswith(STRIP_CACHE_PREFIXES) else None
            msgs = req.get("messages", [])
            self.info = {"msgs": len(msgs), "stripped": stripped, **({"cache_marks": marks} if marks is not None else {}),
                         "effort": (req.get("output_config") or {}).get("effort"), "stream": req.get("stream"),
                         "thinking": (req.get("thinking") or {}).get("type"),
                         "thinking_chars": sum(len(c.get("thinking", "")) for m in msgs if m.get("role") == "assistant"
                                               and isinstance(m.get("content"), list) for c in m["content"]
                                               if isinstance(c, dict) and c.get("type") == "thinking")}
            body = json.dumps(req).encode()
        return body

    def _check(self, gen: str, body: bytes | None, thinking: str, text: str, tools: int, stop: str | None) -> bool:
        """True if this reply must be retried: a non-tool stop whose generation did not finish (OpenRouter's record),
        or the thinking-spill signature (at most SPILL_RETRIES per identical request). Logs into self.info."""
        if stop in (None, "tool_use") and not (stop is None and not tools and text):
            return False
        if gen:
            ok, why = finished(gen, Proxy.key)
            self.info["finish_check"] = why
            if ok is False:
                self.info["retry_incomplete"] = True
                return True
        if not is_spill(thinking, text, tools, stop):
            return False
        try:  # the same request whether streamed or not (Claude Code falls back to stream: false after errors)
            key = hashlib.sha256(json.dumps({k: v for k, v in json.loads(body or b"{}").items() if k != "stream"},
                                            sort_keys=True).encode()).hexdigest()
        except ValueError:
            key = hashlib.sha256(body or b"").hexdigest()
        with Proxy.spill_lock:
            n = Proxy.spills.get(key, 0) + 1
            Proxy.spills[key] = n
        self.info["spill_attempt"] = n
        retry = n <= SPILL_RETRIES
        if retry:
            self.info["retry_spill"] = True
        if Proxy.log:
            d = os.path.join(os.path.dirname(Proxy.log), "spill_retries")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{len(os.listdir(d)) + 1:03d}.json"), "w") as f:
                json.dump({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "generation": gen, "request_sha256": key,
                           "attempt": n, "retried": retry, "thinking": thinking, "text": text}, f, indent=1)
        return retry

    def _forward(self) -> None:
        self.info = {}
        body = self._body() if self.command == "POST" else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        headers["Authorization"] = f"Bearer {Proxy.key}"
        headers["Accept-Encoding"] = "identity"
        if body is not None:
            headers["Content-Length"] = str(len(body))
        t0 = time.time()
        status, gen, started, retries, err_body = 502, "", False, [], None
        try:
            for attempt in range(len(RETRIES) + 1):
                conn = http.client.HTTPSConnection(UPSTREAM, timeout=900, context=ssl.create_default_context())
                try:
                    conn.request(self.command, PREFIX + self.path, body=body, headers=headers)
                    r = conn.getresponse()
                except OSError as e:
                    conn.close()
                    status, err_body = 502, f"upstream unreachable: {type(e).__name__}"
                    if attempt < len(RETRIES):
                        retries.append(status); time.sleep(RETRIES[attempt]); continue
                    data = json.dumps({"type": "error", "error": {"type": "api_error", "message": err_body}}).encode()
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                status, gen = r.status, r.getheader("x-generation-id") or ""
                if status in RETRY_STATUS and attempt < len(RETRIES) and self.command == "POST":
                    err_body = r.read().decode("utf-8", "replace")[:4000]
                    conn.close()
                    retries.append(status); time.sleep(RETRIES[attempt]); continue
                break
            sse = "event-stream" in (r.getheader("Content-Type") or "")
            is_msg = self.command == "POST" and self.path.split("?")[0].endswith("/messages")
            if not sse and is_msg and status == 200:
                # a non-streaming reply (Claude Code falls back to these after stream errors): read it whole, check it,
                # then answer it, or answer 529 overloaded instead
                whole = r.read()
                try:
                    j = json.loads(whole)
                except ValueError:
                    j = {}
                content = j.get("content") or []
                retry = self._check(gen, body,
                                    "".join(c.get("thinking", "") for c in content if c.get("type") == "thinking"),
                                    "".join(c.get("text", "") for c in content if c.get("type") == "text"),
                                    sum(c.get("type") == "tool_use" for c in content), j.get("stop_reason"))
                data = OVERLOADED_JSON if retry else whole
                self.send_response(529 if retry else 200)
                for k, v in r.getheaders():
                    if k.lower() not in HOP:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                started = True
                self.wfile.write(data)
                self.info.update(usage(whole), stop_reason=j.get("stop_reason"), served=j.get("provider"))
                conn.close()
                return
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            started = True
            raw, pend, held = [], b"", []   # held: the reply's content events, released once the stream has ended
            wlock, done = threading.Lock(), threading.Event()

            def send(data: bytes) -> None:
                if data:
                    with wlock:
                        self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                        self.wfile.flush()

            def keepalive() -> None:
                while not done.wait(10):
                    try:
                        send(b'event: ping\ndata: {"type": "ping"}\n\n')
                    except OSError:
                        return

            if sse:
                threading.Thread(target=keepalive, daemon=True).start()
            broken = None   # an upstream failure while reading (Alibaba 502s mid-generation also arrive as resets)
            try:
                while chunk := r.read1(65536):
                    raw.append(chunk)
                    if not sse:
                        send(chunk)
                        continue
                    pend += chunk
                    *events, pend = pend.split(b"\n\n")
                    for ev in events:
                        head = ev.lstrip()
                        if not held and (head.startswith(b"event: message_start") or head.startswith(b"event: ping")
                                         or head.startswith(b":")):
                            send(ev + b"\n\n")
                        else:
                            held.append(ev + b"\n\n")
            except OSError as e:
                if not sse:
                    raise
                broken = f"{type(e).__name__}: {e}"
            finally:
                done.set()
            whole = b"".join(raw)
            tail = b"".join(held) + pend
            if sse and status == 200 and (broken or self._check(gen, body, *reply(held))):
                if broken:
                    self.info.update(finish_check=f"upstream broke mid-stream: {broken}"[:300], retry_incomplete=True)
                tail = OVERLOADED_SSE
            send(tail)
            self.wfile.write(b"0\r\n\r\n")
            self.info.update(usage(whole))
            stops, served = STOP.findall(whole), SERVED.findall(whole)
            self.info.update(stop_reason=stops[-1].decode() if stops else None,
                             served=served[-1].decode() if served else r.getheader("x-openrouter-provider"))
            if status != 200:
                err_body = whole.decode("utf-8", "replace")[:4000]
            conn.close()
        except OSError as e:  # after the response started (upstream reset / timeout, or Claude Code hung up)
            self.close_connection = True
            err_body = f"{'mid-stream' if started else 'before response'}: {type(e).__name__}: {e}"[:4000]
            if not started:
                status = 502
        finally:
            if Proxy.log:
                with open(Proxy.log, "a") as f:
                    f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "method": self.command,
                                        "path": self.path, "status": status, "s": round(time.time() - t0, 2),
                                        "model": Proxy.model, "provider": Proxy.provider, "generation": gen,
                                        **({"retries": retries} if retries else {}),
                                        **({"error_body": err_body} if err_body else {}),
                                        **getattr(self, "info", {})}) + "\n")

    def do_GET(self) -> None:
        self._forward()

    def do_POST(self) -> None:
        self._forward()

    def log_message(self, fmt, *args) -> None:  # quiet
        pass


def read_key(path: str) -> str:
    for line in open(path):
        m = re.match(r"\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*['\"]?([^'\"\s]+)", line)
        if m:
            return m.group(1)
    raise SystemExit(f"no OPENROUTER_API_KEY in {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", required=True, help="host:port")
    ap.add_argument("--key-file", required=True, help="a .env file with OPENROUTER_API_KEY=...")
    ap.add_argument("--provider", default="alibaba", help="OpenRouter provider slug to pin")
    ap.add_argument("--model", default="qwen/qwen3.8-2.4t-a95b")
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    Proxy.key, Proxy.provider, Proxy.model, Proxy.log = read_key(a.key_file), a.provider, a.model, a.log
    host, port = a.listen.rsplit(":", 1)
    ThreadingHTTPServer((host, int(port)), Proxy).serve_forever()


if __name__ == "__main__":
    main()
