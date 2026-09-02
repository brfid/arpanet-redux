"""Loopback-only HTTP serving for the passive NCC operator console."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from .board_display import NccBoardDisplay, NccBoardError, NccBoardPending
from .board_viewer import render_ncc_board_html
from .passive_http import (
    PassiveHTTPResponse,
    PassiveHTTPRequestHandler,
    PassiveHTTPServer,
    bind_loopback_server,
    json_response,
    method_not_allowed_response,
    response_for_method,
)


class NccBoardHTTPServer(PassiveHTTPServer):
    """A GET/HEAD-only loopback server over one passive console adapter."""

    display: NccBoardDisplay
    page: str

    def resolve_response(self, method: str, target: str) -> NccBoardResponse:
        return ncc_board_response(self.display, self.page, method, target)


@dataclass(frozen=True)
class NccBoardResponse(PassiveHTTPResponse):
    """One transport-neutral response from the passive console application."""


def create_ncc_board_server(
    display: NccBoardDisplay,
    *,
    port: int = 8765,
) -> NccBoardHTTPServer:
    """Create the loopback server without starting it or opening a browser."""

    server = bind_loopback_server(
        NccBoardHTTPServer,
        _BoardHandler,
        port=port,
        port_subject="board",
    )
    server.display = display
    server.page = render_ncc_board_html(display.shared_topology)
    return server


def ncc_board_response(
    display: NccBoardDisplay,
    page: str,
    method: str,
    target: str,
) -> NccBoardResponse:
    """Resolve one HTTP-shaped request without opening a listening socket."""

    rejected = method_not_allowed_response(
        NccBoardResponse,
        method,
        "passive console accepts GET and HEAD only",
    )
    if rejected is not None:
        return rejected
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
    elif path == "/favicon.ico":
        response = NccBoardResponse(204, "image/x-icon", "")
    else:
        response = _json_response(404, {"error": "not found"})
    return response_for_method(NccBoardResponse, method, response)


def _json_response(status: int, document: Mapping[str, object]) -> NccBoardResponse:
    return json_response(NccBoardResponse, status, document)


class _BoardHandler(PassiveHTTPRequestHandler):
    server: NccBoardHTTPServer
    server_version = "ARPANETReduxNCCBoard/1"
    quiet_logging = True
