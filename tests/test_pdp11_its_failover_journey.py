from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from ncc.message_journey import (
    BoundaryAssessmentState,
    JourneyState,
    ObservationProvenance,
)
from ncc.message_journey_stream import read_message_journey_stream
from ncc.pdp11_its_failover_journey import (
    Pdp11ItsFailoverJourneyError,
    extract_pdp11_its_failover_journey,
    pdp11_its_failover_modem_devices,
    write_pdp11_its_failover_journey_stream,
)
from ncc.pdp11_its_journey import transaction_window_source
from ncc.reconciliation import Endpoint, nominal_topology_from_shared
from ncc.shared_topology import load_shared_topology

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = (
    ROOT / "config" / "topologies" / "ncc-pdp11-its-application-failover.json"
)

REQUEST = (
    0o000106,
    0o003000,
    0o000010,
    0o000040,
    0o000000,
    0o072072,
    0o073151,
)
REQUEST_AT_IMP6 = (0o000176, *REQUEST[1:])
REPLY = (
    0o000176,
    0o003000,
    0o000010,
    0o000050,
    0o000000,
    0o064061,
    0o072040,
    0o061062,
)
REPLY_AT_IMP62 = (0o000106, *REPLY[1:])


def modem_packet(host_words: tuple[int, ...], seed: int) -> tuple[int, ...]:
    return (
        (0o100000 + seed) & 0o177777,
        (0o010000 + seed) & 0o177777,
        host_words[0],
        seed & 0o177777,
        *host_words[1:],
        (0o160000 + seed) & 0o177777,
    )


REQUEST_62_TO_7 = modem_packet(REQUEST, 1)
REQUEST_7_TO_6 = modem_packet(REQUEST, 2)
REPLY_6_TO_7 = modem_packet(REPLY, 3)
REPLY_7_TO_62 = modem_packet(REPLY, 4)


def trace_record(
    tick: int,
    device: str,
    action: str,
    words: tuple[int, ...],
    transport_sequence: int,
    message_number: int,
) -> list[str]:
    lines = []
    if action == "received":
        lines.append(
            f"DBG({tick})> {device} UDP: link 0 - packet received "
            f"(sequence={transport_sequence}, length={len(words)})"
        )
    lines.extend(
        (
            f"DBG({tick})> {device} MSG: message {action} (length={len(words)})",
            f"DBG({tick})> {device} MSG: - "
            + " ".join(f"{word:06o}" for word in words)
            + " ",
        )
    )
    if action == "received":
        lines.append(
            f"DBG({tick})> {device} IO: receive done "
            f"(message #{message_number}, intreq=000004)"
        )
    else:
        lines.append(
            f"DBG({tick})> {device} UDP: link 0 - packet sent "
            f"(sequence={transport_sequence}, length={len(words)})"
        )
    return lines


def synthetic_traces() -> tuple[bytes, bytes, bytes]:
    imp62 = [
        *trace_record(10, "HI2", "received", REQUEST, 100, 1),
        *trace_record(20, "MI2", "sent", REQUEST_62_TO_7, 101, 2),
        *trace_record(70, "MI2", "received", REPLY_7_TO_62, 106, 3),
        *trace_record(80, "HI2", "sent", REPLY_AT_IMP62, 107, 4),
    ]
    imp7 = [
        *trace_record(31, "MI3", "received", REQUEST_62_TO_7, 101, 11),
        *trace_record(32, "MI2", "sent", REQUEST_7_TO_6, 102, 12),
        *trace_record(61, "MI2", "received", REPLY_6_TO_7, 105, 13),
        *trace_record(62, "MI3", "sent", REPLY_7_TO_62, 106, 14),
    ]
    imp6 = [
        *trace_record(40, "MI2", "received", REQUEST_7_TO_6, 102, 21),
        *trace_record(50, "HI2", "sent", REQUEST_AT_IMP6, 103, 22),
        *trace_record(51, "HI2", "received", REPLY, 104, 23),
        *trace_record(60, "MI2", "sent", REPLY_6_TO_7, 105, 24),
    ]
    return tuple(
        ("\n".join(lines) + "\n").encode("ascii") for lines in (imp6, imp7, imp62)
    )


class FailoverTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
        cls.shared = load_shared_topology(TOPOLOGY_PATH)
        cls.nominal = nominal_topology_from_shared(cls.shared)

    def test_adds_one_bounded_alternate_route_without_new_components(self) -> None:
        components = {item["id"] for item in self.document["topology"]["components"]}
        self.assertEqual(
            components,
            {
                "host:176",
                "imp:62",
                "imp:7",
                "imp:6",
                "host:106",
                "imp:5",
                "host:ncc",
            },
        )
        routes = {
            item["id"]: item["components"]
            for item in self.document["topology"]["routes"]
        }
        self.assertEqual(
            routes["route:host176-to-host106-alternate"],
            ["host:176", "imp:62", "imp:7", "imp:6", "host:106"],
        )

    def test_uses_free_supported_modems_and_does_not_invent_report_lines(self) -> None:
        devices = pdp11_its_failover_modem_devices(self.shared)
        self.assertEqual(devices.imp62_to_imp7, ("mi2", "mi3"))
        self.assertEqual(devices.imp7_to_imp6, ("mi2", "mi2"))
        application = [
            item
            for item in self.shared.modem_interfaces
            if item.id.endswith("application-direct")
            or item.id.endswith("application-alternate")
        ]
        self.assertEqual(len(application), 2)
        self.assertTrue(
            all(
                item.first_report_line is None and item.second_report_line is None
                for item in application
            )
        )
        self.assertEqual(len(self.nominal.lines), 1)
        self.assertEqual(self.nominal.lines[0].first, Endpoint(5, 1))
        self.assertEqual(self.nominal.lines[0].second, Endpoint(6, 1))

    def test_configs_consume_bound_ports_and_only_add_the_cut_relay_ports(self) -> None:
        config_paths = {interface.simh_config for interface in self.shared.interfaces}
        config_paths.update(
            path
            for binding in self.shared.modem_interfaces
            for path in (binding.first_simh_config, binding.second_simh_config)
        )
        config_text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8") for path in config_paths
        )
        configured = set(re.findall(r"%([A-Z0-9_]+_PORT)%", config_text))
        bound = {
            name
            for interface in self.shared.interfaces
            for name in (
                interface.imp_listen_environment,
                interface.host_listen_environment,
            )
        }
        bound.update(
            name
            for binding in self.shared.modem_interfaces
            for name in (
                binding.first_listen_environment,
                binding.second_listen_environment,
            )
        )
        self.assertEqual(
            configured - bound,
            {"BRFID_APP_RELAY62_PORT", "BRFID_APP_RELAY6_PORT"},
        )
        self.assertEqual(bound - configured, set())
        self.assertNotIn("deposit 1005", config_text.lower())
        imp62_config = (
            ROOT / "config" / "imp" / "ncc-pdp11-its-failover" / "imp62.simh"
        ).read_text(encoding="utf-8")
        self.assertIn("set hi2 noconvert", imp62_config)
        self.assertNotIn("set hi2 convert", imp62_config)


class FailoverJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = load_shared_topology(TOPOLOGY_PATH)
        self.imp6, self.imp7, self.imp62 = synthetic_traces()

    def extraction(self):
        return extract_pdp11_its_failover_journey(
            self.topology,
            imp6_trace=self.imp6,
            imp7_trace=self.imp7,
            imp62_trace=self.imp62,
            h316_revision="a" * 40,
        )

    def test_extracts_fourteen_boundaries_and_stops_at_host_delivery(self) -> None:
        extraction = self.extraction()

        self.assertEqual(len(extraction.observations), 14)
        self.assertEqual(extraction.diagnosis.state, JourneyState.MISSING_BOUNDARY)
        self.assertEqual(
            extraction.diagnosis.first_boundary_id,
            "boundary:request:8",
        )
        states = {
            item.boundary.id: item.state for item in extraction.diagnosis.boundaries
        }
        self.assertEqual(states["boundary:request:8"], BoundaryAssessmentState.MISSING)
        self.assertEqual(states["boundary:reply:8"], BoundaryAssessmentState.MISSING)
        self.assertTrue(
            all(
                state == BoundaryAssessmentState.OBSERVED
                for identifier, state in states.items()
                if identifier not in {"boundary:request:8", "boundary:reply:8"}
            )
        )

    def test_preserves_each_source_local_transport_identity(self) -> None:
        observations = self.extraction().observations

        self.assertEqual(
            [item.provenance.kind for item in observations].count(
                "h316-connected-peer-delivery"
            ),
            2,
        )
        self.assertEqual(
            [item.provenance.kind for item in observations].count("h316-hi-mi-trace"),
            12,
        )
        self.assertEqual(
            [item.transport_sequence for item in observations[:7]],
            [100, 100, 101, 101, 102, 102, 103],
        )
        self.assertEqual(
            [item.transport_sequence for item in observations[7:]],
            [104, 104, 105, 105, 106, 106, 107],
        )

    def test_rejects_a_cross_process_packet_mismatch(self) -> None:
        changed = self.imp7.replace(b"100001 010001", b"100007 010001", 1)

        with self.assertRaisesRegex(
            Pdp11ItsFailoverJourneyError,
            "no exact application request",
        ):
            extract_pdp11_its_failover_journey(
                self.topology,
                imp6_trace=self.imp6,
                imp7_trace=changed,
                imp62_trace=self.imp62,
            )

    def test_rejects_an_apparent_direct_route_that_bypasses_imp7(self) -> None:
        direct_imp6 = self.imp6.replace(b"MI2", b"MI3")

        with self.assertRaisesRegex(
            Pdp11ItsFailoverJourneyError,
            "no exact application request",
        ):
            extract_pdp11_its_failover_journey(
                self.topology,
                imp6_trace=direct_imp6,
                imp7_trace=self.imp7,
                imp62_trace=self.imp62,
            )

    def test_persisted_stream_round_trips_the_three_trace_windows(self) -> None:
        document = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
        traces = (
            ("source:imp6", "imp6.debug.log", self.imp6),
            ("source:imp7", "imp7.debug.log", self.imp7),
            ("source:imp62", "imp62.debug.log", self.imp62),
        )
        windows = tuple(
            transaction_window_source(
                source_id=source_id,
                artifact=artifact,
                start_offset=100 * index,
                end_offset=100 * index + len(content),
                content=content,
            )
            for index, (source_id, artifact, content) in enumerate(traces, start=1)
        )
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "post-cut-message-journey.jsonl"
            stream = write_pdp11_its_failover_journey_stream(
                path,
                run_id="failover-test",
                started_at="2026-09-01T12:00:00Z",
                provenance=(
                    ObservationProvenance(
                        "source:controller",
                        "pdp11-its-failover-controller",
                        "b" * 40,
                    ),
                ),
                topology_document=document,
                transaction_window=windows,
                imp6_trace=self.imp6,
                imp7_trace=self.imp7,
                imp62_trace=self.imp62,
                h316_revision="a" * 40,
            )

            reread = read_message_journey_stream(path)
            self.assertEqual(reread, stream)
            self.assertEqual(len(reread.transaction_window), 3)
            self.assertEqual(len(reread.observations), 14)


if __name__ == "__main__":
    unittest.main()
