"""Loopback-only HTTP serving for the passive historical NCC display."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from .historical_display import HistoricalDisplayError, HistoricalDisplayObserver
from .historical_viewer import render_historical_display_html
from .passive_http import (
    CONTENT_SECURITY_POLICY,
    PassiveHTTPResponse,
    PassiveHTTPRequestHandler,
    PassiveHTTPServer,
    bind_loopback_server,
    json_response,
    method_not_allowed_response,
    response_for_method,
)
from .viewer import render_summary_html


class HistoricalDisplayHTTPServer(PassiveHTTPServer):
    """A GET/HEAD-only loopback server over one passive observer."""

    observer: HistoricalDisplayObserver
    page: str

    def resolve_response(self, method: str, target: str) -> HistoricalDisplayResponse:
        return historical_display_response(self.observer, self.page, method, target)


@dataclass(frozen=True)
class HistoricalDisplayResponse(PassiveHTTPResponse):
    """One transport-neutral result from the GET/HEAD display application."""


def create_historical_display_server(
    observer: HistoricalDisplayObserver,
    *,
    port: int = 8765,
) -> HistoricalDisplayHTTPServer:
    """Create a loopback server without starting a thread or opening a browser."""

    server = bind_loopback_server(
        HistoricalDisplayHTTPServer,
        _DisplayHandler,
        port=port,
        port_subject="display",
    )
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

    rejected = method_not_allowed_response(
        HistoricalDisplayResponse,
        method,
        "passive display accepts GET and HEAD only",
    )
    if rejected is not None:
        return rejected
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
    return response_for_method(HistoricalDisplayResponse, method, response)


def _json_response(status: int, document: Mapping[str, object]) -> HistoricalDisplayResponse:
    return json_response(HistoricalDisplayResponse, status, document)


class _DisplayHandler(PassiveHTTPRequestHandler):
    server: HistoricalDisplayHTTPServer
    server_version = "ARPANETReduxNCC/1"
