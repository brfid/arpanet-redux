#!/usr/bin/env python3
"""Evaluate one completed NCC alternate-path direct-line loopback run."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
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
    Reconciliation,
    nominal_topology_from_shared,
    reconcile,
)
from ncc.shared_topology import load_shared_topology


DIRECT_LINE_ID = "binding:imp5-mi1-imp6-mi1"
REPORT_INTERVAL = timedelta(seconds=30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--reflector", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(
            timezone.utc
        )
    except ValueError as error:
        raise ValueError(f"{location} must be an RFC 3339 UTC timestamp") from error


def line_result(result: Reconciliation, identifier: str) -> ReconciledLine:
    for line in result.lines:
        if line.id == identifier:
            return line
    raise ValueError(f"missing reconciled line {identifier}")


def evaluate(
    *,
    topology: NominalTopology,
    events: Sequence[NccEvent],
    receiver: Mapping[str, Any],
    reflector: Mapping[str, Any],
) -> dict[str, Any]:
    if not events:
        raise ValueError("historical event stream is empty")
    if reflector.get("kind") != "two-ended-udp-loop-reflector":
        raise ValueError("reflector.kind is not two-ended-udp-loop-reflector")
    reflector_version = reflector.get("version")
    if isinstance(reflector_version, bool) or reflector_version != 1:
        raise ValueError("reflector.version is not 1")
    started_at = receiver.get("started_at")
    if not isinstance(started_at, str):
        raise ValueError("receiver.started_at must be an RFC 3339 UTC timestamp")
    timestamp(started_at, "receiver.started_at")
    loop_time = timestamp(reflector.get("loop_started_at"), "reflector.loop_started_at")
    pre_events = tuple(
        event
        for event in events
        if timestamp(event.observed_at, "event.observed_at") < loop_time
    )
    if not pre_events:
        raise ValueError("loopback run has no pre-loop report events")

    pre = reconcile(
        topology,
        pre_events,
        started_at=started_at,
        observed_at=pre_events[-1].observed_at,
        report_interval=REPORT_INTERVAL,
    )
    final = reconcile(
        topology,
        events,
        started_at=started_at,
        observed_at=events[-1].observed_at,
        report_interval=REPORT_INTERVAL,
    )
    pre_line = line_result(pre, DIRECT_LINE_ID)
    final_line = line_result(final, DIRECT_LINE_ID)

    trouble_reports = receiver.get("trouble_reports")
    if not isinstance(trouble_reports, list):
        raise ValueError("receiver.trouble_reports must be a list")
    source_counts = {
        str(imp): sum(
            isinstance(report, Mapping) and report.get("source_imp") == imp
            for report in trouble_reports
        )
        for imp in (5, 6, 7)
    }
    post_loop_reports = {
        str(imp): sum(
            isinstance(report, Mapping)
            and report.get("source_imp") == imp
            and timestamp(report.get("observed_at"), "trouble_report.observed_at")
            > loop_time
            for report in trouble_reports
        )
        for imp in (5, 6)
    }

    directions = reflector.get("directions")
    if not isinstance(directions, Mapping):
        raise ValueError("reflector.directions must be a mapping")
    forwarded = {
        direction: _direction_count(directions, direction, "forwarded")
        for direction in ("a-to-b", "b-to-a")
    }
    reflected = {
        direction: _direction_count(directions, direction, "reflected")
        for direction in ("a-to-b", "b-to-a")
    }
    unexpected_sources = reflector.get("unexpected_sources")
    if not isinstance(unexpected_sources, list):
        raise ValueError("reflector.unexpected_sources must be a list")

    raw_endpoints: dict[str, dict[str, object]] = {}
    for imp in (5, 6):
        subject = f"imp:{imp}:line:1"
        matching = [
            event
            for event in events
            if event.event_type == "line-endpoint.state"
            and event.subject == subject
            and timestamp(event.observed_at, "event.observed_at") > loop_time
        ]
        if matching:
            event = matching[-1]
            raw_endpoints[str(imp)] = {
                "sequence": event.sequence,
                "observed_at": event.observed_at,
                "state": event.state,
                "neighbor_imp": event.details.get("neighbor_imp"),
            }

    checks = {
        "reflector-forwarded-both-directions": all(forwarded.values()),
        "direct-line-pre-loop-up": pre_line.state.value == "up",
        "reflector-reflected-both-directions": all(reflected.values()),
        "reflector-no-unexpected-source": not unexpected_sources,
        "reports-from-imps-5-6-7": all(source_counts.values()),
        "post-loop-reports-from-imps-5-and-6": all(post_loop_reports.values()),
        "raw-endpoints-final-looped-to-self": all(
            str(imp) in raw_endpoints
            and raw_endpoints[str(imp)]["state"] == "looped"
            and raw_endpoints[str(imp)]["neighbor_imp"] == imp
            for imp in (5, 6)
        ),
        "direct-line-final-looped": final_line.state.value == "looped",
    }
    return {
        "version": 1,
        "kind": "ncc-line-loopback-verdict",
        "passed": all(checks.values()),
        "checks": checks,
        "report_counts_by_source_imp": source_counts,
        "post_loop_trouble_report_counts": post_loop_reports,
        "reflector_forwarded": forwarded,
        "reflector_reflected": reflected,
        "raw_final_direct_endpoints": raw_endpoints,
        "direct_line": {
            "id": DIRECT_LINE_ID,
            "pre_loop_state": pre_line.state.value,
            "pre_loop_supporting_sequences": list(pre_line.supporting_sequences),
            "final_state": final_line.state.value,
            "final_supporting_sequences": list(final_line.supporting_sequences),
        },
    }


def _direction_count(
    directions: Mapping[str, Any], direction: str, field: str
) -> int:
    counters = directions.get(direction)
    if not isinstance(counters, Mapping):
        raise ValueError(f"reflector.directions.{direction} must be a mapping")
    value = counters.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"reflector.directions.{direction}.{field} must be nonnegative"
        )
    return value


def main() -> int:
    args = parse_args()
    shared = load_shared_topology(args.topology)
    topology = nominal_topology_from_shared(shared)
    stream = read_historical_event_stream(args.events)
    receiver = json.loads(args.receiver.read_text(encoding="utf-8"))
    reflector = json.loads(args.reflector.read_text(encoding="utf-8"))
    result = evaluate(
        topology=topology,
        events=stream.events,
        receiver=receiver,
        reflector=reflector,
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
