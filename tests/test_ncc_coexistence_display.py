from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from ncc.coexistence_display import CoexistenceDisplay, CoexistenceDisplayError
from ncc.coexistence_server import (
    coexistence_display_response,
    create_coexistence_display_server,
)
from ncc.coexistence_viewer import render_coexistence_display_html
from ncc.events import EventSource, NccEvent
from ncc.historical_events import HistoricalEventRecorder
from ncc.message_journey import (
    DecodedMessage,
    ExternalEvidenceReference,
    JourneyLeg,
    MessageClass,
    MessageExpectation,
    MessageJourneyObservation,
    ObservationProvenance,
    build_expected_journey,
)
from ncc.message_journey_stream import (
    MessageJourneyStreamRecorder,
    TransactionWindowSource,
)
from ncc.shared_topology import load_shared_topology

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "config" / "topologies" / "ncc-pdp11-its-coexistence.json"
REQUEST_FINGERPRINT = "a" * 64
REPLY_FINGERPRINT = "b" * 64


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expectation(leg: JourneyLeg) -> MessageExpectation:
    return MessageExpectation(
        correlation_fingerprint=(
            REQUEST_FINGERPRINT if leg == JourneyLeg.REQUEST else REPLY_FINGERPRINT
        ),
        message_class=MessageClass.REGULAR,
        message_type=0,
        host=None,
        link=0,
        subtype=0,
        m1=0,
        byte_size=8,
        byte_count=10 if leg == JourneyLeg.REQUEST else 13,
        m2=0,
        ncp_opcode=1 if leg == JourneyLeg.REQUEST else 0,
    )


def decoded(contract: MessageExpectation) -> DecodedMessage:
    return DecodedMessage(
        message_class=contract.message_class,
        leader_format="synthetic-nosc-short",
        message_type=contract.message_type,
        host=contract.host,
        link=contract.link,
        subtype=contract.subtype,
        m1=contract.m1,
        byte_size=contract.byte_size,
        byte_count=contract.byte_count,
        m2=contract.m2,
        ncp_opcode=contract.ncp_opcode,
    )


class CoexistenceFixture:
    def __init__(self, parent: Path) -> None:
        self.result = parent / "ncc-pdp11-its-coexistence-fixture"
        self.result.mkdir()
        (self.result / "runtime").mkdir()
        self.run_id = self.result.name
        self.topology_document = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
        self.topology = load_shared_topology(TOPOLOGY)
        self._write_historical_stream()
        self._write_journey()
        self._write_application()
        self._write_verdict()
        self._write_manifest()

    def _write_historical_stream(self) -> None:
        path = self.result / "historical-events.jsonl"
        recorder = HistoricalEventRecorder(
            path,
            run_id=self.run_id,
            started_at="2026-09-01T12:00:03Z",
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
        for offset, imp in enumerate((5, 6, 7, 62), start=5):
            events.append(
                NccEvent(
                    sequence=sequence,
                    observed_at=f"2026-09-01T12:00:{offset:02d}Z",
                    event_type="imp.report",
                    subject=f"imp:{imp}",
                    state="received",
                    source=EventSource("imp-trouble-report", imp),
                    details={},
                )
            )
            sequence += 1
            events.append(
                NccEvent(
                    sequence=sequence,
                    observed_at=f"2026-09-01T12:00:{offset + 1:02d}Z",
                    event_type="imp.throughput-report",
                    subject=f"imp:{imp}",
                    state="received",
                    source=EventSource("imp-throughput-report", imp),
                    details={},
                )
            )
            sequence += 1
        events.extend(
            (
                NccEvent(
                    sequence=9,
                    observed_at="2026-09-01T12:00:20Z",
                    event_type="line-endpoint.state",
                    subject="imp:6:line:1",
                    state="up",
                    source=EventSource("imp-trouble-report", 6),
                    details={"neighbor_imp": 5},
                ),
                NccEvent(
                    sequence=10,
                    observed_at="2026-09-01T12:00:25Z",
                    event_type="line-endpoint.state",
                    subject="imp:5:line:1",
                    state="up",
                    source=EventSource("imp-trouble-report", 5),
                    details={"neighbor_imp": 6},
                ),
                NccEvent(
                    sequence=11,
                    observed_at="2026-09-01T12:01:00Z",
                    event_type="line-endpoint.state",
                    subject="imp:5:line:1",
                    state="down",
                    source=EventSource("imp-trouble-report", 5),
                    details={"neighbor_imp": None},
                ),
            )
        )
        try:
            recorder.append(events)
        finally:
            recorder.close()

    def _write_journey(self) -> None:
        shared = load_shared_topology(TOPOLOGY)
        expected = build_expected_journey(
            shared,
            journey_id="journey:network-unix-telnet-open",
            route_id="route:host176-to-host106",
            request=expectation(JourneyLeg.REQUEST),
            reply=expectation(JourneyLeg.REPLY),
        )
        path = self.result / "message-journey.jsonl"
        recorder = MessageJourneyStreamRecorder(
            path,
            run_id=self.run_id,
            started_at="2026-09-01T12:00:00Z",
            provenance=(
                ObservationProvenance(
                    "source:controller",
                    "formal-pdp11-its-controller",
                    "c" * 40,
                ),
            ),
            topology_document=self.topology_document,
            expected=expected,
            transaction_window=(
                TransactionWindowSource(
                    "source:imp6",
                    "imp6.debug.log",
                    100,
                    200,
                    "d" * 64,
                ),
                TransactionWindowSource(
                    "source:imp62",
                    "imp62.debug.log",
                    300,
                    450,
                    "e" * 64,
                ),
            ),
        )
        source_sequences: dict[str, int] = {}
        observations = []
        for boundary in expected.boundaries:
            if boundary.position == 6:
                continue
            harness = boundary.position == 1
            source_id = (
                f"source:{boundary.component_id}:connected-peer"
                if harness
                else f"source:{boundary.component_id}"
            )
            source_sequences[source_id] = source_sequences.get(source_id, 0) + 1
            contract = expectation(boundary.leg)
            observations.append(
                MessageJourneyObservation(
                    id=f"observation:{boundary.leg.value}:{boundary.position}",
                    journey_id=expected.id,
                    leg=boundary.leg,
                    component_id=boundary.component_id,
                    interface_id=boundary.interface_id,
                    direction=boundary.direction,
                    source_local_sequence=source_sequences[source_id],
                    decoded=decoded(contract),
                    correlation_fingerprint=contract.correlation_fingerprint,
                    provenance=ObservationProvenance(
                        source_id,
                        (
                            "h316-connected-peer-delivery"
                            if harness
                            else "h316-hi-mi-trace"
                        ),
                        "f" * 40,
                    ),
                    simulator_tick=source_sequences[source_id] * 100,
                    transport_sequence=boundary.position * 10,
                    external_evidence=(
                        ExternalEvidenceReference(
                            f"evidence:{boundary.leg.value}:{boundary.position}",
                            "trace-byte-range",
                            "fixture.debug.log:10-20",
                        ),
                    ),
                )
            )
        try:
            recorder.publish(observations)
            recorder.complete()
        finally:
            recorder.close()

    def _write_application(self) -> None:
        (self.result / "application-evidence.txt").write_text(
            "\n".join(
                (
                    "connection_open=1",
                    "its_service_user=53TLNT",
                    "its_greeting=1",
                    "remote_time=structured",
                    "imp6_post_probe_traffic=1",
                    "imp62_post_probe_traffic=1",
                    "correlated_inter_imp_traffic=both-directions",
                    "message_journey_observations=10",
                    "message_journey_state=missing-boundary",
                    "message_journey_first_boundary=boundary:request:6",
                    "legacy_option_diagnostic=observed",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        (self.result / "cleanup-evidence.txt").write_text(
            "surviving_owned_processes=0\n",
            encoding="utf-8",
        )
        (self.result / "outcome.txt").write_text("passed\n", encoding="ascii")

    def _write_verdict(self) -> None:
        checks = {
            "evidence-identities-match": True,
            "clean-pinned-inputs": True,
            "outer-runtime-cleanup": True,
            "application-passed": True,
            "typed-journey-retained": True,
            "application-controller-cleanup": True,
            "trouble-reports-from-imps-5-6-7-62": True,
            "throughput-reports-from-imps-5-6-7-62": True,
            "mapped-direct-line-observed-up": True,
        }
        verdict = {
            "version": 1,
            "kind": "ncc-pdp11-its-coexistence-verdict",
            "passed": True,
            "checks": checks,
            "report_counts_by_source_imp": {
                "trouble": {str(imp): 1 for imp in (5, 6, 7, 62)},
                "throughput": {str(imp): 1 for imp in (5, 6, 7, 62)},
            },
            "direct_line": {
                "id": "binding:imp5-mi1-imp6-mi1",
                "observed_state": "up",
                "supporting_sequences": [9, 10],
            },
        }
        (self.result / "verdict.json").write_text(
            json.dumps(verdict, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_manifest(self) -> None:
        journey = self.result / "message-journey.jsonl"
        verdict = self.result / "verdict.json"
        values = {
            "format": "1",
            "topology": "ncc-pdp11-its-coexistence",
            "started_utc": "2026-09-01T12:00:00Z",
            "finished_utc": "2026-09-01T12:01:05Z",
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
            "path.message-journey": str(journey.resolve()),
            "sha256.message-journey": sha256_file(journey),
            "message-journey.observations": "10",
            "message-journey.state": "missing-boundary",
            "message-journey.first-boundary": "boundary:request:6",
            "application.client": "network-unix-telnet",
            "application.server": "TELSER",
            "application.service_user": "53TLNT",
            "application.remote_time": "structured",
            "process.controller.exit-status": "0",
            "process.receiver.exit-status": "0",
            "cleanup.outer-runtime": "passed",
            "path.verdict": str(verdict.resolve()),
            "sha256.verdict": sha256_file(verdict),
            "outcome": "passed",
            "exit_status": "0",
        }
        self.write_manifest(values)

    def manifest(self) -> dict[str, str]:
        return {
            line.split("=", 1)[0]: line.split("=", 1)[1]
            for line in (self.result / "runtime" / "run.env")
            .read_text(encoding="utf-8")
            .splitlines()
        }

    def write_manifest(self, values: dict[str, str]) -> None:
        (self.result / "runtime" / "run.env").write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )

    def rewrite_verdict(self, update) -> None:
        path = self.result / "verdict.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        update(document)
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = self.manifest()
        manifest["sha256.verdict"] = sha256_file(path)
        self.write_manifest(manifest)


class CoexistenceDisplayTests(unittest.TestCase):
    def test_composes_independent_application_journey_and_line_authorities(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            display = CoexistenceDisplay(fixture.result, TOPOLOGY)

            first = display.snapshot()
            repeated = display.snapshot()
            self.assertEqual(first.to_json(), repeated.to_json())
            snapshot = first.to_dict()

            self.assertEqual(snapshot["composition"]["state"], "passed")
            self.assertEqual(snapshot["application"]["state"], "passed")
            self.assertEqual(snapshot["journey"]["assessment"]["state"], "missing-boundary")
            self.assertEqual(
                snapshot["journey"]["assessment"]["first_boundary_id"],
                "boundary:request:6",
            )
            accepted = snapshot["historical"]["accepted_line"]
            self.assertEqual(accepted["state"], "up")
            self.assertEqual(accepted["supporting_sequences"], [9, 10])
            tail = snapshot["historical"]["post_support_tail"]
            self.assertEqual(
                [event["sequence"] for event in tail["mapped_direct_events"]],
                [11],
            )
            final_endpoints = {
                item["component_id"]: item["state"]
                for item in snapshot["historical"]["final_at_run_finish"]["endpoints"]
            }
            self.assertEqual(final_endpoints, {"imp:5": "down", "imp:6": "stale"})
            self.assertEqual(
                snapshot["historical"]["final_at_run_finish"]["line"]["state"],
                "stale",
            )
            self.assertEqual(len(snapshot["topology"]["configured_only_link_ids"]), 6)
            self.assertIsNone(snapshot["phases"]["controller_exit_sequence"])

    def test_fails_closed_when_saved_support_is_not_the_latest_up_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            fixture.rewrite_verdict(
                lambda verdict: verdict["direct_line"].update(
                    {"supporting_sequences": [10, 11]}
                )
            )

            with self.assertRaisesRegex(
                CoexistenceDisplayError,
                "latest observed up pair",
            ):
                CoexistenceDisplay(fixture.result, TOPOLOGY)

    def test_fails_closed_when_direct_report_counts_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            fixture.rewrite_verdict(
                lambda verdict: verdict["report_counts_by_source_imp"]["trouble"].update(
                    {"5": 2}
                )
            )

            with self.assertRaisesRegex(
                CoexistenceDisplayError,
                "report counts disagree",
            ):
                CoexistenceDisplay(fixture.result, TOPOLOGY)

    def test_manifest_digest_change_blocks_typed_journey(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            with (fixture.result / "message-journey.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write("\n")

            with self.assertRaisesRegex(
                CoexistenceDisplayError,
                "message-journey digest does not match",
            ):
                CoexistenceDisplay(fixture.result, TOPOLOGY)

    def test_exact_topology_identity_survives_checkout_relocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            fixture = CoexistenceFixture(root)
            relocated = root / "other-checkout" / "config" / "topologies" / TOPOLOGY.name
            relocated.parent.mkdir(parents=True)
            shutil.copyfile(TOPOLOGY, relocated)

            snapshot = CoexistenceDisplay(fixture.result, relocated).snapshot().to_dict()

            self.assertEqual(snapshot["application"]["state"], "passed")
            wrong_name = relocated.with_name("other-topology.json")
            shutil.copyfile(TOPOLOGY, wrong_name)
            with self.assertRaisesRegex(
                CoexistenceDisplayError,
                "topology filename",
            ):
                CoexistenceDisplay(fixture.result, wrong_name)

    def test_loopback_application_accepts_only_get_and_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            fixture = CoexistenceFixture(Path(directory_name))
            display = CoexistenceDisplay(fixture.result, TOPOLOGY)
            page = render_coexistence_display_html()

            root = coexistence_display_response(display, page, "GET", "/")
            api = coexistence_display_response(display, page, "GET", "/api/snapshot")
            head = coexistence_display_response(display, page, "HEAD", "/api/snapshot")
            mutation = coexistence_display_response(display, page, "POST", "/api/snapshot")
            arbitrary = coexistence_display_response(display, page, "GET", "/etc/passwd")

            self.assertEqual(root.status, 200)
            self.assertIn("Scenario register / evidence phase rail", root.body)
            self.assertEqual(api.status, 200)
            self.assertEqual(json.loads(api.body)["mode"], "completed")
            self.assertEqual(head.status, 200)
            self.assertEqual(head.body, "")
            self.assertEqual(mutation.status, 405)
            self.assertEqual(mutation.headers["Allow"], "GET, HEAD")
            self.assertEqual(arbitrary.status, 404)

            with patch(
                "ncc.coexistence_server.CoexistenceDisplayHTTPServer"
            ) as server_type:
                server = create_coexistence_display_server(display, port=0)
            server_type.assert_called_once_with(("127.0.0.1", 0), ANY)
            self.assertIs(server.display, display)

    def test_viewer_keeps_reduction_in_python_and_accessible_controls(self) -> None:
        page = render_coexistence_display_html()

        self.assertIn("Observation folio NCC / 01", page)
        self.assertIn("SRI / NIC 11863 (1972)", page)
        self.assertIn("repeating-linear-gradient", page)
        self.assertIn("text-decoration: underline", page)
        self.assertIn(".journey-body > * { min-width: 0; }", page)
        self.assertIn("prefers-reduced-motion", page)
        self.assertIn('fetch("/api/snapshot"', page)
        self.assertIn('button.type = "button"', page)
        self.assertIn("aria-pressed", page)
        self.assertNotIn("data:image", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("<form", page)
        self.assertNotIn("WebSocket", page)


if __name__ == "__main__":
    unittest.main()
