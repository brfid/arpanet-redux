"""Loopback-only HTTP serving for the passive NCC message-journey display."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from .journey_display import JourneyDisplayError, JourneyDisplayObserver
from .journey_viewer import render_journey_display_html
from .passive_http import (
    PassiveHTTPResponse,
    PassiveHTTPRequestHandler,
    PassiveHTTPServer,
    bind_loopback_server,
    json_response,
    method_not_allowed_response,
    response_for_method,
)


class JourneyDisplayHTTPServer(PassiveHTTPServer):
    """A GET/HEAD-only loopback server over one passive journey observer."""

    observer: JourneyDisplayObserver
    page: str

    def resolve_response(self, method: str, target: str) -> JourneyDisplayResponse:
        return journey_display_response(self.observer, self.page, method, target)


@dataclass(frozen=True)
class JourneyDisplayResponse(PassiveHTTPResponse):
    """One transport-neutral result from the GET/HEAD journey application."""


def create_journey_display_server(
    observer: JourneyDisplayObserver,
    *,
    port: int = 8766,
) -> JourneyDisplayHTTPServer:
    """Create a loopback server without starting a thread or opening a browser."""

    server = bind_loopback_server(
        JourneyDisplayHTTPServer,
        _DisplayHandler,
        port=port,
        port_subject="display",
    )
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

    rejected = method_not_allowed_response(
        JourneyDisplayResponse,
        method,
        "passive display accepts GET and HEAD only",
    )
    if rejected is not None:
        return rejected
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
    return response_for_method(JourneyDisplayResponse, method, response)


def _json_response(status: int, document: Mapping[str, object]) -> JourneyDisplayResponse:
    return json_response(JourneyDisplayResponse, status, document)


class _DisplayHandler(PassiveHTTPRequestHandler):
    server: JourneyDisplayHTTPServer
    server_version = "ARPANETReduxNCCJourney/1"
    quiet_logging = True
