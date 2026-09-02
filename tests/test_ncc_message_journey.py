from __future__ import annotations

import unittest
from collections import defaultdict
from dataclasses import replace

from ncc.h316_journey import (
    H316TraceError,
    observation_from_h316_transfer,
    parse_h316_trace,
)
from ncc.message_journey import (
    BoundaryDirection,
    DecodedMessage,
    ExpectedJourney,
    JourneyLeg,
    JourneyState,
    JourneyValidationError,
    MessageClass,
    MessageExpectation,
    MessageJourneyObservation,
    ObservationProvenance,
    build_expected_journey,
    correlation_fingerprint,
    decode_nosc_short_leader,
    diagnose_message_journey,
    observation_from_ka10_imp_trace,
    observation_from_pdp11_imp11a_trace,
)
from ncc.shared_topology import shared_topology_from_mapping


def journey_topology_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "topology:heterogeneous-message-journey",
        "topology": {
            "components": [
                {
                    "id": "host:176",
                    "kind": "host",
                    "label": "PDP-11 host 176",
                    "position": {"x": 0, "y": 0},
                    "endpoints": [{"id": "host:176:1822", "label": "1822"}],
                },
                {
                    "id": "imp:62",
                    "kind": "imp",
                    "label": "IMP 62",
                    "position": {"x": 1, "y": 0},
                    "endpoints": [
                        {"id": "imp:62:host:1", "label": "HI2"},
                        {"id": "imp:62:mi1", "label": "MI1"},
                    ],
                },
                {
                    "id": "imp:6",
                    "kind": "imp",
                    "label": "IMP 6",
                    "position": {"x": 2, "y": 0},
                    "endpoints": [
                        {"id": "imp:6:mi1", "label": "MI1"},
                        {"id": "imp:6:host:1", "label": "HI2"},
                    ],
                },
                {
                    "id": "host:106",
                    "kind": "host",
                    "label": "ITS host 106",
                    "position": {"x": 3, "y": 0},
                    "endpoints": [{"id": "host:106:1822", "label": "1822"}],
                },
            ],
            "links": [
                {
                    "id": "link:host176-imp62",
                    "endpoints": ["host:176:1822", "imp:62:host:1"],
                },
                {
                    "id": "link:imp62-imp6",
                    "endpoints": ["imp:62:mi1", "imp:6:mi1"],
                },
                {
                    "id": "link:imp6-host106",
                    "endpoints": ["imp:6:host:1", "host:106:1822"],
                },
            ],
            "routes": [
                {
                    "id": "route:host176-to-host106",
                    "components": ["host:176", "imp:62", "imp:6", "host:106"],
                }
            ],
        },
        "interfaces": [
            {
                "id": "binding:host176-imp62-hi2",
                "kind": "host-interface",
                "imp_id": "imp:62",
                "imp_endpoint": "imp:62:host:1",
                "host_id": "host:176",
                "host_endpoint": "host:176:1822",
                "host_number": 1,
                "simh_device": "hi2",
                "imp_listen_environment": "BRFID_IMP62_HI_PORT",
                "host_listen_environment": "BRFID_HOST176_HI_PORT",
                "simh_config": "config/imp/its-pair/imp62.simh",
            },
            {
                "id": "binding:imp6-hi2-host106",
                "kind": "host-interface",
                "imp_id": "imp:6",
                "imp_endpoint": "imp:6:host:1",
                "host_id": "host:106",
                "host_endpoint": "host:106:1822",
                "host_number": 1,
                "simh_device": "hi2",
                "imp_listen_environment": "BRFID_IMP6_HI_PORT",
                "host_listen_environment": "BRFID_HOST106_HI_PORT",
                "simh_config": "config/imp/its-pair/imp6.simh",
            },
        ],
        "modem_interfaces": [
            {
                "id": "binding:imp62-mi1-imp6-mi1",
                "kind": "modem-interface",
                "first_imp_id": "imp:62",
                "first_endpoint": "imp:62:mi1",
                "first_simh_device": "mi1",
                "first_listen_environment": "BRFID_IMP62_MI1_PORT",
                "first_simh_config": "config/imp/its-pair/imp62.simh",
                "second_imp_id": "imp:6",
                "second_endpoint": "imp:6:mi1",
                "second_simh_device": "mi1",
                "second_listen_environment": "BRFID_IMP6_MI1_PORT",
                "second_simh_config": "config/imp/its-pair/imp6.simh",
            }
        ],
        "proof": {
            "kind": "passive-h316-host-interface",
            "requirements": [
                "host-ready-sent",
                "imp-ready-received",
                "complete-imp-message-received",
            ],
        },
    }


REQUEST_FINGERPRINT = correlation_fingerprint(b"RST host 106")
REPLY_FINGERPRINT = correlation_fingerprint(b"RRP from host 106")


def request_expectation() -> MessageExpectation:
    return MessageExpectation(
        correlation_fingerprint=REQUEST_FINGERPRINT,
        message_class=MessageClass.REGULAR,
        message_type=0,
        host=0o106,
        link=0,
        subtype=0,
        m1=0,
        byte_size=8,
        byte_count=0o13,
        m2=0,
        ncp_opcode=0o14,
    )


def reply_expectation() -> MessageExpectation:
    return MessageExpectation(
        correlation_fingerprint=REPLY_FINGERPRINT,
        message_class=MessageClass.REGULAR,
        message_type=0,
        host=0o106,
        link=0,
        subtype=0,
        m1=0,
        byte_size=8,
        byte_count=1,
        m2=0,
        ncp_opcode=0o15,
    )


def decoded(expectation: MessageExpectation) -> DecodedMessage:
    return DecodedMessage(
        message_class=expectation.message_class,
        leader_format="normalized-test-leader",
        message_type=expectation.message_type,
        host=expectation.host,
        link=expectation.link,
        subtype=expectation.subtype,
        m1=expectation.m1,
        byte_size=expectation.byte_size,
        byte_count=expectation.byte_count,
        m2=expectation.m2,
        ncp_opcode=expectation.ncp_opcode,
    )


def source_for(component_id: str) -> str:
    return {
        "host:176": "source:pdp11",
        "imp:62": "source:imp62",
        "imp:6": "source:imp6",
        "host:106": "source:ka10",
    }[component_id]


def complete_observations(expected: ExpectedJourney) -> list[MessageJourneyObservation]:
    observations = []
    source_sequences: defaultdict[str, int] = defaultdict(int)
    for index, boundary in enumerate(expected.boundaries, start=1):
        source_id = source_for(boundary.component_id)
        source_sequences[source_id] += 1
        expectation = (
            request_expectation() if boundary.leg == JourneyLeg.REQUEST else reply_expectation()
        )
        observations.append(
            MessageJourneyObservation(
                id=f"observation:{index}",
                journey_id=expected.id,
                leg=boundary.leg,
                component_id=boundary.component_id,
                interface_id=boundary.interface_id,
                direction=boundary.direction,
                source_local_sequence=source_sequences[source_id],
                decoded=decoded(expectation),
                correlation_fingerprint=expectation.correlation_fingerprint,
                provenance=ObservationProvenance(source_id, "synthetic-fixture"),
                simulator_tick=source_sequences[source_id] * (1 if source_id == "source:imp6" else 1000),
            )
        )
    return observations


class MessageJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = shared_topology_from_mapping(journey_topology_document())
        self.expected = build_expected_journey(
            self.topology,
            journey_id="journey:pdp11-to-its-rst",
            route_id="route:host176-to-host106",
            request=request_expectation(),
            reply=reply_expectation(),
        )

    def test_complete_request_and_reply_preserve_every_direct_support_id(self) -> None:
        observations = complete_observations(self.expected)

        diagnosis = diagnose_message_journey(self.topology, self.expected, observations)

        self.assertEqual(diagnosis.state, JourneyState.COMPLETE)
        self.assertIsNone(diagnosis.first_boundary_id)
        self.assertEqual(
            diagnosis.supporting_observation_ids,
            tuple(observation.id for observation in observations),
        )
        self.assertEqual(len(diagnosis.boundaries), 12)

    def test_reports_the_first_missing_inter_imp_boundary_without_claiming_failure(self) -> None:
        observations = complete_observations(self.expected)[:3]

        diagnosis = diagnose_message_journey(self.topology, self.expected, observations)

        self.assertEqual(diagnosis.state, JourneyState.MISSING_BOUNDARY)
        self.assertEqual(diagnosis.first_boundary_id, "boundary:request:4")
        self.assertEqual(
            diagnosis.boundaries[3].supporting_observation_ids,
            tuple(observation.id for observation in observations),
        )

    def test_rejects_a_contradictory_destination_field_at_the_host_boundary(self) -> None:
        observations = complete_observations(self.expected)[:6]
        observations[-1] = replace(
            observations[-1],
            decoded=replace(observations[-1].decoded, host=0),
        )

        diagnosis = diagnose_message_journey(self.topology, self.expected, observations)

        self.assertEqual(diagnosis.state, JourneyState.CONTRADICTORY_BOUNDARY)
        self.assertEqual(diagnosis.first_boundary_id, "boundary:request:6")
        self.assertEqual(
            diagnosis.boundaries[5].supporting_observation_ids,
            (observations[-1].id,),
        )

    def test_pdp11_reply_reaches_the_guest_boundary_but_decodes_byte_reversed(self) -> None:
        observations = complete_observations(self.expected)
        observations[-1] = replace(
            observations[-1],
            decoded=replace(
                observations[-1].decoded,
                message_type=0o106,
                host=0,
            ),
        )

        diagnosis = diagnose_message_journey(self.topology, self.expected, observations)

        self.assertEqual(diagnosis.state, JourneyState.CONTRADICTORY_BOUNDARY)
        self.assertEqual(diagnosis.first_boundary_id, "boundary:reply:6")
        self.assertEqual(
            diagnosis.boundaries[-1].supporting_observation_ids,
            (observations[-1].id,),
        )

    def test_duplicate_or_absent_evidence_remains_ambiguous_or_unknown(self) -> None:
        first = complete_observations(self.expected)[0]
        duplicate = replace(
            first,
            id="observation:duplicate",
            source_local_sequence=first.source_local_sequence + 1,
        )

        ambiguous = diagnose_message_journey(
            self.topology,
            self.expected,
            [first, duplicate],
        )
        unknown = diagnose_message_journey(self.topology, self.expected, [])

        self.assertEqual(ambiguous.state, JourneyState.AMBIGUOUS)
        self.assertEqual(ambiguous.first_boundary_id, "boundary:request:1")
        self.assertEqual(unknown.state, JourneyState.UNKNOWN)
        self.assertEqual(unknown.supporting_observation_ids, ())

    def test_unknown_topology_and_malformed_correlations_fail_closed(self) -> None:
        with self.assertRaisesRegex(JourneyValidationError, "has no route"):
            build_expected_journey(
                self.topology,
                journey_id="journey:unknown-route",
                route_id="route:missing",
                request=request_expectation(),
                reply=reply_expectation(),
            )

        observation = complete_observations(self.expected)[0]
        with self.assertRaisesRegex(JourneyValidationError, "unknown interface"):
            diagnose_message_journey(
                self.topology,
                self.expected,
                [replace(observation, interface_id="host:176:unknown")],
            )
        with self.assertRaisesRegex(JourneyValidationError, "malformed leg correlation"):
            diagnose_message_journey(
                self.topology,
                self.expected,
                [replace(observation, correlation_fingerprint=REPLY_FINGERPRINT)],
            )
        with self.assertRaisesRegex(JourneyValidationError, "direction is unsupported"):
            replace(observation, direction="sideways")  # type: ignore[arg-type]

    def test_source_local_order_fails_closed_without_comparing_independent_ticks(self) -> None:
        observations = complete_observations(self.expected)
        first_imp62 = observations[1]
        second_imp62 = observations[2]
        reversed_source_order = [
            replace(first_imp62, source_local_sequence=2, simulator_tick=200),
            replace(second_imp62, source_local_sequence=1, simulator_tick=100),
        ]

        with self.assertRaisesRegex(JourneyValidationError, "strictly increasing"):
            diagnose_message_journey(
                self.topology,
                self.expected,
                reversed_source_order,
            )

        independent_ticks = [
            replace(observations[0], simulator_tick=9_000_000),
            replace(observations[1], simulator_tick=1),
        ]
        diagnosis = diagnose_message_journey(
            self.topology,
            self.expected,
            independent_ticks,
        )
        self.assertEqual(diagnosis.state, JourneyState.MISSING_BOUNDARY)

    def test_decodes_the_established_nosc_short_leader_fields(self) -> None:
        decoded_reply = decode_nosc_short_leader(
            (0o000106, 0o000000, 0o000010, 0o000001, 0o000015)
        )

        self.assertEqual(decoded_reply.message_class, MessageClass.REGULAR)
        self.assertEqual(decoded_reply.host, 0o106)
        self.assertEqual(decoded_reply.byte_size, 8)
        self.assertEqual(decoded_reply.byte_count, 1)
        self.assertEqual(decoded_reply.ncp_opcode, 0o15)

    def test_narrow_h316_adapter_reassembles_received_hi_chunks(self) -> None:
        transfers = parse_h316_trace(
            [
                "DBG(10)> HI2 UDP: link 1 - packet received (sequence=262, length=32)",
                "DBG(10)> HI2 MSG: message received (length=2)",
                "DBG(10)> HI2 MSG: - 000106 000000 ",
                "DBG(10)> HI2 IO: receive done (message #260, intreq=000004)",
                "DBG(11)> HI2 MSG: message received (length=3)",
                "DBG(11)> HI2 MSG: - 000010 000001 000015 ",
                "DBG(11)> HI2 IO: receive done (message #260, intreq=000004)",
                "DBG(20)> MI1 MSG: message sent (length=3)",
                "DBG(20)> MI1 MSG: - 000001 000002 000003 ",
                "DBG(20)> MI1 UDP: link 0 - packet sent (sequence=7, length=3)",
            ]
        )

        self.assertEqual(len(transfers), 2)
        received, sent = transfers
        self.assertEqual(received.words, (0o106, 0, 0o10, 1, 0o15))
        self.assertEqual(received.transport_sequence, 262)
        self.assertTrue(received.complete)
        self.assertEqual(sent.transport_sequence, 7)

        observation = observation_from_h316_transfer(
            sent,
            observation_id="observation:h316",
            journey_id=self.expected.id,
            leg=JourneyLeg.REQUEST,
            component_id="imp:62",
            interface_id="imp:62:mi1",
            direction=BoundaryDirection.EGRESS,
            decoded=decoded(request_expectation()),
            fingerprint=REQUEST_FINGERPRINT,
            provenance_id="source:imp62",
        )
        self.assertEqual(observation.simulator_tick, 20)
        self.assertEqual(observation.transport_sequence, 7)

    def test_h316_adapter_rejects_compressed_message_content(self) -> None:
        transfer = parse_h316_trace(
            [
                "DBG(20)> MI1 MSG: message sent (length=8)",
                "DBG(20)> MI1 MSG: - 000001 000002 ",
                "DBG(20)> same as above (3 times)",
            ]
        )[0]

        self.assertFalse(transfer.complete)
        with self.assertRaisesRegex(H316TraceError, "incomplete or compressed"):
            observation_from_h316_transfer(
                transfer,
                observation_id="observation:compressed",
                journey_id=self.expected.id,
                leg=JourneyLeg.REQUEST,
                component_id="imp:62",
                interface_id="imp:62:mi1",
                direction=BoundaryDirection.EGRESS,
                decoded=decoded(request_expectation()),
                fingerprint=REQUEST_FINGERPRINT,
                provenance_id="source:imp62",
            )

    def test_ka10_and_imp11a_expose_typed_observation_seams(self) -> None:
        request = request_expectation()
        ka10 = observation_from_ka10_imp_trace(
            observation_id="observation:ka10",
            journey_id=self.expected.id,
            leg=JourneyLeg.REQUEST,
            component_id="host:106",
            interface_id="host:106:1822",
            direction=BoundaryDirection.INGRESS,
            source_local_sequence=17,
            decoded=decoded(request),
            fingerprint=request.correlation_fingerprint,
            provenance_id="source:ka10",
            simulator_tick=117_662_483,
        )
        pdp11 = observation_from_pdp11_imp11a_trace(
            observation_id="observation:pdp11",
            journey_id=self.expected.id,
            leg=JourneyLeg.REQUEST,
            component_id="host:176",
            interface_id="host:176:1822",
            direction=BoundaryDirection.EGRESS,
            source_local_sequence=261,
            decoded=decoded(request),
            fingerprint=request.correlation_fingerprint,
            provenance_id="source:pdp11",
            simulator_tick=1_271_684_840,
            transport_sequence=261,
        )

        self.assertEqual(ka10.provenance.kind, "ka10-imp-trace")
        self.assertEqual(pdp11.provenance.kind, "pdp11-imp11a-trace")
        self.assertNotEqual(ka10.simulator_tick, pdp11.simulator_tick)


if __name__ == "__main__":
    unittest.main()
