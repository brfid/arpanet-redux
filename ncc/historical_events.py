"""Validated append-only records of direct passive NCC observations.

This sidecar preserves historical report events without extending the accepted
completed-run or controller-owned live-stream contracts. It records only the
project-authored, topology-neutral facts emitted by a passive receiver; it
never reads raw simulator output or has simulator-control authority.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

from .events import EventSource, NccEvent
from .run_summary import RunSummaryValidationError, validate_normalized_topology


HISTORICAL_EVENT_STREAM_SCHEMA_VERSION = 2
_SUPPORTED_SCHEMA_VERSIONS = frozenset((1, HISTORICAL_EVENT_STREAM_SCHEMA_VERSION))
_STREAM_KIND = "ncc-historical-event-stream"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_HOST_SUBJECT = re.compile(r"imp:([1-9][0-9]*):host:([0-3])\Z")
_LINE_SUBJECT = re.compile(r"imp:([1-9][0-9]*):line:([1-5])\Z")


class HistoricalEventStreamError(ValueError):
    """Raised when a passive historical-event record is not trustworthy."""


@dataclass(frozen=True)
class HistoricalEventStream:
    """An immutable, validated record of direct historical NCC events."""

    _header: Mapping[str, Any]
    _records: tuple[Mapping[str, Any], ...]

    @property
    def run_id(self) -> str:
        """Return the stable recording identity."""

        return str(self._header["run"]["id"])

    @property
    def events(self) -> tuple[NccEvent, ...]:
        """Return fresh, ordered direct events suitable for replay."""

        return tuple(_event_from_record(record) for record in self._records)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe copy for a read-only replay consumer."""

        return {
            "header": _copy_json_value(self._header),
            "events": [_copy_json_value(record) for record in self._records],
        }


@dataclass(frozen=True)
class HistoricalReplayFrame:
    """One direct historical event and the subject states known after it."""

    sequence: int
    observed_at: str
    event_type: str
    subject: str
    state: str
    source: EventSource
    details: Mapping[str, Any]
    known_states: Mapping[str, str]


class HistoricalEventRecorder:
    """Write a bounded direct-event stream without process-control authority."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        started_at: str,
        topology_id: str,
        interface_id: str,
        topology: Mapping[str, Any],
        provenance: Sequence[Mapping[str, str]],
    ) -> None:
        self.path = Path(path)
        self._header = {
            "schema_version": HISTORICAL_EVENT_STREAM_SCHEMA_VERSION,
            "kind": _STREAM_KIND,
            "run": {
                "id": run_id,
                "started_at": started_at,
                "topology_id": topology_id,
                "interface_id": interface_id,
                "provenance": [_copy_json_value(item) for item in provenance],
            },
            "topology": _copy_json_value(topology),
        }
        (
            self._schema_version,
            self._started_at,
            self._component_ids,
        ) = _validate_header(self._header)
        self._records: list[dict[str, Any]] = []
        self._closed = False
        try:
            self._stream = self.path.open("x", encoding="utf-8")
        except OSError as error:
            raise HistoricalEventStreamError(
                f"could not create historical event stream {self.path}: {error}"
            ) from error
        self._write(self._header)

    def append(self, events: Iterable[NccEvent]) -> None:
        """Validate and append one ordered batch of direct historical events."""

        if self._closed:
            raise HistoricalEventStreamError("cannot append to a closed historical event stream")
        records: list[dict[str, Any]] = []
        for index, event in enumerate(events):
            if not isinstance(event, NccEvent):
                raise TypeError(f"event {index} is not an NccEvent")
            records.append(_copy_json_value(event.to_dict()))
        if not records:
            return
        candidate = [*self._records, *records]
        _validate_event_records(
            candidate,
            self._schema_version,
            self._started_at,
            self._component_ids,
        )
        self._records.extend(records)
        for record in records:
            self._write(record)

    def close(self) -> None:
        """Close the record without changing receiver or simulator state."""

        if not self._closed:
            self._stream.close()
            self._closed = True

    def _write(self, record: Mapping[str, Any]) -> None:
        self._stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        self._stream.flush()


def read_historical_event_stream(path: str | Path) -> HistoricalEventStream:
    """Read complete JSON Lines, tolerating an interrupted final write."""

    stream_path = Path(path)
    try:
        contents = stream_path.read_text(encoding="utf-8")
    except OSError as error:
        raise HistoricalEventStreamError(
            f"could not read historical event stream {stream_path}: {error}"
        ) from error
    lines = contents.splitlines()
    if contents and not contents.endswith("\n"):
        lines.pop()
    if not lines:
        raise HistoricalEventStreamError("historical event stream has no complete header")
    records: list[object] = []
    for number, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise HistoricalEventStreamError(
                f"historical event stream line {number} is not JSON: {error}"
            ) from error
    header = records[0]
    schema_version, started_at, component_ids = _validate_header(header)
    event_records = records[1:]
    _validate_event_records(event_records, schema_version, started_at, component_ids)
    return HistoricalEventStream(
        _header=MappingProxyType(_copy_json_value(header)),
        _records=tuple(MappingProxyType(_copy_json_value(record)) for record in event_records),
    )


def replay_historical_event_stream(
    stream: HistoricalEventStream,
) -> tuple[HistoricalReplayFrame, ...]:
    """Replay validated direct events without adding topology inference."""

    known_states: dict[str, str] = {}
    frames: list[HistoricalReplayFrame] = []
    for event in stream.events:
        known_states[event.subject] = event.state
        frames.append(
            HistoricalReplayFrame(
                sequence=event.sequence,
                observed_at=event.observed_at,
                event_type=event.event_type,
                subject=event.subject,
                state=event.state,
                source=event.source,
                details=MappingProxyType(_copy_json_value(event.details)),
                known_states=MappingProxyType(dict(known_states)),
            )
        )
    return tuple(frames)


def _validate_header(header: object) -> tuple[int, datetime, set[str]]:
    value = _mapping(header, "historical event stream header")
    _fields(
        value,
        "historical event stream header",
        required={"schema_version", "kind", "run", "topology"},
    )
    schema_version = value["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version not in _SUPPORTED_SCHEMA_VERSIONS
    ):
        raise HistoricalEventStreamError(
            "historical event stream has unsupported schema version "
            f"{schema_version!r}"
        )
    if value["kind"] != _STREAM_KIND:
        raise HistoricalEventStreamError("historical event stream has unexpected kind")
    run = _mapping(value["run"], "historical event stream.run")
    _fields(
        run,
        "historical event stream.run",
        required={"id", "started_at", "topology_id", "interface_id", "provenance"},
    )
    _identifier(run["id"], "historical event stream.run.id")
    started_at = _timestamp(run["started_at"], "historical event stream.run.started_at")
    _identifier(run["topology_id"], "historical event stream.run.topology_id")
    _identifier(run["interface_id"], "historical event stream.run.interface_id")
    _validate_provenance(run["provenance"])
    try:
        component_ids, _, _, _ = validate_normalized_topology(value["topology"])
    except RunSummaryValidationError as error:
        raise HistoricalEventStreamError(
            f"historical event stream has invalid topology: {error}"
        ) from error
    return schema_version, started_at, component_ids


def _validate_provenance(value: object) -> None:
    provenance = _sequence(value, "historical event stream.run.provenance")
    if not provenance:
        raise HistoricalEventStreamError(
            "historical event stream.run.provenance must not be empty"
        )
    for index, item in enumerate(provenance):
        location = f"historical event stream.run.provenance[{index}]"
        source = _mapping(item, location)
        _fields(source, location, required={"id", "kind"}, optional={"revision"})
        _identifier(source["id"], f"{location}.id")
        _text(source["kind"], f"{location}.kind")
        if "revision" in source:
            _text(source["revision"], f"{location}.revision")


def _validate_event_records(
    records: Sequence[object],
    schema_version: int,
    started_at: datetime,
    component_ids: set[str],
) -> None:
    previous_at: datetime | None = None
    for index, record in enumerate(records, start=1):
        event = _event_from_record(record)
        if event.sequence != index:
            raise HistoricalEventStreamError(
                f"historical event {index} must have sequence {index}, got {event.sequence!r}"
            )
        observed_at = _timestamp(
            event.observed_at, f"historical event {index}.observed_at"
        )
        if observed_at < started_at:
            raise HistoricalEventStreamError(
                f"historical event {index}.observed_at precedes the run start"
            )
        if previous_at is not None and observed_at < previous_at:
            raise HistoricalEventStreamError(
                f"historical event {index}.observed_at is earlier than the preceding event"
            )
        previous_at = observed_at
        _validate_event_shape(event, index, component_ids, schema_version)


def _event_from_record(record: object) -> NccEvent:
    value = _mapping(record, "historical event")
    _fields(
        value,
        "historical event",
        required={"version", "sequence", "observed_at", "type", "subject", "state", "source", "details"},
    )
    if isinstance(value["version"], bool) or value["version"] != 1:
        raise HistoricalEventStreamError(
            f"historical event has unsupported version {value['version']!r}"
        )
    sequence = value["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise HistoricalEventStreamError("historical event.sequence must be a positive integer")
    observed_at = value["observed_at"]
    _timestamp(observed_at, "historical event.observed_at")
    event_type = _text(value["type"], "historical event.type")
    subject = _text(value["subject"], "historical event.subject")
    state = _text(value["state"], "historical event.state")
    source_value = _mapping(value["source"], "historical event.source")
    _fields(source_value, "historical event.source", required={"kind", "imp"})
    source_kind = _text(source_value["kind"], "historical event.source.kind")
    source_imp = source_value["imp"]
    if isinstance(source_imp, bool) or not isinstance(source_imp, int) or source_imp < 1:
        raise HistoricalEventStreamError("historical event.source.imp must be a positive integer")
    details = _mapping(value["details"], "historical event.details")
    _validate_json_value(details, "historical event.details")
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type=event_type,
        subject=subject,
        state=state,
        source=EventSource(kind=source_kind, imp=source_imp),
        details=MappingProxyType(_copy_json_value(details)),
        version=1,
    )


def _validate_event_shape(
    event: NccEvent,
    index: int,
    component_ids: set[str],
    schema_version: int,
) -> None:
    location = f"historical event {index}"
    imp_id = f"imp:{event.source.imp}"
    if imp_id not in component_ids:
        raise HistoricalEventStreamError(
            f"{location}.source.imp refers to unknown topology IMP {event.source.imp}"
        )
    if event.event_type == "imp.report":
        if event.source.kind != "imp-trouble-report":
            raise HistoricalEventStreamError(
                f"{location}.source.kind must be 'imp-trouble-report'"
            )
        if event.subject != imp_id or event.state != "received":
            raise HistoricalEventStreamError(
                f"{location} has an invalid IMP report subject or state"
            )
        return
    if event.event_type == "host-interface.state":
        if event.source.kind != "imp-trouble-report":
            raise HistoricalEventStreamError(
                f"{location}.source.kind must be 'imp-trouble-report'"
            )
        subject = _HOST_SUBJECT.fullmatch(event.subject)
        if subject is None or int(subject.group(1)) != event.source.imp:
            raise HistoricalEventStreamError(
                f"{location} has an invalid host-interface subject"
            )
        if event.state not in {"up", "down"}:
            raise HistoricalEventStreamError(
                f"{location} has an invalid host-interface state {event.state!r}"
            )
        return
    if event.event_type == "line-endpoint.state":
        if event.source.kind != "imp-trouble-report":
            raise HistoricalEventStreamError(
                f"{location}.source.kind must be 'imp-trouble-report'"
            )
        subject = _LINE_SUBJECT.fullmatch(event.subject)
        if subject is None or int(subject.group(1)) != event.source.imp:
            raise HistoricalEventStreamError(
                f"{location} has an invalid line-endpoint subject"
            )
        if event.state not in {"up", "down", "looped", "unknown"}:
            raise HistoricalEventStreamError(
                f"{location} has an invalid line-endpoint state {event.state!r}"
            )
        return
    if event.event_type == "imp.throughput-report":
        if schema_version < 2:
            raise HistoricalEventStreamError(
                f"{location} requires historical event stream schema version 2"
            )
        if event.source.kind != "imp-throughput-report":
            raise HistoricalEventStreamError(
                f"{location}.source.kind must be 'imp-throughput-report'"
            )
        if event.subject != imp_id or event.state != "received":
            raise HistoricalEventStreamError(
                f"{location} has an invalid IMP throughput-report subject or state"
            )
        return
    raise HistoricalEventStreamError(
        f"{location} has unsupported direct event type {event.event_type!r}"
    )


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HistoricalEventStreamError(f"{location} must be an object")
    return value


def _sequence(value: object, location: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise HistoricalEventStreamError(f"{location} must be an array")
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
        raise HistoricalEventStreamError(
            f"{location} is missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise HistoricalEventStreamError(
            f"{location} has unknown fields: {', '.join(sorted(unknown))}"
        )


def _identifier(value: object, location: str) -> str:
    text = _text(value, location)
    if not _IDENTIFIER.fullmatch(text):
        raise HistoricalEventStreamError(f"{location} is not a stable identifier: {text!r}")
    return text


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise HistoricalEventStreamError(f"{location} must be a non-empty string")
    return value


def _timestamp(value: object, location: str) -> datetime:
    text = _text(value, location)
    if not text.endswith("Z"):
        raise HistoricalEventStreamError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(text.removesuffix("Z") + "+00:00").astimezone(
            timezone.utc
        )
    except ValueError as error:
        raise HistoricalEventStreamError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error


def _validate_json_value(value: object, location: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise HistoricalEventStreamError(f"{location} must not contain a non-finite number")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{location}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise HistoricalEventStreamError(f"{location} must have string object keys")
            _validate_json_value(item, f"{location}.{key}")
        return
    raise HistoricalEventStreamError(f"{location} must contain only JSON values")


def _copy_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_json_value(item) for item in value]
    return value
