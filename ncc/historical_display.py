"""Passive progressive snapshots for historical NCC event sidecars.

The display observer reads only a validated complete JSONL prefix and a supplied
project topology. It delegates endpoint pairing and freshness to
``ncc.reconciliation`` and delegates terminal authority to the accepted
version-2 completed-summary adapter. It never opens raw logs or controls a
simulator, receiver, relay, reflector, or external network endpoint.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from .events import NccEvent
from .historical_events import (
    HistoricalEventStream,
    HistoricalEventStreamError,
    read_historical_event_stream,
)
from .historical_summary import (
    HistoricalLineSummaryError,
    summarize_historical_line_result,
)
from .reconciliation import (
    HistoricalLineTopology,
    ReconciledEndpoint,
    Reconciliation,
    ReconciliationError,
    historical_line_topology_from_shared,
    observation_is_stale,
    reconcile,
)
from .run_summary import RunSummary
from .shared_topology import (
    SharedTopology,
    SharedTopologyValidationError,
    load_shared_topology,
)


HISTORICAL_DISPLAY_SNAPSHOT_VERSION = 1
DEFAULT_REPORT_INTERVAL = timedelta(seconds=30)


class HistoricalDisplayError(ValueError):
    """Raised when the passive display cannot produce a trustworthy snapshot."""


@dataclass(frozen=True)
class HistoricalDisplaySnapshot:
    """One deterministic display document and an optional validated handoff."""

    _serialized: str
    completed_summary: RunSummary | None = None

    @property
    def mode(self) -> str:
        """Return live, completed, or completion-error display mode."""

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
    event_json: tuple[str, ...]


class HistoricalDisplayObserver:
    """Observe one growing sidecar without retaining evidence across rewrites."""

    def __init__(
        self,
        stream_path: str | Path,
        shared_topology_path: str | Path,
        *,
        results_dir: str | Path | None = None,
        report_interval: timedelta = DEFAULT_REPORT_INTERVAL,
    ) -> None:
        if report_interval <= timedelta(0):
            raise HistoricalDisplayError("report_interval must be positive")
        self.stream_path = Path(stream_path)
        self.shared_topology_path = Path(shared_topology_path)
        self.results_dir = Path(results_dir) if results_dir is not None else None
        self.report_interval = report_interval
        try:
            self.shared_topology = load_shared_topology(self.shared_topology_path)
            self.historical_topology = historical_line_topology_from_shared(
                self.shared_topology
            )
        except (ReconciliationError, SharedTopologyValidationError) as error:
            raise HistoricalDisplayError(str(error)) from error
        self._previous_revision: _StreamRevision | None = None
        self._last_change = "initial"
        self._generation = 1

    def snapshot(
        self,
        observed_at: datetime | None = None,
    ) -> HistoricalDisplaySnapshot:
        """Read, validate, reduce, and project one passive observation snapshot."""

        current = _utc_datetime(observed_at)
        current_text = _timestamp_text(current)
        try:
            stream, file_identity = _read_stable_stream(self.stream_path)
            document = stream.to_dict()
            self._validate_stream_header(stream, document["header"])
            revision = _stream_revision(
                stream,
                document,
                file_identity=file_identity,
            )
            change = self._classify_revision(revision)
            events = stream.events
            reconciliation = reconcile(
                self.historical_topology.nominal,
                events,
                started_at=str(document["header"]["run"]["started_at"]),
                observed_at=current_text,
                report_interval=self.report_interval,
            )
        except (HistoricalEventStreamError, OSError, ReconciliationError) as error:
            raise HistoricalDisplayError(str(error)) from error

        completion, completed_summary = self._completion(
            stream=stream,
            events=events,
        )
        mode = {
            "matched": "completed",
            "mismatch": "completion-mismatch",
            "invalid": "completion-invalid",
        }.get(str(completion["status"]), "live")
        endpoint_records = _direct_endpoint_records(
            reconciliation,
            events,
            self.historical_topology,
        )
        imp_records = _direct_imp_records(
            self.shared_topology,
            events,
            observed_at=current_text,
            report_interval=self.report_interval,
        )
        line_records = _reconciled_line_records(
            reconciliation,
            self.historical_topology,
        )
        configured_link_ids = [
            str(link["id"]) for link in self.shared_topology.topology["links"]
        ]
        mapped_link_ids = set(self.historical_topology.line_link_ids.values())
        snapshot_document = {
            "snapshot_version": HISTORICAL_DISPLAY_SNAPSHOT_VERSION,
            "mode": mode,
            "observed_at": current_text,
            "run": {
                "id": stream.run_id,
                "started_at": document["header"]["run"]["started_at"],
            },
            "stream": {
                "schema_version": document["header"]["schema_version"],
                "validation": "validated-complete-prefix",
                "complete_event_count": len(events),
                "incomplete_final_record": stream.has_incomplete_final_record,
                "change": change,
                "generation": self._generation,
            },
            "configured": {
                "topology_id": document["header"]["run"]["topology_id"],
                "component_ids": [
                    str(component["id"])
                    for component in self.shared_topology.topology["components"]
                ],
                "link_ids": configured_link_ids,
                "configured_only_link_ids": [
                    identifier
                    for identifier in configured_link_ids
                    if identifier not in mapped_link_ids
                ],
            },
            "direct": {
                "authority": "direct historical-network observation",
                "endpoints": endpoint_records,
                "imps": imp_records,
            },
            "reconciled": {
                "authority": "in-memory reconciliation",
                "observed_at": current_text,
                "report_interval_seconds": self.report_interval.total_seconds(),
                "lines": line_records,
            },
            "event_tape": _event_tape(events, self.historical_topology),
            "provenance": document["header"]["run"]["provenance"],
            "completion": completion,
        }
        serialized = json.dumps(
            snapshot_document,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        return HistoricalDisplaySnapshot(serialized, completed_summary)

    def _validate_stream_header(
        self,
        stream: HistoricalEventStream,
        header: Mapping[str, Any],
    ) -> None:
        run = header["run"]
        if run["topology_id"] != self.shared_topology.id:
            raise HistoricalDisplayError(
                "historical event stream topology identity does not match the supplied topology"
            )
        if header["topology"] != self.shared_topology.topology:
            raise HistoricalDisplayError(
                "historical event stream topology snapshot does not match the supplied topology"
            )
        try:
            self.shared_topology.interface(str(run["interface_id"]))
        except SharedTopologyValidationError as error:
            raise HistoricalDisplayError(str(error)) from error
        if not stream.run_id:
            raise HistoricalDisplayError("historical event stream has no run identity")

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
        elif revision.event_json == previous.event_json:
            change = self._last_change
            changed = False
        elif _is_prefix(previous.event_json, revision.event_json):
            change = "appended"
        elif _is_prefix(revision.event_json, previous.event_json):
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

    def _completion(
        self,
        *,
        stream: HistoricalEventStream,
        events: Sequence[NccEvent],
    ) -> tuple[dict[str, Any], RunSummary | None]:
        if self.results_dir is None:
            return ({"status": "unavailable", "authority": "none"}, None)
        manifest_path = self.results_dir / "runtime" / "run.env"
        verdict_path = self.results_dir / "verdict.json"
        if not manifest_path.is_file() or not verdict_path.is_file():
            return (
                {
                    "status": "pending",
                    "authority": "completed v2 summary",
                    "message": "Formal terminal manifest and supported verdict are not both available.",
                },
                None,
            )
        try:
            if not _manifest_looks_terminal(manifest_path):
                return (
                    {
                        "status": "pending",
                        "authority": "completed v2 summary",
                        "message": "Formal completion has not been recorded in the run manifest.",
                    },
                    None,
                )
            summary = summarize_historical_line_result(
                self.results_dir,
                self.shared_topology_path,
            )
        except (HistoricalDisplayError, HistoricalLineSummaryError, OSError) as error:
            return (
                {
                    "status": "invalid",
                    "authority": "completed v2 summary",
                    "message": str(error),
                },
                None,
            )
        if not events:
            return (
                {
                    "status": "mismatch",
                    "authority": "completed v2 summary",
                    "issues": ["completed summary exists but the live stream has no events"],
                },
                summary,
            )
        try:
            final_reconciliation = reconcile(
                self.historical_topology.nominal,
                events,
                started_at=stream.to_dict()["header"]["run"]["started_at"],
                observed_at=events[-1].observed_at,
                report_interval=self.report_interval,
            )
        except ReconciliationError as error:
            raise HistoricalDisplayError(str(error)) from error
        issues = compare_completed_summary(
            summary,
            final_reconciliation,
            self.historical_topology,
        )
        summary_document = summary.to_dict()
        if summary_document["run"]["id"] != f"run:{stream.run_id}":
            issues = (
                "completed summary run identity does not match the observed stream",
                *issues,
            )
        summary_lines = [
            {
                "id": item["id"],
                "subject_id": item["subject_id"],
                "state": item["state"],
                "supporting_observation_ids": item["supporting_observation_ids"],
                "authority": "completed v2 summary",
            }
            for item in summary_document["derived_states"]
            if item["subject_id"] in set(self.historical_topology.line_link_ids.values())
        ]
        harness_observations = [
            item
            for item in summary_document["observations"]
            if item["category"] == "harness"
        ]
        if issues:
            return (
                {
                    "status": "mismatch",
                    "authority": "completed v2 summary",
                    "issues": list(issues),
                    "summary_lines": summary_lines,
                    "harness_observations": harness_observations,
                },
                summary,
            )
        return (
            {
                "status": "matched",
                "authority": "completed v2 summary",
                "schema_version": summary_document["schema_version"],
                "outcome": summary_document["run"]["outcome"],
                "summary_lines": summary_lines,
                "harness_observations": harness_observations,
                "gate_ids": [gate["id"] for gate in summary_document["gates"]],
                "handoff_url": "/completed",
            },
            summary,
        )


def compare_completed_summary(
    summary: RunSummary,
    final_reconciliation: Reconciliation,
    topology: HistoricalLineTopology,
) -> tuple[str, ...]:
    """Compare final in-memory line conclusions with a validated v2 summary."""

    document = summary.to_dict()
    issues: list[str] = []
    if document["schema_version"] != 2:
        issues.append("completed historical-line handoff is not summary schema version 2")
    summary_by_subject: dict[str, list[Mapping[str, Any]]] = {}
    mapped_subjects = set(topology.line_link_ids.values())
    for derived in document["derived_states"]:
        if derived["subject_id"] in mapped_subjects:
            summary_by_subject.setdefault(str(derived["subject_id"]), []).append(derived)
    for line in final_reconciliation.lines:
        subject_id = topology.line_link_ids[line.id]
        entries = summary_by_subject.get(subject_id, [])
        if len(entries) != 1:
            issues.append(
                f"completed summary has {len(entries)} final states for mapped link {subject_id!r}"
            )
            continue
        derived = entries[0]
        if derived["state"] != line.state.value:
            issues.append(
                f"mapped link {subject_id!r} is {line.state.value!r} live but "
                f"{derived['state']!r} in the completed summary"
            )
        expected_support = [
            _event_id(sequence) for sequence in line.supporting_sequences
        ]
        if derived["supporting_observation_ids"] != expected_support:
            issues.append(
                f"mapped link {subject_id!r} live support {expected_support!r} "
                "does not match the completed summary"
            )
    return tuple(issues)


def _direct_endpoint_records(
    reconciliation: Reconciliation,
    events: Sequence[NccEvent],
    topology: HistoricalLineTopology,
) -> list[dict[str, Any]]:
    events_by_sequence = {event.sequence: event for event in events}
    lines_by_id = {line.id: line for line in topology.nominal.lines}
    records = []
    for endpoint in reconciliation.endpoints:
        line = lines_by_id[endpoint.line_id]
        sequence = endpoint.supporting_sequences[0] if endpoint.supporting_sequences else None
        event = events_by_sequence.get(sequence) if sequence is not None else None
        source = (
            {"kind": event.source.kind, "imp": event.source.imp}
            if event is not None
            else None
        )
        records.append(
            {
                "subject": endpoint.endpoint.subject,
                "normalized_subject_id": topology.endpoint_subject_ids[
                    endpoint.endpoint.subject
                ],
                "line_id": endpoint.line_id,
                "normalized_link_id": topology.line_link_ids[endpoint.line_id],
                "direction": endpoint.direction,
                "configured_peer_imp": line.peer(endpoint.endpoint).imp,
                "state": endpoint.state.value,
                "last_known_state": endpoint.last_known_state,
                "observed_at": endpoint.observed_at,
                "topology_match": endpoint.topology_match,
                "event_id": _event_id(sequence) if sequence is not None else None,
                "sequence": sequence,
                "source": source,
                "details": _compact_event_details(event) if event is not None else {},
                "authority": "direct historical-network observation",
                "state_authority": _endpoint_state_authority(endpoint),
            }
        )
    return records


def _direct_imp_records(
    shared: SharedTopology,
    events: Sequence[NccEvent],
    *,
    observed_at: str,
    report_interval: timedelta,
) -> list[dict[str, Any]]:
    imp_ids = sorted(
        str(component["id"])
        for component in shared.topology["components"]
        if component["kind"] == "imp"
    )
    latest = {
        event.subject: event
        for event in events
        if event.event_type == "imp.report" and event.subject in imp_ids
    }
    records = []
    for imp_id in imp_ids:
        event = latest.get(imp_id)
        if event is None:
            records.append(
                {
                    "subject_id": imp_id,
                    "state": "unknown",
                    "last_known_state": None,
                    "event_id": None,
                    "sequence": None,
                    "observed_at": None,
                    "source": None,
                    "authority": "direct historical-network observation",
                    "state_authority": "in-memory absence classification",
                    "meaning": "no attributed trouble report observed",
                }
            )
            continue
        stale = observation_is_stale(
            event.observed_at,
            as_of=observed_at,
            report_interval=report_interval,
        )
        records.append(
            {
                "subject_id": imp_id,
                "state": "stale" if stale else "up",
                "last_known_state": "report-received",
                "event_id": _event_id(event.sequence),
                "sequence": event.sequence,
                "observed_at": event.observed_at,
                "source": {"kind": event.source.kind, "imp": event.source.imp},
                "authority": "direct historical-network observation",
                "state_authority": "in-memory report-freshness classification",
                "meaning": (
                    "last attributed trouble report is expired"
                    if stale
                    else "fresh attributed trouble report received"
                ),
            }
        )
    return records


def _reconciled_line_records(
    reconciliation: Reconciliation,
    topology: HistoricalLineTopology,
) -> list[dict[str, Any]]:
    return [
        {
            "id": line.id,
            "subject_id": topology.line_link_ids[line.id],
            "state": line.state.value,
            "supporting_sequences": list(line.supporting_sequences),
            "supporting_observation_ids": [
                _event_id(sequence) for sequence in line.supporting_sequences
            ],
            "basis": "inference",
            "authority": "in-memory reconciliation",
        }
        for line in reconciliation.lines
    ]


def _endpoint_state_authority(endpoint: ReconciledEndpoint) -> str:
    state = endpoint.state
    if endpoint.observed_at is None:
        return "in-memory absence classification"
    if state.value == "stale":
        return "in-memory report-freshness classification"
    if state.value == "contradictory":
        return "in-memory topology comparison"
    return "direct historical-network observation"


def _event_tape(
    events: Sequence[NccEvent],
    topology: HistoricalLineTopology,
) -> list[dict[str, Any]]:
    tape = []
    for event in events:
        normalized_subject = topology.endpoint_subject_ids.get(event.subject)
        if normalized_subject is None and event.event_type in {
            "imp.report",
            "imp.throughput-report",
            "host-interface.state",
        }:
            normalized_subject = event.subject
        tape.append(
            {
                "id": _event_id(event.sequence),
                "sequence": event.sequence,
                "observed_at": event.observed_at,
                "type": event.event_type,
                "subject": event.subject,
                "normalized_subject_id": normalized_subject,
                "state": event.state,
                "source": {"kind": event.source.kind, "imp": event.source.imp},
                "authority": "direct historical-network observation",
                "label": _event_label(event),
                "details": _compact_event_details(event),
            }
        )
    return tape


def _event_label(event: NccEvent) -> str:
    if event.event_type == "imp.report":
        return f"IMP {event.source.imp} trouble report arrived"
    if event.event_type == "imp.throughput-report":
        return f"IMP {event.source.imp} cumulative throughput report arrived"
    if event.event_type == "line-endpoint.state":
        return f"{event.subject} reported {event.state}"
    if event.event_type == "host-interface.state":
        return f"{event.subject} reported {event.state}"
    return f"{event.subject} {event.state}"


def _compact_event_details(event: NccEvent | None) -> dict[str, Any]:
    if event is None:
        return {}
    details = event.details
    if event.event_type == "imp.throughput-report":
        line_counters = details.get("line_throughput", [])
        host_counters = details.get("host_throughput", [])
        return {
            "message_type": details.get("message_type"),
            "line_counter_groups": len(line_counters) if isinstance(line_counters, list) else None,
            "host_counter_groups": len(host_counters) if isinstance(host_counters, list) else None,
            "counter_semantics": "cumulative, not a rate",
        }
    return json.loads(json.dumps(dict(details), allow_nan=False, sort_keys=True))


def _stream_revision(
    stream: HistoricalEventStream,
    document: Mapping[str, Any],
    *,
    file_identity: tuple[int, int],
) -> _StreamRevision:
    return _StreamRevision(
        file_identity=file_identity,
        run_id=stream.run_id,
        header_json=json.dumps(document["header"], separators=(",", ":"), sort_keys=True),
        event_json=tuple(
            json.dumps(event, separators=(",", ":"), sort_keys=True)
            for event in document["events"]
        ),
    )


def _read_stable_stream(
    path: Path,
) -> tuple[HistoricalEventStream, tuple[int, int]]:
    """Avoid assigning a validated prefix to a file modified during its read."""

    for _ in range(2):
        before = path.stat()
        stream = read_historical_event_stream(path)
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
    raise HistoricalDisplayError(
        "historical event stream was repeatedly modified while being observed"
    )


def _manifest_looks_terminal(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise HistoricalDisplayError(f"could not read run manifest {path}: {error}") from error
    keys = {line.partition("=")[0] for line in lines if "=" in line}
    return {
        "cleanup.completed",
        "exit_status",
        "finished_utc",
        "outcome",
        "result.verdict-exit-status",
    } <= keys


def _event_id(sequence: int) -> str:
    return f"observation:historical:{sequence}"


def _is_prefix(first: tuple[str, ...], second: tuple[str, ...]) -> bool:
    return len(first) <= len(second) and second[: len(first)] == first


def _utc_datetime(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise HistoricalDisplayError("snapshot observation time must be timezone-aware")
    return current.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
