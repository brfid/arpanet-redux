from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from socketserver import ThreadingMixIn
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import ncc.board_server as board_server
import ncc.coexistence_server as coexistence_server
import ncc.historical_server as historical_server
import ncc.journey_server as journey_server


@dataclass(frozen=True)
class PassiveDisplayCase:
    module: ModuleType
    server_name: str
    handler_name: str
    factory_name: str
    renderer_name: str
    state_name: str
    server_version: str
    port_subject: str
    method_error: str
    quiet: bool
    renderer_uses_topology: bool = False


CASES = (
    PassiveDisplayCase(
        board_server,
        "NccBoardHTTPServer",
        "_BoardHandler",
        "create_ncc_board_server",
        "render_ncc_board_html",
        "display",
        "ARPANETReduxNCCBoard/1",
        "board",
        "passive console accepts GET and HEAD only",
        True,
        True,
    ),
    PassiveDisplayCase(
        coexistence_server,
        "CoexistenceDisplayHTTPServer",
        "_DisplayHandler",
        "create_coexistence_display_server",
        "render_coexistence_display_html",
        "display",
        "ARPANETReduxNCCCoexistence/1",
        "display",
        "passive display accepts GET and HEAD only",
        True,
    ),
    PassiveDisplayCase(
        historical_server,
        "HistoricalDisplayHTTPServer",
        "_DisplayHandler",
        "create_historical_display_server",
        "render_historical_display_html",
        "observer",
        "ARPANETReduxNCC/1",
        "display",
        "passive display accepts GET and HEAD only",
        False,
        True,
    ),
    PassiveDisplayCase(
        journey_server,
        "JourneyDisplayHTTPServer",
        "_DisplayHandler",
        "create_journey_display_server",
        "render_journey_display_html",
        "observer",
        "ARPANETReduxNCCJourney/1",
        "display",
        "passive display accepts GET and HEAD only",
        True,
    ),
)


class PassiveDisplayTransportTests(unittest.TestCase):
    def test_idle_browser_connection_cannot_block_another_request(self) -> None:
        for case in CASES:
            server_type = getattr(case.module, case.server_name)
            with self.subTest(server_type=server_type.__name__):
                self.assertTrue(issubclass(server_type, ThreadingMixIn))
                self.assertTrue(server_type.daemon_threads)

    def test_factories_bind_ipv4_loopback_and_preserve_server_identity(self) -> None:
        for case in CASES:
            application = SimpleNamespace(shared_topology=object())
            factory = getattr(case.module, case.factory_name)
            handler_type = getattr(case.module, case.handler_name)
            with self.subTest(server_type=case.server_name):
                with (
                    patch.object(case.module, case.server_name) as server_type,
                    patch.object(
                        case.module,
                        case.renderer_name,
                        return_value="display page",
                    ) as renderer,
                ):
                    server = factory(application, port=0)

                server_type.assert_called_once_with(("127.0.0.1", 0), handler_type)
                self.assertIs(server, server_type.return_value)
                self.assertIs(getattr(server, case.state_name), application)
                self.assertEqual(server.page, "display page")
                if case.renderer_uses_topology:
                    renderer.assert_called_once_with(application.shared_topology)
                else:
                    renderer.assert_called_once_with()
                self.assertEqual(handler_type.server_version, case.server_version)
                self.assertEqual(handler_type.sys_version, "")

    def test_factories_reject_invalid_ports_without_binding(self) -> None:
        for case in CASES:
            factory = getattr(case.module, case.factory_name)
            application = SimpleNamespace(shared_topology=object())
            for port in (True, -1, 65536, 1.5):
                with self.subTest(server_type=case.server_name, port=port):
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"^{case.port_subject} port must be an integer in 0\.\.65535$",
                    ):
                        factory(application, port=port)

    def test_handlers_serialize_each_application_adapter_identically(self) -> None:
        security_headers = [
            ("Cache-Control", "no-store"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Content-Security-Policy", historical_server.CONTENT_SECURITY_POLICY),
        ]
        for case in CASES:
            with self.subTest(server_type=case.server_name):
                status, headers, body = self._request(case, "GET", "/")
                self.assertEqual(status, 200)
                self.assertEqual(
                    headers,
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        *security_headers,
                        ("Content-Length", "5"),
                    ],
                )
                self.assertEqual(body, "caf\N{LATIN SMALL LETTER E WITH ACUTE}".encode())

                status, headers, body = self._request(
                    case,
                    "GET",
                    "/api/snapshot",
                )
                self.assertEqual(status, 200)
                self.assertEqual(headers[-1], ("Content-Length", "23"))
                self.assertEqual(body, b'{"application":"test"}\n')

                status, headers, body = self._request(case, "GET", "/report")
                self.assertEqual(status, 404)
                self.assertEqual(headers[-1], ("Content-Length", "22"))
                self.assertEqual(body, b'{"error":"not found"}\n')

                status, headers, body = self._request(case, "HEAD", "/")
                self.assertEqual(status, 200)
                self.assertEqual(headers[-1], ("Content-Length", "0"))
                self.assertEqual(body, b"")

                for method in ("POST", "PUT", "PATCH", "DELETE"):
                    status, headers, body = self._request(
                        case,
                        method,
                        "/api/snapshot",
                    )
                    expected = (
                        f'{{"error":"{case.method_error}"}}\n'.encode("utf-8")
                    )
                    self.assertEqual(status, 405)
                    self.assertEqual(headers[-2], ("Allow", "GET, HEAD"))
                    self.assertEqual(
                        headers[-1],
                        ("Content-Length", str(len(expected))),
                    )
                    self.assertEqual(body, expected)

    def test_handler_logging_matches_each_existing_application(self) -> None:
        for case in CASES:
            handler_type = getattr(case.module, case.handler_name)
            handler = handler_type.__new__(handler_type)
            with self.subTest(server_type=case.server_name):
                with patch.object(
                    BaseHTTPRequestHandler,
                    "log_message",
                    autospec=True,
                ) as base_log:
                    handler.log_message("request %s", "complete")

                if case.quiet:
                    base_log.assert_not_called()
                else:
                    base_log.assert_called_once_with(
                        handler,
                        "request %s",
                        "complete",
                    )

    def _request(
        self,
        case: PassiveDisplayCase,
        method: str,
        target: str,
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        snapshot = SimpleNamespace(to_json=lambda: '{"application":"test"}\n')
        application = SimpleNamespace(snapshot=lambda: snapshot)
        server_type = getattr(case.module, case.server_name)
        server = server_type.__new__(server_type)
        setattr(server, case.state_name, application)
        server.page = "caf\N{LATIN SMALL LETTER E WITH ACUTE}"

        handler_type = getattr(case.module, case.handler_name)
        handler = handler_type.__new__(handler_type)
        handler.server = server
        handler.path = target
        handler.wfile = BytesIO()
        statuses: list[int] = []
        headers: list[tuple[str, str]] = []
        handler.send_response = statuses.append  # type: ignore[method-assign]
        handler.send_header = lambda name, value: headers.append(  # type: ignore[method-assign]
            (name, value)
        )
        handler.end_headers = lambda: None  # type: ignore[method-assign]

        getattr(handler, f"do_{method}")()

        self.assertEqual(len(statuses), 1)
        return statuses[0], headers, handler.wfile.getvalue()


if __name__ == "__main__":
    unittest.main()
