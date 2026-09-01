#!/usr/bin/env python3
"""Evaluate one completed PDP-11-to-ITS application-link failover run."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.message_journey_stream import read_message_journey_stream
from ncc.pdp11_its_failover_journey import (
    PDP11_ITS_FAILOVER_JOURNEY_ID,
    PDP11_ITS_FAILOVER_ROUTE_ID,
)
from ncc.shared_topology import load_shared_topology

EXPECTED_TOPOLOGY_ID = "topology:ncc-pdp11-its-application-failover"
_LINE_SUBJECT = re.compile(r"imp:([1-9][0-9]*):line:([1-5])\Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", required=True, type=Path)
    parser.add_argument("--receiver", required=True, type=Path)
    parser.add_argument("--relay", required=True, type=Path)
    parser.add_argument("--cut-state", required=True, type=Path)
    parser.add_argument("--application-evidence", required=True, type=Path)
    parser.add_argument("--message-journey", required=True, type=Path)
    parser.add_argument("--cleanup-evidence", required=True, type=Path)
    parser.add_argument("--outcome", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as error:
        raise ValueError(f"{location} must be an RFC 3339 UTC timestamp") from error


def key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(
        path.read_text(encoding="ascii").splitlines(), start=1
    ):
        if "=" not in line:
            raise ValueError(f"{path.name} line {number} has no '=' separator")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(
                f"{path.name} line {number} has an invalid or duplicate key"
            )
        values[key] = value
    return values


def _line_events(receiver: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    reports = receiver.get("trouble_reports")
    if not isinstance(reports, list):
        raise TypeError("receiver.trouble_reports must be a list")
    result: list[dict[str, Any]] = []
    for report_index, report in enumerate(reports):
        if not isinstance(report, Mapping):
            raise TypeError(
                f"receiver.trouble_reports[{report_index}] must be an object"
            )
        observed_at = report.get("observed_at")
        timestamp(observed_at, f"trouble_reports[{report_index}].observed_at")
        events = report.get("events")
        if not isinstance(events, list):
            raise TypeError(
                f"receiver.trouble_reports[{report_index}].events must be a list"
            )
        for event in events:
            if (
                not isinstance(event, Mapping)
                or event.get("type") != "line-endpoint.state"
            ):
                continue
            match = _LINE_SUBJECT.fullmatch(str(event.get("subject", "")))
            details = event.get("details")
            if match is None or not isinstance(details, Mapping):
                raise ValueError(
                    "trouble report contains a malformed line-endpoint event"
                )
            state = event.get("state")
            if state not in {"up", "down", "looped"}:
                raise ValueError(
                    "trouble report line-endpoint event has an invalid state"
                )
            result.append(
                {
                    "imp": int(match.group(1)),
                    "line": int(match.group(2)),
                    "state": state,
                    "neighbor_imp": details.get("neighbor_imp"),
                    "observed_at": observed_at,
                }
            )
    return tuple(result)


def _candidate_line(
    events: Sequence[Mapping[str, Any]],
    *,
    imp: int,
    neighbor: int,
    before: datetime | None = None,
    after: datetime | None = None,
) -> int:
    lines = {
        event["line"]
        for event in events
        if event["imp"] == imp
        and event["state"] == "up"
        and event["neighbor_imp"] == neighbor
        and (before is None or timestamp(event["observed_at"], "line event") < before)
        and (after is None or timestamp(event["observed_at"], "line event") > after)
    }
    if len(lines) != 1:
        raise ValueError(
            f"reports do not identify one unique line on IMP {imp} toward IMP {neighbor}"
        )
    return next(iter(lines))


def discover_mapping(
    receiver: Mapping[str, Any], fault_time: datetime
) -> dict[str, Any]:
    """Retain unique reciprocal candidates without promoting topology authority."""

    events = _line_events(receiver)
    imp62_direct = _candidate_line(events, imp=62, neighbor=6, before=fault_time)
    imp6_direct = _candidate_line(events, imp=6, neighbor=62, before=fault_time)
    imp62_alternate = _candidate_line(events, imp=62, neighbor=7, after=fault_time)
    imp7_alternate = _candidate_line(events, imp=7, neighbor=62, after=fault_time)
    post_cut_down = {
        (event["imp"], event["line"])
        for event in events
        if event["state"] == "down"
        and timestamp(event["observed_at"], "line event") > fault_time
    }
    if (62, imp62_direct) not in post_cut_down or (6, imp6_direct) not in post_cut_down:
        raise ValueError(
            "direct application candidate lacks reciprocal post-cut down reports"
        )
    return {
        "status": "candidate-only-one-exact-run",
        "promoted_to_topology": False,
        "direct_application_link": {
            "imp62_report_line": imp62_direct,
            "imp6_report_line": imp6_direct,
            "pre_cut_state": "up",
            "post_cut_state": "down",
        },
        "alternate_application_link": {
            "imp62_report_line": imp62_alternate,
            "imp7_report_line": imp7_alternate,
            "post_cut_state": "up",
        },
    }


def _direction_count(relay: Mapping[str, Any], direction: str, field: str) -> int:
    directions = relay.get("directions")
    if not isinstance(directions, Mapping):
        raise TypeError("relay.directions must be an object")
    counters = directions.get(direction)
    if not isinstance(counters, Mapping):
        raise TypeError(f"relay.directions.{direction} must be an object")
    value = counters.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"relay.directions.{direction}.{field} must be nonnegative")
    return value


def _report_sources_after(
    receiver: Mapping[str, Any], fault_time: datetime
) -> set[int]:
    reports = receiver.get("trouble_reports")
    if not isinstance(reports, list):
        raise TypeError("receiver.trouble_reports must be a list")
    return {
        report["source_imp"]
        for report in reports
        if isinstance(report, Mapping)
        and isinstance(report.get("source_imp"), int)
        and timestamp(report.get("observed_at"), "trouble report") > fault_time
    }


def evaluate(
    *,
    receiver: Mapping[str, Any],
    relay: Mapping[str, Any],
    cut_state: Mapping[str, Any],
    application: Mapping[str, str],
    journey: Mapping[str, Any],
    cleanup: Mapping[str, str],
    outcome: str,
    manifest: Mapping[str, str],
    identities: Mapping[str, str],
) -> dict[str, Any]:
    if relay.get("cut_mode") != "request-file":
        raise ValueError("application failover requires the request-file relay mode")
    fault_started_at = relay.get("fault_started_at")
    if (
        cut_state.get("state") != "cut"
        or cut_state.get("fault_started_at") != fault_started_at
    ):
        raise ValueError("relay result and atomic cut acknowledgement disagree")
    fault_time = timestamp(fault_started_at, "relay.fault_started_at")
    mapping = discover_mapping(receiver, fault_time)
    unexpected = relay.get("unexpected_sources")
    if not isinstance(unexpected, list):
        raise TypeError("relay.unexpected_sources must be a list")
    report_sources = _report_sources_after(receiver, fault_time)
    clean_keys = (
        "repository.tracked_dirty",
        "source.arpanet-in-a-box.tracked_dirty",
        "source.network-unix-v6.tracked_dirty",
        "source.h316-simh.tracked_dirty",
        "source.ka10-simh.tracked_dirty",
        "source.imp11a-simh.tracked_dirty",
    )
    checks = {
        "identity-chain": (
            identities.get("topology_id") == EXPECTED_TOPOLOGY_ID
            and identities.get("receiver_topology_id") == EXPECTED_TOPOLOGY_ID
            and identities.get("run_id") == identities.get("journey_run_id")
        ),
        "relay-forwarded-before-cut": all(
            _direction_count(relay, direction, "forwarded") > 0
            for direction in ("a-to-b", "b-to-a")
        ),
        "relay-dropped-after-cut": all(
            _direction_count(relay, direction, "dropped") > 0
            for direction in ("a-to-b", "b-to-a")
        ),
        "relay-no-unexpected-source": not unexpected,
        "same-session-post-cut-time": (
            application.get("connection_open") == "1"
            and application.get("pre_cut_remote_time") == "structured"
            and application.get("cut_acknowledged") == "1"
            and application.get("session_survived_cut") == "1"
            and application.get("post_cut_remote_time") == "structured"
        ),
        "network-unix-host-ready-before-open": manifest.get(
            "application.network-unix-host106-ready"
        )
        == "host-host-rrp-consumed",
        "typed-alternate-journey": (
            journey.get("journey_id") == PDP11_ITS_FAILOVER_JOURNEY_ID
            and journey.get("route_id") == PDP11_ITS_FAILOVER_ROUTE_ID
            and journey.get("observation_count") == 14
            and journey.get("state") == "missing-boundary"
            and journey.get("first_boundary") == "boundary:request:8"
        ),
        "ncc-reports-after-cut-from-all-imps": {5, 6, 7, 62}.issubset(report_sources),
        "mapping-remains-candidate-only": not mapping["promoted_to_topology"],
        "clean-owned-processes": cleanup.get("surviving_owned_processes") == "0",
        "clean-pinned-inputs": all(manifest.get(key) == "0" for key in clean_keys),
        "application-outcome-passed": outcome == "passed",
        "outer-runtime-cleanup": manifest.get("cleanup.outer-runtime") == "passed",
    }
    return {
        "version": 1,
        "kind": "ncc-pdp11-its-application-failover-verdict",
        "passed": all(checks.values()),
        "checks": checks,
        "fault_started_at": fault_started_at,
        "post_cut_report_sources": sorted(report_sources),
        "discovered_report_mapping": mapping,
        "journey": dict(journey),
    }


def main() -> int:
    args = parse_args()
    topology = load_shared_topology(args.topology)
    receiver = json.loads(args.receiver.read_text(encoding="utf-8"))
    relay = json.loads(args.relay.read_text(encoding="utf-8"))
    cut_state = json.loads(args.cut_state.read_text(encoding="utf-8"))
    application = key_values(args.application_evidence)
    cleanup = key_values(args.cleanup_evidence)
    manifest = key_values(args.manifest)
    outcome = args.outcome.read_text(encoding="ascii").strip()
    stream = read_message_journey_stream(args.message_journey)
    if not stream.is_terminal:
        raise ValueError("post-cut message-journey stream is not terminal")
    journey = {
        "journey_id": stream.expected.id,
        "route_id": stream.expected.route_id,
        "observation_count": len(stream.observations),
        "state": stream.diagnosis.state.value,
        "first_boundary": stream.diagnosis.first_boundary_id,
    }
    result = evaluate(
        receiver=receiver,
        relay=relay,
        cut_state=cut_state,
        application=application,
        journey=journey,
        cleanup=cleanup,
        outcome=outcome,
        manifest=manifest,
        identities={
            "topology_id": topology.id,
            "receiver_topology_id": str(receiver.get("topology_id", "")),
            "run_id": args.run_id,
            "journey_run_id": stream.run_id,
        },
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
