"""Loopback-only HTTP serving for the passive coexistence desk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from .coexistence_display import CoexistenceDisplay
from .coexistence_viewer import render_coexistence_display_html
from .passive_http import (
    PassiveHTTPResponse,
    PassiveHTTPRequestHandler,
    PassiveHTTPServer,
    bind_loopback_server,
    json_response,
    method_not_allowed_response,
    response_for_method,
)


class CoexistenceDisplayHTTPServer(PassiveHTTPServer):
    """A GET/HEAD-only loopback server over one validated completed desk."""

    display: CoexistenceDisplay
    page: str

    def resolve_response(self, method: str, target: str) -> CoexistenceDisplayResponse:
        return coexistence_display_response(self.display, self.page, method, target)


@dataclass(frozen=True)
class CoexistenceDisplayResponse(PassiveHTTPResponse):
    """One transport-neutral response from the passive local application."""


def create_coexistence_display_server(
    display: CoexistenceDisplay,
    *,
    port: int = 8767,
) -> CoexistenceDisplayHTTPServer:
    """Create the loopback server without starting it or opening a browser."""

    server = bind_loopback_server(
        CoexistenceDisplayHTTPServer,
        _DisplayHandler,
        port=port,
        port_subject="display",
    )
    server.display = display
    server.page = render_coexistence_display_html()
    return server


def coexistence_display_response(
    display: CoexistenceDisplay,
    page: str,
    method: str,
    target: str,
) -> CoexistenceDisplayResponse:
    """Resolve one HTTP-shaped request without opening a listening socket."""

    rejected = method_not_allowed_response(
        CoexistenceDisplayResponse,
        method,
        "passive display accepts GET and HEAD only",
    )
    if rejected is not None:
        return rejected
    path = urlsplit(target).path
    if path == "/":
        response = CoexistenceDisplayResponse(200, "text/html; charset=utf-8", page)
    elif path == "/api/snapshot":
        response = CoexistenceDisplayResponse(
            200,
            "application/json; charset=utf-8",
            display.snapshot().to_json(),
        )
    elif path == "/favicon.ico":
        response = CoexistenceDisplayResponse(204, "image/x-icon", "")
    else:
        response = _json_response(404, {"error": "not found"})
    return response_for_method(CoexistenceDisplayResponse, method, response)


def _json_response(
    status: int,
    document: Mapping[str, object],
) -> CoexistenceDisplayResponse:
    return json_response(CoexistenceDisplayResponse, status, document)


class _DisplayHandler(PassiveHTTPRequestHandler):
    server: CoexistenceDisplayHTTPServer
    server_version = "ARPANETReduxNCCCoexistence/1"
    quiet_logging = True
