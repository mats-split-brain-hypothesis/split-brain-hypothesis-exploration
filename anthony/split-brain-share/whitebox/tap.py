"""A logging tap between Claude Code and api_proxy.py: writes every request body as Claude Code sends it on the wire
(not as its session log records it) to DIR/NNN.json, and passes the response through.

    python3 tap.py --listen HOST:PORT --upstream 127.0.0.1:P --dir out/tap
"""

import argparse
import http.client
import itertools
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

N = itertools.count()


class Tap(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream: tuple[str, int]
    dir: Path

    def _go(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
        if body:
            (Tap.dir / f"{next(N):03d}.json").write_text(json.dumps(
                {"path": self.path, "headers": {k: v for k, v in self.headers.items() if k.lower() != "authorization"},
                 "body": json.loads(body)}, indent=1))
        conn = http.client.HTTPConnection(*Tap.upstream, timeout=900)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "connection")}
        if body is not None:
            headers["Content-Length"] = str(len(body))
        conn.request(self.command, self.path, body=body, headers=headers)
        r = conn.getresponse()
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        while chunk := r.read1(65536):
            self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        conn.close()

    do_GET = do_POST = _go

    def log_message(self, fmt, *args) -> None:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", required=True)
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    h, p = a.upstream.rsplit(":", 1)
    Tap.upstream, Tap.dir = (h, int(p)), Path(a.dir)
    Tap.dir.mkdir(parents=True, exist_ok=True)
    host, port = a.listen.rsplit(":", 1)
    ThreadingHTTPServer((host, int(port)), Tap).serve_forever()


if __name__ == "__main__":
    main()
