"""Validated, read-only summaries of completed NCC-observed runs.

The schemas deliberately contain derived, project-authored facts only. They do
not read an external laboratory, launch a simulator, or imply that an external
evidence locator is available on the machine reading the summary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any


RUN_SUMMARY_SCHEMA_VERSION = 2
_SUPPORTED_SCHEMA_VERSIONS = frozenset((1, RUN_SUMMARY_SCHEMA_VERSION))

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_OBSERVATION_CATEGORIES = frozenset(
    {"application", "harness", "historical-network", "missing-evidence"}
)
_DERIVED_STATES_V1 = frozenset(
    {"contradictory", "down", "incomplete", "partitioned", "stale", "unknown", "up"}
)
_DERIVED_STATES_V2 = _DERIVED_STATES_V1 | frozenset(
    {"looped", "minus-down", "minus-looped", "plus-down", "plus-looped"}
)
_DERIVATION_BASES = frozenset({"direct", "inference"})
_GATE_KINDS = frozenset({"application", "network-behavior"})
_GATE_VERDICTS = frozenset({"failed", "inconclusive", "passed"})
_RUN_OUTCOMES = frozenset({"failed", "incomplete", "passed"})


class RunSummaryValidationError(ValueError):
    """Raised when a run summary cannot safely support NCC conclusions."""


@dataclass(frozen=True)
class RunSummary:
    """An immutable, canonical JSON representation of one completed run."""

    _serialized: str

    @property
    def run_id(self) -> str:
        """Return the stable identity of the summarized run."""

        return str(self.to_dict()["run"]["id"])

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh copy suitable for a read-only consumer."""

        return json.loads(self._serialized)

    def to_json(self) -> str:
        """Return the deterministic on-disk form, including its final newline."""

        return self._serialized


def load_run_summary(path: str | Path) -> RunSummary:
    """Load and validate one project-authored or safely derived JSON summary."""

    summary_path = Path(path)
    try:
        document = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RunSummaryValidationError(
            f"could not load run summary {summary_path}: {error}"
        ) from error
    return run_summary_from_mapping(document)


def run_summary_from_mapping(document: object) -> RunSummary:
    """Validate a mapping and return its deterministic, immutable representation."""

    _validate_document(document)
    canonical_document = _copy_json_value(document)
    return RunSummary(
        json.dumps(canonical_document, allow_nan=False, indent=2, sort_keys=True) + "\n"
    )


def validate_normalized_observations(
    topology: object,
    observations: object,
    *,
    started_at: str,
    finished_at: str,
) -> None:
    """Validate direct observations against the version-1 topology envelope.

    A live publisher has no completed-run verdict or final clock yet, but it
    must use the same topology identities and observation record shape as a
    completed summary. This shared validation boundary keeps a live reader
    from becoming a second, looser event schema.
    """

    run_started = _timestamp(started_at, "observation stream.started_at")
    run_finished = _timestamp(finished_at, "observation stream.finished_at")
    if run_finished < run_started:
        raise RunSummaryValidationError(
            "observation stream.finished_at precedes started_at"
        )
    component_ids, endpoint_owners, link_ids, route_ids = validate_normalized_topology(
        topology
    )
    subject_ids = component_ids | set(endpoint_owners) | link_ids | route_ids
    _validate_observations(
        observations,
        subject_ids,
        set(),
        run_started,
        run_finished,
    )


def validate_normalized_topology(
    topology: object,
) -> tuple[set[str], dict[str, str], set[str], set[str]]:
    """Validate the topology portion shared by summaries and live streams."""

    return _validate_topology(topology)


def _validate_document(document: object) -> None:
    root = _mapping(document, "summary")
    _fields(
        root,
        "summary",
        required={
            "schema_version",
            "run",
            "topology",
            "observations",
            "derived_states",
            "gates",
        },
        optional={"external_evidence"},
    )
    schema_version = root["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version not in _SUPPORTED_SCHEMA_VERSIONS
    ):
        raise RunSummaryValidationError(
            "summary.schema_version must be 1 or "
            f"{RUN_SUMMARY_SCHEMA_VERSION}, got {schema_version!r}"
        )

    run_started, run_finished, run_outcome = _validate_run(root["run"])
    external_evidence_ids = _validate_external_evidence(root.get("external_evidence", []))
    component_ids, endpoint_owners, link_ids, route_ids = _validate_topology(
        root["topology"]
    )
    subject_ids = component_ids | set(endpoint_owners) | link_ids | route_ids
    observations = _validate_observations(
        root["observations"],
        subject_ids,
        external_evidence_ids,
        run_started,
        run_finished,
    )
    derived_states = _validate_derived_states(
        root["derived_states"], subject_ids, observations, schema_version
    )
    gate_verdicts = _validate_gates(
        root["gates"],
        observations,
        derived_states,
        external_evidence_ids,
        schema_version,
    )
    if run_outcome == "passed" and any(verdict != "passed" for verdict in gate_verdicts):
        raise RunSummaryValidationError(
            "a passed run requires every acceptance gate to pass"
        )
    if run_outcome == "failed" and "failed" not in gate_verdicts:
        raise RunSummaryValidationError(
            "a failed run requires at least one failed acceptance gate"
        )
    _validate_json_value(root, "summary")


def _validate_run(value: object) -> tuple[datetime, datetime, str]:
    run = _mapping(value, "summary.run")
    _fields(
        run,
        "summary.run",
        required={"id", "started_at", "finished_at", "outcome", "provenance"},
    )
    _identifier(run["id"], "summary.run.id")
    started = _timestamp(run["started_at"], "summary.run.started_at")
    finished = _timestamp(run["finished_at"], "summary.run.finished_at")
    if finished < started:
        raise RunSummaryValidationError("summary.run.finished_at precedes started_at")
    outcome = _one_of(run["outcome"], _RUN_OUTCOMES, "summary.run.outcome")
    provenance = _list(run["provenance"], "summary.run.provenance")
    if not provenance:
        raise RunSummaryValidationError("summary.run.provenance must not be empty")
    for index, source_value in enumerate(provenance):
        location = f"summary.run.provenance[{index}]"
        source = _mapping(source_value, location)
        _fields(source, location, required={"id", "kind"}, optional={"revision"})
        _identifier(source["id"], f"{location}.id")
        _text(source["kind"], f"{location}.kind")
        if "revision" in source:
            _text(source["revision"], f"{location}.revision")
    return started, finished, outcome


def _validate_external_evidence(value: object) -> set[str]:
    evidence = _list(value, "summary.external_evidence")
    evidence_ids: set[str] = set()
    for index, entry_value in enumerate(evidence):
        location = f"summary.external_evidence[{index}]"
        entry = _mapping(entry_value, location)
        _fields(entry, location, required={"id", "kind", "locator"})
        evidence_id = _identifier(entry["id"], f"{location}.id")
        _unique(evidence_id, evidence_ids, f"{location}.id")
        _text(entry["kind"], f"{location}.kind")
        _text(entry["locator"], f"{location}.locator")
    return evidence_ids


def _validate_topology(value: object) -> tuple[set[str], dict[str, str], set[str], set[str]]:
    topology = _mapping(value, "summary.topology")
    _fields(topology, "summary.topology", required={"components", "links", "routes"})

    components = _list(topology["components"], "summary.topology.components")
    if not components:
        raise RunSummaryValidationError("summary.topology.components must not be empty")
    component_ids: set[str] = set()
    endpoint_owners: dict[str, str] = {}
    for index, component_value in enumerate(components):
        location = f"summary.topology.components[{index}]"
        component = _mapping(component_value, location)
        _fields(component, location, required={"endpoints", "id", "kind", "label", "position"})
        component_id = _identifier(component["id"], f"{location}.id")
        _unique(component_id, component_ids, f"{location}.id")
        _text(component["kind"], f"{location}.kind")
        _text(component["label"], f"{location}.label")
        position = _mapping(component["position"], f"{location}.position")
        _fields(position, f"{location}.position", required={"x", "y"})
        _number(position["x"], f"{location}.position.x")
        _number(position["y"], f"{location}.position.y")
        endpoints = _list(component["endpoints"], f"{location}.endpoints")
        if not endpoints:
            raise RunSummaryValidationError(f"{location}.endpoints must not be empty")
        for endpoint_index, endpoint_value in enumerate(endpoints):
            endpoint_location = f"{location}.endpoints[{endpoint_index}]"
            endpoint = _mapping(endpoint_value, endpoint_location)
            _fields(endpoint, endpoint_location, required={"id", "label"})
            endpoint_id = _identifier(endpoint["id"], f"{endpoint_location}.id")
            if endpoint_id in endpoint_owners:
                raise RunSummaryValidationError(
                    f"{endpoint_location}.id duplicates endpoint {endpoint_id!r}"
                )
            endpoint_owners[endpoint_id] = component_id
            _text(endpoint["label"], f"{endpoint_location}.label")

    links = _list(topology["links"], "summary.topology.links")
    link_ids: set[str] = set()
    component_pairs: set[frozenset[str]] = set()
    for index, link_value in enumerate(links):
        location = f"summary.topology.links[{index}]"
        link = _mapping(link_value, location)
        _fields(link, location, required={"endpoints", "id"})
        link_id = _identifier(link["id"], f"{location}.id")
        _unique(link_id, link_ids, f"{location}.id")
        endpoints = _list(link["endpoints"], f"{location}.endpoints")
        if len(endpoints) != 2:
            raise RunSummaryValidationError(f"{location}.endpoints must contain two endpoints")
        first = _identifier(endpoints[0], f"{location}.endpoints[0]")
        second = _identifier(endpoints[1], f"{location}.endpoints[1]")
        if first == second:
            raise RunSummaryValidationError(f"{location}.endpoints must be distinct")
        for endpoint in (first, second):
            if endpoint not in endpoint_owners:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown endpoint {endpoint!r}"
                )
        component_pairs.add(
            frozenset((endpoint_owners[first], endpoint_owners[second]))
        )

    routes = _list(topology["routes"], "summary.topology.routes")
    route_ids: set[str] = set()
    for index, route_value in enumerate(routes):
        location = f"summary.topology.routes[{index}]"
        route = _mapping(route_value, location)
        _fields(route, location, required={"components", "id"})
        route_id = _identifier(route["id"], f"{location}.id")
        _unique(route_id, route_ids, f"{location}.id")
        route_components = _list(route["components"], f"{location}.components")
        if len(route_components) < 2:
            raise RunSummaryValidationError(
                f"{location}.components must contain at least two components"
            )
        component_path = [
            _identifier(component, f"{location}.components[{position}]")
            for position, component in enumerate(route_components)
        ]
        for component in component_path:
            if component not in component_ids:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown component {component!r}"
                )
        for first, second in zip(component_path, component_path[1:]):
            if frozenset((first, second)) not in component_pairs:
                raise RunSummaryValidationError(
                    f"{location} has no configured link between {first!r} and {second!r}"
                )
    topology_ids: set[str] = set()
    for kind, identifiers in (
        ("component", component_ids),
        ("endpoint", set(endpoint_owners)),
        ("link", link_ids),
        ("route", route_ids),
    ):
        overlap = topology_ids & identifiers
        if overlap:
            raise RunSummaryValidationError(
                f"summary.topology {kind} identifiers overlap: {', '.join(sorted(overlap))}"
            )
        topology_ids.update(identifiers)
    return component_ids, endpoint_owners, link_ids, route_ids


def _validate_observations(
    value: object,
    subject_ids: set[str],
    external_evidence_ids: set[str],
    run_started: datetime,
    run_finished: datetime,
) -> dict[str, Mapping[str, Any]]:
    entries = _list(value, "summary.observations")
    if not entries:
        raise RunSummaryValidationError("summary.observations must not be empty")
    observations: dict[str, Mapping[str, Any]] = {}
    previous_time: datetime | None = None
    for index, observation_value in enumerate(entries):
        location = f"summary.observations[{index}]"
        observation = _mapping(observation_value, location)
        _fields(
            observation,
            location,
            required={
                "category",
                "id",
                "observed_at",
                "sequence",
                "source",
                "state",
                "subject_id",
            },
            optional={"details", "external_evidence_ids"},
        )
        observation_id = _identifier(observation["id"], f"{location}.id")
        if observation_id in observations:
            raise RunSummaryValidationError(
                f"{location}.id duplicates observation {observation_id!r}"
            )
        sequence = observation["sequence"]
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence != index + 1
        ):
            raise RunSummaryValidationError(
                f"{location}.sequence must be {index + 1}, got {sequence!r}"
            )
        observed_at = _timestamp(observation["observed_at"], f"{location}.observed_at")
        if not run_started <= observed_at <= run_finished:
            raise RunSummaryValidationError(
                f"{location}.observed_at falls outside the run clock"
            )
        if previous_time is not None and observed_at < previous_time:
            raise RunSummaryValidationError(
                f"{location}.observed_at is earlier than the preceding observation"
            )
        previous_time = observed_at
        _one_of(observation["category"], _OBSERVATION_CATEGORIES, f"{location}.category")
        subject_id = _identifier(observation["subject_id"], f"{location}.subject_id")
        if subject_id not in subject_ids:
            raise RunSummaryValidationError(
                f"{location}.subject_id refers to unknown topology item {subject_id!r}"
            )
        _text(observation["state"], f"{location}.state")
        source = _mapping(observation["source"], f"{location}.source")
        _fields(source, f"{location}.source", required={"id", "kind"})
        _identifier(source["id"], f"{location}.source.id")
        _text(source["kind"], f"{location}.source.kind")
        if "details" in observation:
            _mapping(observation["details"], f"{location}.details")
        for evidence_id in _identifiers(
            observation.get("external_evidence_ids", []),
            f"{location}.external_evidence_ids",
        ):
            if evidence_id not in external_evidence_ids:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown external evidence {evidence_id!r}"
                )
        observations[observation_id] = observation
    return observations


def _validate_derived_states(
    value: object,
    subject_ids: set[str],
    observations: Mapping[str, Mapping[str, Any]],
    schema_version: int,
) -> dict[str, Mapping[str, Any]]:
    entries = _list(value, "summary.derived_states")
    derived_states: dict[str, Mapping[str, Any]] = {}
    allowed_states = (
        _DERIVED_STATES_V1 if schema_version == 1 else _DERIVED_STATES_V2
    )
    for index, derived_value in enumerate(entries):
        location = f"summary.derived_states[{index}]"
        derived = _mapping(derived_value, location)
        _fields(
            derived,
            location,
            required={"basis", "id", "state", "subject_id", "supporting_observation_ids"},
        )
        derived_id = _identifier(derived["id"], f"{location}.id")
        if derived_id in derived_states:
            raise RunSummaryValidationError(
                f"{location}.id duplicates identifier {derived_id!r}"
            )
        subject_id = _identifier(derived["subject_id"], f"{location}.subject_id")
        if subject_id not in subject_ids:
            raise RunSummaryValidationError(
                f"{location}.subject_id refers to unknown topology item {subject_id!r}"
            )
        state = _one_of(derived["state"], allowed_states, f"{location}.state")
        basis = _one_of(derived["basis"], _DERIVATION_BASES, f"{location}.basis")
        supporting_ids = _identifiers(
            derived["supporting_observation_ids"],
            f"{location}.supporting_observation_ids",
        )
        if not supporting_ids:
            raise RunSummaryValidationError(
                f"{location}.supporting_observation_ids must not be empty"
            )
        for observation_id in supporting_ids:
            if observation_id not in observations:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown observation {observation_id!r}"
                )
        if state in {"contradictory", "partitioned"} and basis != "inference":
            raise RunSummaryValidationError(
                f"{location}.basis must be inference for {state!r} state"
            )
        derived_states[derived_id] = derived
    return derived_states


def _validate_gates(
    value: object,
    observations: Mapping[str, Mapping[str, Any]],
    derived_states: Mapping[str, Mapping[str, Any]],
    external_evidence_ids: set[str],
    schema_version: int,
) -> list[str]:
    entries = _list(value, "summary.gates")
    if not entries:
        raise RunSummaryValidationError("summary.gates must not be empty")
    gate_ids: set[str] = set()
    verdicts: list[str] = []
    for index, gate_value in enumerate(entries):
        location = f"summary.gates[{index}]"
        gate = _mapping(gate_value, location)
        if schema_version == 1:
            _fields(
                gate,
                location,
                required={"assertion", "evidence_observation_ids", "id", "verdict"},
                optional={"external_evidence_ids"},
            )
            gate_kind = "application"
            derived_evidence_ids: list[str] = []
        else:
            _fields(
                gate,
                location,
                required={
                    "assertion",
                    "evidence_derived_state_ids",
                    "evidence_observation_ids",
                    "id",
                    "kind",
                    "verdict",
                },
                optional={"external_evidence_ids"},
            )
            gate_kind = _one_of(gate["kind"], _GATE_KINDS, f"{location}.kind")
            derived_evidence_ids = _identifiers(
                gate["evidence_derived_state_ids"],
                f"{location}.evidence_derived_state_ids",
            )
        gate_id = _identifier(gate["id"], f"{location}.id")
        _unique(gate_id, gate_ids, f"{location}.id")
        _text(gate["assertion"], f"{location}.assertion")
        verdict = _one_of(gate["verdict"], _GATE_VERDICTS, f"{location}.verdict")
        evidence_ids = _identifiers(
            gate["evidence_observation_ids"], f"{location}.evidence_observation_ids"
        )
        if not evidence_ids:
            raise RunSummaryValidationError(
                f"{location}.evidence_observation_ids must not be empty"
            )
        evidence = []
        for observation_id in evidence_ids:
            try:
                evidence.append(observations[observation_id])
            except KeyError as error:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown observation {observation_id!r}"
                ) from error
        derived_evidence = []
        for derived_id in derived_evidence_ids:
            try:
                derived_evidence.append(derived_states[derived_id])
            except KeyError as error:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown derived state {derived_id!r}"
                ) from error
        if verdict == "passed":
            if gate_kind == "application" and not any(
                observation["category"] == "application"
                and observation["state"] == "passed"
                for observation in evidence
            ):
                raise RunSummaryValidationError(
                    f"{location} passes without passed application evidence"
                )
            if gate_kind == "network-behavior":
                _validate_passed_network_gate(
                    location,
                    evidence_ids,
                    evidence,
                    derived_evidence,
                    observations,
                )
        for evidence_id in _identifiers(
            gate.get("external_evidence_ids", []), f"{location}.external_evidence_ids"
        ):
            if evidence_id not in external_evidence_ids:
                raise RunSummaryValidationError(
                    f"{location} refers to unknown external evidence {evidence_id!r}"
                )
        verdicts.append(verdict)
    return verdicts


def _validate_passed_network_gate(
    location: str,
    evidence_ids: list[str],
    evidence: list[Mapping[str, Any]],
    derived_evidence: list[Mapping[str, Any]],
    observations: Mapping[str, Mapping[str, Any]],
) -> None:
    if not derived_evidence:
        raise RunSummaryValidationError(
            f"{location} passes without a derived network-behavior state"
        )
    if not any(
        observation["category"] == "harness" and observation["state"] == "passed"
        for observation in evidence
    ):
        raise RunSummaryValidationError(
            f"{location} passes without a passed harness observation"
        )
    evidence_id_set = set(evidence_ids)
    for derived in derived_evidence:
        if derived["basis"] != "inference":
            raise RunSummaryValidationError(
                f"{location} network-behavior evidence must be inferential"
            )
        support_ids = list(derived["supporting_observation_ids"])
        if not support_ids or not set(support_ids) <= evidence_id_set:
            raise RunSummaryValidationError(
                f"{location} does not include the complete derived-state support closure"
            )
        if any(
            observations[observation_id]["category"] != "historical-network"
            for observation_id in support_ids
        ):
            raise RunSummaryValidationError(
                f"{location} derived network state is not supported only by "
                "historical-network observations"
            )


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunSummaryValidationError(f"{location} must be an object")
    return value


def _list(value: object, location: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise RunSummaryValidationError(f"{location} must be an array")
    return value


def _fields(
    mapping: Mapping[str, Any],
    location: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = required - mapping.keys()
    unknown = mapping.keys() - allowed
    if missing:
        raise RunSummaryValidationError(f"{location} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise RunSummaryValidationError(f"{location} has unknown fields: {', '.join(sorted(unknown))}")


def _identifier(value: object, location: str) -> str:
    text = _text(value, location)
    if not _IDENTIFIER.fullmatch(text):
        raise RunSummaryValidationError(f"{location} is not a stable identifier: {text!r}")
    return text


def _identifiers(value: object, location: str) -> list[str]:
    values = _list(value, location)
    identifiers = [_identifier(item, f"{location}[{index}]") for index, item in enumerate(values)]
    if len(set(identifiers)) != len(identifiers):
        raise RunSummaryValidationError(f"{location} must not contain duplicate identifiers")
    return identifiers


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise RunSummaryValidationError(f"{location} must be a non-empty string")
    return value


def _number(value: object, location: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise RunSummaryValidationError(f"{location} must be a number")


def _timestamp(value: object, location: str) -> datetime:
    text = _text(value, location)
    if not text.endswith("Z"):
        raise RunSummaryValidationError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise RunSummaryValidationError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error


def _one_of(value: object, options: frozenset[str], location: str) -> str:
    text = _text(value, location)
    if text not in options:
        raise RunSummaryValidationError(
            f"{location} must be one of {', '.join(sorted(options))}, got {text!r}"
        )
    return text


def _unique(identifier: str, known: set[str], location: str) -> None:
    if identifier in known:
        raise RunSummaryValidationError(f"{location} duplicates identifier {identifier!r}")
    known.add(identifier)


def _validate_json_value(value: object, location: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise RunSummaryValidationError(
            f"{location} must not contain a non-finite number"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{location}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise RunSummaryValidationError(
                    f"{location} must have string object keys"
                )
            _validate_json_value(item, f"{location}.{key}")
        return
    raise RunSummaryValidationError(f"{location} must contain only JSON values")


def _copy_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json_value(item) for item in value]
    return value
