"""Loopback-only HTTP serving for the passive NCC message-journey display."""

from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from .historical_server import CONTENT_SECURITY_POLICY
from .journey_display import JourneyDisplayError, JourneyDisplayObserver
from .journey_viewer import render_journey_display_html


class JourneyDisplayHTTPServer(HTTPServer):
    """A GET-only loopback server over one passive journey observer."""

    observer: JourneyDisplayObserver
    page: str


@dataclass(frozen=True)
class JourneyDisplayResponse:
    """One transport-neutral result from the GET-only journey application."""

    status: int
    content_type: str
    body: str
    headers: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


def create_journey_display_server(
    observer: JourneyDisplayObserver,
    *,
    port: int = 8766,
) -> JourneyDisplayHTTPServer:
    """Create a loopback server without starting a thread or opening a browser."""

    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port < 65536:
        raise ValueError("display port must be an integer in 0..65535")
    server = JourneyDisplayHTTPServer(("127.0.0.1", port), _DisplayHandler)
    server.observer = observer
    server.page = render_journey_display_html()
    return server


def journey_display_response(
    observer: JourneyDisplayObserver,
    page: str,
    method: str,
    target: str,
) -> JourneyDisplayResponse:
    """Resolve one HTTP-shaped request without opening a listening socket."""

    if method not in {"GET", "HEAD"}:
        return JourneyDisplayResponse(
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
            response = JourneyDisplayResponse(200, "text/html; charset=utf-8", page)
        elif path == "/api/snapshot":
            response = JourneyDisplayResponse(
                200,
                "application/json; charset=utf-8",
                observer.snapshot().to_json(),
            )
        elif path == "/favicon.ico":
            response = JourneyDisplayResponse(204, "image/x-icon", "")
        else:
            response = _json_response(404, {"error": "not found"})
    except JourneyDisplayError as error:
        response = _json_response(409, {"error": str(error)})
    if method == "HEAD":
        return JourneyDisplayResponse(
            response.status,
            response.content_type,
            "",
            response.headers,
        )
    return response


def _json_response(status: int, document: Mapping[str, object]) -> JourneyDisplayResponse:
    return JourneyDisplayResponse(
        status,
        "application/json; charset=utf-8",
        json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n",
    )


class _DisplayHandler(BaseHTTPRequestHandler):
    server: JourneyDisplayHTTPServer
    server_version = "ARPANETReduxNCCJourney/1"
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

    def log_message(self, format: str, *args: object) -> None:
        """Keep the polling observer quiet in the operator's terminal."""

        return

    def _dispatch(self, method: str) -> None:
        response = journey_display_response(
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
