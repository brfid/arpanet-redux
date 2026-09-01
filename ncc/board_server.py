"""Loopback-only HTTP serving for the passive NCC network board."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from .board_display import NccBoardDisplay, NccBoardError, NccBoardPending
from .board_viewer import render_ncc_board_html
from .coexistence_viewer import render_coexistence_display_html
from .historical_server import CONTENT_SECURITY_POLICY


class NccBoardHTTPServer(ThreadingHTTPServer):
    """A GET/HEAD-only loopback server over one passive board adapter."""

    display: NccBoardDisplay
    page: str
    report_page: str


@dataclass(frozen=True)
class NccBoardResponse:
    """One transport-neutral response from the passive board application."""

    status: int
    content_type: str
    body: str
    headers: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


def create_ncc_board_server(
    display: NccBoardDisplay,
    *,
    port: int = 8765,
) -> NccBoardHTTPServer:
    """Create the loopback server without starting it or opening a browser."""

    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port < 65536:
        raise ValueError("board port must be an integer in 0..65535")
    server = NccBoardHTTPServer(("127.0.0.1", port), _BoardHandler)
    server.display = display
    server.page = render_ncc_board_html(display.shared_topology)
    server.report_page = render_coexistence_display_html()
    return server


def ncc_board_response(
    display: NccBoardDisplay,
    page: str,
    report_page: str,
    method: str,
    target: str,
) -> NccBoardResponse:
    """Resolve one HTTP-shaped request without opening a listening socket."""

    if method not in {"GET", "HEAD"}:
        return NccBoardResponse(
            status=405,
            content_type="application/json; charset=utf-8",
            body=json.dumps(
                {"error": "passive board accepts GET and HEAD only"},
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n",
            headers=MappingProxyType({"Allow": "GET, HEAD"}),
        )
    path = urlsplit(target).path
    if path == "/":
        response = NccBoardResponse(200, "text/html; charset=utf-8", page)
    elif path == "/api/snapshot":
        try:
            response = NccBoardResponse(
                200,
                "application/json; charset=utf-8",
                display.snapshot().to_json(),
            )
        except NccBoardPending as error:
            response = _json_response(
                202,
                {
                    "status": "waiting",
                    "run_id": display.run_id,
                    "message": str(error),
                },
            )
        except NccBoardError as error:
            response = _json_response(409, {"error": str(error)})
    elif path == "/report":
        try:
            display.completed_display()
            response = NccBoardResponse(
                200,
                "text/html; charset=utf-8",
                report_page,
            )
        except NccBoardPending as error:
            response = _json_response(409, {"error": str(error)})
        except NccBoardError as error:
            response = _json_response(409, {"error": str(error)})
    elif path == "/favicon.ico":
        response = NccBoardResponse(204, "image/x-icon", "")
    else:
        response = _json_response(404, {"error": "not found"})
    if method == "HEAD":
        return NccBoardResponse(
            response.status,
            response.content_type,
            "",
            response.headers,
        )
    return response


def _json_response(status: int, document: Mapping[str, object]) -> NccBoardResponse:
    return NccBoardResponse(
        status,
        "application/json; charset=utf-8",
        json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n",
    )


class _BoardHandler(BaseHTTPRequestHandler):
    server: NccBoardHTTPServer
    server_version = "ARPANETReduxNCCBoard/1"
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
        """Keep the polling board quiet in the operator terminal."""

        return

    def _dispatch(self, method: str) -> None:
        response = ncc_board_response(
            self.server.display,
            self.server.page,
            self.server.report_page,
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
