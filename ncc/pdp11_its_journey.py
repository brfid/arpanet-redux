"""Typed message-journey extraction for the formal PDP-11-to-ITS gate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
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
from .shared_topology import SharedTopology, shared_topology_from_mapping


PDP11_ITS_JOURNEY_ID = "journey:network-unix-telnet-open"
PDP11_ITS_ROUTE_ID = "route:host176-to-host106"
_ROUTE_COMPONENTS = ("host:176", "imp:62", "imp:6", "host:106")


class Pdp11ItsJourneyError(ValueError):
    """Raised when the formal trace window cannot support the typed journey."""


@dataclass(frozen=True)
class Pdp11ItsJourneyExtraction:
    """The existing model populated by the formal H316 trace evidence."""

    expected: ExpectedJourney
    observations: tuple[MessageJourneyObservation, ...]
    diagnosis: JourneyDiagnosis


@dataclass(frozen=True)
class _LegPath:
    origin_hi: H316TraceTransfer
    origin_mi: H316TraceTransfer
    destination_mi: H316TraceTransfer
    destination_hi: H316TraceTransfer
    expectation: MessageExpectation
    origin_decoded: DecodedMessage
    destination_decoded: DecodedMessage


def write_pdp11_its_journey_stream(
    path: str | Path,
    *,
    run_id: str,
    started_at: str,
    provenance: Sequence[ObservationProvenance],
    topology_document: Mapping[str, Any],
    transaction_window: Sequence[TransactionWindowSource],
    imp6_trace: bytes,
    imp62_trace: bytes,
    h316_revision: str | None = None,
) -> MessageJourneyStream:
    """Extract, record, and read back one formal typed journey sidecar."""

    topology = shared_topology_from_mapping(topology_document)
    extraction = extract_pdp11_its_journey(
        topology,
        imp6_trace=imp6_trace,
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
        raise Pdp11ItsJourneyError(
            "persisted message-journey diagnosis changed during recording"
        )
    stream = read_message_journey_stream(path)
    if (
        not stream.is_terminal
        or stream.observations != extraction.observations
        or stream.diagnosis != extraction.diagnosis
    ):
        raise Pdp11ItsJourneyError(
            "message-journey sidecar does not read back as the extracted journey"
        )
    return stream


def transaction_window_source(
    *,
    source_id: str,
    artifact: str,
    start_offset: int,
    end_offset: int,
    content: bytes,
) -> TransactionWindowSource:
    """Bind one already-read trace slice to its exact byte range and digest."""

    if end_offset - start_offset != len(content):
        raise Pdp11ItsJourneyError(
            "transaction window offsets do not match the supplied trace slice"
        )
    return TransactionWindowSource(
        id=source_id,
        artifact=artifact,
        start_offset=start_offset,
        end_offset=end_offset,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def extract_pdp11_its_journey(
    topology: SharedTopology,
    *,
    imp6_trace: bytes,
    imp62_trace: bytes,
    h316_revision: str | None = None,
) -> Pdp11ItsJourneyExtraction:
    """Extract the first exact TELNET-open request and correlated reply path.

    Every cross-process association uses literal packet equality. Within one
    H316 process, source-local sequence establishes the adjacent HI-to-MI or
    MI-to-HI transition. The adapter never compares simulator ticks.
    """

    imp62_mi_device, imp6_mi_device = pdp11_its_modem_devices(topology)
    try:
        imp6 = parse_h316_trace(imp6_trace.decode("ascii").splitlines())
        imp62 = parse_h316_trace(imp62_trace.decode("ascii").splitlines())
    except UnicodeDecodeError as error:
        raise Pdp11ItsJourneyError("formal H316 trace window is not ASCII") from error

    request = _request_path(
        imp62,
        imp6,
        origin_mi_device=imp62_mi_device,
        destination_mi_device=imp6_mi_device,
    )
    reply = _reply_path(
        imp6,
        imp62,
        request,
        origin_mi_device=imp6_mi_device,
        destination_mi_device=imp62_mi_device,
    )
    expected = build_expected_journey(
        topology,
        journey_id=PDP11_ITS_JOURNEY_ID,
        route_id=PDP11_ITS_ROUTE_ID,
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
        raise Pdp11ItsJourneyError(
            "formal journey did not stop at the expected unproved host-106 ingress boundary"
        )
    return Pdp11ItsJourneyExtraction(expected, observations, diagnosis)


def _request_path(
    imp62: tuple[H316TraceTransfer, ...],
    imp6: tuple[H316TraceTransfer, ...],
    *,
    origin_mi_device: str,
    destination_mi_device: str,
) -> _LegPath:
    origin_hi = _first(
        transfer
        for transfer in imp62
        if _is_hi(transfer, action="received")
        and _is_telnet_open_request(transfer)
    )
    origin_decoded = decode_nosc_short_leader(origin_hi.words)
    expectation = _expectation(origin_hi, origin_decoded)
    origin_mi = _first(
        transfer
        for transfer in imp62
        if transfer.source_local_sequence > origin_hi.source_local_sequence
        and _is_mi(transfer, action="sent", device=origin_mi_device)
        and _mi_packet_contains_hi_message(transfer.words, origin_hi.words)
    )
    destination_mi = _first(
        transfer
        for transfer in imp6
        if _is_mi(transfer, action="received", device=destination_mi_device)
        and transfer.words == origin_mi.words
    )
    destination_hi = _first(
        transfer
        for transfer in imp6
        if transfer.source_local_sequence > destination_mi.source_local_sequence
        and _is_hi(transfer, action="sent")
        and _matches_expectation(transfer, expectation)
    )
    destination_decoded = decode_nosc_short_leader(destination_hi.words)
    if origin_decoded.host != 0o106 or destination_decoded.host != 0o176:
        raise Pdp11ItsJourneyError(
            "TELNET-open request does not retain destination 106 and source 176 identities"
        )
    return _LegPath(
        origin_hi,
        origin_mi,
        destination_mi,
        destination_hi,
        expectation,
        origin_decoded,
        destination_decoded,
    )


def _reply_path(
    imp6: tuple[H316TraceTransfer, ...],
    imp62: tuple[H316TraceTransfer, ...],
    request: _LegPath,
    *,
    origin_mi_device: str,
    destination_mi_device: str,
) -> _LegPath:
    for origin_hi in imp6:
        if (
            origin_hi.source_local_sequence
            <= request.destination_hi.source_local_sequence
            or not _is_hi(origin_hi, action="received")
            or not _is_control_reply(origin_hi)
        ):
            continue
        origin_decoded = decode_nosc_short_leader(origin_hi.words)
        expectation = _expectation(origin_hi, origin_decoded)
        origin_mi = _find_first(
            transfer
            for transfer in imp6
            if transfer.source_local_sequence > origin_hi.source_local_sequence
            and _is_mi(transfer, action="sent", device=origin_mi_device)
            and _mi_packet_contains_hi_message(transfer.words, origin_hi.words)
        )
        if origin_mi is None:
            continue
        destination_mi = _find_first(
            transfer
            for transfer in imp62
            if _is_mi(transfer, action="received", device=destination_mi_device)
            and transfer.words == origin_mi.words
        )
        if destination_mi is None:
            continue
        destination_hi = _find_first(
            transfer
            for transfer in imp62
            if transfer.source_local_sequence > destination_mi.source_local_sequence
            and _is_hi(transfer, action="sent")
            and _matches_expectation(transfer, expectation)
        )
        if destination_hi is None:
            continue
        destination_decoded = decode_nosc_short_leader(destination_hi.words)
        if origin_decoded.host != 0o176 or destination_decoded.host != 0o106:
            continue
        return _LegPath(
            origin_hi,
            origin_mi,
            destination_mi,
            destination_hi,
            expectation,
            origin_decoded,
            destination_decoded,
        )
    raise Pdp11ItsJourneyError(
        "formal trace window has no exact first control reply path after the TELNET RFC"
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
    observations = (
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
            request.origin_mi,
            request_boundaries[2],
            request.origin_decoded,
            request.expectation,
            source="imp62",
            revision=h316_revision,
        ),
        _direct(
            request.destination_mi,
            request_boundaries[3],
            request.destination_decoded,
            request.expectation,
            source="imp6",
            revision=h316_revision,
        ),
        _direct(
            request.destination_hi,
            request_boundaries[4],
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
            reply.origin_mi,
            reply_boundaries[2],
            reply.origin_decoded,
            reply.expectation,
            source="imp6",
            revision=h316_revision,
        ),
        _direct(
            reply.destination_mi,
            reply_boundaries[3],
            reply.destination_decoded,
            reply.expectation,
            source="imp62",
            revision=h316_revision,
        ),
        _direct(
            reply.destination_hi,
            reply_boundaries[4],
            reply.destination_decoded,
            reply.expectation,
            source="imp62",
            revision=h316_revision,
        ),
    )
    return observations


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
        journey_id=PDP11_ITS_JOURNEY_ID,
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
        raise Pdp11ItsJourneyError(
            "connected-peer evidence requires an H316 receive for peer egress"
        )
    return MessageJourneyObservation(
        id=f"observation:{boundary.leg.value}:{boundary.position}",
        journey_id=PDP11_ITS_JOURNEY_ID,
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


def _evidence(
    transfer: H316TraceTransfer, source: str
) -> ExternalEvidenceReference:
    transport = (
        "none" if transfer.transport_sequence is None else str(transfer.transport_sequence)
    )
    return ExternalEvidenceReference(
        id=f"evidence:{source}:{transfer.source_local_sequence}",
        kind="h316-trace-transfer",
        locator=(
            f"{source}.debug.log#transfer={transfer.source_local_sequence};"
            f"tick={transfer.simulator_tick};transport={transport}"
        ),
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
    if not _is_hi(transfer, action=transfer.action):
        return False
    if _content_fingerprint(transfer) != expectation.correlation_fingerprint:
        return False
    return (
        expectation.compare(decode_nosc_short_leader(transfer.words))
        == BoundaryAssessmentState.OBSERVED
    )


def _content_fingerprint(transfer: H316TraceTransfer) -> str:
    if len(transfer.words) < 2:
        raise Pdp11ItsJourneyError("H316 host message lacks its two-word 1822 leader")
    return correlation_fingerprint_words(transfer.words[2:])


def _is_telnet_open_request(transfer: H316TraceTransfer) -> bool:
    if not _is_hi(transfer, action="received") or len(transfer.words) < 5:
        return False
    decoded = decode_nosc_short_leader(transfer.words)
    return (
        decoded.message_class == MessageClass.REGULAR
        and decoded.message_type == 0
        and decoded.host == 0o106
        and decoded.link == 0
        and decoded.byte_size == 8
        and decoded.ncp_opcode == 1
    )


def _is_control_reply(transfer: H316TraceTransfer) -> bool:
    if not _is_hi(transfer, action="received") or len(transfer.words) < 5:
        return False
    decoded = decode_nosc_short_leader(transfer.words)
    return (
        decoded.message_class == MessageClass.REGULAR
        and decoded.message_type == 0
        and decoded.host == 0o176
        and decoded.link == 0
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


def _is_mi(
    transfer: H316TraceTransfer, *, action: str, device: str
) -> bool:
    return (
        transfer.complete
        and transfer.device == device.upper()
        and transfer.action == action
    )


def _mi_packet_contains_hi_message(
    modem_words: tuple[int, ...], host_words: tuple[int, ...]
) -> bool:
    """Match the literal host message inside one established H316 MI packet.

    This deliberately does not interpret the four MI-only envelope/checksum
    words. It requires the observed host leader word and every remaining host
    word to appear in their established literal positions.
    """

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
    if len(boundaries) != 6:
        raise Pdp11ItsJourneyError(
            "formal PDP-11-to-ITS route must have six boundaries per leg"
        )
    return boundaries


def pdp11_its_modem_devices(topology: SharedTopology) -> tuple[str, str]:
    """Return the exact IMP 62 and IMP 6 SIMH devices on the formal route."""

    route = next(
        (
            item
            for item in topology.topology["routes"]
            if item["id"] == PDP11_ITS_ROUTE_ID
        ),
        None,
    )
    if route is None or tuple(route["components"]) != _ROUTE_COMPONENTS:
        raise Pdp11ItsJourneyError(
            "shared topology lacks the formal host176-to-host106 component route"
        )
    interfaces = {(item.imp_id, item.host_id): item for item in topology.interfaces}
    if (
        interfaces.get(("imp:62", "host:176")) is None
        or interfaces[("imp:62", "host:176")].simh_device != "hi2"
        or interfaces.get(("imp:6", "host:106")) is None
        or interfaces[("imp:6", "host:106")].simh_device != "hi2"
    ):
        raise Pdp11ItsJourneyError(
            "shared topology does not bind both formal hosts through HI2"
        )
    modem_bindings = tuple(
        item
        for item in topology.modem_interfaces
        if frozenset((item.first_imp_id, item.second_imp_id))
        == frozenset(("imp:62", "imp:6"))
    )
    if len(modem_bindings) != 1:
        raise Pdp11ItsJourneyError(
            "shared topology must bind IMP 62 and IMP 6 through exactly one modem interface"
        )
    binding = modem_bindings[0]
    if binding.first_imp_id == "imp:62":
        return binding.first_simh_device, binding.second_simh_device
    return binding.second_simh_device, binding.first_simh_device


def _first(values: Any) -> H316TraceTransfer:
    value = _find_first(values)
    if value is None:
        raise Pdp11ItsJourneyError(
            "formal trace window is missing an exact message-journey boundary"
        )
    return value


def _find_first(values: Any) -> H316TraceTransfer | None:
    return next(iter(values), None)
