"""Project validated message journeys into passive reducer-backed snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .message_journey import (
    BoundaryAssessmentState,
    ExpectedBoundary,
    JourneyLeg,
    JourneyValidationError,
)
from .message_journey_stream import (
    MessageJourneyStream,
    MessageJourneyStreamError,
    read_message_journey_stream,
)


JOURNEY_DISPLAY_SNAPSHOT_VERSION = 1


class JourneyDisplayError(ValueError):
    """Raised when the passive display cannot produce a trustworthy snapshot."""


@dataclass(frozen=True)
class JourneyDisplaySnapshot:
    """One deterministic, JSON-safe projection of a validated stream prefix."""

    _serialized: str

    @property
    def mode(self) -> str:
        """Return progressive or terminal display mode."""

        return str(self.to_dict()["mode"])

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh JSON-safe copy of the internal view model."""

        return json.loads(self._serialized)

    def to_json(self) -> str:
        """Return deterministic compact JSON suitable for the local API."""

        return self._serialized


@dataclass(frozen=True)
class _StreamRevision:
    file_identity: tuple[int, int]
    run_id: str
    header_json: str
    record_json: tuple[str, ...]


class JourneyDisplayObserver:
    """Observe one growing sidecar without retaining evidence across rewrites."""

    def __init__(self, stream_path: str | Path) -> None:
        self.stream_path = Path(stream_path)
        self._previous_revision: _StreamRevision | None = None
        self._last_change = "initial"
        self._generation = 1

    def snapshot(self) -> JourneyDisplaySnapshot:
        """Read, validate, reduce, and project one passive observation snapshot."""

        try:
            stream, file_identity = _read_stable_stream(self.stream_path)
            document = stream.to_dict()
            revision = _stream_revision(
                stream,
                document,
                file_identity=file_identity,
            )
            change = self._classify_revision(revision)
            snapshot_document = _snapshot_document(
                stream,
                document,
                change=change,
                generation=self._generation,
            )
        except (JourneyValidationError, MessageJourneyStreamError, OSError) as error:
            raise JourneyDisplayError(str(error)) from error
        serialized = json.dumps(
            snapshot_document,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        return JourneyDisplaySnapshot(serialized)

    def _classify_revision(self, revision: _StreamRevision) -> str:
        previous = self._previous_revision
        changed = True
        if previous is None:
            change = "initial"
        elif revision.file_identity != previous.file_identity:
            change = (
                "identity-changed"
                if revision.run_id != previous.run_id
                else "restarted"
            )
        elif revision.run_id != previous.run_id:
            change = "identity-changed"
        elif revision.header_json != previous.header_json:
            change = "replaced"
        elif revision.record_json == previous.record_json:
            change = self._last_change
            changed = False
        elif _is_prefix(previous.record_json, revision.record_json):
            change = "appended"
        elif _is_prefix(revision.record_json, previous.record_json):
            change = "truncated"
        else:
            change = "replaced"
        if changed and change in {
            "identity-changed",
            "replaced",
            "restarted",
            "truncated",
        }:
            self._generation += 1
        if changed:
            self._last_change = change
        self._previous_revision = revision
        return self._last_change


def _snapshot_document(
    stream: MessageJourneyStream,
    document: Mapping[str, Any],
    *,
    change: str,
    generation: int,
) -> dict[str, Any]:
    header = _mapping(document["header"], "message-journey display header")
    run = _mapping(header["run"], "message-journey display run")
    observation_documents = _sequence(
        document["observations"], "message-journey display observations"
    )
    route_projection = _route_projection(stream)
    observations_by_id = {
        str(_mapping(item, "message-journey display observation")["id"]): _mapping(
            item, "message-journey display observation"
        )
        for item in observation_documents
    }
    boundary_by_observation: dict[str, str] = {}
    for assessment in stream.diagnosis.boundaries:
        if assessment.state == BoundaryAssessmentState.MISSING:
            continue
        for observation_id in assessment.supporting_observation_ids:
            if observation_id in boundary_by_observation:
                raise JourneyDisplayError(
                    f"observation {observation_id!r} supports multiple journey boundaries"
                )
            boundary_by_observation[observation_id] = assessment.boundary.id
    if set(boundary_by_observation) != set(observations_by_id):
        raise JourneyDisplayError(
            "message-journey reducer did not assign every direct observation to one boundary"
        )

    observation_records = []
    for position, item in enumerate(observation_documents, start=1):
        observation = _mapping(item, "message-journey display observation")
        provenance = _mapping(
            observation["provenance"], "message-journey display observation provenance"
        )
        authority_class, authority = _observation_authority(str(provenance["kind"]))
        observation_records.append(
            {
                **_copy(observation),
                "record_position": position,
                "boundary_id": boundary_by_observation[str(observation["id"])],
                "authority_class": authority_class,
                "authority": authority,
            }
        )
    projected_by_id = {item["id"]: item for item in observation_records}

    boundary_records = []
    for assessment in stream.diagnosis.boundaries:
        boundary = assessment.boundary
        evidence_ids = (
            ()
            if assessment.state == BoundaryAssessmentState.MISSING
            else assessment.supporting_observation_ids
        )
        authorities = sorted(
            {str(projected_by_id[item]["authority_class"]) for item in evidence_ids}
        )
        boundary_records.append(
            {
                **_boundary_identity(boundary, route_projection),
                "state": assessment.state.value,
                "state_authority": "in-memory message-journey reducer",
                "configured_authority": "configured expected route",
                "evidence_observation_ids": list(evidence_ids),
                "context_supporting_observation_ids": list(
                    assessment.supporting_observation_ids
                ),
                "source_authority_classes": authorities,
            }
        )

    diagnosis = _mapping(document["diagnosis"], "message-journey display diagnosis")
    return {
        "snapshot_version": JOURNEY_DISPLAY_SNAPSHOT_VERSION,
        "mode": "terminal" if stream.is_terminal else "progressive",
        "run": {
            "id": stream.run_id,
            "started_at": run["started_at"],
        },
        "stream": {
            "schema_version": header["schema_version"],
            "validation": "validated-complete-prefix",
            "record_order": header["record_order"],
            "complete_observation_count": len(stream.observations),
            "complete_record_count": (
                1 + len(stream.observations) + int(stream.is_terminal)
            ),
            "incomplete_final_record": stream.has_incomplete_final_record,
            "is_terminal": stream.is_terminal,
            "change": change,
            "generation": generation,
        },
        "route": route_projection,
        "expected_messages": {
            "request": _copy(_mapping(header["journey"], "journey header")["request"]),
            "reply": _copy(_mapping(header["journey"], "journey header")["reply"]),
        },
        "assessment": {
            "authority": (
                "persisted terminal diagnosis verified against existing reducer"
                if stream.is_terminal
                else "current in-memory message-journey reducer"
            ),
            "journey_id": diagnosis["journey_id"],
            "state": diagnosis["state"],
            "first_boundary_id": diagnosis["first_boundary_id"],
            "supporting_observation_ids": _copy(
                diagnosis["supporting_observation_ids"]
            ),
            "boundaries": boundary_records,
        },
        "observations": observation_records,
        "provenance": _copy(run["provenance"]),
        "transaction_window": {
            "authority": "retained immutable byte-window metadata",
            "kind": _mapping(
                header["transaction_window"], "journey transaction window"
            )["kind"],
            "sources": _copy(
                _mapping(
                    header["transaction_window"], "journey transaction window"
                )["sources"]
            ),
        },
    }


def _route_projection(stream: MessageJourneyStream) -> dict[str, Any]:
    topology = stream.topology.topology
    components = _sequence(topology["components"], "message-journey route components")
    routes = _sequence(topology["routes"], "message-journey routes")
    route = next(
        (
            _mapping(item, "message-journey route")
            for item in routes
            if _mapping(item, "message-journey route")["id"] == stream.expected.route_id
        ),
        None,
    )
    if route is None:
        raise JourneyDisplayError(
            f"validated topology has no journey route {stream.expected.route_id!r}"
        )
    components_by_id = {
        str(_mapping(item, "message-journey component")["id"]): _mapping(
            item, "message-journey component"
        )
        for item in components
    }
    route_components = []
    endpoint_labels: dict[str, str] = {}
    for component_id in _sequence(route["components"], "message-journey route components"):
        component = components_by_id[str(component_id)]
        route_components.append(
            {
                "id": component["id"],
                "kind": component["kind"],
                "label": component["label"],
                "position": _copy(component["position"]),
            }
        )
        for endpoint_item in _sequence(
            component["endpoints"], "message-journey component endpoints"
        ):
            endpoint = _mapping(endpoint_item, "message-journey endpoint")
            endpoint_labels[str(endpoint["id"])] = str(endpoint["label"])

    request_boundaries = tuple(
        boundary
        for boundary in stream.expected.boundaries
        if boundary.leg == JourneyLeg.REQUEST
    )
    links_by_endpoints = {
        frozenset(str(endpoint) for endpoint in _sequence(link["endpoints"], "link endpoints")): str(
            link["id"]
        )
        for item in _sequence(topology["links"], "message-journey links")
        for link in (_mapping(item, "message-journey link"),)
    }
    route_links = []
    for index in range(0, len(request_boundaries), 2):
        first, second = request_boundaries[index : index + 2]
        link_id = links_by_endpoints.get(
            frozenset((first.interface_id, second.interface_id))
        )
        if link_id is None:
            raise JourneyDisplayError(
                f"expected boundary pair {first.id!r}/{second.id!r} has no configured link"
            )
        route_links.append(
            {
                "id": link_id,
                "from_component_id": first.component_id,
                "to_component_id": second.component_id,
                "from_interface_id": first.interface_id,
                "to_interface_id": second.interface_id,
                "authority": "configured shared topology",
            }
        )
    return {
        "journey_id": stream.expected.id,
        "topology_id": stream.expected.topology_id,
        "route_id": stream.expected.route_id,
        "authority": "configured shared topology",
        "components": route_components,
        "links": route_links,
        "interface_labels": endpoint_labels,
    }


def _boundary_identity(
    boundary: ExpectedBoundary,
    route: Mapping[str, Any],
) -> dict[str, Any]:
    components = {
        item["id"]: item
        for component in _sequence(route["components"], "message-journey route components")
        for item in (_mapping(component, "message-journey route component"),)
    }
    interface_labels = _mapping(
        route["interface_labels"], "message-journey route interface labels"
    )
    return {
        "id": boundary.id,
        "leg": boundary.leg.value,
        "position": boundary.position,
        "component_id": boundary.component_id,
        "component_label": components[boundary.component_id]["label"],
        "component_kind": components[boundary.component_id]["kind"],
        "interface_id": boundary.interface_id,
        "interface_label": interface_labels[boundary.interface_id],
        "direction": boundary.direction.value,
    }


def _observation_authority(kind: str) -> tuple[str, str]:
    if kind == "h316-hi-mi-trace":
        return ("direct", "direct H316 trace observation")
    if kind == "h316-connected-peer-delivery":
        return (
            "harness-derived",
            "harness-derived connected-peer observation",
        )
    return ("typed-other", "typed observation from another declared source")


def _stream_revision(
    stream: MessageJourneyStream,
    document: Mapping[str, Any],
    *,
    file_identity: tuple[int, int],
) -> _StreamRevision:
    records = [
        json.dumps(
            {"record_type": "observation", "observation": item},
            separators=(",", ":"),
            sort_keys=True,
        )
        for item in _sequence(
            document["observations"], "message-journey display observations"
        )
    ]
    if stream.is_terminal:
        records.append(
            json.dumps(
                {"record_type": "diagnosis", "diagnosis": document["diagnosis"]},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    return _StreamRevision(
        file_identity=file_identity,
        run_id=stream.run_id,
        header_json=json.dumps(
            document["header"], separators=(",", ":"), sort_keys=True
        ),
        record_json=tuple(records),
    )


def _read_stable_stream(path: Path) -> tuple[MessageJourneyStream, tuple[int, int]]:
    """Avoid assigning a validated prefix to a file modified during its read."""

    for _ in range(2):
        before = path.stat()
        stream = read_message_journey_stream(path)
        after = path.stat()
        before_identity = (before.st_dev, before.st_ino)
        after_identity = (after.st_dev, after.st_ino)
        before_revision = (
            *before_identity,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_revision = (
            *after_identity,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_revision == after_revision:
            return stream, after_identity
    raise JourneyDisplayError(
        "message-journey stream was repeatedly modified while being observed"
    )


def _is_prefix(first: tuple[str, ...], second: tuple[str, ...]) -> bool:
    return len(first) <= len(second) and second[: len(first)] == first


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise JourneyDisplayError(f"{location} must be an object")
    return value


def _sequence(value: object, location: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise JourneyDisplayError(f"{location} must be an array")
    return value


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(item) for item in value]
    return value
