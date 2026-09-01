from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ncc.journey_display import JourneyDisplayObserver
from ncc.journey_server import journey_display_response
from ncc.journey_viewer import render_journey_display_html
from ncc.message_journey import (
    DecodedMessage,
    ExternalEvidenceReference,
    JourneyLeg,
    JourneyState,
    MessageClass,
    MessageExpectation,
    MessageJourneyObservation,
    ObservationProvenance,
    build_expected_journey,
)
from ncc.message_journey_stream import (
    MessageJourneyStreamRecorder,
    TransactionWindowSource,
    read_message_journey_stream,
)
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "config" / "topologies" / "pdp11-its-telnet.json"
REQUEST_FINGERPRINT = "a" * 64
REPLY_FINGERPRINT = "b" * 64


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


class JourneyDisplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = load_shared_topology(TOPOLOGY)
        self.topology_document = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
        self.expected = build_expected_journey(
            self.topology,
            journey_id="journey:display-fixture",
            route_id="route:host176-to-host106",
            request=expectation(JourneyLeg.REQUEST),
            reply=expectation(JourneyLeg.REPLY),
        )
        self.observations = self._observations()

    def test_progressive_append_incomplete_tail_and_terminal_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            path = root / "message-journey.jsonl"
            recorder = self._recorder(path)
            observer = JourneyDisplayObserver(path)

            unknown = observer.snapshot().to_dict()
            self.assertEqual(unknown["assessment"]["state"], "unknown")
            self.assertEqual(unknown["assessment"]["first_boundary_id"], "boundary:request:1")
            self.assertEqual(unknown["stream"]["complete_observation_count"], 0)

            recorder.publish((self.observations[0],))
            recorder.close()
            first = observer.snapshot().to_dict()
            self.assertEqual(first["stream"]["change"], "appended")
            self.assertEqual(first["assessment"]["first_boundary_id"], "boundary:request:2")

            two_records = root / "two-records.jsonl"
            self._write_stream(two_records, self.observations[:2])
            second_line = two_records.read_text(encoding="utf-8").splitlines()[2]
            split = len(second_line) // 2
            with path.open("a", encoding="utf-8") as output:
                output.write(second_line[:split])

            partial = observer.snapshot()
            repeated = observer.snapshot()
            self.assertEqual(partial.to_json(), repeated.to_json())
            self.assertTrue(partial.to_dict()["stream"]["incomplete_final_record"])
            self.assertEqual(partial.to_dict()["stream"]["complete_observation_count"], 1)

            with path.open("a", encoding="utf-8") as output:
                output.write(second_line[split:] + "\n")
            complete = observer.snapshot().to_dict()
            self.assertFalse(complete["stream"]["incomplete_final_record"])
            self.assertEqual(complete["stream"]["complete_observation_count"], 2)

            terminal_source = root / "terminal.jsonl"
            self._write_stream(terminal_source, self.observations[:2], terminal=True)
            terminal_line = terminal_source.read_text(encoding="utf-8").splitlines()[-1]
            with path.open("a", encoding="utf-8") as output:
                output.write(terminal_line + "\n")
            terminal = observer.snapshot().to_dict()
            self.assertEqual(terminal["mode"], "terminal")
            self.assertTrue(terminal["stream"]["is_terminal"])
            self.assertEqual(
                terminal["assessment"]["authority"],
                "persisted terminal diagnosis verified against existing reducer",
            )

    def test_generation_changes_do_not_carry_superseded_observations(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            path = root / "message-journey.jsonl"
            self._write_stream(path, self.observations[:2])
            observer = JourneyDisplayObserver(path)
            original_lines = path.read_text(encoding="utf-8").splitlines()

            initial = observer.snapshot()
            self.assertEqual(initial.to_json(), observer.snapshot().to_json())

            path.write_text("\n".join(original_lines[:2]) + "\n", encoding="utf-8")
            truncated = observer.snapshot().to_dict()
            self.assertEqual(truncated["stream"]["change"], "truncated")
            self.assertEqual(truncated["stream"]["generation"], 2)
            self.assertEqual(len(truncated["observations"]), 1)

            replacement_records = root / "replacement-records.jsonl"
            self._write_stream(replacement_records, (self.observations[1],))
            path.write_text(replacement_records.read_text(encoding="utf-8"), encoding="utf-8")
            replaced = observer.snapshot().to_dict()
            self.assertEqual(replaced["stream"]["change"], "replaced")
            self.assertEqual(replaced["stream"]["generation"], 3)
            self.assertEqual(
                [item["id"] for item in replaced["observations"]],
                ["observation:request:2"],
            )

            restarted_path = root / "restarted.jsonl"
            self._write_stream(restarted_path, (self.observations[0],))
            restarted_path.replace(path)
            restarted = observer.snapshot().to_dict()
            self.assertEqual(restarted["stream"]["change"], "restarted")
            self.assertEqual(restarted["stream"]["generation"], 4)

            changed_path = root / "identity.jsonl"
            self._write_stream(
                changed_path,
                (self.observations[0],),
                run_id="pdp11-its-telnet-new-run",
            )
            changed_path.replace(path)
            changed = observer.snapshot().to_dict()
            self.assertEqual(changed["stream"]["change"], "identity-changed")
            self.assertEqual(changed["stream"]["generation"], 5)
            self.assertEqual(changed["run"]["id"], "pdp11-its-telnet-new-run")

    def test_same_inode_append_during_read_retries_before_snapshotting(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self._write_stream(path, self.observations[:1])
            reads = 0

            def append_during_first_read(candidate: Path):
                nonlocal reads
                stream = read_message_journey_stream(candidate)
                reads += 1
                if reads == 1:
                    with candidate.open("a", encoding="utf-8") as output:
                        output.write('{"incomplete":')
                return stream

            with patch(
                "ncc.journey_display.read_message_journey_stream",
                side_effect=append_during_first_read,
            ):
                snapshot = JourneyDisplayObserver(path).snapshot().to_dict()

            self.assertEqual(reads, 2)
            self.assertTrue(snapshot["stream"]["incomplete_final_record"])
            self.assertEqual(snapshot["stream"]["complete_observation_count"], 1)

    def test_terminal_projection_preserves_route_authority_and_exact_support(self) -> None:
        accepted_shape = tuple(
            observation
            for observation in self.observations
            if not observation.id.endswith(":6")
        )
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self._write_stream(path, accepted_shape, terminal=True)

            snapshot = JourneyDisplayObserver(path).snapshot().to_dict()

        self.assertEqual(snapshot["mode"], "terminal")
        self.assertEqual(snapshot["assessment"]["state"], "missing-boundary")
        self.assertEqual(snapshot["assessment"]["first_boundary_id"], "boundary:request:6")
        self.assertEqual(
            snapshot["assessment"]["supporting_observation_ids"],
            [observation.id for observation in accepted_shape],
        )
        self.assertEqual(
            [component["id"] for component in snapshot["route"]["components"]],
            ["host:176", "imp:62", "imp:6", "host:106"],
        )
        self.assertEqual(len(snapshot["route"]["links"]), 3)
        self.assertEqual(
            [item["authority_class"] for item in snapshot["observations"]].count("direct"),
            8,
        )
        self.assertEqual(
            [item["authority_class"] for item in snapshot["observations"]].count(
                "harness-derived"
            ),
            2,
        )
        boundaries = {item["id"]: item for item in snapshot["assessment"]["boundaries"]}
        self.assertEqual(
            boundaries["boundary:request:1"]["source_authority_classes"],
            ["harness-derived"],
        )
        self.assertEqual(
            boundaries["boundary:request:2"]["source_authority_classes"],
            ["direct"],
        )
        self.assertEqual(boundaries["boundary:request:6"]["state"], "missing")
        self.assertEqual(boundaries["boundary:request:6"]["evidence_observation_ids"], [])
        self.assertEqual(
            boundaries["boundary:request:6"]["context_supporting_observation_ids"],
            [f"observation:request:{position}" for position in range(1, 6)],
        )

    def test_ambiguous_and_contradictory_assessments_remain_visible(self) -> None:
        first = self.observations[0]
        duplicate = replace(
            first,
            id="observation:request:duplicate",
            source_local_sequence=first.source_local_sequence + 1,
            simulator_tick=(first.simulator_tick or 0) + 1,
        )
        contradiction = replace(
            first,
            decoded=replace(first.decoded, message_type=1),
        )
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            ambiguous_path = root / "ambiguous.jsonl"
            self._write_stream(ambiguous_path, (first, duplicate))
            ambiguous = JourneyDisplayObserver(ambiguous_path).snapshot().to_dict()

            contradictory_path = root / "contradictory.jsonl"
            self._write_stream(contradictory_path, (contradiction,))
            contradictory = JourneyDisplayObserver(contradictory_path).snapshot().to_dict()

        self.assertEqual(ambiguous["assessment"]["state"], JourneyState.AMBIGUOUS.value)
        self.assertEqual(
            ambiguous["assessment"]["boundaries"][0]["evidence_observation_ids"],
            [first.id, duplicate.id],
        )
        self.assertEqual(
            contradictory["assessment"]["state"],
            JourneyState.CONTRADICTORY_BOUNDARY.value,
        )
        self.assertEqual(
            contradictory["assessment"]["boundaries"][0]["state"],
            "contradictory",
        )

    def test_browser_and_transport_are_passive_and_presentation_only(self) -> None:
        page = render_journey_display_html()
        self.assertIn("Message journey bench", page)
        self.assertIn("configured · no observation", page)
        self.assertIn("harness-derived", page)
        self.assertIn("direct H316", page)
        self.assertIn("Incomplete final JSONL record ignored", page)
        self.assertIn("not a completed-run or Gate 4H verdict", page)
        self.assertIn("textContent", page)
        self.assertNotIn("diagnose_message_journey", page)
        self.assertNotIn("build_expected_journey", page)
        self.assertNotIn("WebSocket", page)
        self.assertNotIn("innerHTML", page)

        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self._write_stream(path, self.observations[:1])
            observer = JourneyDisplayObserver(path)

            root = journey_display_response(observer, page, "GET", "/")
            api = journey_display_response(observer, page, "GET", "/api/snapshot")
            head = journey_display_response(observer, page, "HEAD", "/api/snapshot")
            mutation = journey_display_response(observer, page, "POST", "/api/snapshot")
            arbitrary = journey_display_response(observer, page, "GET", "/../../run.env")
            invalid = journey_display_response(
                JourneyDisplayObserver(path.parent / "missing.jsonl"),
                page,
                "GET",
                "/api/snapshot",
            )

        self.assertEqual(root.status, 200)
        self.assertEqual(json.loads(api.body)["stream"]["complete_observation_count"], 1)
        self.assertEqual(head.status, 200)
        self.assertEqual(head.body, "")
        self.assertEqual(mutation.status, 405)
        self.assertEqual(mutation.headers["Allow"], "GET, HEAD")
        self.assertEqual(arbitrary.status, 404)
        self.assertEqual(invalid.status, 409)

    def _recorder(
        self,
        path: Path,
        *,
        run_id: str = "pdp11-its-telnet-display-fixture",
    ) -> MessageJourneyStreamRecorder:
        return MessageJourneyStreamRecorder(
            path,
            run_id=run_id,
            started_at="2026-09-01T12:00:00Z",
            provenance=(
                ObservationProvenance(
                    "source:controller",
                    "formal-pdp11-its-controller",
                    "c" * 40,
                ),
            ),
            topology_document=self.topology_document,
            expected=self.expected,
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

    def _write_stream(
        self,
        path: Path,
        observations: tuple[MessageJourneyObservation, ...],
        *,
        terminal: bool = False,
        run_id: str = "pdp11-its-telnet-display-fixture",
    ) -> None:
        recorder = self._recorder(path, run_id=run_id)
        try:
            recorder.publish(observations)
            if terminal:
                recorder.complete()
        finally:
            recorder.close()

    def _observations(self) -> tuple[MessageJourneyObservation, ...]:
        sequences: dict[str, int] = {}
        observations = []
        for boundary in self.expected.boundaries:
            harness = boundary.position == 1
            source_id = (
                f"source:{boundary.component_id}:connected-peer"
                if harness
                else f"source:{boundary.component_id}"
            )
            sequences[source_id] = sequences.get(source_id, 0) + 1
            contract = expectation(boundary.leg)
            observations.append(
                MessageJourneyObservation(
                    id=f"observation:{boundary.leg.value}:{boundary.position}",
                    journey_id=self.expected.id,
                    leg=boundary.leg,
                    component_id=boundary.component_id,
                    interface_id=boundary.interface_id,
                    direction=boundary.direction,
                    source_local_sequence=sequences[source_id],
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
                    simulator_tick=sequences[source_id] * 100,
                    transport_sequence=boundary.position * 10,
                    external_evidence=(
                        ExternalEvidenceReference(
                            id=f"evidence:{boundary.leg.value}:{boundary.position}",
                            kind="trace-byte-range",
                            locator="fixture.debug.log:10-20",
                        ),
                    ),
                )
            )
        return tuple(observations)


if __name__ == "__main__":
    unittest.main()
