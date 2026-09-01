"""Typed post-cut journey extraction for the PDP-11-to-ITS alternate route."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .h316_journey import (
    H316TraceTransfer,
    observation_from_h316_transfer,
    parse_h316_trace,
)
from .message_journey import (
    BoundaryAssessmentState,
    BoundaryDirection,
    DecodedMessage,
    ExpectedBoundary,
    ExpectedJourney,
    ExternalEvidenceReference,
    JourneyDiagnosis,
    JourneyLeg,
    JourneyState,
    MessageClass,
    MessageExpectation,
    MessageJourneyObservation,
    ObservationProvenance,
    build_expected_journey,
    correlation_fingerprint_words,
    decode_nosc_short_leader,
    diagnose_message_journey,
)
from .message_journey_stream import (
    MessageJourneyStream,
    MessageJourneyStreamRecorder,
    TransactionWindowSource,
    read_message_journey_stream,
)
from .shared_topology import (
    ModemInterfaceBinding,
    SharedTopology,
    shared_topology_from_mapping,
)

PDP11_ITS_FAILOVER_JOURNEY_ID = "journey:network-unix-telnet-post-cut"
PDP11_ITS_FAILOVER_ROUTE_ID = "route:host176-to-host106-alternate"
_ROUTE_COMPONENTS = ("host:176", "imp:62", "imp:7", "imp:6", "host:106")


class Pdp11ItsFailoverJourneyError(ValueError):
    """Raised when a post-cut H316 window cannot prove the alternate route."""


@dataclass(frozen=True)
class Pdp11ItsFailoverJourneyExtraction:
    """The shared journey model populated by one post-cut transaction window."""

    expected: ExpectedJourney
    observations: tuple[MessageJourneyObservation, ...]
    diagnosis: JourneyDiagnosis


@dataclass(frozen=True)
class _RouteDevices:
    imp62_to_imp7: tuple[str, str]
    imp7_to_imp6: tuple[str, str]


@dataclass(frozen=True)
class _LegPath:
    origin_hi: H316TraceTransfer
    first_mi_out: H316TraceTransfer
    transit_mi_in: H316TraceTransfer
    transit_mi_out: H316TraceTransfer
    destination_mi_in: H316TraceTransfer
    destination_hi: H316TraceTransfer
    expectation: MessageExpectation
    origin_decoded: DecodedMessage
    transit_decoded: DecodedMessage
    destination_decoded: DecodedMessage


def write_pdp11_its_failover_journey_stream(
    path: str | Path,
    *,
    run_id: str,
    started_at: str,
    provenance: Sequence[ObservationProvenance],
    topology_document: Mapping[str, Any],
    transaction_window: Sequence[TransactionWindowSource],
    imp6_trace: bytes,
    imp7_trace: bytes,
    imp62_trace: bytes,
    h316_revision: str | None = None,
) -> MessageJourneyStream:
    """Extract and persist one exact post-cut journey sidecar."""

    topology = shared_topology_from_mapping(topology_document)
    extraction = extract_pdp11_its_failover_journey(
        topology,
        imp6_trace=imp6_trace,
        imp7_trace=imp7_trace,
        imp62_trace=imp62_trace,
        h316_revision=h316_revision,
    )
    recorder = MessageJourneyStreamRecorder(
        path,
        run_id=run_id,
        started_at=started_at,
        provenance=provenance,
        topology_document=topology_document,
        expected=extraction.expected,
        transaction_window=transaction_window,
    )
    try:
        recorder.publish(extraction.observations)
        diagnosis = recorder.complete()
    finally:
        recorder.close()
    if diagnosis != extraction.diagnosis:
        raise Pdp11ItsFailoverJourneyError(
            "persisted post-cut diagnosis changed during recording"
        )
    stream = read_message_journey_stream(path)
    if (
        not stream.is_terminal
        or stream.observations != extraction.observations
        or stream.diagnosis != extraction.diagnosis
    ):
        raise Pdp11ItsFailoverJourneyError(
            "post-cut journey sidecar does not read back as extracted"
        )
    return stream


def extract_pdp11_its_failover_journey(
    topology: SharedTopology,
    *,
    imp6_trace: bytes,
    imp7_trace: bytes,
    imp62_trace: bytes,
    h316_revision: str | None = None,
) -> Pdp11ItsFailoverJourneyExtraction:
    """Extract the first exact request/reply transaction over IMP 62–7–6.

    The caller must provide a trace window opened after the direct application
    cable was cut and immediately before the post-cut application request. Each
    cross-process modem association requires literal packet equality. Forwarding
    through IMP 7 requires the same literal host message inside both MI packets;
    simulator ticks are never compared across processes.
    """

    devices = pdp11_its_failover_modem_devices(topology)
    traces = {
        "imp6": _parse_trace(imp6_trace),
        "imp7": _parse_trace(imp7_trace),
        "imp62": _parse_trace(imp62_trace),
    }
    request = _request_path(traces, devices)
    reply = _reply_path(traces, devices, request)
    expected = build_expected_journey(
        topology,
        journey_id=PDP11_ITS_FAILOVER_JOURNEY_ID,
        route_id=PDP11_ITS_FAILOVER_ROUTE_ID,
        request=request.expectation,
        reply=reply.expectation,
    )
    observations = _observations(
        expected,
        request,
        reply,
        h316_revision=h316_revision,
    )
    diagnosis = diagnose_message_journey(topology, expected, observations)
    first = next(
        boundary
        for boundary in expected.boundaries
        if boundary.id == diagnosis.first_boundary_id
    )
    if (
        diagnosis.state != JourneyState.MISSING_BOUNDARY
        or first.leg != JourneyLeg.REQUEST
        or first.component_id != "host:106"
        or first.direction != BoundaryDirection.INGRESS
    ):
        raise Pdp11ItsFailoverJourneyError(
            "post-cut journey did not stop at the unproved host-106 ingress boundary"
        )
    return Pdp11ItsFailoverJourneyExtraction(expected, observations, diagnosis)


def pdp11_its_failover_modem_devices(topology: SharedTopology) -> _RouteDevices:
    """Return topology-bound SIMH devices for both alternate-route cables."""

    route = next(
        (
            item
            for item in topology.topology["routes"]
            if item["id"] == PDP11_ITS_FAILOVER_ROUTE_ID
        ),
        None,
    )
    if route is None or tuple(route["components"]) != _ROUTE_COMPONENTS:
        raise Pdp11ItsFailoverJourneyError(
            "shared topology lacks the exact host176-to-host106 alternate route"
        )
    interfaces = {(item.imp_id, item.host_id): item for item in topology.interfaces}
    if (
        interfaces.get(("imp:62", "host:176")) is None
        or interfaces[("imp:62", "host:176")].simh_device != "hi2"
        or interfaces.get(("imp:6", "host:106")) is None
        or interfaces[("imp:6", "host:106")].simh_device != "hi2"
    ):
        raise Pdp11ItsFailoverJourneyError(
            "shared topology does not bind both application hosts through HI2"
        )
    first = _unique_binding(topology, "imp:62", "imp:7")
    second = _unique_binding(topology, "imp:7", "imp:6")
    return _RouteDevices(
        imp62_to_imp7=(_device(first, "imp:62"), _device(first, "imp:7")),
        imp7_to_imp6=(_device(second, "imp:7"), _device(second, "imp:6")),
    )


def _request_path(
    traces: Mapping[str, tuple[H316TraceTransfer, ...]], devices: _RouteDevices
) -> _LegPath:
    for origin_hi in traces["imp62"]:
        if not _is_application_data(origin_hi, action="received", host=0o106):
            continue
        path = _forward_path(
            origin_hi=origin_hi,
            origin=traces["imp62"],
            transit=traces["imp7"],
            destination=traces["imp6"],
            origin_device=devices.imp62_to_imp7[0],
            transit_in_device=devices.imp62_to_imp7[1],
            transit_out_device=devices.imp7_to_imp6[0],
            destination_device=devices.imp7_to_imp6[1],
            destination_host=0o176,
        )
        if path is not None:
            return path
    raise Pdp11ItsFailoverJourneyError(
        "post-cut trace window has no exact application request over IMP 62–7–6"
    )


def _reply_path(
    traces: Mapping[str, tuple[H316TraceTransfer, ...]],
    devices: _RouteDevices,
    request: _LegPath,
) -> _LegPath:
    for origin_hi in traces["imp6"]:
        if (
            origin_hi.source_local_sequence
            <= request.destination_hi.source_local_sequence
            or not _is_application_data(origin_hi, action="received", host=0o176)
        ):
            continue
        decoded = decode_nosc_short_leader(origin_hi.words)
        if decoded.link != request.origin_decoded.link:
            continue
        path = _forward_path(
            origin_hi=origin_hi,
            origin=traces["imp6"],
            transit=traces["imp7"],
            destination=traces["imp62"],
            origin_device=devices.imp7_to_imp6[1],
            transit_in_device=devices.imp7_to_imp6[0],
            transit_out_device=devices.imp62_to_imp7[1],
            destination_device=devices.imp62_to_imp7[0],
            destination_host=0o106,
        )
        if path is not None:
            return path
    raise Pdp11ItsFailoverJourneyError(
        "post-cut trace window has no exact application reply over IMP 6–7–62"
    )


def _forward_path(
    *,
    origin_hi: H316TraceTransfer,
    origin: tuple[H316TraceTransfer, ...],
    transit: tuple[H316TraceTransfer, ...],
    destination: tuple[H316TraceTransfer, ...],
    origin_device: str,
    transit_in_device: str,
    transit_out_device: str,
    destination_device: str,
    destination_host: int,
) -> _LegPath | None:
    origin_decoded = decode_nosc_short_leader(origin_hi.words)
    expectation = _expectation(origin_hi, origin_decoded)
    first_mi_out = _find_first(
        transfer
        for transfer in origin
        if transfer.source_local_sequence > origin_hi.source_local_sequence
        and _is_mi(transfer, action="sent", device=origin_device)
        and _mi_packet_contains_hi_message(transfer.words, origin_hi.words)
    )
    if first_mi_out is None:
        return None
    transit_mi_in = _find_first(
        transfer
        for transfer in transit
        if _is_mi(transfer, action="received", device=transit_in_device)
        and transfer.words == first_mi_out.words
    )
    if transit_mi_in is None:
        return None
    transit_mi_out = _find_first(
        transfer
        for transfer in transit
        if transfer.source_local_sequence > transit_mi_in.source_local_sequence
        and _is_mi(transfer, action="sent", device=transit_out_device)
        and _mi_packet_contains_hi_message(transfer.words, origin_hi.words)
    )
    if transit_mi_out is None:
        return None
    destination_mi_in = _find_first(
        transfer
        for transfer in destination
        if _is_mi(transfer, action="received", device=destination_device)
        and transfer.words == transit_mi_out.words
    )
    if destination_mi_in is None:
        return None
    destination_hi = _find_first(
        transfer
        for transfer in destination
        if transfer.source_local_sequence > destination_mi_in.source_local_sequence
        and _is_hi(transfer, action="sent")
        and _matches_expectation(transfer, expectation)
    )
    if destination_hi is None:
        return None
    destination_decoded = decode_nosc_short_leader(destination_hi.words)
    if destination_decoded.host != destination_host:
        return None
    return _LegPath(
        origin_hi=origin_hi,
        first_mi_out=first_mi_out,
        transit_mi_in=transit_mi_in,
        transit_mi_out=transit_mi_out,
        destination_mi_in=destination_mi_in,
        destination_hi=destination_hi,
        expectation=expectation,
        origin_decoded=origin_decoded,
        transit_decoded=origin_decoded,
        destination_decoded=destination_decoded,
    )


def _observations(
    expected: ExpectedJourney,
    request: _LegPath,
    reply: _LegPath,
    *,
    h316_revision: str | None,
) -> tuple[MessageJourneyObservation, ...]:
    request_boundaries = _boundaries(expected, JourneyLeg.REQUEST)
    reply_boundaries = _boundaries(expected, JourneyLeg.REPLY)
    return (
        _connected_peer_egress(
            request.origin_hi,
            request_boundaries[0],
            request.origin_decoded,
            request.expectation,
            receiver="imp62",
            revision=h316_revision,
        ),
        _direct(
            request.origin_hi,
            request_boundaries[1],
            request.origin_decoded,
            request.expectation,
            source="imp62",
            revision=h316_revision,
        ),
        _direct(
            request.first_mi_out,
            request_boundaries[2],
            request.origin_decoded,
            request.expectation,
            source="imp62",
            revision=h316_revision,
        ),
        _direct(
            request.transit_mi_in,
            request_boundaries[3],
            request.transit_decoded,
            request.expectation,
            source="imp7",
            revision=h316_revision,
        ),
        _direct(
            request.transit_mi_out,
            request_boundaries[4],
            request.transit_decoded,
            request.expectation,
            source="imp7",
            revision=h316_revision,
        ),
        _direct(
            request.destination_mi_in,
            request_boundaries[5],
            request.destination_decoded,
            request.expectation,
            source="imp6",
            revision=h316_revision,
        ),
        _direct(
            request.destination_hi,
            request_boundaries[6],
            request.destination_decoded,
            request.expectation,
            source="imp6",
            revision=h316_revision,
        ),
        _connected_peer_egress(
            reply.origin_hi,
            reply_boundaries[0],
            reply.origin_decoded,
            reply.expectation,
            receiver="imp6",
            revision=h316_revision,
        ),
        _direct(
            reply.origin_hi,
            reply_boundaries[1],
            reply.origin_decoded,
            reply.expectation,
            source="imp6",
            revision=h316_revision,
        ),
        _direct(
            reply.first_mi_out,
            reply_boundaries[2],
            reply.origin_decoded,
            reply.expectation,
            source="imp6",
            revision=h316_revision,
        ),
        _direct(
            reply.transit_mi_in,
            reply_boundaries[3],
            reply.transit_decoded,
            reply.expectation,
            source="imp7",
            revision=h316_revision,
        ),
        _direct(
            reply.transit_mi_out,
            reply_boundaries[4],
            reply.transit_decoded,
            reply.expectation,
            source="imp7",
            revision=h316_revision,
        ),
        _direct(
            reply.destination_mi_in,
            reply_boundaries[5],
            reply.destination_decoded,
            reply.expectation,
            source="imp62",
            revision=h316_revision,
        ),
        _direct(
            reply.destination_hi,
            reply_boundaries[6],
            reply.destination_decoded,
            reply.expectation,
            source="imp62",
            revision=h316_revision,
        ),
    )


def _direct(
    transfer: H316TraceTransfer,
    boundary: ExpectedBoundary,
    decoded: DecodedMessage,
    expectation: MessageExpectation,
    *,
    source: str,
    revision: str | None,
) -> MessageJourneyObservation:
    observation = observation_from_h316_transfer(
        transfer,
        observation_id=f"observation:{boundary.leg.value}:{boundary.position}",
        journey_id=PDP11_ITS_FAILOVER_JOURNEY_ID,
        leg=boundary.leg,
        component_id=boundary.component_id,
        interface_id=boundary.interface_id,
        direction=boundary.direction,
        decoded=decoded,
        fingerprint=expectation.correlation_fingerprint,
        provenance_id=f"source:{source}",
        external_evidence=(_evidence(transfer, source),),
    )
    if revision is None:
        return observation
    return replace(
        observation,
        provenance=ObservationProvenance(
            id=observation.provenance.id,
            kind=observation.provenance.kind,
            revision=revision,
        ),
    )


def _connected_peer_egress(
    transfer: H316TraceTransfer,
    boundary: ExpectedBoundary,
    decoded: DecodedMessage,
    expectation: MessageExpectation,
    *,
    receiver: str,
    revision: str | None,
) -> MessageJourneyObservation:
    if transfer.action != "received" or boundary.direction != BoundaryDirection.EGRESS:
        raise Pdp11ItsFailoverJourneyError(
            "connected-peer evidence requires an H316 receive for peer egress"
        )
    return MessageJourneyObservation(
        id=f"observation:{boundary.leg.value}:{boundary.position}",
        journey_id=PDP11_ITS_FAILOVER_JOURNEY_ID,
        leg=boundary.leg,
        component_id=boundary.component_id,
        interface_id=boundary.interface_id,
        direction=boundary.direction,
        source_local_sequence=transfer.source_local_sequence,
        decoded=decoded,
        correlation_fingerprint=expectation.correlation_fingerprint,
        provenance=ObservationProvenance(
            id=f"source:{receiver}:connected-peer",
            kind="h316-connected-peer-delivery",
            revision=revision,
        ),
        simulator_tick=transfer.simulator_tick,
        transport_sequence=transfer.transport_sequence,
        external_evidence=(_evidence(transfer, receiver),),
    )


def _expectation(
    transfer: H316TraceTransfer, decoded: DecodedMessage
) -> MessageExpectation:
    return MessageExpectation(
        correlation_fingerprint=_content_fingerprint(transfer),
        message_class=decoded.message_class,
        message_type=decoded.message_type,
        host=None,
        link=decoded.link,
        subtype=decoded.subtype,
        m1=decoded.m1,
        byte_size=decoded.byte_size,
        byte_count=decoded.byte_count,
        m2=decoded.m2,
        ncp_opcode=decoded.ncp_opcode,
    )


def _matches_expectation(
    transfer: H316TraceTransfer, expectation: MessageExpectation
) -> bool:
    return (
        _is_hi(transfer, action=transfer.action)
        and _content_fingerprint(transfer) == expectation.correlation_fingerprint
        and expectation.compare(decode_nosc_short_leader(transfer.words))
        == BoundaryAssessmentState.OBSERVED
    )


def _content_fingerprint(transfer: H316TraceTransfer) -> str:
    if len(transfer.words) < 2:
        raise Pdp11ItsFailoverJourneyError(
            "H316 host message lacks its two-word 1822 leader"
        )
    return correlation_fingerprint_words(transfer.words[2:])


def _is_application_data(
    transfer: H316TraceTransfer, *, action: str, host: int
) -> bool:
    if not _is_hi(transfer, action=action) or len(transfer.words) < 5:
        return False
    decoded = decode_nosc_short_leader(transfer.words)
    return (
        decoded.message_class == MessageClass.REGULAR
        and decoded.message_type == 0
        and decoded.host == host
        and decoded.link is not None
        and decoded.link > 0
        and decoded.byte_size == 8
        and decoded.byte_count is not None
        and decoded.byte_count > 0
    )


def _is_hi(transfer: H316TraceTransfer, *, action: str) -> bool:
    return (
        transfer.complete
        and transfer.device == "HI2"
        and transfer.action == action
        and len(transfer.words) >= 2
    )


def _is_mi(transfer: H316TraceTransfer, *, action: str, device: str) -> bool:
    return (
        transfer.complete
        and transfer.device == device.upper()
        and transfer.action == action
    )


def _mi_packet_contains_hi_message(
    modem_words: tuple[int, ...], host_words: tuple[int, ...]
) -> bool:
    return (
        len(host_words) >= 2
        and len(modem_words) == len(host_words) + 4
        and modem_words[2] == host_words[0]
        and modem_words[4:-1] == host_words[1:]
    )


def _boundaries(
    expected: ExpectedJourney, leg: JourneyLeg
) -> tuple[ExpectedBoundary, ...]:
    boundaries = tuple(item for item in expected.boundaries if item.leg == leg)
    if len(boundaries) != 8:
        raise Pdp11ItsFailoverJourneyError(
            "post-cut PDP-11-to-ITS route must have eight boundaries per leg"
        )
    return boundaries


def _parse_trace(content: bytes) -> tuple[H316TraceTransfer, ...]:
    try:
        return parse_h316_trace(content.decode("ascii").splitlines())
    except UnicodeDecodeError as error:
        raise Pdp11ItsFailoverJourneyError(
            "post-cut H316 trace window is not ASCII"
        ) from error


def _unique_binding(
    topology: SharedTopology, first_imp: str, second_imp: str
) -> ModemInterfaceBinding:
    bindings = tuple(
        item
        for item in topology.modem_interfaces
        if frozenset((item.first_imp_id, item.second_imp_id))
        == frozenset((first_imp, second_imp))
    )
    if len(bindings) != 1:
        raise Pdp11ItsFailoverJourneyError(
            f"shared topology must bind {first_imp} and {second_imp} exactly once"
        )
    return bindings[0]


def _device(binding: ModemInterfaceBinding, imp_id: str) -> str:
    if binding.first_imp_id == imp_id:
        return binding.first_simh_device
    if binding.second_imp_id == imp_id:
        return binding.second_simh_device
    raise Pdp11ItsFailoverJourneyError(
        f"modem binding {binding.id!r} does not contain {imp_id!r}"
    )


def _evidence(transfer: H316TraceTransfer, source: str) -> ExternalEvidenceReference:
    transport = (
        "none"
        if transfer.transport_sequence is None
        else str(transfer.transport_sequence)
    )
    return ExternalEvidenceReference(
        id=f"evidence:{source}:{transfer.source_local_sequence}",
        kind="h316-trace-transfer",
        locator=(
            f"{source}.debug.log#transfer={transfer.source_local_sequence};"
            f"tick={transfer.simulator_tick};transport={transport}"
        ),
    )


def _find_first(values: Any) -> H316TraceTransfer | None:
    return next(iter(values), None)
