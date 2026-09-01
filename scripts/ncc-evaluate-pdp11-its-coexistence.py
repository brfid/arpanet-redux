#!/usr/bin/env python3
"""Evaluate one completed NCC-observed PDP-11-to-ITS coexistence run."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import timedelta
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.events import NccEvent
from ncc.historical_events import read_historical_event_stream
from ncc.reconciliation import (
    NominalTopology,
    ReconciledLine,
    nominal_topology_from_shared,
    reconcile,
)
from ncc.shared_topology import load_shared_topology


DIRECT_LINE_ID = "binding:imp5-mi1-imp6-mi1"
EXPECTED_IMPS = (5, 6, 7, 62)
REPORT_INTERVAL = timedelta(seconds=30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--application-evidence", type=Path, required=True)
    parser.add_argument("--cleanup-evidence", type=Path, required=True)
    parser.add_argument("--outcome", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_key_value(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "=" not in line:
            raise ValueError(f"{path} line {number} has no '=' separator")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"{path} line {number} has an invalid or duplicate key")
        values[key] = value
    return values


def line_result(result: object, identifier: str) -> ReconciledLine:
    for line in result.lines:
        if line.id == identifier:
            return line
    raise ValueError(f"missing reconciled line {identifier}")


def latest_observed_up(
    topology: NominalTopology,
    events: Sequence[NccEvent],
    *,
    started_at: str,
) -> ReconciledLine | None:
    latest: ReconciledLine | None = None
    for index, event in enumerate(events, start=1):
        result = reconcile(
            topology,
            events[:index],
            started_at=started_at,
            observed_at=event.observed_at,
            report_interval=REPORT_INTERVAL,
        )
        line = line_result(result, DIRECT_LINE_ID)
        if line.state.value == "up":
            latest = line
    return latest


def report_counts(receiver: Mapping[str, Any], field: str) -> dict[str, int]:
    reports = receiver.get(field)
    if not isinstance(reports, list):
        raise ValueError(f"receiver.{field} must be a list")
    return {
        str(imp): sum(
            isinstance(report, Mapping) and report.get("source_imp") == imp
            for report in reports
        )
        for imp in EXPECTED_IMPS
    }


def evaluate(
    *,
    topology: NominalTopology,
    events: Sequence[NccEvent],
    receiver: Mapping[str, Any],
    application: Mapping[str, str],
    cleanup: Mapping[str, str],
    outcome: str,
    manifest: Mapping[str, str],
    identities: Mapping[str, str],
) -> dict[str, Any]:
    if not events:
        raise ValueError("historical event stream is empty")
    started_at = receiver.get("started_at")
    if not isinstance(started_at, str):
        raise ValueError("receiver.started_at must be a timestamp")

    observed_up = latest_observed_up(topology, events, started_at=started_at)
    trouble_counts = report_counts(receiver, "trouble_reports")
    throughput_counts = report_counts(receiver, "throughput_reports")
    application_required = {
        "connection_open": "1",
        "remote_time": "structured",
        "correlated_inter_imp_traffic": "both-directions",
    }
    journey_required = {
        "message_journey_observations": "10",
        "message_journey_state": "missing-boundary",
        "message_journey_first_boundary": "boundary:request:6",
    }
    clean_identity_keys = (
        "repository.tracked_dirty",
        "source.arpanet-in-a-box.tracked_dirty",
        "source.network-unix-v6.tracked_dirty",
        "source.h316-simh.tracked_dirty",
        "source.ka10-simh.tracked_dirty",
        "source.imp11a-simh.tracked_dirty",
    )
    identity_check = (
        identities.get("run_id") == identities.get("stream_run_id")
        and identities.get("topology_id") == identities.get("stream_topology_id")
        == receiver.get("topology_id")
        and identities.get("interface_id") == identities.get("stream_interface_id")
        == receiver.get("interface_id")
    )
    checks = {
        "evidence-identities-match": identity_check,
        "clean-pinned-inputs": all(manifest.get(key) == "0" for key in clean_identity_keys),
        "outer-runtime-cleanup": manifest.get("cleanup.outer-runtime") == "passed",
        "application-passed": outcome == "passed"
        and all(application.get(key) == value for key, value in application_required.items()),
        "typed-journey-retained": all(
            application.get(key) == value for key, value in journey_required.items()
        ),
        "application-controller-cleanup": cleanup.get("surviving_owned_processes") == "0",
        "trouble-reports-from-imps-5-6-7-62": all(trouble_counts.values()),
        "throughput-reports-from-imps-5-6-7-62": all(throughput_counts.values()),
        "mapped-direct-line-observed-up": observed_up is not None,
    }
    return {
        "version": 1,
        "kind": "ncc-pdp11-its-coexistence-verdict",
        "passed": all(checks.values()),
        "checks": checks,
        "report_counts_by_source_imp": {
            "trouble": trouble_counts,
            "throughput": throughput_counts,
        },
        "direct_line": {
            "id": DIRECT_LINE_ID,
            "observed_state": "up" if observed_up is not None else "unproved",
            "supporting_sequences": (
                list(observed_up.supporting_sequences) if observed_up is not None else []
            ),
        },
    }


def main() -> int:
    args = parse_args()
    shared = load_shared_topology(args.topology)
    topology = nominal_topology_from_shared(shared)
    stream = read_historical_event_stream(args.events)
    header_run = stream.to_dict()["header"]["run"]
    receiver = json.loads(args.receiver.read_text(encoding="utf-8"))
    application = read_key_value(args.application_evidence)
    cleanup = read_key_value(args.cleanup_evidence)
    manifest = read_key_value(args.manifest)
    result = evaluate(
        topology=topology,
        events=stream.events,
        receiver=receiver,
        application=application,
        cleanup=cleanup,
        outcome=args.outcome.read_text(encoding="ascii").strip(),
        manifest=manifest,
        identities={
            "run_id": args.run_id,
            "stream_run_id": str(header_run["id"]),
            "topology_id": shared.id,
            "stream_topology_id": str(header_run["topology_id"]),
            "interface_id": "binding:ncc-host0-imp5",
            "stream_interface_id": str(header_run["interface_id"]),
        },
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
