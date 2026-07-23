"""Restricted HTTPS CONNECT relay for Docker Desktop on Windows.

Docker containers on some Windows networks cannot complete TLS handshakes with
selected cloud APIs, while the Windows host can. This relay keeps TLS end-to-end
and only permits the explicitly configured HTTPS endpoints.
"""

from __future__ import annotations

import argparse
import selectors
import socket
import socketserver


ALLOWED_TARGETS = {
    ("dashscope.aliyuncs.com", 443),
    ("cls.tencentcloudapi.com", 443),
}
MAX_LINE_BYTES = 8192


def parse_connect_target(authority: str) -> tuple[str, int]:
    host, separator, port_text = authority.rpartition(":")
    if not separator or not host or not port_text.isdigit():
        raise ValueError("invalid CONNECT target")
    return host.rstrip(".").lower(), int(port_text)


def is_allowed_target(host: str, port: int) -> bool:
    return (host.rstrip(".").lower(), port) in ALLOWED_TARGETS


class ConnectHandler(socketserver.StreamRequestHandler):
    timeout = 30

    def handle(self) -> None:
        request_line = self.rfile.readline(MAX_LINE_BYTES).decode("ascii", errors="replace")
        try:
            method, authority, _ = request_line.strip().split(" ", 2)
            host, port = parse_connect_target(authority)
        except ValueError:
            self.wfile.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            return

        self._consume_headers()
        if method.upper() != "CONNECT" or not is_allowed_target(host, port):
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return

        try:
            upstream = socket.create_connection((host, port), timeout=15)
        except OSError:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            return

        with upstream:
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            self._relay(upstream)

    def _consume_headers(self) -> None:
        while True:
            line = self.rfile.readline(MAX_LINE_BYTES)
            if not line or line in (b"\r\n", b"\n"):
                return

    def _relay(self, upstream: socket.socket) -> None:
        selector = selectors.DefaultSelector()
        selector.register(self.connection, selectors.EVENT_READ, upstream)
        selector.register(upstream, selectors.EVENT_READ, self.connection)
        try:
            while True:
                events = selector.select(timeout=60)
                if not events:
                    return
                for key, _ in events:
                    data = key.fileobj.recv(65536)
                    if not data:
                        return
                    key.data.sendall(data)
        finally:
            selector.close()


class ThreadingRelay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Restricted cloud HTTPS relay")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()

    with ThreadingRelay((args.host, args.port), ConnectHandler) as server:
        print(f"Restricted cloud HTTPS relay listening on {args.host}:{args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
