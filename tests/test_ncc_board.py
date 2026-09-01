from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from ncc.board_display import NccBoardDisplay, NccBoardPending
from ncc.board_server import (
    create_ncc_board_server,
    ncc_board_response,
)
from ncc.board_viewer import render_ncc_board_html
from tests.test_ncc_coexistence_display import CoexistenceFixture, TOPOLOGY


class NccBoardTests(unittest.TestCase):
    def test_waits_with_configured_map_before_result_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = Path(directory_name) / "ncc-pdp11-its-coexistence-future"
            display = NccBoardDisplay(result, TOPOLOGY)
            page = render_ncc_board_html(display.shared_topology)

            with self.assertRaisesRegex(NccBoardPending, "historical event stream"):
                display.snapshot()
            response = ncc_board_response(display, page, "report", "GET", "/api/snapshot")

            self.assertEqual(response.status, 202)
            self.assertEqual(json.loads(response.body)["run_id"], result.name)
            self.assertIn("NCC network board", page)
            self.assertIn('data-component-id="imp:5"', page)
            self.assertIn('data-link-id="link:imp5-imp6-direct"', page)

    def test_switches_from_existing_live_snapshot_to_completed_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            manifest = fixture.manifest()
            terminal = {
                key: manifest.pop(key)
                for key in ("finished_utc", "outcome", "exit_status")
            }
            fixture.write_manifest(manifest)
            display = NccBoardDisplay(fixture.result, TOPOLOGY)

            live = display.snapshot().to_dict()
            self.assertEqual(live["mode"], "live")
            self.assertIn("direct", live)

            manifest.update(terminal)
            fixture.write_manifest(manifest)
            completed = display.snapshot().to_dict()
            self.assertEqual(completed["mode"], "completed")
            self.assertEqual(completed["application"]["state"], "passed")
            self.assertEqual(
                completed["journey"]["assessment"]["first_boundary_id"],
                "boundary:request:6",
            )

    def test_board_transport_keeps_report_read_only_and_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            display = NccBoardDisplay(fixture.result, TOPOLOGY)
            page = render_ncc_board_html(display.shared_topology)
            report_page = "completed report"

            root = ncc_board_response(display, page, report_page, "GET", "/")
            api = ncc_board_response(
                display,
                page,
                report_page,
                "GET",
                "/api/snapshot",
            )
            report = ncc_board_response(
                display,
                page,
                report_page,
                "GET",
                "/report",
            )
            head = ncc_board_response(
                display,
                page,
                report_page,
                "HEAD",
                "/api/snapshot",
            )
            mutation = ncc_board_response(
                display,
                page,
                report_page,
                "POST",
                "/api/snapshot",
            )
            arbitrary = ncc_board_response(
                display,
                page,
                report_page,
                "GET",
                "/etc/passwd",
            )

            self.assertEqual(root.status, 200)
            self.assertEqual(api.status, 200)
            self.assertEqual(json.loads(api.body)["mode"], "completed")
            self.assertEqual(report.status, 200)
            self.assertEqual(report.body, report_page)
            self.assertEqual(head.status, 200)
            self.assertEqual(head.body, "")
            self.assertEqual(mutation.status, 405)
            self.assertEqual(mutation.headers["Allow"], "GET, HEAD")
            self.assertEqual(arbitrary.status, 404)

            with patch("ncc.board_server.NccBoardHTTPServer") as server_type:
                server = create_ncc_board_server(display, port=0)
            server_type.assert_called_once_with(("127.0.0.1", 0), ANY)
            self.assertIs(server.display, display)

    def test_board_browser_is_presentation_only_and_accessible(self) -> None:
        display = NccBoardDisplay(Path("/tmp/nonexistent-ncc-board-result"), TOPOLOGY)
        page = render_ncc_board_html(display.shared_topology)

        self.assertIn("validated observations only", page)
        self.assertIn("prefers-reduced-motion", page)
        self.assertIn('fetch("/api/snapshot"', page)
        self.assertIn("focus-visible", page)
        self.assertIn('href="/report"', page)
        self.assertNotIn("repeating-linear-gradient", page)
        self.assertNotIn("data:image", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("<form", page)
        self.assertNotIn("WebSocket", page)


if __name__ == "__main__":
    unittest.main()
