"""Completed passive projection for the accepted application failover result.

The adapter binds only project-authored structured artifacts from one formal
result directory. It does not parse simulator logs, promote discovered report
line numbers, mutate retained evidence, or control any process.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .events import NccEvent
from .historical_events import (
    HistoricalEventStream,
    HistoricalEventStreamError,
    read_historical_event_stream,
)
from .journey_display import JourneyDisplayError, JourneyDisplayObserver
from .message_journey_stream import (
    MessageJourneyStream,
    MessageJourneyStreamError,
    read_message_journey_stream,
)
from .shared_topology import (
    SharedTopology,
    SharedTopologyValidationError,
    load_shared_topology,
)

FAILOVER_DISPLAY_SNAPSHOT_VERSION = 1

TOPOLOGY_ID = "topology:ncc-pdp11-its-application-failover"
MANIFEST_TOPOLOGY = "ncc-pdp11-its-application-failover"
VERDICT_KIND = "ncc-pdp11-its-application-failover-verdict"
NCC_INTERFACE_ID = "binding:ncc-host0-imp5"
JOURNEY_ID = "journey:network-unix-telnet-post-cut"
ALTERNATE_ROUTE_ID = "route:host176-to-host106-alternate"
DIRECT_LINK_ID = "link:imp62-imp6-application-direct"
ALTERNATE_LINK_IDS = (
    "link:imp62-imp7-application-alternate",
    "link:imp7-imp6-application-alternate",
)
EXPECTED_IMPS = (5, 6, 7, 62)

_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SERVICE_USER = re.compile(r"[0-9]+TLNT\Z")

_CHECK_IDS = (
    "identity-chain",
    "relay-forwarded-before-cut",
    "relay-dropped-after-cut",
    "relay-no-unexpected-source",
    "same-session-post-cut-time",
    "network-unix-host-ready-before-open",
    "typed-alternate-journey",
    "ncc-reports-after-cut-from-all-imps",
    "mapping-remains-candidate-only",
    "clean-owned-processes",
    "clean-pinned-inputs",
    "application-outcome-passed",
    "outer-runtime-cleanup",
)

_APPLICATION_REQUIRED = {
    "connection_open": "1",
    "pre_cut_remote_time": "structured",
    "cut_acknowledged": "1",
    "session_survived_cut": "1",
    "post_cut_remote_time": "structured",
    "message_journey_observations": "14",
    "message_journey_state": "missing-boundary",
    "message_journey_first_boundary": "boundary:request:8",
}

_MANIFEST_REQUIRED = frozenset(
    {
        "application.client",
        "application.cut-requested",
        "application.fault-started-at",
        "application.network-unix-host106-ready",
        "application.server",
        "application.service_user",
        "application.session-survived-cut",
        "cleanup.outer-runtime",
        "exit_status",
        "finished_utc",
        "format",
        "message-journey.first-boundary",
        "message-journey.observations",
        "message-journey.state",
        "outcome",
        "path.message-journey",
        "path.pre-cut-message-journey",
        "path.shared-topology",
        "path.verdict",
        "process.application-relay.exit-status",
        "process.controller.exit-status",
        "process.receiver.exit-status",
        "repository.revision",
        "repository.tracked_dirty",
        "sha256.message-journey",
        "sha256.pre-cut-message-journey",
        "sha256.shared-topology",
        "sha256.verdict",
        "source.arpanet-in-a-box.tracked_dirty",
        "source.h316-simh.tracked_dirty",
        "source.imp11a-simh.tracked_dirty",
        "source.ka10-simh.tracked_dirty",
        "source.network-unix-v6.tracked_dirty",
        "started_utc",
        "topology",
        "udp.count",
    }
)


class FailoverDisplayError(ValueError):
    """Raised when structured artifacts cannot prove the failover board."""


@dataclass(frozen=True)
class FailoverDisplaySnapshot:
    """One deterministic JSON-safe projection of a completed failover."""

    _serialized: str

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh copy of the in-memory display document."""

        return json.loads(self._serialized)

    def to_json(self) -> str:
        """Return deterministic compact JSON for the loopback board API."""

        return self._serialized


class FailoverDisplay:
    """Validate one immutable result and retain its in-memory board snapshot."""

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

    def snapshot(self) -> FailoverDisplaySnapshot:
        """Return the already validated deterministic completed snapshot."""

        return self._snapshot


def _build_snapshot(results_dir: Path, topology_path: Path) -> FailoverDisplaySnapshot:
    if not results_dir.is_dir():
        raise FailoverDisplayError(
            f"application failover result directory does not exist: {results_dir}"
        )
    paths = {
        "application": results_dir / "application-evidence.txt",
        "cleanup": results_dir / "cleanup-evidence.txt",
        "cut": results_dir / "application-link-cut-state.json",
        "events": results_dir / "historical-events.jsonl",
        "journey": results_dir / "message-journey.jsonl",
        "manifest": results_dir / "runtime" / "run.env",
        "outcome": results_dir / "outcome.txt",
        "pre_cut_journey": results_dir / "pre-cut-message-journey.jsonl",
        "relay": results_dir / "application-relay.json",
        "verdict": results_dir / "verdict.json",
    }
    for description, path in paths.items():
        if not path.is_file():
            raise FailoverDisplayError(
                f"application failover result has no {description} artifact: {path}"
            )

    try:
        topology = load_shared_topology(topology_path)
    except SharedTopologyValidationError as error:
        raise FailoverDisplayError(str(error)) from error
    topology_document = _load_json(topology_path, "shared topology")
    _validate_topology(topology)

    manifest = _load_record(paths["manifest"], "run manifest")
    application = _load_record(paths["application"], "application evidence")
    cleanup = _load_record(paths["cleanup"], "cleanup evidence")
    outcome = _load_outcome(paths["outcome"])
    verdict = _validate_verdict(_load_json(paths["verdict"], "failover verdict"))
    relay = _mapping(_load_json(paths["relay"], "application relay"), "application relay")
    cut = _mapping(_load_json(paths["cut"], "application cut state"), "application cut state")
    started, finished = _validate_manifest(
        manifest,
        results_dir=results_dir,
        topology_path=topology_path,
        journey_path=paths["journey"],
        pre_cut_journey_path=paths["pre_cut_journey"],
        verdict_path=paths["verdict"],
        outcome=outcome,
    )
    _validate_application(application, cleanup, manifest, outcome)
    fault_started = _validate_relay_and_cut(
        relay,
        cut,
        manifest,
        verdict,
        started=started,
        finished=finished,
    )

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
        raise FailoverDisplayError(str(error)) from error

    _validate_journey(
        journey_stream,
        journey_snapshot,
        topology,
        manifest,
        verdict,
        run_id=results_dir.name,
    )
    report_counts, evidence_tape = _validate_historical_stream(
        historical_stream,
        topology,
        verdict,
        run_id=results_dir.name,
        fault_started=fault_started,
        finished=finished,
    )
    events = historical_stream.events
    directions = _relay_projection(relay)
    document = {
        "snapshot_version": FAILOVER_DISPLAY_SNAPSHOT_VERSION,
        "mode": "completed",
        "profile": "application-failover",
        "run": {
            "id": results_dir.name,
            "topology_id": topology.id,
            "started_at": _timestamp_text(started),
            "finished_at": _timestamp_text(finished),
            "outcome": outcome,
        },
        "application": {
            "state": "passed",
            "authority": "formal application evidence and passing failover verdict",
            "client": manifest["application.client"],
            "server": manifest["application.server"],
            "service_user": manifest["application.service_user"],
            "facts": [
                {
                    "label": "TELNET connection",
                    "value": "open",
                    "evidence_key": "connection_open",
                },
                {
                    "label": "Pre-cut :TIME",
                    "value": application["pre_cut_remote_time"],
                    "evidence_key": "pre_cut_remote_time",
                },
                {
                    "label": "Cut acknowledgement",
                    "value": "received",
                    "evidence_key": "cut_acknowledged",
                },
                {
                    "label": "Session survived cut",
                    "value": "yes",
                    "evidence_key": "session_survived_cut",
                },
                {
                    "label": "Post-cut :TIME",
                    "value": application["post_cut_remote_time"],
                    "evidence_key": "post_cut_remote_time",
                },
            ],
            "note": (
                "The same terminal-owned TELNET session returned structured ITS "
                "time before and after the acknowledged application-link cut."
            ),
        },
        "journey": journey_snapshot,
        "failover": {
            "state": "passed",
            "fault_started_at": _timestamp_text(fault_started),
            "direct_link": {
                "id": DIRECT_LINK_ID,
                "state": "cut",
                "authority": "two-ended relay cut acknowledgement",
            },
            "alternate_route": {
                "id": ALTERNATE_ROUTE_ID,
                "link_ids": list(ALTERNATE_LINK_IDS),
                "state": "observed",
                "authority": "typed post-cut message journey",
            },
            "phase": [
                {"label": "direct", "state": "forwarded"},
                {"label": "cut", "state": "acknowledged"},
                {"label": "via IMP 7", "state": "observed"},
            ],
            "check_count": len(_CHECK_IDS),
            "post_cut_report_sources": list(EXPECTED_IMPS),
            "relay": {"directions": directions},
            "report_mapping": {
                "status": verdict["discovered_report_mapping"]["status"],
                "promoted_to_topology": False,
                "note": (
                    "Line numbers discovered in this exact run remain candidate-only "
                    "and are not used to draw the route."
                ),
            },
        },
        "historical": {
            "authority": "direct historical-network observation",
            "stream_schema_version": historical_stream.to_dict()["header"][
                "schema_version"
            ],
            "complete_event_count": len(events),
            "last_observed_at": events[-1].observed_at,
            "post_cut_report_sources": list(EXPECTED_IMPS),
            "report_counts_by_source_imp": report_counts,
            "evidence_tape": evidence_tape,
            "note": (
                "NCC reports establish post-cut visibility, not the application "
                "route or a promoted report-line mapping."
            ),
        },
        "lifecycle": {
            "authority": "run manifest and cleanup evidence",
            "application_controller_exit_status": 0,
            "receiver_exit_status": 0,
            "application_relay_exit_status": 0,
            "application_surviving_owned_processes": 0,
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
                    "binding": "manifest digest and topology identity",
                },
                {
                    "name": paths["journey"].name,
                    "kind": "typed post-cut journey",
                    "sha256": manifest["sha256.message-journey"],
                    "binding": "manifest digest, run identity, and topology",
                },
                {
                    "name": paths["verdict"].name,
                    "kind": "failover verdict",
                    "sha256": manifest["sha256.verdict"],
                    "binding": "manifest digest and exact result path",
                },
                {
                    "name": paths["events"].name,
                    "kind": "historical event stream",
                    "sha256": None,
                    "binding": (
                        "complete stream, run identity, topology, and independent "
                        "post-cut report-source verification"
                    ),
                },
                {
                    "name": paths["relay"].name,
                    "kind": "application-link relay result",
                    "sha256": None,
                    "binding": "fault timestamp, cut acknowledgement, and counters",
                },
            ],
        },
        "passive_boundary": (
            "GET/HEAD presentation only; no simulator, controller, guest, result "
            "mutation, raw-log, report-line promotion, arbitrary-file, or external-"
            "network authority."
        ),
    }
    serialized = json.dumps(
        document,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"
    return FailoverDisplaySnapshot(serialized)


def _validate_topology(topology: SharedTopology) -> None:
    if topology.id != TOPOLOGY_ID:
        raise FailoverDisplayError(
            f"unsupported application failover topology identity {topology.id!r}"
        )
    routes = {
        str(route["id"]): tuple(str(item) for item in route["components"])
        for route in topology.topology["routes"]
    }
    expected_route = ("host:176", "imp:62", "imp:7", "imp:6", "host:106")
    if routes.get(ALTERNATE_ROUTE_ID) != expected_route:
        raise FailoverDisplayError("failover topology has no exact alternate route")
    link_ids = {str(link["id"]) for link in topology.topology["links"]}
    if not {DIRECT_LINK_ID, *ALTERNATE_LINK_IDS}.issubset(link_ids):
        raise FailoverDisplayError("failover topology lacks its application links")
    application_bindings = [
        binding
        for binding in topology.modem_interfaces
        if binding.id.endswith("application-direct")
        or binding.id.endswith("application-alternate")
    ]
    if len(application_bindings) != 2 or any(
        binding.first_report_line is not None
        or binding.second_report_line is not None
        for binding in application_bindings
    ):
        raise FailoverDisplayError(
            "application links must remain free of promoted report-line mappings"
        )


def _validate_manifest(
    manifest: Mapping[str, str],
    *,
    results_dir: Path,
    topology_path: Path,
    journey_path: Path,
    pre_cut_journey_path: Path,
    verdict_path: Path,
    outcome: str,
) -> tuple[datetime, datetime]:
    missing = sorted(_MANIFEST_REQUIRED - set(manifest))
    if missing:
        raise FailoverDisplayError(
            f"run manifest is missing required fields: {', '.join(missing)}"
        )
    if manifest["format"] != "1" or manifest["topology"] != MANIFEST_TOPOLOGY:
        raise FailoverDisplayError("run manifest is not an application failover run")
    if outcome != "passed" or manifest["outcome"] != outcome:
        raise FailoverDisplayError("run outcome and manifest do not record a pass")
    if manifest["exit_status"] != "0":
        raise FailoverDisplayError("run manifest records a nonzero terminal status")
    for key in (
        "process.controller.exit-status",
        "process.receiver.exit-status",
        "process.application-relay.exit-status",
    ):
        if manifest[key] != "0":
            raise FailoverDisplayError(
                f"run manifest records an unsuccessful owned process in {key!r}"
            )
    if manifest["cleanup.outer-runtime"] != "passed":
        raise FailoverDisplayError("run manifest does not record outer cleanup")
    if manifest["udp.count"] != "18":
        raise FailoverDisplayError("run manifest does not record the bounded 18 ports")
    if manifest["repository.tracked_dirty"] != "0":
        raise FailoverDisplayError("run manifest does not identify a clean repository")
    if not _REVISION.fullmatch(manifest["repository.revision"]):
        raise FailoverDisplayError("run manifest repository revision is invalid")
    for key, value in manifest.items():
        if key.startswith("source.") and key.endswith(".tracked_dirty") and value != "0":
            raise FailoverDisplayError(
                f"run manifest does not identify a clean source in {key!r}"
            )
        if key.startswith("source.") and key.endswith(".revision"):
            if not _REVISION.fullmatch(value):
                raise FailoverDisplayError(f"run manifest has an invalid {key}")

    bindings = (
        ("message-journey", journey_path, True),
        ("pre-cut-message-journey", pre_cut_journey_path, True),
        ("verdict", verdict_path, True),
        ("shared-topology", topology_path, False),
    )
    for name, path, exact_path in bindings:
        recorded_path = Path(manifest[f"path.{name}"])
        if exact_path and recorded_path.resolve() != path.resolve():
            raise FailoverDisplayError(
                f"run manifest {name} path does not identify the supplied artifact"
            )
        if not exact_path and recorded_path.name != path.name:
            raise FailoverDisplayError(
                f"run manifest {name} path does not identify the topology filename"
            )
        recorded_digest = manifest[f"sha256.{name}"]
        if not _SHA256.fullmatch(recorded_digest):
            raise FailoverDisplayError(
                f"run manifest {name} digest is not a lowercase SHA-256"
            )
        if _sha256_file(path, name) != recorded_digest:
            raise FailoverDisplayError(
                f"run manifest {name} digest does not match the supplied artifact"
            )

    expected = {
        "application.client": "network-unix-telnet",
        "application.server": "TELSER",
        "application.network-unix-host106-ready": "host-host-rrp-consumed",
        "application.cut-requested": "1",
        "application.session-survived-cut": "1",
        "message-journey.observations": "14",
        "message-journey.state": "missing-boundary",
        "message-journey.first-boundary": "boundary:request:8",
    }
    for key, value in expected.items():
        if manifest[key] != value:
            raise FailoverDisplayError(f"run manifest {key!r} is not {value!r}")
    if not _SERVICE_USER.fullmatch(manifest["application.service_user"]):
        raise FailoverDisplayError("run manifest has no valid ITS TLNT service user")

    started = _timestamp(manifest["started_utc"], "run manifest.started_utc")
    finished = _timestamp(manifest["finished_utc"], "run manifest.finished_utc")
    if finished < started:
        raise FailoverDisplayError("run finish precedes its start")
    if results_dir.name == "runtime":
        raise FailoverDisplayError("result directory identity is invalid")
    return started, finished


def _validate_application(
    application: Mapping[str, str],
    cleanup: Mapping[str, str],
    manifest: Mapping[str, str],
    outcome: str,
) -> None:
    for key, expected in _APPLICATION_REQUIRED.items():
        if application.get(key) != expected:
            raise FailoverDisplayError(
                f"application evidence {key!r} does not equal {expected!r}"
            )
    service_user = application.get("its_service_user")
    if service_user is None or not _SERVICE_USER.fullmatch(service_user):
        raise FailoverDisplayError("application evidence has no valid ITS TLNT job")
    if manifest["application.service_user"] != service_user:
        raise FailoverDisplayError("manifest and application service users disagree")
    if cleanup.get("surviving_owned_processes") != "0":
        raise FailoverDisplayError("cleanup evidence records a surviving owned process")
    if outcome != "passed":
        raise FailoverDisplayError("application outcome is not passed")


def _validate_verdict(document: object) -> dict[str, Any]:
    verdict = _mapping(document, "failover verdict")
    _fields(
        verdict,
        "failover verdict",
        {
            "checks",
            "discovered_report_mapping",
            "fault_started_at",
            "journey",
            "kind",
            "passed",
            "post_cut_report_sources",
            "version",
        },
    )
    if verdict["version"] != 1 or isinstance(verdict["version"], bool):
        raise FailoverDisplayError("failover verdict version is unsupported")
    if verdict["kind"] != VERDICT_KIND or verdict["passed"] is not True:
        raise FailoverDisplayError("failover verdict is not a passing formal verdict")
    checks = _mapping(verdict["checks"], "failover verdict checks")
    if set(checks) != set(_CHECK_IDS):
        raise FailoverDisplayError("failover verdict has an unexpected check set")
    if any(checks[identifier] is not True for identifier in _CHECK_IDS):
        raise FailoverDisplayError("failover verdict contains a failed check")
    sources = _integers(verdict["post_cut_report_sources"], "post-cut report sources")
    if tuple(sources) != EXPECTED_IMPS:
        raise FailoverDisplayError("failover verdict has unexpected post-cut IMP sources")
    journey = _mapping(verdict["journey"], "failover verdict journey")
    _fields(
        journey,
        "failover verdict journey",
        {"first_boundary", "journey_id", "observation_count", "route_id", "state"},
    )
    if journey != {
        "journey_id": JOURNEY_ID,
        "route_id": ALTERNATE_ROUTE_ID,
        "observation_count": 14,
        "state": "missing-boundary",
        "first_boundary": "boundary:request:8",
    }:
        raise FailoverDisplayError("failover verdict does not retain the typed alternate journey")
    mapping = _mapping(
        verdict["discovered_report_mapping"],
        "failover verdict discovered report mapping",
    )
    if mapping.get("status") != "candidate-only-one-exact-run":
        raise FailoverDisplayError("failover report mapping is not candidate-only")
    if mapping.get("promoted_to_topology") is not False:
        raise FailoverDisplayError("failover report mapping was promoted to topology")
    for key in ("direct_application_link", "alternate_application_link"):
        _mapping(mapping.get(key), f"failover report mapping {key}")
    _timestamp(verdict["fault_started_at"], "failover verdict fault_started_at")
    return _copy(verdict)


def _validate_relay_and_cut(
    relay: Mapping[str, Any],
    cut: Mapping[str, Any],
    manifest: Mapping[str, str],
    verdict: Mapping[str, Any],
    *,
    started: datetime,
    finished: datetime,
) -> datetime:
    if relay.get("version") != 1 or relay.get("kind") != "two-ended-udp-cut-relay":
        raise FailoverDisplayError("application relay artifact has an unsupported identity")
    if relay.get("cut_mode") != "request-file":
        raise FailoverDisplayError("application relay did not use request-file cut mode")
    if relay.get("unexpected_sources") != []:
        raise FailoverDisplayError("application relay observed an unexpected source")
    if cut != {
        "version": 1,
        "kind": "two-ended-udp-cut-state",
        "state": "cut",
        "fault_started_at": relay.get("fault_started_at"),
    }:
        raise FailoverDisplayError("relay result and atomic cut acknowledgement disagree")
    fault = _timestamp(relay.get("fault_started_at"), "application relay fault_started_at")
    if not (started <= fault <= finished):
        raise FailoverDisplayError("application relay fault falls outside the formal run")
    if (
        manifest["application.fault-started-at"] != relay["fault_started_at"]
        or verdict["fault_started_at"] != relay["fault_started_at"]
    ):
        raise FailoverDisplayError("failover artifacts disagree on the fault timestamp")
    relay_started = _timestamp(relay.get("started_at"), "application relay started_at")
    relay_finished = _timestamp(relay.get("finished_at"), "application relay finished_at")
    if not (started <= relay_started < fault < relay_finished <= finished):
        raise FailoverDisplayError("application relay lifecycle is inconsistent with the run")
    _relay_projection(relay)
    return fault


def _relay_projection(relay: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    directions = _mapping(relay.get("directions"), "application relay directions")
    if set(directions) != {"a-to-b", "b-to-a"}:
        raise FailoverDisplayError("application relay has an unexpected direction set")
    result: dict[str, dict[str, int]] = {}
    for direction in ("a-to-b", "b-to-a"):
        counters = _mapping(directions[direction], f"application relay {direction}")
        projected: dict[str, int] = {}
        for field in ("forwarded", "dropped"):
            value = counters.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise FailoverDisplayError(
                    f"application relay {direction}.{field} is not positive"
                )
            projected[field] = value
        result[direction] = projected
    return result


def _validate_journey(
    stream: MessageJourneyStream,
    snapshot: Mapping[str, Any],
    topology: SharedTopology,
    manifest: Mapping[str, str],
    verdict: Mapping[str, Any],
    *,
    run_id: str,
) -> None:
    if stream.has_incomplete_final_record or not stream.is_terminal:
        raise FailoverDisplayError("typed post-cut journey is not a complete terminal stream")
    if stream.run_id != run_id:
        raise FailoverDisplayError("typed journey run identity disagrees with the result")
    if stream.topology.id != topology.id or stream.topology.topology != topology.topology:
        raise FailoverDisplayError("typed journey topology disagrees with the supplied topology")
    actual = {
        "journey_id": stream.expected.id,
        "route_id": stream.expected.route_id,
        "observation_count": len(stream.observations),
        "state": stream.diagnosis.state.value,
        "first_boundary": stream.diagnosis.first_boundary_id,
    }
    if actual != verdict["journey"]:
        raise FailoverDisplayError("typed journey disagrees with the failover verdict")
    manifest_actual = {
        "message-journey.observations": str(actual["observation_count"]),
        "message-journey.state": str(actual["state"]),
        "message-journey.first-boundary": str(actual["first_boundary"]),
    }
    if any(manifest[key] != value for key, value in manifest_actual.items()):
        raise FailoverDisplayError("typed journey disagrees with the run manifest")
    if snapshot.get("mode") != "terminal" or snapshot.get("run", {}).get("id") != run_id:
        raise FailoverDisplayError("typed journey display projection is not terminal")
    route = _mapping(snapshot.get("route"), "typed journey display route")
    if route.get("route_id") != ALTERNATE_ROUTE_ID or route.get("topology_id") != topology.id:
        raise FailoverDisplayError("typed journey display does not identify the alternate route")


def _validate_historical_stream(
    stream: HistoricalEventStream,
    topology: SharedTopology,
    verdict: Mapping[str, Any],
    *,
    run_id: str,
    fault_started: datetime,
    finished: datetime,
) -> tuple[dict[str, dict[str, int]], list[dict[str, Any]]]:
    document = stream.to_dict()
    header = _mapping(document["header"], "historical event header")
    run = _mapping(header["run"], "historical event run")
    if stream.has_incomplete_final_record:
        raise FailoverDisplayError("completed failover board refuses an incomplete event tail")
    if header["schema_version"] != 2:
        raise FailoverDisplayError("failover historical stream must use schema version 2")
    if run["id"] != run_id:
        raise FailoverDisplayError("historical event run identity disagrees with the result")
    if run["topology_id"] != topology.id or header["topology"] != topology.topology:
        raise FailoverDisplayError("historical event topology disagrees with the supplied topology")
    if run["interface_id"] != NCC_INTERFACE_ID:
        raise FailoverDisplayError("historical event stream uses an unsupported NCC interface")
    events = stream.events
    if not events:
        raise FailoverDisplayError("historical event stream is empty")
    if _timestamp(events[-1].observed_at, "last historical event") > finished:
        raise FailoverDisplayError("historical event stream extends past run finish")

    post_cut_sources = {
        event.source.imp
        for event in events
        if event.event_type == "imp.report"
        and event.source.kind == "imp-trouble-report"
        and _timestamp(event.observed_at, "historical report") > fault_started
    }
    expected_sources = set(EXPECTED_IMPS)
    if post_cut_sources != expected_sources:
        raise FailoverDisplayError(
            "historical event stream does not independently retain post-cut reports "
            "from exactly IMPs 5, 6, 7, and 62"
        )
    if post_cut_sources != set(verdict["post_cut_report_sources"]):
        raise FailoverDisplayError("historical post-cut sources disagree with the verdict")
    report_counts = {
        "trouble": _counts_by_imp(events, "imp.report", "imp-trouble-report"),
        "throughput": _counts_by_imp(
            events,
            "imp.throughput-report",
            "imp-throughput-report",
        ),
    }
    for kind, by_imp in report_counts.items():
        if set(by_imp) != {str(imp) for imp in EXPECTED_IMPS} or any(
            value <= 0 for value in by_imp.values()
        ):
            raise FailoverDisplayError(
                f"historical stream lacks complete {kind} report-source coverage"
            )
    report_events = [
        event
        for event in events
        if event.event_type in {"imp.report", "imp.throughput-report"}
        and _timestamp(event.observed_at, "historical report") > fault_started
    ]
    tape = [_historical_event_record(event) for event in report_events[-20:]]
    return report_counts, tape


def _counts_by_imp(
    events: Sequence[NccEvent],
    event_type: str,
    source_kind: str,
) -> dict[str, int]:
    counts = Counter(
        event.source.imp
        for event in events
        if event.event_type == event_type and event.source.kind == source_kind
    )
    return {str(imp): counts[imp] for imp in EXPECTED_IMPS}


def _historical_event_record(event: NccEvent) -> dict[str, Any]:
    report_name = "trouble report" if event.event_type == "imp.report" else "throughput report"
    return {
        "sequence": event.sequence,
        "observed_at": event.observed_at,
        "type": event.event_type,
        "subject": event.subject,
        "state": event.state,
        "source": {"kind": event.source.kind, "imp": event.source.imp},
        "authority": "direct historical-network observation",
        "label": f"IMP {event.source.imp} · {report_name}",
    }


def _read_stable_historical_stream(path: Path) -> HistoricalEventStream:
    first = read_historical_event_stream(path)
    second = read_historical_event_stream(path)
    if first.to_dict() != second.to_dict():
        raise FailoverDisplayError("historical event stream changed while being read")
    return second


def _read_stable_journey_stream(path: Path) -> MessageJourneyStream:
    first = read_message_journey_stream(path)
    second = read_message_journey_stream(path)
    if first.to_dict() != second.to_dict():
        raise FailoverDisplayError("typed journey stream changed while being read")
    return second


def _load_record(path: Path, description: str) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise FailoverDisplayError(f"could not read {description}: {error}") from error
    values: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if "=" not in line:
            raise FailoverDisplayError(
                f"{description} line {number} has no '=' separator"
            )
        key, value = line.split("=", 1)
        if not key or key in values:
            raise FailoverDisplayError(
                f"{description} line {number} has an invalid or duplicate key"
            )
        values[key] = value
    return values


def _load_json(path: Path, description: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FailoverDisplayError(f"could not read {description}: {error}") from error


def _load_outcome(path: Path) -> str:
    try:
        outcome = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as error:
        raise FailoverDisplayError(f"could not read application outcome: {error}") from error
    if outcome not in {"passed", "failed"}:
        raise FailoverDisplayError("application outcome is invalid")
    return outcome


def _sha256_file(path: Path, description: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise FailoverDisplayError(f"could not hash {description}: {error}") from error


def _timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FailoverDisplayError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise FailoverDisplayError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FailoverDisplayError(f"{location} must be an object")
    return value


def _fields(value: Mapping[str, Any], location: str, expected: set[str]) -> None:
    if set(value) != expected:
        raise FailoverDisplayError(f"{location} has an unexpected field set")


def _integers(value: object, location: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FailoverDisplayError(f"{location} must be an array")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise FailoverDisplayError(f"{location} must contain only integers")
        result.append(item)
    return tuple(result)


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, allow_nan=False))
