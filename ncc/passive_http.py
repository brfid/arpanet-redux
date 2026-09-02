"""Neutral HTTP transport for loopback-only passive NCC applications."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import MappingProxyType
from typing import Callable, Mapping, TypeVar


IPV4_LOOPBACK = "127.0.0.1"
JSON_CONTENT_TYPE = "application/json; charset=utf-8"
SUPPORTED_METHODS = frozenset({"GET", "HEAD"})
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
    "style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "frame-ancestors 'none'; form-action 'none'; base-uri 'none'"
)
_EMPTY_HEADERS: Mapping[str, str] = MappingProxyType({})
_METHOD_HEADERS: Mapping[str, str] = MappingProxyType({"Allow": "GET, HEAD"})


@dataclass(frozen=True)
class PassiveHTTPResponse:
    """Wire-ready application response consumed by the shared handler."""

    status: int
    content_type: str
    body: str
    headers: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


ResponseT = TypeVar("ResponseT", bound=PassiveHTTPResponse)
ResponseFactory = Callable[[int, str, str, Mapping[str, str]], ResponseT]
ServerT = TypeVar("ServerT", bound="PassiveHTTPServer")


class PassiveHTTPServer(ThreadingHTTPServer):
    """Threaded loopback server whose application resolves fixed routes."""

    def resolve_response(self, method: str, target: str) -> PassiveHTTPResponse:
        """Return the application-owned response for one request."""

        raise NotImplementedError


class PassiveHTTPRequestHandler(BaseHTTPRequestHandler):
    """Serialize passive application responses without owning their routes."""

    server: PassiveHTTPServer
    sys_version = ""
    quiet_logging = False

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
        """Apply the adapter's existing terminal logging policy."""

        if not self.quiet_logging:
            super().log_message(format, *args)

    def _dispatch(self, method: str) -> None:
        response = self.server.resolve_response(method, self.path)
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


def bind_loopback_server(
    server_type: type[ServerT],
    handler_type: type[BaseHTTPRequestHandler],
    *,
    port: int,
    port_subject: str,
) -> ServerT:
    """Validate a port and construct one IPv4-loopback server."""

    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port < 65536:
        raise ValueError(f"{port_subject} port must be an integer in 0..65535")
    return server_type((IPV4_LOOPBACK, port), handler_type)


def json_response(
    response_factory: ResponseFactory[ResponseT],
    status: int,
    document: Mapping[str, object],
    *,
    headers: Mapping[str, str] = _EMPTY_HEADERS,
) -> ResponseT:
    """Serialize one deterministic JSON response."""

    return response_factory(
        status,
        JSON_CONTENT_TYPE,
        json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n",
        headers,
    )


def method_not_allowed_response(
    response_factory: ResponseFactory[ResponseT],
    method: str,
    message: str,
) -> ResponseT | None:
    """Return the standard passive rejection, or None for GET and HEAD."""

    if method in SUPPORTED_METHODS:
        return None
    return json_response(
        response_factory,
        405,
        {"error": message},
        headers=_METHOD_HEADERS,
    )


def response_for_method(
    response_factory: ResponseFactory[ResponseT],
    method: str,
    response: ResponseT,
) -> ResponseT:
    """Preserve the existing empty-body representation for HEAD."""

    if method != "HEAD":
        return response
    return response_factory(
        response.status,
        response.content_type,
        "",
        response.headers,
    )
