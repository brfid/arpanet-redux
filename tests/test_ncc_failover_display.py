from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ncc.board_display import NccBoardDisplay
from ncc.board_server import ncc_board_response
from ncc.board_viewer import render_ncc_board_html
from ncc.events import EventSource, NccEvent
from ncc.failover_display import FailoverDisplay, FailoverDisplayError
from ncc.historical_events import HistoricalEventRecorder
from ncc.message_journey import ObservationProvenance
from ncc.pdp11_its_failover_journey import (
    write_pdp11_its_failover_journey_stream,
)
from ncc.pdp11_its_journey import transaction_window_source
from ncc.shared_topology import load_shared_topology
from tests.test_pdp11_its_failover_journey import synthetic_traces

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "config" / "topologies" / "ncc-pdp11-its-application-failover.json"
CHECK_IDS = (
    "identity-chain",
    "relay-forwarded-before-cut",
    "relay-dropped-after-cut",
    "relay-no-unexpected-source",
    "same-session-post-cut-time",
    "network-unix-host-ready-before-open",
    "typed-alternate-journey",
    "ncc-reports-after-cut-from-all-imps",
    "mapping-remains-candidate-only",
    "clean-owned-processes",
    "clean-pinned-inputs",
    "application-outcome-passed",
    "outer-runtime-cleanup",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FailoverFixture:
    def __init__(self, parent: Path) -> None:
        self.result = parent / "ncc-pdp11-its-application-failover-fixture"
        self.result.mkdir()
        (self.result / "runtime").mkdir()
        self.run_id = self.result.name
        self.topology = load_shared_topology(TOPOLOGY)
        self.topology_document = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
        self._write_historical_stream()
        self._write_journeys()
        self._write_application()
        self._write_relay_and_cut()
        self._write_verdict()
        self._write_manifest()

    def _write_historical_stream(self) -> None:
        recorder = HistoricalEventRecorder(
            self.result / "historical-events.jsonl",
            run_id=self.run_id,
            started_at="2026-09-01T12:00:05Z",
            topology_id=self.topology.id,
            interface_id="binding:ncc-host0-imp5",
            topology=self.topology.topology,
            provenance=(
                {
                    "id": "source:fixture-receiver",
                    "kind": "project-authored-receiver",
                },
            ),
        )
        events = []
        sequence = 1
        for offset, imp in enumerate((5, 6, 7, 62), start=20):
            observed_at = f"2026-09-01T12:01:{offset:02d}Z"
            events.extend(
                (
                    NccEvent(
                        sequence=sequence,
                        observed_at=observed_at,
                        event_type="imp.report",
                        subject=f"imp:{imp}",
                        state="received",
                        source=EventSource("imp-trouble-report", imp),
                        details={},
                    ),
                    NccEvent(
                        sequence=sequence + 1,
                        observed_at=observed_at,
                        event_type="imp.throughput-report",
                        subject=f"imp:{imp}",
                        state="received",
                        source=EventSource("imp-throughput-report", imp),
                        details={},
                    ),
                )
            )
            sequence += 2
        try:
            recorder.append(events)
        finally:
            recorder.close()

    def _write_journeys(self) -> None:
        imp6, imp7, imp62 = synthetic_traces()
        traces = (
            ("source:imp6:post-cut", "imp6.debug.log", imp6),
            ("source:imp7:post-cut", "imp7.debug.log", imp7),
            ("source:imp62:post-cut", "imp62.debug.log", imp62),
        )
        windows = tuple(
            transaction_window_source(
                source_id=source_id,
                artifact=artifact,
                start_offset=1000 * index,
                end_offset=1000 * index + len(content),
                content=content,
            )
            for index, (source_id, artifact, content) in enumerate(traces, start=1)
        )
        write_pdp11_its_failover_journey_stream(
            self.result / "message-journey.jsonl",
            run_id=self.run_id,
            started_at="2026-09-01T12:00:00Z",
            provenance=(
                ObservationProvenance(
                    "source:controller",
                    "pdp11-its-failover-controller",
                    "a" * 40,
                ),
            ),
            topology_document=self.topology_document,
            transaction_window=windows,
            imp6_trace=imp6,
            imp7_trace=imp7,
            imp62_trace=imp62,
            h316_revision="b" * 40,
        )
        (self.result / "pre-cut-message-journey.jsonl").write_text(
            "fixture pre-cut journey is retained but outside this projection\n",
            encoding="utf-8",
        )

    def _write_application(self) -> None:
        (self.result / "application-evidence.txt").write_text(
            "\n".join(
                (
                    "connection_open=1",
                    "its_service_user=53TLNT",
                    "pre_cut_remote_time=structured",
                    "cut_acknowledged=1",
                    "session_survived_cut=1",
                    "post_cut_remote_time=structured",
                    "pre_cut_message_journey_observations=10",
                    "message_journey_observations=14",
                    "message_journey_state=missing-boundary",
                    "message_journey_first_boundary=boundary:request:8",
                )
            )
            + "\n",
            encoding="ascii",
        )
        (self.result / "cleanup-evidence.txt").write_text(
            "surviving_owned_processes=0\n",
            encoding="ascii",
        )
        (self.result / "outcome.txt").write_text("passed\n", encoding="ascii")

    def _write_relay_and_cut(self) -> None:
        relay = {
            "version": 1,
            "kind": "two-ended-udp-cut-relay",
            "cut_mode": "request-file",
            "started_at": "2026-09-01T12:00:02Z",
            "fault_started_at": "2026-09-01T12:01:00Z",
            "finished_at": "2026-09-01T12:02:00Z",
            "directions": {
                "a-to-b": {"forwarded": 10, "dropped": 20},
                "b-to-a": {"forwarded": 11, "dropped": 21},
            },
            "unexpected_sources": [],
        }
        self._write_json("application-relay.json", relay)
        self._write_json(
            "application-link-cut-state.json",
            {
                "version": 1,
                "kind": "two-ended-udp-cut-state",
                "state": "cut",
                "fault_started_at": relay["fault_started_at"],
            },
        )

    def _write_verdict(self) -> None:
        self._write_json(
            "verdict.json",
            {
                "version": 1,
                "kind": "ncc-pdp11-its-application-failover-verdict",
                "passed": True,
                "checks": {identifier: True for identifier in CHECK_IDS},
                "fault_started_at": "2026-09-01T12:01:00Z",
                "post_cut_report_sources": [5, 6, 7, 62],
                "discovered_report_mapping": {
                    "status": "candidate-only-one-exact-run",
                    "promoted_to_topology": False,
                    "direct_application_link": {
                        "imp62_report_line": 1,
                        "imp6_report_line": 3,
                        "pre_cut_state": "up",
                        "post_cut_state": "down",
                    },
                    "alternate_application_link": {
                        "imp62_report_line": 2,
                        "imp7_report_line": 3,
                        "post_cut_state": "up",
                    },
                },
                "journey": {
                    "journey_id": "journey:network-unix-telnet-post-cut",
                    "route_id": "route:host176-to-host106-alternate",
                    "observation_count": 14,
                    "state": "missing-boundary",
                    "first_boundary": "boundary:request:8",
                },
            },
        )

    def _write_manifest(self) -> None:
        journey = self.result / "message-journey.jsonl"
        pre_cut = self.result / "pre-cut-message-journey.jsonl"
        verdict = self.result / "verdict.json"
        values = {
            "format": "1",
            "topology": "ncc-pdp11-its-application-failover",
            "started_utc": "2026-09-01T12:00:00Z",
            "finished_utc": "2026-09-01T12:03:00Z",
            "repository.revision": "a" * 40,
            "repository.tracked_dirty": "0",
            "source.arpanet-in-a-box.revision": "b" * 40,
            "source.arpanet-in-a-box.tracked_dirty": "0",
            "source.network-unix-v6.revision": "c" * 40,
            "source.network-unix-v6.tracked_dirty": "0",
            "source.h316-simh.revision": "d" * 40,
            "source.h316-simh.tracked_dirty": "0",
            "source.ka10-simh.revision": "e" * 40,
            "source.ka10-simh.tracked_dirty": "0",
            "source.imp11a-simh.revision": "f" * 40,
            "source.imp11a-simh.tracked_dirty": "0",
            "path.shared-topology": str(TOPOLOGY.resolve()),
            "sha256.shared-topology": sha256_file(TOPOLOGY),
            "path.pre-cut-message-journey": str(pre_cut.resolve()),
            "sha256.pre-cut-message-journey": sha256_file(pre_cut),
            "path.message-journey": str(journey.resolve()),
            "sha256.message-journey": sha256_file(journey),
            "message-journey.observations": "14",
            "message-journey.state": "missing-boundary",
            "message-journey.first-boundary": "boundary:request:8",
            "application.client": "network-unix-telnet",
            "application.server": "TELSER",
            "application.service_user": "53TLNT",
            "application.network-unix-host106-ready": "host-host-rrp-consumed",
            "application.cut-requested": "1",
            "application.fault-started-at": "2026-09-01T12:01:00Z",
            "application.session-survived-cut": "1",
            "process.controller.exit-status": "0",
            "process.receiver.exit-status": "0",
            "process.application-relay.exit-status": "0",
            "cleanup.outer-runtime": "passed",
            "path.verdict": str(verdict.resolve()),
            "sha256.verdict": sha256_file(verdict),
            "udp.count": "18",
            "outcome": "passed",
            "exit_status": "0",
        }
        self.write_manifest(values)

    def manifest(self) -> dict[str, str]:
        return {
            line.split("=", 1)[0]: line.split("=", 1)[1]
            for line in (self.result / "runtime" / "run.env")
            .read_text(encoding="ascii")
            .splitlines()
        }

    def write_manifest(self, values: dict[str, str]) -> None:
        (self.result / "runtime" / "run.env").write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="ascii",
        )

    def rewrite_verdict(self, update) -> None:
        path = self.result / "verdict.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        update(document)
        self._write_json("verdict.json", document)
        manifest = self.manifest()
        manifest["sha256.verdict"] = sha256_file(path)
        self.write_manifest(manifest)

    def _write_json(self, name: str, document: object) -> None:
        (self.result / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class FailoverDisplayTests(unittest.TestCase):
    def test_composes_cut_alternate_journey_and_post_cut_report_authorities(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = FailoverFixture(Path(directory_name))
            display = FailoverDisplay(fixture.result, TOPOLOGY)

            first = display.snapshot()
            repeated = display.snapshot()
            self.assertEqual(first.to_json(), repeated.to_json())
            snapshot = first.to_dict()

            self.assertEqual(snapshot["profile"], "application-failover")
            self.assertEqual(snapshot["application"]["state"], "passed")
            self.assertEqual(snapshot["failover"]["direct_link"]["state"], "cut")
            self.assertEqual(
                snapshot["failover"]["alternate_route"]["state"],
                "observed",
            )
            self.assertEqual(
                snapshot["journey"]["assessment"]["first_boundary_id"],
                "boundary:request:8",
            )
            self.assertEqual(
                snapshot["historical"]["post_cut_report_sources"],
                [5, 6, 7, 62],
            )
            self.assertFalse(
                snapshot["failover"]["report_mapping"]["promoted_to_topology"]
            )

    def test_manifest_digest_change_blocks_typed_journey(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = FailoverFixture(Path(directory_name))
            with (fixture.result / "message-journey.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write("\n")

            with self.assertRaisesRegex(
                FailoverDisplayError,
                "message-journey digest does not match",
            ):
                FailoverDisplay(fixture.result, TOPOLOGY)

    def test_refuses_to_promote_one_run_report_line_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = FailoverFixture(Path(directory_name))
            fixture.rewrite_verdict(
                lambda verdict: verdict["discovered_report_mapping"].update(
                    {"promoted_to_topology": True}
                )
            )

            with self.assertRaisesRegex(FailoverDisplayError, "promoted to topology"):
                FailoverDisplay(fixture.result, TOPOLOGY)

    def test_refuses_a_cut_timestamp_not_bound_to_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = FailoverFixture(Path(directory_name))
            fixture._write_json(
                "application-link-cut-state.json",
                {
                    "version": 1,
                    "kind": "two-ended-udp-cut-state",
                    "state": "cut",
                    "fault_started_at": "2026-09-01T12:01:01Z",
                },
            )

            with self.assertRaisesRegex(
                FailoverDisplayError,
                "cut acknowledgement disagree",
            ):
                FailoverDisplay(fixture.result, TOPOLOGY)

    def test_board_selects_failover_projection_on_the_single_console(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = FailoverFixture(Path(directory_name))
            display = NccBoardDisplay(fixture.result, TOPOLOGY)
            page = render_ncc_board_html(display.shared_topology)

            snapshot = display.snapshot().to_dict()
            report = ncc_board_response(
                display,
                page,
                "GET",
                "/report",
            )

            self.assertEqual(snapshot["profile"], "application-failover")
            self.assertEqual(report.status, 404)

    def test_board_withholds_failover_conclusions_until_terminal_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = FailoverFixture(Path(directory_name))
            manifest = fixture.manifest()
            terminal = {
                key: manifest.pop(key)
                for key in ("finished_utc", "outcome", "exit_status")
            }
            fixture.write_manifest(manifest)
            display = NccBoardDisplay(fixture.result, TOPOLOGY)

            growing = display.snapshot().to_dict()
            self.assertEqual(growing["mode"], "live")
            self.assertNotIn("failover", growing)

            manifest.update(terminal)
            fixture.write_manifest(manifest)
            completed = display.snapshot().to_dict()
            self.assertEqual(completed["profile"], "application-failover")
            self.assertEqual(completed["failover"]["direct_link"]["state"], "cut")

    def test_board_browser_projects_failover_into_explicit_run_proof(self) -> None:
        shared = load_shared_topology(TOPOLOGY)
        page = render_ncc_board_html(shared)

        self.assertIn('data-bank="proof"', page)
        self.assertIn("modern validated facts", page)
        self.assertIn("function modelFromFailover", page)
        self.assertIn("payload.failover", page)
        self.assertIn("Direct application link", page)
        self.assertNotIn("topology-map", page)
        self.assertNotIn("<form", page)
        self.assertNotIn("WebSocket", page)


if __name__ == "__main__":
    unittest.main()
