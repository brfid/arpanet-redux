"""Versioned persistence for typed message-journey observations.

The stream is additive to the accepted completed-run and controller-live
contracts.  Its records retain source-local order only; record order never
claims that independent simulator clocks share a timebase.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

from .message_journey import (
    BoundaryDirection,
    DecodedMessage,
    ExternalEvidenceReference,
    ExpectedJourney,
    JourneyDiagnosis,
    JourneyLeg,
    JourneyState,
    MessageClass,
    MessageExpectation,
    MessageJourneyObservation,
    ObservationProvenance,
    build_expected_journey,
    diagnose_message_journey,
)
from .shared_topology import (
    SharedTopology,
    SharedTopologyValidationError,
    shared_topology_from_mapping,
)


MESSAGE_JOURNEY_STREAM_SCHEMA_VERSION = 1
_STREAM_KIND = "ncc-message-journey-stream"
_RECORD_ORDER = "emission-only-no-global-clock"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_ARTIFACT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EXPECTATION_FIELDS = (
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


class MessageJourneyStreamError(ValueError):
    """Raised when a persisted journey cannot be trusted."""


@dataclass(frozen=True)
class TransactionWindowSource:
    """One immutable byte range that bounds a source-local trace."""

    id: str
    artifact: str
    start_offset: int
    end_offset: int
    sha256: str

    def __post_init__(self) -> None:
        _identifier(self.id, "transaction window source id")
        if not isinstance(self.artifact, str) or not _ARTIFACT.fullmatch(self.artifact):
            raise MessageJourneyStreamError(
                f"transaction window artifact is not a basename: {self.artifact!r}"
            )
        for value, location in (
            (self.start_offset, "transaction window start_offset"),
            (self.end_offset, "transaction window end_offset"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise MessageJourneyStreamError(f"{location} must be a non-negative integer")
        if self.end_offset < self.start_offset:
            raise MessageJourneyStreamError(
                "transaction window end_offset precedes start_offset"
            )
        if not isinstance(self.sha256, str) or not _SHA256.fullmatch(self.sha256):
            raise MessageJourneyStreamError(
                "transaction window sha256 must be a lowercase SHA-256 digest"
            )


@dataclass(frozen=True)
class MessageJourneyStream:
    """A validated snapshot of one bounded message-journey stream."""

    _header: Mapping[str, Any]
    topology: SharedTopology
    expected: ExpectedJourney
    transaction_window: tuple[TransactionWindowSource, ...]
    observations: tuple[MessageJourneyObservation, ...]
    diagnosis: JourneyDiagnosis
    is_terminal: bool
    has_incomplete_final_record: bool = False

    @property
    def run_id(self) -> str:
        """Return the formal harness run identity."""

        return str(self._header["run"]["id"])

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh JSON-safe representation for passive consumers."""

        return {
            "header": _copy(self._header),
            "observations": [
                _observation_record(observation) for observation in self.observations
            ],
            "diagnosis": _diagnosis_record(self.diagnosis),
            "is_terminal": self.is_terminal,
            "has_incomplete_final_record": self.has_incomplete_final_record,
        }


class MessageJourneyStreamRecorder:
    """Write typed observations and one reducer-verified terminal diagnosis."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        started_at: str,
        provenance: Sequence[ObservationProvenance],
        topology_document: Mapping[str, Any],
        expected: ExpectedJourney,
        transaction_window: Sequence[TransactionWindowSource],
    ) -> None:
        self.path = Path(path)
        self._header, self._topology, self._expected, self._window = _build_header(
            run_id=run_id,
            started_at=started_at,
            provenance=provenance,
            topology_document=topology_document,
            expected=expected,
            transaction_window=transaction_window,
        )
        self._observations: list[MessageJourneyObservation] = []
        self._terminal = False
        self._closed = False
        try:
            self._stream = self.path.open("x", encoding="utf-8")
        except OSError as error:
            raise MessageJourneyStreamError(
                f"could not create message-journey stream {self.path}: {error}"
            ) from error
        self._write(self._header)

    def publish(self, observations: Iterable[MessageJourneyObservation]) -> None:
        """Append a validated batch without assigning cross-source time order."""

        if self._closed or self._terminal:
            raise MessageJourneyStreamError(
                "cannot publish to a closed or terminal message-journey stream"
            )
        batch = tuple(observations)
        if not batch:
            return
        for index, observation in enumerate(batch):
            if not isinstance(observation, MessageJourneyObservation):
                raise TypeError(f"message-journey observation {index} has an invalid type")
        candidate = (*self._observations, *batch)
        diagnose_message_journey(self._topology, self._expected, candidate)
        self._observations.extend(batch)
        for observation in batch:
            self._write(
                {
                    "record_type": "observation",
                    "observation": _observation_record(observation),
                }
            )

    def complete(self) -> JourneyDiagnosis:
        """Append the exact diagnosis produced by the existing pure reducer."""

        if self._closed or self._terminal:
            raise MessageJourneyStreamError(
                "cannot complete a closed or terminal message-journey stream"
            )
        diagnosis = diagnose_message_journey(
            self._topology, self._expected, self._observations
        )
        self._write(
            {
                "record_type": "diagnosis",
                "diagnosis": _diagnosis_record(diagnosis),
            }
        )
        self._terminal = True
        return diagnosis

    def close(self) -> None:
        """Close the sidecar without changing harness or simulator state."""

        if not self._closed:
            self._stream.close()
            self._closed = True

    def _write(self, record: Mapping[str, Any]) -> None:
        self._stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        self._stream.flush()


def read_message_journey_stream(path: str | Path) -> MessageJourneyStream:
    """Read complete JSON Lines, ignoring only an interrupted final record."""

    stream_path = Path(path)
    try:
        contents = stream_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise MessageJourneyStreamError(
            f"could not read message-journey stream {stream_path}: {error}"
        ) from error
    lines = contents.splitlines()
    has_incomplete_final_record = bool(contents and not contents.endswith("\n"))
    if has_incomplete_final_record:
        lines.pop()
    if not lines:
        raise MessageJourneyStreamError(
            "message-journey stream has no complete header"
        )
    records: list[object] = []
    for number, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise MessageJourneyStreamError(
                f"message-journey stream line {number} is not JSON: {error}"
            ) from error

    header, topology, expected, window = _parse_header(records[0])
    observations: list[MessageJourneyObservation] = []
    terminal_record: Mapping[str, Any] | None = None
    for number, record in enumerate(records[1:], start=2):
        value = _mapping(record, f"message-journey stream line {number}")
        _fields(
            value,
            f"message-journey stream line {number}",
            required={"record_type"},
            optional={"observation", "diagnosis"},
        )
        record_type = value["record_type"]
        if terminal_record is not None:
            raise MessageJourneyStreamError(
                "message-journey stream has a record after its terminal diagnosis"
            )
        if record_type == "observation":
            if set(value) != {"record_type", "observation"}:
                raise MessageJourneyStreamError(
                    f"message-journey observation line {number} has invalid fields"
                )
            observations.append(_observation_from_record(value["observation"]))
            diagnose_message_journey(topology, expected, observations)
            continue
        if record_type == "diagnosis":
            if set(value) != {"record_type", "diagnosis"}:
                raise MessageJourneyStreamError(
                    f"message-journey diagnosis line {number} has invalid fields"
                )
            terminal_record = _mapping(
                value["diagnosis"], "message-journey terminal diagnosis"
            )
            continue
        raise MessageJourneyStreamError(
            f"message-journey stream line {number} has unknown record_type {record_type!r}"
        )

    diagnosis = diagnose_message_journey(topology, expected, observations)
    if terminal_record is not None and _copy(terminal_record) != _diagnosis_record(diagnosis):
        raise MessageJourneyStreamError(
            "message-journey terminal diagnosis disagrees with the reducer"
        )
    return MessageJourneyStream(
        _header=MappingProxyType(_copy(header)),
        topology=topology,
        expected=expected,
        transaction_window=window,
        observations=tuple(observations),
        diagnosis=diagnosis,
        is_terminal=terminal_record is not None,
        has_incomplete_final_record=has_incomplete_final_record,
    )


def _build_header(
    *,
    run_id: str,
    started_at: str,
    provenance: Sequence[ObservationProvenance],
    topology_document: Mapping[str, Any],
    expected: ExpectedJourney,
    transaction_window: Sequence[TransactionWindowSource],
) -> tuple[
    dict[str, Any], SharedTopology, ExpectedJourney, tuple[TransactionWindowSource, ...]
]:
    header = {
        "schema_version": MESSAGE_JOURNEY_STREAM_SCHEMA_VERSION,
        "kind": _STREAM_KIND,
        "record_order": _RECORD_ORDER,
        "run": {
            "id": run_id,
            "started_at": started_at,
            "provenance": [_provenance_record(item) for item in provenance],
        },
        "shared_topology": _copy(topology_document),
        "journey": _expected_record(expected),
        "transaction_window": {
            "kind": "byte-offsets",
            "sources": [_window_record(item) for item in transaction_window],
        },
    }
    parsed, topology, parsed_expected, window = _parse_header(header)
    if parsed_expected != expected:
        raise MessageJourneyStreamError(
            "message-journey expectation does not match the supplied shared topology"
        )
    return parsed, topology, parsed_expected, window


def _parse_header(
    record: object,
) -> tuple[
    dict[str, Any], SharedTopology, ExpectedJourney, tuple[TransactionWindowSource, ...]
]:
    header = _mapping(record, "message-journey stream header")
    _fields(
        header,
        "message-journey stream header",
        required={
            "schema_version",
            "kind",
            "record_order",
            "run",
            "shared_topology",
            "journey",
            "transaction_window",
        },
    )
    if (
        isinstance(header["schema_version"], bool)
        or header["schema_version"] != MESSAGE_JOURNEY_STREAM_SCHEMA_VERSION
    ):
        raise MessageJourneyStreamError(
            "message-journey stream has an unsupported schema version"
        )
    if header["kind"] != _STREAM_KIND or header["record_order"] != _RECORD_ORDER:
        raise MessageJourneyStreamError(
            "message-journey stream has unexpected kind or record-order semantics"
        )

    run = _mapping(header["run"], "message-journey stream.run")
    _fields(run, "message-journey stream.run", required={"id", "started_at", "provenance"})
    _identifier(run["id"], "message-journey stream.run.id")
    _timestamp(run["started_at"], "message-journey stream.run.started_at")
    provenance = _sequence(run["provenance"], "message-journey stream.run.provenance")
    if not provenance:
        raise MessageJourneyStreamError(
            "message-journey stream.run.provenance must not be empty"
        )
    for item in provenance:
        _provenance_from_record(item)

    try:
        topology = shared_topology_from_mapping(header["shared_topology"])
    except SharedTopologyValidationError as error:
        raise MessageJourneyStreamError(
            f"message-journey stream has invalid shared topology: {error}"
        ) from error
    journey = _mapping(header["journey"], "message-journey stream.journey")
    _fields(
        journey,
        "message-journey stream.journey",
        required={"id", "route_id", "request", "reply"},
    )
    expected = build_expected_journey(
        topology,
        journey_id=_identifier(journey["id"], "message-journey stream.journey.id"),
        route_id=_identifier(
            journey["route_id"], "message-journey stream.journey.route_id"
        ),
        request=_expectation_from_record(journey["request"]),
        reply=_expectation_from_record(journey["reply"]),
    )

    transaction = _mapping(
        header["transaction_window"], "message-journey stream.transaction_window"
    )
    _fields(
        transaction,
        "message-journey stream.transaction_window",
        required={"kind", "sources"},
    )
    if transaction["kind"] != "byte-offsets":
        raise MessageJourneyStreamError(
            "message-journey transaction window kind must be 'byte-offsets'"
        )
    source_records = _sequence(
        transaction["sources"], "message-journey stream.transaction_window.sources"
    )
    if not source_records:
        raise MessageJourneyStreamError(
            "message-journey transaction window must contain a source"
        )
    window = tuple(_window_from_record(item) for item in source_records)
    if len({item.id for item in window}) != len(window):
        raise MessageJourneyStreamError(
            "message-journey transaction window source ids must be unique"
        )
    return _copy(header), topology, expected, window


def _expected_record(expected: ExpectedJourney) -> dict[str, Any]:
    return {
        "id": expected.id,
        "route_id": expected.route_id,
        "request": _expectation_record(expected.request),
        "reply": _expectation_record(expected.reply),
    }


def _expectation_record(expectation: MessageExpectation) -> dict[str, Any]:
    return {
        "correlation_fingerprint": expectation.correlation_fingerprint,
        "message_class": expectation.message_class.value,
        **{name: getattr(expectation, name) for name in _EXPECTATION_FIELDS},
    }


def _expectation_from_record(record: object) -> MessageExpectation:
    value = _mapping(record, "message expectation")
    _fields(
        value,
        "message expectation",
        required={"correlation_fingerprint", "message_class", *_EXPECTATION_FIELDS},
    )
    return MessageExpectation(
        correlation_fingerprint=value["correlation_fingerprint"],
        message_class=_enum(MessageClass, value["message_class"], "message expectation.message_class"),
        **{name: value[name] for name in _EXPECTATION_FIELDS},
    )


def _observation_record(observation: MessageJourneyObservation) -> dict[str, Any]:
    return {
        "id": observation.id,
        "journey_id": observation.journey_id,
        "leg": observation.leg.value,
        "component_id": observation.component_id,
        "interface_id": observation.interface_id,
        "direction": observation.direction.value,
        "source_local_sequence": observation.source_local_sequence,
        "decoded": {
            "message_class": observation.decoded.message_class.value,
            "leader_format": observation.decoded.leader_format,
            **{
                name: getattr(observation.decoded, name)
                for name in _EXPECTATION_FIELDS
            },
        },
        "correlation_fingerprint": observation.correlation_fingerprint,
        "provenance": _provenance_record(observation.provenance),
        "simulator_tick": observation.simulator_tick,
        "transport_sequence": observation.transport_sequence,
        "external_evidence": [
            {"id": item.id, "kind": item.kind, "locator": item.locator}
            for item in observation.external_evidence
        ],
    }


def _observation_from_record(record: object) -> MessageJourneyObservation:
    value = _mapping(record, "message-journey observation")
    required = {
        "id",
        "journey_id",
        "leg",
        "component_id",
        "interface_id",
        "direction",
        "source_local_sequence",
        "decoded",
        "correlation_fingerprint",
        "provenance",
        "simulator_tick",
        "transport_sequence",
        "external_evidence",
    }
    _fields(value, "message-journey observation", required=required)
    decoded_value = _mapping(value["decoded"], "message-journey observation.decoded")
    _fields(
        decoded_value,
        "message-journey observation.decoded",
        required={"message_class", "leader_format", *_EXPECTATION_FIELDS},
    )
    evidence = []
    for item in _sequence(
        value["external_evidence"], "message-journey observation.external_evidence"
    ):
        reference = _mapping(item, "message-journey external evidence")
        _fields(
            reference,
            "message-journey external evidence",
            required={"id", "kind", "locator"},
        )
        evidence.append(
            ExternalEvidenceReference(
                id=reference["id"],
                kind=reference["kind"],
                locator=reference["locator"],
            )
        )
    return MessageJourneyObservation(
        id=value["id"],
        journey_id=value["journey_id"],
        leg=_enum(JourneyLeg, value["leg"], "message-journey observation.leg"),
        component_id=value["component_id"],
        interface_id=value["interface_id"],
        direction=_enum(
            BoundaryDirection,
            value["direction"],
            "message-journey observation.direction",
        ),
        source_local_sequence=value["source_local_sequence"],
        decoded=DecodedMessage(
            message_class=_enum(
                MessageClass,
                decoded_value["message_class"],
                "message-journey observation.decoded.message_class",
            ),
            leader_format=decoded_value["leader_format"],
            **{name: decoded_value[name] for name in _EXPECTATION_FIELDS},
        ),
        correlation_fingerprint=value["correlation_fingerprint"],
        provenance=_provenance_from_record(value["provenance"]),
        simulator_tick=value["simulator_tick"],
        transport_sequence=value["transport_sequence"],
        external_evidence=tuple(evidence),
    )


def _diagnosis_record(diagnosis: JourneyDiagnosis) -> dict[str, Any]:
    return {
        "journey_id": diagnosis.journey_id,
        "state": diagnosis.state.value,
        "first_boundary_id": diagnosis.first_boundary_id,
        "supporting_observation_ids": list(diagnosis.supporting_observation_ids),
        "boundaries": [
            {
                "boundary_id": assessment.boundary.id,
                "state": assessment.state.value,
                "supporting_observation_ids": list(
                    assessment.supporting_observation_ids
                ),
            }
            for assessment in diagnosis.boundaries
        ],
    }


def _provenance_record(provenance: ObservationProvenance) -> dict[str, Any]:
    if not isinstance(provenance, ObservationProvenance):
        raise MessageJourneyStreamError("message-journey provenance has an invalid type")
    record = {"id": provenance.id, "kind": provenance.kind}
    if provenance.revision is not None:
        record["revision"] = provenance.revision
    return record


def _provenance_from_record(record: object) -> ObservationProvenance:
    value = _mapping(record, "message-journey provenance")
    _fields(
        value,
        "message-journey provenance",
        required={"id", "kind"},
        optional={"revision"},
    )
    return ObservationProvenance(
        id=value["id"], kind=value["kind"], revision=value.get("revision")
    )


def _window_record(source: TransactionWindowSource) -> dict[str, Any]:
    if not isinstance(source, TransactionWindowSource):
        raise MessageJourneyStreamError("transaction window source has an invalid type")
    return {
        "id": source.id,
        "artifact": source.artifact,
        "start_offset": source.start_offset,
        "end_offset": source.end_offset,
        "sha256": source.sha256,
    }


def _window_from_record(record: object) -> TransactionWindowSource:
    value = _mapping(record, "message-journey transaction window source")
    _fields(
        value,
        "message-journey transaction window source",
        required={"id", "artifact", "start_offset", "end_offset", "sha256"},
    )
    return TransactionWindowSource(
        id=value["id"],
        artifact=value["artifact"],
        start_offset=value["start_offset"],
        end_offset=value["end_offset"],
        sha256=value["sha256"],
    )


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MessageJourneyStreamError(f"{location} must be an object")
    return value


def _sequence(value: object, location: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise MessageJourneyStreamError(f"{location} must be an array")
    return value


def _fields(
    value: Mapping[str, Any],
    location: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        raise MessageJourneyStreamError(
            f"{location} is missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise MessageJourneyStreamError(
            f"{location} has unknown fields: {', '.join(sorted(unknown))}"
        )


def _identifier(value: object, location: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise MessageJourneyStreamError(
            f"{location} is not a stable identifier: {value!r}"
        )
    return value


def _timestamp(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MessageJourneyStreamError(
            f"{location} must be an RFC 3339 UTC timestamp"
        )
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise MessageJourneyStreamError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error
    return value


def _enum(enum_type: Any, value: object, location: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise MessageJourneyStreamError(
            f"{location} has unsupported value {value!r}"
        ) from error


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(item) for item in value]
    return value
