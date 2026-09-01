"""Project one validated coexistence result into a passive completed snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .events import NccEvent
from .historical_events import (
    HistoricalEventStream,
    HistoricalEventStreamError,
    read_historical_event_stream,
)
from .journey_display import (
    JourneyDisplayError,
    JourneyDisplayObserver,
)
from .message_journey_stream import (
    MessageJourneyStream,
    MessageJourneyStreamError,
    read_message_journey_stream,
)
from .reconciliation import (
    HistoricalLineTopology,
    LineState,
    ReconciledLine,
    Reconciliation,
    ReconciliationError,
    historical_line_topology_from_shared,
    reconcile,
)
from .shared_topology import (
    SharedTopology,
    SharedTopologyValidationError,
    load_shared_topology,
)

COEXISTENCE_DISPLAY_SNAPSHOT_VERSION = 1
REPORT_INTERVAL = timedelta(seconds=30)

TOPOLOGY_ID = "topology:ncc-pdp11-its-coexistence"
MANIFEST_TOPOLOGY = "ncc-pdp11-its-coexistence"
VERDICT_KIND = "ncc-pdp11-its-coexistence-verdict"
DIRECT_LINE_ID = "binding:imp5-mi1-imp6-mi1"
DIRECT_LINK_ID = "link:imp5-imp6-direct"
NCC_INTERFACE_ID = "binding:ncc-host0-imp5"
APPLICATION_ROUTE_ID = "route:host176-to-host106"
JOURNEY_ID = "journey:network-unix-telnet-open"
EXPECTED_IMPS = (5, 6, 7, 62)

_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SERVICE_USER = re.compile(r"[0-9]+TLNT\Z")

_CHECK_IDS = (
    "evidence-identities-match",
    "clean-pinned-inputs",
    "outer-runtime-cleanup",
    "application-passed",
    "typed-journey-retained",
    "application-controller-cleanup",
    "trouble-reports-from-imps-5-6-7-62",
    "throughput-reports-from-imps-5-6-7-62",
    "mapped-direct-line-observed-up",
)

_APPLICATION_REQUIRED = {
    "connection_open": "1",
    "its_greeting": "1",
    "remote_time": "structured",
    "imp6_post_probe_traffic": "1",
    "imp62_post_probe_traffic": "1",
    "correlated_inter_imp_traffic": "both-directions",
    "message_journey_observations": "10",
    "message_journey_state": "missing-boundary",
    "message_journey_first_boundary": "boundary:request:6",
}

_MANIFEST_REQUIRED = frozenset(
    {
        "application.client",
        "application.remote_time",
        "application.server",
        "application.service_user",
        "cleanup.outer-runtime",
        "exit_status",
        "finished_utc",
        "format",
        "message-journey.first-boundary",
        "message-journey.observations",
        "message-journey.state",
        "outcome",
        "path.message-journey",
        "path.shared-topology",
        "path.verdict",
        "process.controller.exit-status",
        "process.receiver.exit-status",
        "repository.revision",
        "repository.tracked_dirty",
        "sha256.message-journey",
        "sha256.shared-topology",
        "sha256.verdict",
        "source.arpanet-in-a-box.tracked_dirty",
        "source.h316-simh.tracked_dirty",
        "source.imp11a-simh.tracked_dirty",
        "source.ka10-simh.tracked_dirty",
        "source.network-unix-v6.tracked_dirty",
        "started_utc",
        "topology",
    }
)


class CoexistenceDisplayError(ValueError):
    """Raised when structured result artifacts cannot support the desk."""


@dataclass(frozen=True)
class CoexistenceDisplaySnapshot:
    """One deterministic JSON-safe projection of a completed composition."""

    _serialized: str

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh copy of the in-memory display document."""

        return json.loads(self._serialized)

    def to_json(self) -> str:
        """Return deterministic compact JSON suitable for the local API."""

        return self._serialized


class CoexistenceDisplay:
    """Validate one immutable result and retain its in-memory desk snapshot."""

    def __init__(
        self,
        results_dir: str | Path,
        shared_topology_path: str | Path,
    ) -> None:
        self.results_dir = Path(results_dir)
        self.shared_topology_path = Path(shared_topology_path)
        self._snapshot = _build_snapshot(
            self.results_dir,
            self.shared_topology_path,
        )

    def snapshot(self) -> CoexistenceDisplaySnapshot:
        """Return the already validated, deterministic completed snapshot."""

        return self._snapshot


def _build_snapshot(
    results_dir: Path,
    topology_path: Path,
) -> CoexistenceDisplaySnapshot:
    if not results_dir.is_dir():
        raise CoexistenceDisplayError(
            f"coexistence result directory does not exist: {results_dir}"
        )

    paths = {
        "application": results_dir / "application-evidence.txt",
        "cleanup": results_dir / "cleanup-evidence.txt",
        "events": results_dir / "historical-events.jsonl",
        "journey": results_dir / "message-journey.jsonl",
        "manifest": results_dir / "runtime" / "run.env",
        "outcome": results_dir / "outcome.txt",
        "verdict": results_dir / "verdict.json",
    }
    for description, path in paths.items():
        if not path.is_file():
            raise CoexistenceDisplayError(
                f"coexistence result has no {description} artifact: {path}"
            )

    try:
        topology = load_shared_topology(topology_path)
        historical_topology = historical_line_topology_from_shared(topology)
    except (SharedTopologyValidationError, ReconciliationError) as error:
        raise CoexistenceDisplayError(str(error)) from error
    topology_document = _load_json(topology_path, "shared topology")
    _validate_topology(topology, historical_topology)

    manifest = _load_record(paths["manifest"], "run manifest")
    application = _load_record(paths["application"], "application evidence")
    cleanup = _load_record(paths["cleanup"], "application cleanup evidence")
    outcome = _load_outcome(paths["outcome"])
    verdict = _validate_verdict(_load_json(paths["verdict"], "composition verdict"))
    started, finished = _validate_manifest(
        manifest,
        results_dir=results_dir,
        topology_path=topology_path,
        journey_path=paths["journey"],
        verdict_path=paths["verdict"],
        outcome=outcome,
    )
    _validate_application(application, cleanup, manifest, outcome)

    try:
        historical_stream = _read_stable_historical_stream(paths["events"])
        journey_stream = _read_stable_journey_stream(paths["journey"])
        journey_snapshot = JourneyDisplayObserver(paths["journey"]).snapshot().to_dict()
    except (
        HistoricalEventStreamError,
        JourneyDisplayError,
        MessageJourneyStreamError,
        OSError,
    ) as error:
        raise CoexistenceDisplayError(str(error)) from error

    run_id = results_dir.name
    _validate_historical_stream(
        historical_stream,
        topology,
        verdict,
        run_id=run_id,
        finished=finished,
    )
    _validate_journey(
        journey_stream,
        journey_snapshot,
        topology_document,
        application,
        manifest,
        run_id=run_id,
        started=started,
    )

    historical_document = historical_stream.to_dict()
    events = historical_stream.events
    support_sequences = tuple(verdict["direct_line"]["supporting_sequences"])
    support_end = max(support_sequences)
    accepted = reconcile(
        historical_topology.nominal,
        events[:support_end],
        started_at=str(historical_document["header"]["run"]["started_at"]),
        observed_at=events[support_end - 1].observed_at,
        report_interval=REPORT_INTERVAL,
    )
    final = reconcile(
        historical_topology.nominal,
        events,
        started_at=str(historical_document["header"]["run"]["started_at"]),
        observed_at=_timestamp_text(finished),
        report_interval=REPORT_INTERVAL,
    )
    accepted_line = _line_result(accepted, DIRECT_LINE_ID)
    final_line = _line_result(final, DIRECT_LINE_ID)
    events_by_sequence = {event.sequence: event for event in events}
    support_events = [events_by_sequence[sequence] for sequence in support_sequences]
    mapped_subjects = set(historical_topology.endpoint_subject_ids)
    tail_direct_events = [
        event
        for event in events
        if event.sequence > support_end
        and event.event_type == "line-endpoint.state"
        and event.subject in mapped_subjects
    ]
    report_counts = _report_counts(events)

    configured_links = list(topology.topology["links"])
    mapped_link_ids = set(historical_topology.line_link_ids.values())
    topology_projection = {
        "id": topology.id,
        "authority": "configured shared topology",
        "components": _copy(topology.topology["components"]),
        "links": [
            {
                **_copy(link),
                "configured_only": str(link["id"]) not in mapped_link_ids,
                "report_mapping": (
                    DIRECT_LINE_ID if str(link["id"]) == DIRECT_LINK_ID else None
                ),
                "authority": "configured shared topology",
            }
            for link in configured_links
        ],
        "routes": [
            {**_copy(route), "authority": "configured shared topology"}
            for route in topology.topology["routes"]
        ],
        "configured_only_link_ids": [
            str(link["id"])
            for link in configured_links
            if str(link["id"]) not in mapped_link_ids
        ],
    }

    evidence_tape = [
        {
            **_historical_event_record(event),
            "phase": (
                "accepted-support"
                if event.sequence in support_sequences
                else "post-support-receiver-tail"
            ),
        }
        for event in sorted(
            (*support_events, *tail_direct_events),
            key=lambda item: item.sequence,
        )
    ]
    phase_markers = _phase_markers(
        events,
        support_events,
        tail_direct_events,
    )

    document = {
        "snapshot_version": COEXISTENCE_DISPLAY_SNAPSHOT_VERSION,
        "mode": "completed",
        "run": {
            "id": run_id,
            "topology_id": topology.id,
            "started_at": _timestamp_text(started),
            "finished_at": _timestamp_text(finished),
            "outcome": outcome,
            "repository_revision": manifest["repository.revision"],
            "authority": "validated run manifest",
        },
        "composition": {
            "state": "passed",
            "authority": "composition verdict",
            "kind": verdict["kind"],
            "version": verdict["version"],
            "checks": [
                {"id": identifier, "passed": verdict["checks"][identifier]}
                for identifier in _CHECK_IDS
            ],
        },
        "application": {
            "gate_id": "gate:4h-network-unix-pdp11-to-its",
            "state": "passed",
            "authority": "application evidence and run outcome",
            "composition_check": "application-passed",
            "facts": [
                {
                    "label": "TELNET connection",
                    "value": "open",
                    "evidence_key": "connection_open",
                },
                {
                    "label": "ITS service job",
                    "value": application["its_service_user"],
                    "evidence_key": "its_service_user",
                },
                {
                    "label": "Remote greeting",
                    "value": "received",
                    "evidence_key": "its_greeting",
                },
                {
                    "label": "Remote :TIME",
                    "value": application["remote_time"],
                    "evidence_key": "remote_time",
                },
                {
                    "label": "Inter-IMP correlation",
                    "value": application["correlated_inter_imp_traffic"],
                    "evidence_key": "correlated_inter_imp_traffic",
                },
            ],
            "route_id": APPLICATION_ROUTE_ID,
            "note": (
                "Application success does not fill either missing destination-host "
                "ingress boundary in the typed journey."
            ),
        },
        "journey": journey_snapshot,
        "topology": topology_projection,
        "historical": {
            "authority": "direct historical-network observation",
            "stream_schema_version": historical_document["header"]["schema_version"],
            "complete_event_count": len(events),
            "accepted_line": {
                "id": accepted_line.id,
                "normalized_link_id": DIRECT_LINK_ID,
                "state": accepted_line.state.value,
                "supporting_sequences": list(accepted_line.supporting_sequences),
                "supporting_observation_ids": [
                    _event_id(sequence)
                    for sequence in accepted_line.supporting_sequences
                ],
                "supporting_events": [
                    _historical_event_record(event) for event in support_events
                ],
                "authority": "composition verdict",
                "reducer_authority": "in-memory reconciliation",
            },
            "post_support_tail": {
                "after_sequence": support_end,
                "complete_event_count": len(events) - support_end,
                "mapped_direct_events": [
                    _historical_event_record(event) for event in tail_direct_events
                ],
                "authority": "later direct historical-network observation",
            },
            "final_at_run_finish": {
                "observed_at": _timestamp_text(finished),
                "line": {
                    "id": final_line.id,
                    "normalized_link_id": DIRECT_LINK_ID,
                    "state": final_line.state.value,
                    "supporting_sequences": list(final_line.supporting_sequences),
                    "authority": "in-memory reconciliation",
                },
                "endpoints": _endpoint_records(final, events_by_sequence),
                "meaning": (
                    "Run-finish reduction of the receiver tail; it is not the "
                    "accepted application or composition verdict."
                ),
            },
            "report_counts_by_source_imp": {
                report_kind: {
                    str(imp): report_counts[report_kind][str(imp)]
                    for imp in EXPECTED_IMPS
                }
                for report_kind in ("trouble", "throughput")
            },
            "evidence_tape": evidence_tape,
        },
        "phases": {
            "axis": "historical event sequence",
            "first_sequence": events[0].sequence,
            "last_sequence": events[-1].sequence,
            "markers": phase_markers,
            "accepted_support_sequences": list(support_sequences),
            "post_support_starts_after": support_end,
            "controller_exit_sequence": None,
            "controller_exit_sequence_authority": "not persisted",
            "note": (
                "The supported harness waits for the application controller before "
                "the outer receiver completes, but it persists no controller-exit "
                "historical-event sequence. The exact display boundary is therefore "
                "accepted support versus post-support receiver tail."
            ),
        },
        "lifecycle": {
            "authority": "run manifest and cleanup evidence",
            "application_controller_exit_status": int(
                manifest["process.controller.exit-status"]
            ),
            "receiver_exit_status": int(manifest["process.receiver.exit-status"]),
            "application_surviving_owned_processes": int(
                cleanup["surviving_owned_processes"]
            ),
            "outer_runtime_cleanup": manifest["cleanup.outer-runtime"],
        },
        "artifact_validation": {
            "status": "validated",
            "authority": "in-memory structured-artifact adapter",
            "artifacts": [
                {
                    "name": topology_path.name,
                    "kind": "configured topology",
                    "sha256": manifest["sha256.shared-topology"],
                    "binding": "manifest digest and exact path",
                },
                {
                    "name": paths["journey"].name,
                    "kind": "typed journey",
                    "sha256": manifest["sha256.message-journey"],
                    "binding": "manifest digest, run identity, and topology",
                },
                {
                    "name": paths["verdict"].name,
                    "kind": "composition verdict",
                    "sha256": manifest["sha256.verdict"],
                    "binding": "manifest digest and exact path",
                },
                {
                    "name": paths["events"].name,
                    "kind": "historical event stream",
                    "sha256": None,
                    "binding": (
                        "validated complete stream, run identity, interface, topology, "
                        "report counts, and verdict support; no manifest digest exists"
                    ),
                },
                {
                    "name": paths["application"].name,
                    "kind": "application evidence",
                    "sha256": None,
                    "binding": "required Gate 4H facts and composition verdict check",
                },
                {
                    "name": paths["cleanup"].name,
                    "kind": "cleanup evidence",
                    "sha256": None,
                    "binding": "zero surviving owned processes and verdict check",
                },
            ],
        },
        "authority_legend": [
            {
                "id": "configured",
                "label": "configured shared topology",
                "meaning": "expected components, bindings, links, and routes only",
            },
            {
                "id": "direct",
                "label": "direct historical-network observation",
                "meaning": "validated Type 303 or Type 302 derived event",
            },
            {
                "id": "reducer",
                "label": "in-memory reconciliation",
                "meaning": "freshness and reciprocal endpoint conclusion",
            },
            {
                "id": "application",
                "label": "application evidence",
                "meaning": "Gate 4H guest and correlated IMP result",
            },
            {
                "id": "verdict",
                "label": "composition verdict",
                "meaning": "accepted coexistence checks and exact support pair",
            },
            {
                "id": "journey",
                "label": "typed message journey",
                "meaning": "direct and harness-derived boundary observations",
            },
        ],
        "passive_boundary": (
            "GET/HEAD presentation only; no simulator, controller, guest, result "
            "mutation, raw-log, arbitrary-file, or external-network authority."
        ),
    }
    serialized = json.dumps(
        document,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"
    return CoexistenceDisplaySnapshot(serialized)


def _validate_topology(
    topology: SharedTopology,
    historical: HistoricalLineTopology,
) -> None:
    if topology.id != TOPOLOGY_ID:
        raise CoexistenceDisplayError(
            f"unsupported coexistence topology identity {topology.id!r}"
        )
    if len(historical.nominal.lines) != 1:
        raise CoexistenceDisplayError(
            "coexistence topology must retain exactly one mapped report line"
        )
    line = historical.nominal.lines[0]
    if line.id != DIRECT_LINE_ID:
        raise CoexistenceDisplayError(
            "coexistence topology does not retain the accepted direct-line mapping"
        )
    if historical.line_link_ids.get(DIRECT_LINE_ID) != DIRECT_LINK_ID:
        raise CoexistenceDisplayError(
            "accepted direct report line does not map to the expected normalized link"
        )
    route_ids = {str(route["id"]) for route in topology.topology["routes"]}
    if APPLICATION_ROUTE_ID not in route_ids:
        raise CoexistenceDisplayError(
            "coexistence topology has no accepted application route"
        )


def _validate_manifest(
    manifest: Mapping[str, str],
    *,
    results_dir: Path,
    topology_path: Path,
    journey_path: Path,
    verdict_path: Path,
    outcome: str,
) -> tuple[datetime, datetime]:
    missing = sorted(_MANIFEST_REQUIRED - set(manifest))
    if missing:
        raise CoexistenceDisplayError(
            f"run manifest is missing required fields: {', '.join(missing)}"
        )
    if manifest["format"] != "1" or manifest["topology"] != MANIFEST_TOPOLOGY:
        raise CoexistenceDisplayError("run manifest is not an integrated coexistence run")
    if outcome != "passed" or manifest["outcome"] != outcome:
        raise CoexistenceDisplayError("run outcome and manifest do not record a pass")
    if manifest["exit_status"] != "0":
        raise CoexistenceDisplayError("run manifest records a nonzero terminal status")
    for key in ("process.controller.exit-status", "process.receiver.exit-status"):
        if manifest[key] != "0":
            raise CoexistenceDisplayError(
                f"run manifest records an unsuccessful owned process in {key!r}"
            )
    if manifest["cleanup.outer-runtime"] != "passed":
        raise CoexistenceDisplayError("run manifest does not record outer cleanup")
    if manifest["repository.tracked_dirty"] != "0":
        raise CoexistenceDisplayError("run manifest does not identify a clean repository")
    if not _REVISION.fullmatch(manifest["repository.revision"]):
        raise CoexistenceDisplayError("run manifest repository revision is invalid")
    for key, value in manifest.items():
        if key.startswith("source.") and key.endswith(".tracked_dirty") and value != "0":
            raise CoexistenceDisplayError(
                f"run manifest does not identify a clean source in {key!r}"
            )
        if key.startswith("source.") and key.endswith(".revision"):
            if not _REVISION.fullmatch(value):
                raise CoexistenceDisplayError(f"run manifest has an invalid {key}")

    bindings = (
        ("shared-topology", topology_path),
        ("message-journey", journey_path),
        ("verdict", verdict_path),
    )
    for name, path in bindings:
        recorded_path = Path(manifest[f"path.{name}"])
        if recorded_path.resolve() != path.resolve():
            raise CoexistenceDisplayError(
                f"run manifest {name} path does not identify the supplied artifact"
            )
        recorded_digest = manifest[f"sha256.{name}"]
        if not _SHA256.fullmatch(recorded_digest):
            raise CoexistenceDisplayError(
                f"run manifest {name} digest is not a lowercase SHA-256"
            )
        if _sha256_file(path, name) != recorded_digest:
            raise CoexistenceDisplayError(
                f"run manifest {name} digest does not match the supplied artifact"
            )

    started = _timestamp(manifest["started_utc"], "run manifest.started_utc")
    finished = _timestamp(manifest["finished_utc"], "run manifest.finished_utc")
    if finished < started:
        raise CoexistenceDisplayError("run finish precedes its start")
    if results_dir.name == "runtime":
        raise CoexistenceDisplayError("result directory identity is invalid")
    return started, finished


def _validate_application(
    application: Mapping[str, str],
    cleanup: Mapping[str, str],
    manifest: Mapping[str, str],
    outcome: str,
) -> None:
    for key, expected in _APPLICATION_REQUIRED.items():
        if application.get(key) != expected:
            raise CoexistenceDisplayError(
                f"application evidence {key!r} does not equal {expected!r}"
            )
    service_user = application.get("its_service_user")
    if service_user is None or not _SERVICE_USER.fullmatch(service_user):
        raise CoexistenceDisplayError("application evidence has no valid ITS TLNT job")
    if cleanup.get("surviving_owned_processes") != "0":
        raise CoexistenceDisplayError(
            "application cleanup evidence records a surviving owned process"
        )
    if outcome != "passed":
        raise CoexistenceDisplayError("application outcome is not passed")
    manifest_expected = {
        "application.client": "network-unix-telnet",
        "application.server": "TELSER",
        "application.service_user": service_user,
        "application.remote_time": application["remote_time"],
        "message-journey.observations": application["message_journey_observations"],
        "message-journey.state": application["message_journey_state"],
        "message-journey.first-boundary": application[
            "message_journey_first_boundary"
        ],
    }
    for key, expected in manifest_expected.items():
        if manifest.get(key) != expected:
            raise CoexistenceDisplayError(
                f"run manifest {key!r} disagrees with application evidence"
            )


def _validate_verdict(document: object) -> dict[str, Any]:
    verdict = _mapping(document, "composition verdict")
    _fields(
        verdict,
        "composition verdict",
        {
            "checks",
            "direct_line",
            "kind",
            "passed",
            "report_counts_by_source_imp",
            "version",
        },
    )
    if verdict["version"] != 1 or isinstance(verdict["version"], bool):
        raise CoexistenceDisplayError("composition verdict version is unsupported")
    if verdict["kind"] != VERDICT_KIND or verdict["passed"] is not True:
        raise CoexistenceDisplayError("composition verdict is not a passing coexistence verdict")
    checks = _mapping(verdict["checks"], "composition verdict checks")
    if set(checks) != set(_CHECK_IDS):
        raise CoexistenceDisplayError("composition verdict has an unexpected check set")
    if any(checks[identifier] is not True for identifier in _CHECK_IDS):
        raise CoexistenceDisplayError("composition verdict contains a failed check")

    direct = _mapping(verdict["direct_line"], "composition verdict direct line")
    _fields(
        direct,
        "composition verdict direct line",
        {"id", "observed_state", "supporting_sequences"},
    )
    if direct["id"] != DIRECT_LINE_ID or direct["observed_state"] != "up":
        raise CoexistenceDisplayError(
            "composition verdict does not accept the mapped direct line as up"
        )
    sequences = _positive_integers(
        direct["supporting_sequences"],
        "composition verdict supporting sequences",
    )
    if len(sequences) != 2 or tuple(sorted(sequences)) != sequences:
        raise CoexistenceDisplayError(
            "composition verdict must retain one ordered reciprocal support pair"
        )

    counts = _mapping(
        verdict["report_counts_by_source_imp"],
        "composition verdict report counts",
    )
    if set(counts) != {"trouble", "throughput"}:
        raise CoexistenceDisplayError("composition verdict has invalid report count classes")
    for report_kind in ("trouble", "throughput"):
        by_imp = _mapping(counts[report_kind], f"composition verdict {report_kind} counts")
        if set(by_imp) != {str(imp) for imp in EXPECTED_IMPS}:
            raise CoexistenceDisplayError(
                f"composition verdict {report_kind} counts have unexpected IMP identities"
            )
        for imp, count in by_imp.items():
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise CoexistenceDisplayError(
                    f"composition verdict {report_kind} count for IMP {imp} is invalid"
                )
    return _copy(verdict)


def _validate_historical_stream(
    stream: HistoricalEventStream,
    topology: SharedTopology,
    verdict: Mapping[str, Any],
    *,
    run_id: str,
    finished: datetime,
) -> None:
    document = stream.to_dict()
    header = _mapping(document["header"], "historical event header")
    run = _mapping(header["run"], "historical event run")
    if stream.has_incomplete_final_record:
        raise CoexistenceDisplayError(
            "completed coexistence desk refuses an incomplete historical-event tail"
        )
    if header["schema_version"] != 2:
        raise CoexistenceDisplayError(
            "coexistence historical stream must retain Type 302 events in schema version 2"
        )
    if run["id"] != run_id:
        raise CoexistenceDisplayError(
            "historical event stream run identity does not match the result directory"
        )
    if run["topology_id"] != topology.id or header["topology"] != topology.topology:
        raise CoexistenceDisplayError(
            "historical event stream topology does not match the supplied topology"
        )
    if run["interface_id"] != NCC_INTERFACE_ID:
        raise CoexistenceDisplayError(
            "historical event stream does not use the supported NCC host interface"
        )
    if not stream.events:
        raise CoexistenceDisplayError("historical event stream is empty")
    if _timestamp(stream.events[-1].observed_at, "last historical event") > finished:
        raise CoexistenceDisplayError("historical event stream extends past run finish")

    actual_counts = _report_counts(stream.events)
    expected_counts = _mapping(
        verdict["report_counts_by_source_imp"],
        "composition verdict report counts",
    )
    if actual_counts != expected_counts:
        raise CoexistenceDisplayError(
            "historical event report counts disagree with the composition verdict"
        )

    historical_topology = historical_line_topology_from_shared(topology)
    latest_up: ReconciledLine | None = None
    started_at = str(run["started_at"])
    for index, event in enumerate(stream.events, start=1):
        result = reconcile(
            historical_topology.nominal,
            stream.events[:index],
            started_at=started_at,
            observed_at=event.observed_at,
            report_interval=REPORT_INTERVAL,
        )
        line = _line_result(result, DIRECT_LINE_ID)
        if line.state == LineState.UP:
            latest_up = line
    verdict_support = tuple(verdict["direct_line"]["supporting_sequences"])
    if latest_up is None or latest_up.supporting_sequences != verdict_support:
        raise CoexistenceDisplayError(
            "composition verdict support is not the stream's latest observed up pair"
        )
    events_by_sequence = {event.sequence: event for event in stream.events}
    endpoint_subjects = set(historical_topology.endpoint_subject_ids)
    for sequence in verdict_support:
        event = events_by_sequence.get(sequence)
        if (
            event is None
            or event.event_type != "line-endpoint.state"
            or event.subject not in endpoint_subjects
            or event.state != "up"
        ):
            raise CoexistenceDisplayError(
                "composition verdict support does not identify reciprocal direct up events"
            )
    if {events_by_sequence[sequence].subject for sequence in verdict_support} != endpoint_subjects:
        raise CoexistenceDisplayError(
            "composition verdict support does not cover both mapped endpoints"
        )


def _validate_journey(
    stream: MessageJourneyStream,
    snapshot: Mapping[str, Any],
    topology_document: Mapping[str, Any],
    application: Mapping[str, str],
    manifest: Mapping[str, str],
    *,
    run_id: str,
    started: datetime,
) -> None:
    document = stream.to_dict()
    header = _mapping(document["header"], "message-journey header")
    run = _mapping(header["run"], "message-journey run")
    if stream.has_incomplete_final_record or not stream.is_terminal:
        raise CoexistenceDisplayError(
            "completed coexistence desk requires a complete terminal journey stream"
        )
    if run["id"] != run_id or run["started_at"] != _timestamp_text(started):
        raise CoexistenceDisplayError(
            "message-journey run identity or start does not match the formal result"
        )
    if header["shared_topology"] != topology_document:
        raise CoexistenceDisplayError(
            "message-journey topology snapshot does not match the supplied topology"
        )
    if stream.expected.id != JOURNEY_ID or stream.expected.route_id != APPLICATION_ROUTE_ID:
        raise CoexistenceDisplayError(
            "message journey does not describe the accepted application route"
        )
    diagnosis = stream.diagnosis
    if (
        len(stream.observations) != 10
        or diagnosis.state.value != "missing-boundary"
        or diagnosis.first_boundary_id != "boundary:request:6"
    ):
        raise CoexistenceDisplayError(
            "message journey does not retain the accepted ten-observation boundary stop"
        )
    if (
        application["message_journey_observations"] != str(len(stream.observations))
        or application["message_journey_state"] != diagnosis.state.value
        or application["message_journey_first_boundary"] != diagnosis.first_boundary_id
    ):
        raise CoexistenceDisplayError(
            "application evidence disagrees with the typed journey reducer"
        )
    if (
        manifest["message-journey.observations"] != str(len(stream.observations))
        or manifest["message-journey.state"] != diagnosis.state.value
        or manifest["message-journey.first-boundary"] != diagnosis.first_boundary_id
    ):
        raise CoexistenceDisplayError(
            "run manifest disagrees with the typed journey reducer"
        )
    assessment = _mapping(snapshot["assessment"], "journey display assessment")
    stream_status = _mapping(snapshot["stream"], "journey display stream")
    if (
        snapshot["mode"] != "terminal"
        or stream_status["incomplete_final_record"] is not False
        or assessment["state"] != diagnosis.state.value
        or assessment["first_boundary_id"] != diagnosis.first_boundary_id
    ):
        raise CoexistenceDisplayError(
            "journey display projection disagrees with its validated stream"
        )


def _report_counts(events: Sequence[NccEvent]) -> dict[str, dict[str, int]]:
    trouble = Counter(
        str(event.source.imp) for event in events if event.event_type == "imp.report"
    )
    throughput = Counter(
        str(event.source.imp)
        for event in events
        if event.event_type == "imp.throughput-report"
    )
    return {
        "trouble": {str(imp): trouble[str(imp)] for imp in EXPECTED_IMPS},
        "throughput": {str(imp): throughput[str(imp)] for imp in EXPECTED_IMPS},
    }


def _endpoint_records(
    result: Reconciliation,
    events_by_sequence: Mapping[int, NccEvent],
) -> list[dict[str, Any]]:
    records = []
    for endpoint in result.endpoints:
        sequence = (
            endpoint.supporting_sequences[0]
            if endpoint.supporting_sequences
            else None
        )
        event = events_by_sequence.get(sequence) if sequence is not None else None
        if endpoint.observed_at is None:
            state_authority = "in-memory absence classification"
        elif endpoint.state == LineState.STALE:
            state_authority = "in-memory report-freshness classification"
        elif endpoint.state == LineState.CONTRADICTORY:
            state_authority = "in-memory topology comparison"
        else:
            state_authority = "direct historical-network observation"
        records.append(
            {
                "subject": endpoint.endpoint.subject,
                "component_id": f"imp:{endpoint.endpoint.imp}",
                "interface_number": endpoint.endpoint.interface,
                "direction": endpoint.direction,
                "state": endpoint.state.value,
                "last_known_state": endpoint.last_known_state,
                "observed_at": endpoint.observed_at,
                "topology_match": endpoint.topology_match,
                "supporting_sequence": sequence,
                "supporting_observation_id": (
                    _event_id(sequence) if sequence is not None else None
                ),
                "source_imp": event.source.imp if event is not None else None,
                "state_authority": state_authority,
            }
        )
    return records


def _phase_markers(
    events: Sequence[NccEvent],
    support_events: Sequence[NccEvent],
    tail_direct_events: Sequence[NccEvent],
) -> list[dict[str, Any]]:
    markers = [
        {
            "id": "receiver-stream-begins",
            "sequence": events[0].sequence,
            "observed_at": events[0].observed_at,
            "label": "receiver stream begins",
            "kind": "stream",
            "authority": "direct historical-network observation",
        }
    ]
    for index, event in enumerate(support_events, start=1):
        markers.append(
            {
                "id": f"accepted-support-{index}",
                "sequence": event.sequence,
                "observed_at": event.observed_at,
                "label": f"accepted support {index} · {event.subject}",
                "kind": "accepted-support",
                "authority": "composition verdict",
            }
        )
    if tail_direct_events:
        first = tail_direct_events[0]
        markers.append(
            {
                "id": "later-direct-begins",
                "sequence": first.sequence,
                "observed_at": first.observed_at,
                "label": f"later direct {first.state} · {first.subject}",
                "kind": "receiver-tail",
                "authority": "direct historical-network observation",
            }
        )
        last = tail_direct_events[-1]
        if last.sequence != first.sequence:
            markers.append(
                {
                    "id": "later-direct-latest",
                    "sequence": last.sequence,
                    "observed_at": last.observed_at,
                    "label": f"latest direct {last.state} · {last.subject}",
                    "kind": "receiver-tail",
                    "authority": "direct historical-network observation",
                }
            )
    if events[-1].sequence not in {marker["sequence"] for marker in markers}:
        markers.append(
            {
                "id": "receiver-stream-ends",
                "sequence": events[-1].sequence,
                "observed_at": events[-1].observed_at,
                "label": "receiver stream ends",
                "kind": "stream",
                "authority": "direct historical-network observation",
            }
        )
    return sorted(markers, key=lambda marker: int(marker["sequence"]))


def _historical_event_record(event: NccEvent) -> dict[str, Any]:
    details = dict(event.details)
    return {
        "id": _event_id(event.sequence),
        "sequence": event.sequence,
        "observed_at": event.observed_at,
        "type": event.event_type,
        "subject": event.subject,
        "state": event.state,
        "source": {"kind": event.source.kind, "imp": event.source.imp},
        "details": {
            key: details.get(key)
            for key in (
                "neighbor_imp",
                "routing_messages_sent",
                "routing_messages_missed",
            )
            if key in details
        },
        "authority": "direct historical-network observation",
    }


def _line_result(result: Reconciliation, identifier: str) -> ReconciledLine:
    for line in result.lines:
        if line.id == identifier:
            return line
    raise CoexistenceDisplayError(f"missing reconciled line {identifier!r}")


def _read_stable_historical_stream(path: Path) -> HistoricalEventStream:
    for _ in range(2):
        before = path.stat()
        stream = read_historical_event_stream(path)
        after = path.stat()
        if _stat_revision(before) == _stat_revision(after):
            return stream
    raise CoexistenceDisplayError(
        "historical event stream was repeatedly modified while being read"
    )


def _read_stable_journey_stream(path: Path) -> MessageJourneyStream:
    for _ in range(2):
        before = path.stat()
        stream = read_message_journey_stream(path)
        after = path.stat()
        if _stat_revision(before) == _stat_revision(after):
            return stream
    raise CoexistenceDisplayError(
        "message-journey stream was repeatedly modified while being read"
    )


def _stat_revision(value: Any) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _load_record(path: Path, description: str) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise CoexistenceDisplayError(
            f"could not read {description} {path}: {error}"
        ) from error
    record: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        key, separator, value = line.partition("=")
        if not separator or not key or not value or key in record:
            raise CoexistenceDisplayError(
                f"{description} line {line_number} has an invalid or duplicate key"
            )
        record[key] = value
    if not record:
        raise CoexistenceDisplayError(f"{description} is empty")
    return record


def _load_outcome(path: Path) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as error:
        raise CoexistenceDisplayError(f"could not read run outcome {path}: {error}") from error
    if value not in {"passed", "failed"}:
        raise CoexistenceDisplayError("run outcome artifact is invalid")
    return value


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CoexistenceDisplayError(
            f"could not read {description} {path}: {error}"
        ) from error
    return _copy(_mapping(document, description))


def _sha256_file(path: Path, description: str) -> str:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise CoexistenceDisplayError(
            f"could not hash {description} {path}: {error}"
        ) from error
    return digest


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CoexistenceDisplayError(f"{location} must be an object")
    return value


def _fields(value: Mapping[str, Any], location: str, required: set[str]) -> None:
    if set(value) != required:
        raise CoexistenceDisplayError(f"{location} has invalid fields")


def _positive_integers(value: object, location: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise CoexistenceDisplayError(f"{location} must be an array")
    values = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise CoexistenceDisplayError(f"{location} must contain positive integers")
        values.append(item)
    if len(set(values)) != len(values):
        raise CoexistenceDisplayError(f"{location} must not contain duplicates")
    return tuple(values)


def _timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CoexistenceDisplayError(f"{location} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CoexistenceDisplayError(f"{location} is not a valid timestamp") from error
    if parsed.tzinfo is None:
        raise CoexistenceDisplayError(f"{location} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _event_id(sequence: int) -> str:
    return f"observation:historical:{sequence}"


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(item) for item in value]
    return value
