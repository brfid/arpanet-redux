"""Source-only correlation of one message journey across a shared topology.

This module deliberately does not extend the accepted completed-run summary or
controller-live stream. It derives expected attachment boundaries from one
validated shared-topology route, accepts direct source-local observations, and
returns an evidence-backed diagnosis without inventing a global simulator clock.
"""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

from .run_summary import RunSummaryValidationError, validate_normalized_topology
from .shared_topology import SharedTopology

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CORRELATION_FIELDS = (
    "message_type",
    "host",
    "link",
    "subtype",
    "m1",
    "byte_size",
    "byte_count",
    "m2",
    "ncp_opcode",
)
_OCTET_CORRELATION_FIELDS = tuple(
    field for field in _CORRELATION_FIELDS if field != "byte_count"
)


class JourneyValidationError(ValueError):
    """Raised when topology or direct evidence cannot safely support a journey."""


class BoundaryDirection(str, Enum):
    """Direction of a message at one component-owned interface."""

    INGRESS = "ingress"
    EGRESS = "egress"


class JourneyLeg(str, Enum):
    """One direction of a request/reply transaction."""

    REQUEST = "request"
    REPLY = "reply"


class MessageClass(str, Enum):
    """Safely normalized 1822 message classes used for correlation."""

    REGULAR = "regular"
    ERROR_WITH_LEADER = "error-with-leader"
    NOP = "nop"
    RFNM = "rfnm"
    IMP_CONTROL = "imp-control"
    UNKNOWN = "unknown"


class BoundaryAssessmentState(str, Enum):
    """Evidence condition at one expected route boundary."""

    OBSERVED = "observed"
    MISSING = "missing"
    CONTRADICTORY = "contradictory"
    AMBIGUOUS = "ambiguous"


class JourneyState(str, Enum):
    """The first evidence-backed condition for a complete request/reply path."""

    COMPLETE = "complete"
    MISSING_BOUNDARY = "missing-boundary"
    CONTRADICTORY_BOUNDARY = "contradictory-boundary"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExternalEvidenceReference:
    """An optional opaque pointer that never affects diagnostic semantics."""

    id: str
    kind: str
    locator: str

    def __post_init__(self) -> None:
        _stable_identifier(self.id, "external evidence id")
        _nonempty_text(self.kind, "external evidence kind")
        _nonempty_text(self.locator, "external evidence locator")


@dataclass(frozen=True)
class ObservationProvenance:
    """The source-local producer of one direct observation."""

    id: str
    kind: str
    revision: str | None = None

    def __post_init__(self) -> None:
        _stable_identifier(self.id, "observation provenance id")
        _nonempty_text(self.kind, "observation provenance kind")
        if self.revision is not None:
            _nonempty_text(self.revision, "observation provenance revision")


@dataclass(frozen=True)
class DecodedMessage:
    """Safely decoded 1822/NCP fields, excluding raw message content."""

    message_class: MessageClass
    leader_format: str
    message_type: int | None = None
    host: int | None = None
    link: int | None = None
    subtype: int | None = None
    m1: int | None = None
    byte_size: int | None = None
    byte_count: int | None = None
    m2: int | None = None
    ncp_opcode: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.message_class, MessageClass):
            raise JourneyValidationError("decoded message_class is unsupported")
        _nonempty_text(self.leader_format, "decoded leader_format")
        for name in _OCTET_CORRELATION_FIELDS:
            _optional_unsigned(getattr(self, name), 0xFF, f"decoded {name}")
        _optional_unsigned(self.byte_count, 0xFFFF, "decoded byte_count")


@dataclass(frozen=True)
class MessageExpectation:
    """Fields and safe content fingerprint expected on one journey leg."""

    correlation_fingerprint: str
    message_class: MessageClass
    message_type: int | None = None
    host: int | None = None
    link: int | None = None
    subtype: int | None = None
    m1: int | None = None
    byte_size: int | None = None
    byte_count: int | None = None
    m2: int | None = None
    ncp_opcode: int | None = None

    def __post_init__(self) -> None:
        _fingerprint(self.correlation_fingerprint, "message expectation fingerprint")
        if not isinstance(self.message_class, MessageClass):
            raise JourneyValidationError("message expectation class is unsupported")
        for name in _OCTET_CORRELATION_FIELDS:
            _optional_unsigned(getattr(self, name), 0xFF, f"message expectation {name}")
        _optional_unsigned(self.byte_count, 0xFFFF, "message expectation byte_count")

    def compare(self, message: DecodedMessage) -> BoundaryAssessmentState:
        """Classify a decoded direct observation without guessing missing fields."""

        if message.message_class != self.message_class:
            if message.message_class == MessageClass.UNKNOWN:
                return BoundaryAssessmentState.AMBIGUOUS
            return BoundaryAssessmentState.CONTRADICTORY
        incomplete = False
        for name in _CORRELATION_FIELDS:
            expected = getattr(self, name)
            if expected is None:
                continue
            observed = getattr(message, name)
            if observed is None:
                incomplete = True
            elif observed != expected:
                return BoundaryAssessmentState.CONTRADICTORY
        if incomplete:
            return BoundaryAssessmentState.AMBIGUOUS
        return BoundaryAssessmentState.OBSERVED


@dataclass(frozen=True)
class ExpectedBoundary:
    """One topology-derived interface crossing on a request or reply path."""

    id: str
    leg: JourneyLeg
    position: int
    component_id: str
    interface_id: str
    direction: BoundaryDirection

    def __post_init__(self) -> None:
        _stable_identifier(self.id, "expected boundary id")
        if not isinstance(self.leg, JourneyLeg):
            raise JourneyValidationError("expected boundary leg is unsupported")
        if isinstance(self.position, bool) or not isinstance(self.position, int) or self.position <= 0:
            raise JourneyValidationError("expected boundary position must be positive")
        _stable_identifier(self.component_id, "expected boundary component_id")
        _stable_identifier(self.interface_id, "expected boundary interface_id")
        if not isinstance(self.direction, BoundaryDirection):
            raise JourneyValidationError("expected boundary direction is unsupported")


@dataclass(frozen=True)
class ExpectedJourney:
    """A request/reply route with separate semantic correlation expectations."""

    id: str
    topology_id: str
    route_id: str
    request: MessageExpectation
    reply: MessageExpectation
    boundaries: tuple[ExpectedBoundary, ...]

    def __post_init__(self) -> None:
        _stable_identifier(self.id, "expected journey id")
        _stable_identifier(self.topology_id, "expected journey topology_id")
        _stable_identifier(self.route_id, "expected journey route_id")
        if not isinstance(self.request, MessageExpectation) or not isinstance(
            self.reply, MessageExpectation
        ):
            raise JourneyValidationError("expected journey message contracts are invalid")
        if not self.boundaries:
            raise JourneyValidationError("expected journey must contain route boundaries")


@dataclass(frozen=True)
class MessageJourneyObservation:
    """One direct, source-local observation at a configured interface boundary."""

    id: str
    journey_id: str
    leg: JourneyLeg
    component_id: str
    interface_id: str
    direction: BoundaryDirection
    source_local_sequence: int
    decoded: DecodedMessage
    correlation_fingerprint: str
    provenance: ObservationProvenance
    simulator_tick: int | None = None
    transport_sequence: int | None = None
    external_evidence: tuple[ExternalEvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        _stable_identifier(self.id, "observation id")
        _stable_identifier(self.journey_id, "observation journey_id")
        _stable_identifier(self.component_id, "observation component_id")
        _stable_identifier(self.interface_id, "observation interface_id")
        if not isinstance(self.leg, JourneyLeg):
            raise JourneyValidationError("observation leg is unsupported")
        if not isinstance(self.direction, BoundaryDirection):
            raise JourneyValidationError("observation direction is unsupported")
        if not isinstance(self.decoded, DecodedMessage):
            raise JourneyValidationError("observation decoded message is invalid")
        if not isinstance(self.provenance, ObservationProvenance):
            raise JourneyValidationError("observation provenance is invalid")
        _unsigned(self.source_local_sequence, "observation source_local_sequence")
        _optional_unsigned(self.simulator_tick, 2**63 - 1, "observation simulator_tick")
        _optional_unsigned(
            self.transport_sequence,
            0xFFFFFFFF,
            "observation transport_sequence",
        )
        _fingerprint(self.correlation_fingerprint, "observation fingerprint")
        evidence_ids: set[str] = set()
        for reference in self.external_evidence:
            if not isinstance(reference, ExternalEvidenceReference):
                raise JourneyValidationError("observation external evidence is invalid")
            if reference.id in evidence_ids:
                raise JourneyValidationError("observation external evidence ids must be unique")
            evidence_ids.add(reference.id)


@dataclass(frozen=True)
class BoundaryAssessment:
    """The direct-evidence assessment for one expected boundary."""

    boundary: ExpectedBoundary
    state: BoundaryAssessmentState
    supporting_observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, ExpectedBoundary):
            raise JourneyValidationError("boundary assessment target is invalid")
        if not isinstance(self.state, BoundaryAssessmentState):
            raise JourneyValidationError("boundary assessment state is invalid")
        _unique_identifiers(
            self.supporting_observation_ids,
            "boundary assessment supporting observation ids",
        )


@dataclass(frozen=True)
class JourneyDiagnosis:
    """The first route condition plus every boundary-level evidence result."""

    journey_id: str
    state: JourneyState
    first_boundary_id: str | None
    supporting_observation_ids: tuple[str, ...]
    boundaries: tuple[BoundaryAssessment, ...]

    def __post_init__(self) -> None:
        _stable_identifier(self.journey_id, "journey diagnosis id")
        if not isinstance(self.state, JourneyState):
            raise JourneyValidationError("journey diagnosis state is invalid")
        if self.first_boundary_id is not None:
            _stable_identifier(self.first_boundary_id, "journey diagnosis first boundary id")
        _unique_identifiers(
            self.supporting_observation_ids,
            "journey diagnosis supporting observation ids",
        )


def correlation_fingerprint(content: bytes) -> str:
    """Return a safe content digest without retaining the correlated content."""

    if not isinstance(content, bytes):
        raise JourneyValidationError("correlation content must be bytes")
    return hashlib.sha256(content).hexdigest()


def correlation_fingerprint_words(words: Sequence[int]) -> str:
    """Digest 16-bit words in network order without retaining the word sequence."""

    payload = bytearray()
    for index, word in enumerate(words):
        _unsigned_word(word, f"fingerprint word {index}")
        payload.extend(struct.pack(">H", word))
    return correlation_fingerprint(bytes(payload))


def decode_nosc_short_leader(words: Sequence[int]) -> DecodedMessage:
    """Decode the established NOSC short 1822/NCP leader used by the PDP-11 run."""

    if len(words) < 2:
        raise JourneyValidationError("NOSC short leader requires at least two words")
    for index, word in enumerate(words):
        _unsigned_word(word, f"NOSC short leader word {index}")
    first, second = words[:2]
    message_type = (first >> 8) & 0xFF
    message_class = {
        0: MessageClass.REGULAR,
        1: MessageClass.ERROR_WITH_LEADER,
        4: MessageClass.NOP,
        5: MessageClass.RFNM,
    }.get(message_type, MessageClass.IMP_CONTROL)
    fields: dict[str, int | MessageClass | str | None] = {
        "message_class": message_class,
        "leader_format": "nosc-short-1822-ncp",
        "message_type": message_type,
        "host": first & 0xFF,
        "link": (second >> 8) & 0xFF,
        "subtype": second & 0xFF,
        "m1": None,
        "byte_size": None,
        "byte_count": None,
        "m2": None,
        "ncp_opcode": None,
    }
    if message_class == MessageClass.REGULAR and len(words) >= 5:
        fields.update(
            {
                "m1": (words[2] >> 8) & 0xFF,
                "byte_size": words[2] & 0xFF,
                "byte_count": words[3],
                "m2": (words[4] >> 8) & 0xFF,
                "ncp_opcode": words[4] & 0xFF if ((second >> 8) & 0xFF) == 0 else None,
            }
        )
    return DecodedMessage(**fields)  # type: ignore[arg-type]


def build_expected_journey(
    topology: SharedTopology,
    *,
    journey_id: str,
    route_id: str,
    request: MessageExpectation,
    reply: MessageExpectation,
) -> ExpectedJourney:
    """Derive every attachment crossing from one shared-topology route."""

    _stable_identifier(journey_id, "journey id")
    _stable_identifier(route_id, "journey route_id")
    boundaries = _route_boundaries(topology, route_id)
    return ExpectedJourney(
        id=journey_id,
        topology_id=topology.id,
        route_id=route_id,
        request=request,
        reply=reply,
        boundaries=boundaries,
    )


def diagnose_message_journey(
    topology: SharedTopology,
    expected: ExpectedJourney,
    observations: Iterable[MessageJourneyObservation],
) -> JourneyDiagnosis:
    """Return the first missing, contradictory, or ambiguous expected boundary."""

    if topology.id != expected.topology_id:
        raise JourneyValidationError("journey topology identity does not match the reducer input")
    if _route_boundaries(topology, expected.route_id) != expected.boundaries:
        raise JourneyValidationError("journey boundaries do not match the live shared topology")
    component_ids, endpoint_owners, _, _ = _validated_topology(topology)
    direct = tuple(observations)
    _validate_observations(expected, direct, component_ids, endpoint_owners)

    expected_by_key = {
        (boundary.leg, boundary.component_id, boundary.interface_id, boundary.direction): boundary
        for boundary in expected.boundaries
    }
    candidates: dict[str, list[MessageJourneyObservation]] = {
        boundary.id: [] for boundary in expected.boundaries
    }
    for observation in direct:
        key = (
            observation.leg,
            observation.component_id,
            observation.interface_id,
            observation.direction,
        )
        boundary = expected_by_key.get(key)
        if boundary is None:
            raise JourneyValidationError(
                f"observation {observation.id!r} does not name an expected route boundary"
            )
        candidates[boundary.id].append(observation)

    leg_support = {
        leg: tuple(observation.id for observation in direct if observation.leg == leg)
        for leg in JourneyLeg
    }
    assessments: list[BoundaryAssessment] = []
    for boundary in expected.boundaries:
        boundary_candidates = candidates[boundary.id]
        if not boundary_candidates:
            assessments.append(
                BoundaryAssessment(
                    boundary,
                    BoundaryAssessmentState.MISSING,
                    leg_support[boundary.leg],
                )
            )
            continue
        supporting = tuple(observation.id for observation in boundary_candidates)
        if len(boundary_candidates) > 1:
            assessments.append(
                BoundaryAssessment(boundary, BoundaryAssessmentState.AMBIGUOUS, supporting)
            )
            continue
        expectation = expected.request if boundary.leg == JourneyLeg.REQUEST else expected.reply
        state = expectation.compare(boundary_candidates[0].decoded)
        assessments.append(BoundaryAssessment(boundary, state, supporting))

    first = next(
        (assessment for assessment in assessments if assessment.state != BoundaryAssessmentState.OBSERVED),
        None,
    )
    if first is None:
        state = JourneyState.COMPLETE
        first_boundary_id = None
    elif first.state == BoundaryAssessmentState.CONTRADICTORY:
        state = JourneyState.CONTRADICTORY_BOUNDARY
        first_boundary_id = first.boundary.id
    elif first.state == BoundaryAssessmentState.AMBIGUOUS:
        state = JourneyState.AMBIGUOUS
        first_boundary_id = first.boundary.id
    elif direct:
        state = JourneyState.MISSING_BOUNDARY
        first_boundary_id = first.boundary.id
    else:
        state = JourneyState.UNKNOWN
        first_boundary_id = first.boundary.id
    return JourneyDiagnosis(
        journey_id=expected.id,
        state=state,
        first_boundary_id=first_boundary_id,
        supporting_observation_ids=tuple(observation.id for observation in direct),
        boundaries=tuple(assessments),
    )


def observation_from_ka10_imp_trace(
    *,
    observation_id: str,
    journey_id: str,
    leg: JourneyLeg,
    component_id: str,
    interface_id: str,
    direction: BoundaryDirection,
    source_local_sequence: int,
    decoded: DecodedMessage,
    fingerprint: str,
    provenance_id: str,
    simulator_tick: int | None = None,
    external_evidence: Sequence[ExternalEvidenceReference] = (),
) -> MessageJourneyObservation:
    """Create a typed KA10 seam after a caller correlates DATAIO evidence."""

    return _observation_from_unparsed_external_trace(
        source_kind="ka10-imp-trace",
        observation_id=observation_id,
        journey_id=journey_id,
        leg=leg,
        component_id=component_id,
        interface_id=interface_id,
        direction=direction,
        source_local_sequence=source_local_sequence,
        decoded=decoded,
        fingerprint=fingerprint,
        provenance_id=provenance_id,
        simulator_tick=simulator_tick,
        transport_sequence=None,
        external_evidence=external_evidence,
    )


def observation_from_pdp11_imp11a_trace(
    *,
    observation_id: str,
    journey_id: str,
    leg: JourneyLeg,
    component_id: str,
    interface_id: str,
    direction: BoundaryDirection,
    source_local_sequence: int,
    decoded: DecodedMessage,
    fingerprint: str,
    provenance_id: str,
    simulator_tick: int | None = None,
    transport_sequence: int | None = None,
    external_evidence: Sequence[ExternalEvidenceReference] = (),
) -> MessageJourneyObservation:
    """Create a typed IMP11-A seam after a caller correlates DMA/packet evidence."""

    return _observation_from_unparsed_external_trace(
        source_kind="pdp11-imp11a-trace",
        observation_id=observation_id,
        journey_id=journey_id,
        leg=leg,
        component_id=component_id,
        interface_id=interface_id,
        direction=direction,
        source_local_sequence=source_local_sequence,
        decoded=decoded,
        fingerprint=fingerprint,
        provenance_id=provenance_id,
        simulator_tick=simulator_tick,
        transport_sequence=transport_sequence,
        external_evidence=external_evidence,
    )


def _route_boundaries(topology: SharedTopology, route_id: str) -> tuple[ExpectedBoundary, ...]:
    component_ids, endpoint_owners, _, route_ids = _validated_topology(topology)
    if route_id not in route_ids:
        raise JourneyValidationError(f"shared topology has no route {route_id!r}")
    topology_mapping = topology.topology
    routes = topology_mapping["routes"]
    route = next(item for item in routes if item["id"] == route_id)
    component_path = tuple(route["components"])
    if len(set(component_path)) != len(component_path):
        raise JourneyValidationError("message-journey routes may not repeat components")
    if any(component not in component_ids for component in component_path):
        raise JourneyValidationError("message-journey route contains an unknown component")

    links_by_components: dict[frozenset[str], list[tuple[str, str]]] = {}
    for link in topology_mapping["links"]:
        first, second = link["endpoints"]
        owners = frozenset((endpoint_owners[first], endpoint_owners[second]))
        links_by_components.setdefault(owners, []).append((first, second))

    bound_pairs = {
        frozenset((binding.imp_endpoint, binding.host_endpoint))
        for binding in topology.interfaces
    } | {
        frozenset((binding.first_endpoint, binding.second_endpoint))
        for binding in topology.modem_interfaces
    }
    crossings: list[tuple[str, str, str, str]] = []
    for first_component, second_component in pairwise(component_path):
        links = links_by_components.get(frozenset((first_component, second_component)), [])
        if len(links) != 1:
            raise JourneyValidationError(
                f"route crossing {first_component!r} to {second_component!r} is not uniquely linked"
            )
        first_endpoint, second_endpoint = links[0]
        if endpoint_owners[first_endpoint] != first_component:
            first_endpoint, second_endpoint = second_endpoint, first_endpoint
        if frozenset((first_endpoint, second_endpoint)) not in bound_pairs:
            raise JourneyValidationError(
                f"route crossing {first_component!r} to {second_component!r} has no shared interface binding"
            )
        crossings.append((first_component, first_endpoint, second_component, second_endpoint))

    request = _boundaries_for_crossings(JourneyLeg.REQUEST, crossings)
    reply_crossings = [
        (second_component, second_endpoint, first_component, first_endpoint)
        for first_component, first_endpoint, second_component, second_endpoint in reversed(crossings)
    ]
    reply = _boundaries_for_crossings(JourneyLeg.REPLY, reply_crossings)
    return request + reply


def _boundaries_for_crossings(
    leg: JourneyLeg,
    crossings: Sequence[tuple[str, str, str, str]],
) -> tuple[ExpectedBoundary, ...]:
    boundaries: list[ExpectedBoundary] = []
    for first_component, first_endpoint, second_component, second_endpoint in crossings:
        for component_id, interface_id, direction in (
            (first_component, first_endpoint, BoundaryDirection.EGRESS),
            (second_component, second_endpoint, BoundaryDirection.INGRESS),
        ):
            position = len(boundaries) + 1
            boundaries.append(
                ExpectedBoundary(
                    id=f"boundary:{leg.value}:{position}",
                    leg=leg,
                    position=position,
                    component_id=component_id,
                    interface_id=interface_id,
                    direction=direction,
                )
            )
    return tuple(boundaries)


def _observation_from_unparsed_external_trace(
    *,
    source_kind: str,
    observation_id: str,
    journey_id: str,
    leg: JourneyLeg,
    component_id: str,
    interface_id: str,
    direction: BoundaryDirection,
    source_local_sequence: int,
    decoded: DecodedMessage,
    fingerprint: str,
    provenance_id: str,
    simulator_tick: int | None,
    transport_sequence: int | None,
    external_evidence: Sequence[ExternalEvidenceReference],
) -> MessageJourneyObservation:
    return MessageJourneyObservation(
        id=observation_id,
        journey_id=journey_id,
        leg=leg,
        component_id=component_id,
        interface_id=interface_id,
        direction=direction,
        source_local_sequence=source_local_sequence,
        decoded=decoded,
        correlation_fingerprint=fingerprint,
        provenance=ObservationProvenance(id=provenance_id, kind=source_kind),
        simulator_tick=simulator_tick,
        transport_sequence=transport_sequence,
        external_evidence=tuple(external_evidence),
    )


def _validated_topology(
    topology: SharedTopology,
) -> tuple[set[str], dict[str, str], set[str], set[str]]:
    try:
        return validate_normalized_topology(topology.topology)
    except RunSummaryValidationError as error:
        raise JourneyValidationError(f"invalid journey shared topology: {error}") from error


def _validate_observations(
    expected: ExpectedJourney,
    observations: tuple[MessageJourneyObservation, ...],
    component_ids: set[str],
    endpoint_owners: Mapping[str, str],
) -> None:
    identifiers: set[str] = set()
    previous_by_source: dict[str, tuple[int, int | None]] = {}
    provenance_by_source: dict[str, ObservationProvenance] = {}
    boundary_positions = {
        (boundary.leg, boundary.component_id, boundary.interface_id, boundary.direction): boundary.position
        for boundary in expected.boundaries
    }
    previous_position: dict[tuple[str, JourneyLeg], int] = {}
    for observation in observations:
        if observation.id in identifiers:
            raise JourneyValidationError(f"duplicate direct observation id {observation.id!r}")
        identifiers.add(observation.id)
        if observation.journey_id != expected.id:
            raise JourneyValidationError(
                f"observation {observation.id!r} names another journey"
            )
        expectation = expected.request if observation.leg == JourneyLeg.REQUEST else expected.reply
        if observation.correlation_fingerprint != expectation.correlation_fingerprint:
            raise JourneyValidationError(
                f"observation {observation.id!r} has a malformed leg correlation"
            )
        if observation.component_id not in component_ids:
            raise JourneyValidationError(
                f"observation {observation.id!r} names unknown component {observation.component_id!r}"
            )
        if observation.interface_id not in endpoint_owners:
            raise JourneyValidationError(
                f"observation {observation.id!r} names unknown interface {observation.interface_id!r}"
            )
        if endpoint_owners[observation.interface_id] != observation.component_id:
            raise JourneyValidationError(
                f"observation {observation.id!r} interface is not owned by its component"
            )
        earlier_provenance = provenance_by_source.get(observation.provenance.id)
        if earlier_provenance is not None and earlier_provenance != observation.provenance:
            raise JourneyValidationError(
                f"source {observation.provenance.id!r} changes provenance within one journey"
            )
        provenance_by_source[observation.provenance.id] = observation.provenance
        previous = previous_by_source.get(observation.provenance.id)
        if previous is not None:
            if observation.source_local_sequence <= previous[0]:
                raise JourneyValidationError(
                    f"source {observation.provenance.id!r} sequence is not strictly increasing"
                )
            if (
                observation.simulator_tick is not None
                and previous[1] is not None
                and observation.simulator_tick < previous[1]
            ):
                raise JourneyValidationError(
                    f"source {observation.provenance.id!r} simulator tick moved backward"
                )
        previous_by_source[observation.provenance.id] = (
            observation.source_local_sequence,
            observation.simulator_tick,
        )
        key = (
            observation.leg,
            observation.component_id,
            observation.interface_id,
            observation.direction,
        )
        position = boundary_positions.get(key)
        if position is None:
            continue
        source_leg = (observation.provenance.id, observation.leg)
        earlier_position = previous_position.get(source_leg)
        if earlier_position is not None and position < earlier_position:
            raise JourneyValidationError(
                f"source {observation.provenance.id!r} route order moved backward"
            )
        previous_position[source_leg] = position


def _stable_identifier(value: object, location: str) -> str:
    text = _nonempty_text(value, location)
    if not _IDENTIFIER.fullmatch(text):
        raise JourneyValidationError(f"{location} is not a stable identifier: {text!r}")
    return text


def _nonempty_text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise JourneyValidationError(f"{location} must be a non-empty string")
    return value


def _fingerprint(value: object, location: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise JourneyValidationError(f"{location} must be a lowercase SHA-256 digest")
    return value


def _unique_identifiers(values: Sequence[str], location: str) -> None:
    identifiers = [_stable_identifier(value, location) for value in values]
    if len(identifiers) != len(set(identifiers)):
        raise JourneyValidationError(f"{location} must be unique")


def _unsigned(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise JourneyValidationError(f"{location} must be a non-negative integer")
    return value


def _optional_unsigned(value: object, maximum: int, location: str) -> None:
    if value is None:
        return
    integer = _unsigned(value, location)
    if integer > maximum:
        raise JourneyValidationError(f"{location} exceeds {maximum}")


def _unsigned_word(value: object, location: str) -> int:
    integer = _unsigned(value, location)
    if integer > 0xFFFF:
        raise JourneyValidationError(f"{location} is outside the 16-bit range")
    return integer
