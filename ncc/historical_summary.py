"""Adapt supported historical-line runs into completed NCC summaries.

The adapter reads only project-authored structured results. It never parses raw
simulator logs, controls a process, mutates a result directory, infers an
unmapped report-line identity, or changes the accepted reconciliation rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .events import NccEvent
from .historical_events import (
    HistoricalEventStreamError,
    read_historical_event_stream,
)
from .reconciliation import (
    ImpState,
    LineState,
    Reconciliation,
    ReconciliationError,
    historical_line_topology_from_shared,
    reconcile,
)
from .run_summary import (
    RUN_SUMMARY_SCHEMA_VERSION,
    RunSummary,
    RunSummaryValidationError,
    run_summary_from_mapping,
    validate_normalized_topology,
)
from .shared_topology import (
    SharedTopology,
    SharedTopologyValidationError,
    load_shared_topology,
)


REPORT_INTERVAL = timedelta(seconds=30)

_RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_REQUIRED = frozenset(
    {
        "cleanup.completed",
        "exit_status",
        "finished_utc",
        "format",
        "outcome",
        "process.receiver.exit-status",
        "repository.revision",
        "repository.tracked_dirty",
        "result.verdict",
        "result.verdict-exit-status",
        "sha256.shared-topology",
        "source.arpanet-in-a-box.revision",
        "source.arpanet-in-a-box.tracked_dirty",
        "source.h316-simh.revision",
        "source.h316-simh.tracked_dirty",
        "started_utc",
        "topology",
    }
)


class HistoricalLineSummaryError(ValueError):
    """Raised when structured run evidence cannot support a safe summary."""


@dataclass(frozen=True)
class _Profile:
    verdict_kind: str
    manifest_topology: str
    mechanism_exit_key: str
    expected_final_state: LineState
    pre_state_key: str
    pre_support_key: str
    gate_id: str
    assertion: str


@dataclass(frozen=True)
class _ValidatedVerdict:
    profile: _Profile
    passed: bool
    line_id: str
    pre_supporting_sequences: tuple[int, ...]
    final_state: LineState
    final_supporting_sequences: tuple[int, ...]


_PROFILES = {
    "ncc-alternate-path-fault-verdict": _Profile(
        verdict_kind="ncc-alternate-path-fault-verdict",
        manifest_topology="ncc-alternate-path-fault",
        mechanism_exit_key="process.direct-relay.exit-status",
        expected_final_state=LineState.DOWN,
        pre_state_key="pre_fault_state",
        pre_support_key="pre_fault_supporting_sequences",
        gate_id="gate:ncc-alternate-path-line-fault",
        assertion=(
            "The supported alternate-path run completed and the explicitly mapped "
            "direct line reconciled as down."
        ),
    ),
    "ncc-line-loopback-verdict": _Profile(
        verdict_kind="ncc-line-loopback-verdict",
        manifest_topology="ncc-line-loopback",
        mechanism_exit_key="process.direct-reflector.exit-status",
        expected_final_state=LineState.LOOPED,
        pre_state_key="pre_loop_state",
        pre_support_key="pre_loop_supporting_sequences",
        gate_id="gate:ncc-alternate-path-line-loopback",
        assertion=(
            "The supported line-loopback run completed and the explicitly mapped "
            "direct line reconciled as looped."
        ),
    ),
}


def summarize_historical_line_result(
    results_dir: str | Path,
    shared_topology_path: str | Path,
) -> RunSummary:
    """Return a version-2 summary for one supported completed NCC line run."""

    result_path = Path(results_dir)
    topology_path = Path(shared_topology_path)
    run_name = _run_name(result_path)
    manifest = _load_record(result_path / "runtime" / "run.env", "run manifest")
    verdict_document = _load_json(result_path / "verdict.json", "run verdict")
    verdict = _validate_verdict(verdict_document)
    topology_digest = _sha256_file(topology_path, "shared topology")
    _validate_manifest(
        manifest,
        verdict,
        topology_digest=topology_digest,
        verdict_path=result_path / "verdict.json",
    )

    try:
        shared = load_shared_topology(topology_path)
        stream = read_historical_event_stream(result_path / "historical-events.jsonl")
        historical_topology = historical_line_topology_from_shared(shared)
        nominal = historical_topology.nominal
    except (
        HistoricalEventStreamError,
        ReconciliationError,
        SharedTopologyValidationError,
    ) as error:
        raise HistoricalLineSummaryError(str(error)) from error

    header = stream.to_dict()["header"]
    _validate_stream_header(
        header,
        run_name=run_name,
        shared=shared,
        manifest=manifest,
    )
    events = stream.events
    if not events:
        raise HistoricalLineSummaryError("historical event stream is empty")
    if _timestamp(events[-1].observed_at, "last historical event") > _timestamp(
        manifest["finished_utc"], "run manifest.finished_utc"
    ):
        raise HistoricalLineSummaryError(
            "historical event stream extends beyond the completed run clock"
        )

    try:
        pre_events = tuple(
            event
            for event in events
            if event.sequence <= verdict.pre_supporting_sequences[-1]
        )
        if not pre_events:
            raise HistoricalLineSummaryError(
                "run verdict pre-transition support is absent from the event stream"
            )
        pre_result = reconcile(
            nominal,
            pre_events,
            started_at=header["run"]["started_at"],
            observed_at=pre_events[-1].observed_at,
            report_interval=REPORT_INTERVAL,
        )
        result = reconcile(
            nominal,
            events,
            started_at=header["run"]["started_at"],
            observed_at=events[-1].observed_at,
            report_interval=REPORT_INTERVAL,
        )
    except ReconciliationError as error:
        raise HistoricalLineSummaryError(str(error)) from error

    pre_line = next(
        (line for line in pre_result.lines if line.id == verdict.line_id),
        None,
    )
    if (
        pre_line is None
        or pre_line.state != LineState.UP
        or pre_line.supporting_sequences != verdict.pre_supporting_sequences
    ):
        raise HistoricalLineSummaryError(
            "run verdict pre-transition up state or supporting sequences disagree "
            "with the validated historical-event stream"
        )

    final_line = next(
        (line for line in result.lines if line.id == verdict.line_id),
        None,
    )
    if final_line is None:
        raise HistoricalLineSummaryError(
            f"verdict refers to unmapped reconciled line {verdict.line_id!r}"
        )
    if (
        final_line.state != verdict.final_state
        or final_line.supporting_sequences != verdict.final_supporting_sequences
    ):
        raise HistoricalLineSummaryError(
            "run verdict final line state or supporting sequences disagree with "
            "the validated historical-event stream"
        )

    try:
        document = _summary_document(
            run_name=run_name,
            manifest=manifest,
            verdict=verdict,
            shared=shared,
            events=events,
            reconciliation=result,
            endpoint_subjects=historical_topology.endpoint_subject_ids,
            line_links=historical_topology.line_link_ids,
        )
        return run_summary_from_mapping(document)
    except (HistoricalLineSummaryError, RunSummaryValidationError) as error:
        if isinstance(error, HistoricalLineSummaryError):
            raise
        raise HistoricalLineSummaryError(
            f"derived historical-line summary is invalid: {error}"
        ) from error


def _summary_document(
    *,
    run_name: str,
    manifest: Mapping[str, str],
    verdict: _ValidatedVerdict,
    shared: SharedTopology,
    events: Sequence[NccEvent],
    reconciliation: Reconciliation,
    endpoint_subjects: Mapping[str, str],
    line_links: Mapping[str, str],
) -> dict[str, Any]:
    component_ids, _, _, _ = validate_normalized_topology(shared.topology)
    observations: list[dict[str, Any]] = []
    sequence_observation_ids: dict[int, str] = {}
    for event in events:
        if event.event_type == "imp.report" and event.subject in component_ids:
            subject_id = event.subject
        elif event.event_type == "line-endpoint.state":
            subject_id = endpoint_subjects.get(event.subject)
            if subject_id is None:
                continue
        else:
            continue
        observation_id = f"observation:historical:{event.sequence}"
        sequence_observation_ids[event.sequence] = observation_id
        observations.append(
            {
                "id": observation_id,
                "sequence": len(observations) + 1,
                "observed_at": event.observed_at,
                "category": "historical-network",
                "subject_id": subject_id,
                "state": event.state,
                "source": {
                    "id": f"source:historical-imp:{event.source.imp}",
                    "kind": event.source.kind,
                },
                "details": {
                    "historical_event": {
                        "sequence": event.sequence,
                        "subject": event.subject,
                        "type": event.event_type,
                        "version": event.version,
                    },
                    "report_details": event.to_dict()["details"],
                },
                "external_evidence_ids": ["evidence:historical-events"],
            }
        )

    verdict_observation_id = "observation:harness-outcome"
    target_link = line_links.get(verdict.line_id)
    if target_link is None:
        raise HistoricalLineSummaryError(
            f"verdict line {verdict.line_id!r} does not map to a normalized link"
        )
    observations.append(
        {
            "id": verdict_observation_id,
            "sequence": len(observations) + 1,
            "observed_at": manifest["finished_utc"],
            "category": "harness",
            "subject_id": target_link,
            "state": "passed" if verdict.passed else "failed",
            "source": {
                "id": "source:supported-result-evaluator",
                "kind": "supported-result-evaluator",
            },
            "details": {
                "cleanup_completed": manifest["cleanup.completed"] == "1",
                "exit_status": int(manifest["exit_status"]),
                "verdict_kind": verdict.profile.verdict_kind,
            },
            "external_evidence_ids": ["evidence:manifest", "evidence:verdict"],
        }
    )

    derived_states: list[dict[str, Any]] = []
    line_derived_ids: dict[str, str] = {}
    for line in reconciliation.lines:
        if not line.supporting_sequences:
            continue
        supporting_ids = _supporting_observation_ids(
            line.supporting_sequences,
            sequence_observation_ids,
            f"reconciled line {line.id!r}",
        )
        link_id = line_links.get(line.id)
        if link_id is None:
            raise HistoricalLineSummaryError(
                f"reconciled line {line.id!r} has no normalized link identity"
            )
        derived_id = f"derived:historical-line:{line.id}"
        line_derived_ids[line.id] = derived_id
        derived_states.append(
            {
                "id": derived_id,
                "subject_id": link_id,
                "state": line.state.value,
                "basis": "inference",
                "supporting_observation_ids": supporting_ids,
            }
        )
    for imp in reconciliation.imps:
        if not imp.supporting_sequences:
            continue
        supporting_ids = _supporting_observation_ids(
            imp.supporting_sequences,
            sequence_observation_ids,
            f"reconciled IMP {imp.imp}",
        )
        derived_states.append(
            {
                "id": f"derived:historical-imp:{imp.imp}",
                "subject_id": f"imp:{imp.imp}",
                "state": imp.state.value,
                "basis": "direct" if imp.state == ImpState.UP else "inference",
                "supporting_observation_ids": supporting_ids,
            }
        )

    final_derived_id = line_derived_ids.get(verdict.line_id)
    if final_derived_id is None:
        raise HistoricalLineSummaryError(
            "final reconciled line has no persistable direct observation support"
        )
    final_support_ids = _supporting_observation_ids(
        verdict.final_supporting_sequences,
        sequence_observation_ids,
        "verdict final line",
    )
    gate_evidence = [*final_support_ids, verdict_observation_id]
    run_id = f"run:{run_name}"
    return {
        "schema_version": RUN_SUMMARY_SCHEMA_VERSION,
        "run": {
            "id": run_id,
            "started_at": manifest["started_utc"],
            "finished_at": manifest["finished_utc"],
            "outcome": "passed" if verdict.passed else "failed",
            "provenance": _provenance(run_id, manifest),
        },
        "topology": shared.topology,
        "external_evidence": [
            {
                "id": "evidence:manifest",
                "kind": "ncc-run-manifest",
                "locator": "runtime/run.env",
            },
            {
                "id": "evidence:historical-events",
                "kind": "ncc-historical-event-stream",
                "locator": "historical-events.jsonl",
            },
            {
                "id": "evidence:verdict",
                "kind": verdict.profile.verdict_kind,
                "locator": "verdict.json",
            },
        ],
        "observations": observations,
        "derived_states": derived_states,
        "gates": [
            {
                "id": verdict.profile.gate_id,
                "kind": "network-behavior",
                "assertion": verdict.profile.assertion,
                "verdict": "passed" if verdict.passed else "failed",
                "evidence_observation_ids": gate_evidence,
                "evidence_derived_state_ids": [final_derived_id],
                "external_evidence_ids": [
                    "evidence:manifest",
                    "evidence:historical-events",
                    "evidence:verdict",
                ],
            }
        ],
    }


def _supporting_observation_ids(
    support: Sequence[int],
    sequence_observation_ids: Mapping[int, str],
    location: str,
) -> list[str]:
    identifiers = []
    for sequence in support:
        try:
            identifiers.append(sequence_observation_ids[sequence])
        except KeyError as error:
            raise HistoricalLineSummaryError(
                f"{location} support sequence {sequence} is not a mapped direct observation"
            ) from error
    return identifiers


def _validate_stream_header(
    header: Mapping[str, Any],
    *,
    run_name: str,
    shared: SharedTopology,
    manifest: Mapping[str, str],
) -> None:
    run = header["run"]
    if run["id"] != run_name:
        raise HistoricalLineSummaryError(
            "historical event stream run identity does not match its result directory"
        )
    if run["topology_id"] != shared.id:
        raise HistoricalLineSummaryError(
            "historical event stream topology identity does not match the supplied topology"
        )
    if header["topology"] != shared.topology:
        raise HistoricalLineSummaryError(
            "historical event stream topology snapshot does not match the supplied topology"
        )
    stream_started = _timestamp(run["started_at"], "historical event stream.started_at")
    run_started = _timestamp(manifest["started_utc"], "run manifest.started_utc")
    run_finished = _timestamp(manifest["finished_utc"], "run manifest.finished_utc")
    if not run_started <= stream_started <= run_finished:
        raise HistoricalLineSummaryError(
            "historical event stream start falls outside the completed run clock"
        )


def _validate_verdict(document: object) -> _ValidatedVerdict:
    verdict = _mapping(document, "run verdict")
    if verdict.get("version") != 1 or isinstance(verdict.get("version"), bool):
        raise HistoricalLineSummaryError("run verdict has unsupported version")
    kind = verdict.get("kind")
    profile = _PROFILES.get(kind)
    if profile is None:
        raise HistoricalLineSummaryError(
            f"run verdict has unsupported kind {kind!r}"
        )
    passed = verdict.get("passed")
    if not isinstance(passed, bool):
        raise HistoricalLineSummaryError("run verdict.passed must be boolean")
    checks = _mapping(verdict.get("checks"), "run verdict.checks")
    if not checks or any(not isinstance(value, bool) for value in checks.values()):
        raise HistoricalLineSummaryError(
            "run verdict.checks must be a nonempty boolean mapping"
        )
    if passed != all(checks.values()):
        raise HistoricalLineSummaryError(
            "run verdict.passed disagrees with its individual checks"
        )
    direct_line = _mapping(verdict.get("direct_line"), "run verdict.direct_line")
    line_id = _text(direct_line.get("id"), "run verdict.direct_line.id")
    final_state_value = _text(
        direct_line.get("final_state"), "run verdict.direct_line.final_state"
    )
    try:
        final_state = LineState(final_state_value)
    except ValueError as error:
        raise HistoricalLineSummaryError(
            f"run verdict has unsupported final line state {final_state_value!r}"
        ) from error
    final_support = _positive_sequences(
        direct_line.get("final_supporting_sequences"),
        "run verdict.direct_line.final_supporting_sequences",
    )
    pre_state = _text(
        direct_line.get(profile.pre_state_key),
        f"run verdict.direct_line.{profile.pre_state_key}",
    )
    pre_support = _positive_sequences(
        direct_line.get(profile.pre_support_key),
        f"run verdict.direct_line.{profile.pre_support_key}",
    )
    if passed and (
        pre_state != LineState.UP.value
        or final_state != profile.expected_final_state
    ):
        raise HistoricalLineSummaryError(
            "passed run verdict does not contain its required up-to-final line transition"
        )
    return _ValidatedVerdict(
        profile=profile,
        passed=passed,
        line_id=line_id,
        pre_supporting_sequences=pre_support,
        final_state=final_state,
        final_supporting_sequences=final_support,
    )


def _validate_manifest(
    manifest: Mapping[str, str],
    verdict: _ValidatedVerdict,
    *,
    topology_digest: str,
    verdict_path: Path,
) -> None:
    required = _MANIFEST_REQUIRED | {verdict.profile.mechanism_exit_key}
    missing = required - manifest.keys()
    if missing:
        raise HistoricalLineSummaryError(
            "run manifest is missing fields: " + ", ".join(sorted(missing))
        )
    if manifest["format"] != "1":
        raise HistoricalLineSummaryError("unsupported run manifest format")
    if manifest["topology"] != verdict.profile.manifest_topology:
        raise HistoricalLineSummaryError(
            "run manifest topology does not match the supported verdict kind"
        )
    if manifest["outcome"] not in {"passed", "failed"}:
        raise HistoricalLineSummaryError("run manifest has an invalid terminal outcome")
    exit_status = _nonnegative_integer(manifest["exit_status"], "run exit status")
    manifest_passed = manifest["outcome"] == "passed"
    if manifest_passed != (exit_status == 0) or manifest_passed != verdict.passed:
        raise HistoricalLineSummaryError(
            "run manifest outcome, exit status, and evaluator verdict disagree"
        )
    verdict_status = _nonnegative_integer(
        manifest["result.verdict-exit-status"], "verdict exit status"
    )
    if verdict.passed != (verdict_status == 0):
        raise HistoricalLineSummaryError(
            "run manifest verdict status disagrees with the evaluator verdict"
        )
    if manifest["cleanup.completed"] != "1":
        raise HistoricalLineSummaryError("run manifest does not record complete cleanup")
    for key in (
        "process.receiver.exit-status",
        verdict.profile.mechanism_exit_key,
    ):
        if _nonnegative_integer(manifest[key], key) != 0:
            raise HistoricalLineSummaryError(
                f"run manifest records an unsuccessful owned process in {key!r}"
            )
    if manifest["repository.tracked_dirty"] != "0":
        raise HistoricalLineSummaryError(
            "run manifest does not identify a clean project repository"
        )
    _revision(manifest["repository.revision"], "repository revision")
    for key, value in manifest.items():
        if key.startswith("source.") and key.endswith(".revision"):
            _revision(value, key)
            dirty_key = key.removesuffix(".revision") + ".tracked_dirty"
            if manifest.get(dirty_key) != "0":
                raise HistoricalLineSummaryError(
                    f"run manifest does not identify a clean source for {key!r}"
                )
    if manifest["sha256.shared-topology"] != topology_digest:
        raise HistoricalLineSummaryError(
            "supplied shared topology digest does not match the run manifest"
        )
    recorded_verdict = Path(manifest["result.verdict"])
    if recorded_verdict.resolve() != verdict_path.resolve():
        raise HistoricalLineSummaryError(
            "run manifest verdict path does not identify the supplied result"
        )
    started = _timestamp(manifest["started_utc"], "run manifest.started_utc")
    finished = _timestamp(manifest["finished_utc"], "run manifest.finished_utc")
    if finished < started:
        raise HistoricalLineSummaryError(
            "run manifest finished time precedes its start time"
        )


def _provenance(run_id: str, manifest: Mapping[str, str]) -> list[dict[str, str]]:
    sources = [
        {
            "id": "source:arpanet-redux",
            "kind": "repository",
            "revision": manifest["repository.revision"],
        },
        {"id": run_id, "kind": "ncc-network-behavior-run-manifest"},
    ]
    for key, revision in sorted(manifest.items()):
        if key.startswith("source.") and key.endswith(".revision"):
            source = key.removeprefix("source.").removesuffix(".revision")
            sources.append(
                {
                    "id": f"source:{source}",
                    "kind": "external-source",
                    "revision": revision,
                }
            )
    return sources


def _load_record(path: Path, description: str) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise HistoricalLineSummaryError(
            f"could not read {description} {path}: {error}"
        ) from error
    record: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        key, separator, value = line.partition("=")
        if not separator or not key or not value:
            raise HistoricalLineSummaryError(
                f"{description} {path} has an invalid line {line_number}"
            )
        if key in record:
            raise HistoricalLineSummaryError(
                f"{description} {path} repeats key {key!r}"
            )
        record[key] = value
    if not record:
        raise HistoricalLineSummaryError(f"{description} {path} is empty")
    return record


def _load_json(path: Path, description: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HistoricalLineSummaryError(
            f"could not read {description} {path}: {error}"
        ) from error


def _sha256_file(path: Path, description: str) -> str:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise HistoricalLineSummaryError(
            f"could not read {description} {path}: {error}"
        ) from error
    if not _SHA256.fullmatch(digest):
        raise AssertionError("hashlib returned a malformed SHA-256 digest")
    return digest


def _run_name(result_path: Path) -> str:
    name = result_path.name
    if not _RUN_NAME.fullmatch(name):
        raise HistoricalLineSummaryError(
            "result directory name is not a stable run identifier"
        )
    return name


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HistoricalLineSummaryError(f"{location} must be an object")
    return value


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise HistoricalLineSummaryError(f"{location} must be nonempty text")
    return value


def _positive_sequences(value: object, location: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise HistoricalLineSummaryError(f"{location} must be a nonempty array")
    sequences = tuple(value)
    if any(
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence <= 0
        for sequence in sequences
    ):
        raise HistoricalLineSummaryError(
            f"{location} must contain positive integer sequences"
        )
    if tuple(sorted(set(sequences))) != sequences:
        raise HistoricalLineSummaryError(
            f"{location} must contain unique increasing sequences"
        )
    return sequences


def _nonnegative_integer(value: str, location: str) -> int:
    if not isinstance(value, str) or not value.isdecimal():
        raise HistoricalLineSummaryError(
            f"{location} must be a nonnegative integer"
        )
    return int(value)


def _revision(value: str, location: str) -> None:
    if not _REVISION.fullmatch(value):
        raise HistoricalLineSummaryError(f"{location} is not a Git revision")


def _timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise HistoricalLineSummaryError(
            f"{location} must be an RFC 3339 UTC timestamp"
        )
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(
            timezone.utc
        )
    except ValueError as error:
        raise HistoricalLineSummaryError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error
