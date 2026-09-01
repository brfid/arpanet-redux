"""Loopback-only HTTP serving for the passive historical NCC display."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from .historical_display import HistoricalDisplayError, HistoricalDisplayObserver
from .historical_viewer import render_historical_display_html
from .viewer import render_summary_html


class HistoricalDisplayHTTPServer(ThreadingHTTPServer):
    """A GET/HEAD-only loopback server over one passive observer."""

    observer: HistoricalDisplayObserver
    page: str


@dataclass(frozen=True)
class HistoricalDisplayResponse:
    """One transport-neutral result from the GET/HEAD display application."""

    status: int
    content_type: str
    body: str
    headers: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
    "style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "frame-ancestors 'none'; form-action 'none'; base-uri 'none'"
)


def create_historical_display_server(
    observer: HistoricalDisplayObserver,
    *,
    port: int = 8765,
) -> HistoricalDisplayHTTPServer:
    """Create a loopback server without starting a thread or opening a browser."""

    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port < 65536:
        raise ValueError("display port must be an integer in 0..65535")
    server = HistoricalDisplayHTTPServer(("127.0.0.1", port), _DisplayHandler)
    server.observer = observer
    server.page = render_historical_display_html(observer.shared_topology)
    return server


def historical_display_response(
    observer: HistoricalDisplayObserver,
    page: str,
    method: str,
    target: str,
) -> HistoricalDisplayResponse:
    """Resolve one HTTP-shaped request without opening a listening socket."""

    if method not in {"GET", "HEAD"}:
        return HistoricalDisplayResponse(
            status=405,
            content_type="application/json; charset=utf-8",
            body=json.dumps(
                {"error": "passive display accepts GET and HEAD only"},
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n",
            headers=MappingProxyType({"Allow": "GET, HEAD"}),
        )
    path = urlsplit(target).path
    try:
        if path == "/":
            response = HistoricalDisplayResponse(200, "text/html; charset=utf-8", page)
        elif path == "/api/snapshot":
            response = HistoricalDisplayResponse(
                200,
                "application/json; charset=utf-8",
                observer.snapshot().to_json(),
            )
        elif path == "/completed":
            snapshot = observer.snapshot()
            if snapshot.mode != "completed" or snapshot.completed_summary is None:
                response = _json_response(
                    409,
                    {"error": "validated completed-summary handoff is not available"},
                )
            else:
                response = HistoricalDisplayResponse(
                    200,
                    "text/html; charset=utf-8",
                    render_summary_html(snapshot.completed_summary),
                )
        elif path == "/favicon.ico":
            response = HistoricalDisplayResponse(204, "image/x-icon", "")
        else:
            response = _json_response(404, {"error": "not found"})
    except HistoricalDisplayError as error:
        response = _json_response(409, {"error": str(error)})
    if method == "HEAD":
        return HistoricalDisplayResponse(
            response.status,
            response.content_type,
            "",
            response.headers,
        )
    return response


def _json_response(status: int, document: Mapping[str, object]) -> HistoricalDisplayResponse:
    return HistoricalDisplayResponse(
        status,
        "application/json; charset=utf-8",
        json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n",
    )


class _DisplayHandler(BaseHTTPRequestHandler):
    server: HistoricalDisplayHTTPServer
    server_version = "ARPANETReduxNCC/1"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler interface
        self._dispatch("GET")

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler interface
        self._dispatch("HEAD")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler interface
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler interface
        self._dispatch("PUT")

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler interface
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler interface
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        response = historical_display_response(
            self.server.observer,
            self.server.page,
            method,
            self.path,
        )
        encoded = response.body.encode("utf-8")
        self.send_response(response.status)
        self._security_headers(response.content_type)
        for name, value in response.headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(encoded)

    def _security_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
