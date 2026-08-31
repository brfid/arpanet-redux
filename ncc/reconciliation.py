"""Topology-aware reconciliation of direct historical NCC observations.

The 1973 trouble-report decoder deliberately reports only an IMP's local line endpoint.
This module owns the separate inference step that pairs those endpoints against
project-authored nominal topology. It never reads raw simulator output or
substitutes modern harness state for a missing historical report.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import re

from .events import NccEvent
from .shared_topology import SharedTopology


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_DIRECT_LINE_STATES = frozenset({"up", "down", "looped", "unknown"})


class ReconciliationError(ValueError):
    """Raised when observations cannot safely support a topology conclusion."""


class LineState(str, Enum):
    """A topology-aware line condition suitable for an NCC operator surface."""

    UP = "up"
    DOWN = "down"
    LOOPED = "looped"
    MINUS_DOWN = "minus-down"
    PLUS_DOWN = "plus-down"
    MINUS_LOOPED = "minus-looped"
    PLUS_LOOPED = "plus-looped"
    UNKNOWN = "unknown"
    STALE = "stale"
    CONTRADICTORY = "contradictory"


class ImpState(str, Enum):
    """A report-reachability condition, not an IMP hardware diagnosis."""

    UP = "up"
    UNKNOWN = "unknown"
    STALE = "stale"
    PARTITIONED = "partitioned"


@dataclass(frozen=True, order=True)
class Endpoint:
    """One configured 1973 trouble-report line endpoint."""

    imp: int
    interface: int

    def __post_init__(self) -> None:
        if self.imp <= 0:
            raise ReconciliationError(f"endpoint IMP must be positive, got {self.imp}")
        if self.interface <= 0:
            raise ReconciliationError(
                f"endpoint interface must be positive, got {self.interface}"
            )

    @property
    def subject(self) -> str:
        """Return the direct-event subject used by the trouble-report decoder."""

        return f"imp:{self.imp}:line:{self.interface}"


@dataclass(frozen=True)
class NominalLine:
    """One configured line that pairs two distinct IMP interface endpoints."""

    id: str
    first: Endpoint
    second: Endpoint

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.id):
            raise ReconciliationError(f"line id is not stable: {self.id!r}")
        if self.first == self.second:
            raise ReconciliationError(f"line {self.id!r} repeats one endpoint")
        if self.first.imp == self.second.imp:
            raise ReconciliationError(
                f"line {self.id!r} must connect distinct IMPs for plus/minus direction"
            )

    @property
    def endpoints(self) -> tuple[Endpoint, Endpoint]:
        """Return endpoints in stable local declaration order."""

        return (self.first, self.second)

    @property
    def minus_endpoint(self) -> Endpoint:
        """Return the lower-numbered IMP endpoint, the historical minus end."""

        return min(self.endpoints)

    @property
    def plus_endpoint(self) -> Endpoint:
        """Return the higher-numbered IMP endpoint, the historical plus end."""

        return max(self.endpoints)

    def peer(self, endpoint: Endpoint) -> Endpoint:
        """Return the endpoint at the opposite configured end of this line."""

        if endpoint == self.first:
            return self.second
        if endpoint == self.second:
            return self.first
        raise ReconciliationError(f"endpoint {endpoint!r} is not part of line {self.id!r}")


@dataclass(frozen=True)
class NominalTopology:
    """The minimal nominal topology input required for endpoint reconciliation."""

    lines: tuple[NominalLine, ...]

    def __post_init__(self) -> None:
        if not self.lines:
            raise ReconciliationError("nominal topology must contain at least one line")
        line_ids: set[str] = set()
        endpoints: set[Endpoint] = set()
        for line in self.lines:
            if line.id in line_ids:
                raise ReconciliationError(f"nominal topology duplicates line {line.id!r}")
            line_ids.add(line.id)
            for endpoint in line.endpoints:
                if endpoint in endpoints:
                    raise ReconciliationError(
                        f"nominal topology reuses endpoint {endpoint.subject!r}"
                    )
                endpoints.add(endpoint)

    @property
    def imps(self) -> tuple[int, ...]:
        """Return all configured IMP identities in ascending order."""

        return tuple(sorted({endpoint.imp for line in self.lines for endpoint in line.endpoints}))

    def incident_lines(self, imp: int) -> tuple[NominalLine, ...]:
        """Return all nominal lines connected to one IMP."""

        return tuple(line for line in self.lines if imp in {line.first.imp, line.second.imp})


@dataclass(frozen=True)
class ReconciledLine:
    """One inferred line condition and the direct events supporting it."""

    id: str
    state: LineState
    supporting_sequences: tuple[int, ...]


@dataclass(frozen=True)
class ReconciledImp:
    """One inferred report-reachability condition and its direct support."""

    imp: int
    state: ImpState
    supporting_sequences: tuple[int, ...]


@dataclass(frozen=True)
class Reconciliation:
    """The complete line and IMP condition view for one observation time."""

    lines: tuple[ReconciledLine, ...]
    imps: tuple[ReconciledImp, ...]


@dataclass(frozen=True)
class _EndpointObservation:
    event: NccEvent
    observed_at: datetime
    state: str
    matches_topology: bool


@dataclass(frozen=True)
class _ImpObservation:
    event: NccEvent
    observed_at: datetime


def nominal_topology_from_shared(topology: SharedTopology) -> NominalTopology:
    """Build the existing reducer input from explicit shared report-line mappings."""

    lines = []
    for binding in topology.modem_interfaces:
        first_report_line = binding.first_report_line
        second_report_line = binding.second_report_line
        if first_report_line is None and second_report_line is None:
            continue
        if first_report_line is None or second_report_line is None:
            raise ReconciliationError(
                f"shared modem binding {binding.id!r} has a one-sided report-line mapping"
            )
        lines.append(
            NominalLine(
                binding.id,
                Endpoint(
                    imp=_shared_imp_number(binding.first_imp_id),
                    interface=first_report_line,
                ),
                Endpoint(
                    imp=_shared_imp_number(binding.second_imp_id),
                    interface=second_report_line,
                ),
            )
        )
    if not lines:
        raise ReconciliationError(
            f"shared topology {topology.id!r} has no reciprocal report-line mapping"
        )
    return NominalTopology(tuple(lines))


def reconcile(
    topology: NominalTopology,
    events: Iterable[NccEvent],
    *,
    started_at: str,
    observed_at: str,
    report_interval: timedelta,
) -> Reconciliation:
    """Pair fresh endpoint observations and classify missing-report conditions.

    ``started_at`` establishes when a report first becomes due. A missing report
    is unknown until one report interval has elapsed, then stale. An IMP becomes
    partitioned only when its own report is stale and at least two fresh,
    independent configured peers report their endpoints toward it down. That is
    a reachability inference, never a claim that the IMP hardware has failed.
    """

    started = _timestamp(started_at, "started_at")
    current = _timestamp(observed_at, "observed_at")
    if current < started:
        raise ReconciliationError("observed_at precedes started_at")
    if report_interval <= timedelta(0):
        raise ReconciliationError("report_interval must be positive")

    ordered_events = tuple(events)
    _validate_event_order(ordered_events, current)
    endpoints = {
        endpoint.subject: (line, endpoint)
        for line in topology.lines
        for endpoint in line.endpoints
    }
    endpoint_observations: dict[Endpoint, _EndpointObservation] = {}
    imp_observations: dict[int, _ImpObservation] = {}
    for event in ordered_events:
        if event.event_type == "line-endpoint.state" and event.subject in endpoints:
            line, endpoint = endpoints[event.subject]
            _validate_endpoint_event(event, endpoint)
            endpoint_observations[endpoint] = _EndpointObservation(
                event=event,
                observed_at=_timestamp(event.observed_at, "event.observed_at"),
                state=event.state,
                matches_topology=_matches_expected_peer(event, line, endpoint),
            )
        elif event.event_type == "imp.report" and event.source.imp in topology.imps:
            if event.subject != f"imp:{event.source.imp}":
                raise ReconciliationError(
                    f"IMP report event {event.sequence} source IMP does not match its subject"
                )
            if event.source.kind != "imp-trouble-report" or event.state != "received":
                raise ReconciliationError(
                    f"IMP report event {event.sequence} is not a direct trouble report"
                )
            if event.source.imp in topology.imps:
                imp_observations[event.source.imp] = _ImpObservation(
                    event=event,
                    observed_at=_timestamp(event.observed_at, "event.observed_at"),
                )

    lines = tuple(
        _reconcile_line(line, endpoint_observations, current, report_interval)
        for line in topology.lines
    )
    imps = tuple(
        _reconcile_imp(
            imp,
            topology,
            endpoint_observations,
            imp_observations.get(imp),
            started,
            current,
            report_interval,
        )
        for imp in topology.imps
    )
    return Reconciliation(lines=lines, imps=imps)


def _reconcile_line(
    line: NominalLine,
    observations: dict[Endpoint, _EndpointObservation],
    current: datetime,
    report_interval: timedelta,
) -> ReconciledLine:
    minus = observations.get(line.minus_endpoint)
    plus = observations.get(line.plus_endpoint)
    support = _support_sequences(minus, plus)
    if minus is None and plus is None:
        return ReconciledLine(line.id, LineState.UNKNOWN, support)
    if any(
        observation is not None and _expired(observation.observed_at, current, report_interval)
        for observation in (minus, plus)
    ):
        return ReconciledLine(line.id, LineState.STALE, support)
    if minus is None or plus is None:
        return ReconciledLine(line.id, LineState.UNKNOWN, support)
    if not minus.matches_topology or not plus.matches_topology:
        return ReconciledLine(line.id, LineState.CONTRADICTORY, support)
    return ReconciledLine(line.id, _paired_line_state(minus.state, plus.state), support)


def _reconcile_imp(
    imp: int,
    topology: NominalTopology,
    endpoint_observations: dict[Endpoint, _EndpointObservation],
    report: _ImpObservation | None,
    started: datetime,
    current: datetime,
    report_interval: timedelta,
) -> ReconciledImp:
    report_stale = report is not None and _expired(
        report.observed_at, current, report_interval
    )
    report_missing = report is None and _expired(started, current, report_interval)
    if report is not None and not report_stale:
        return ReconciledImp(imp, ImpState.UP, (report.event.sequence,))
    if not report_stale and not report_missing:
        return ReconciledImp(imp, ImpState.UNKNOWN, ())

    peer_down = []
    for line in topology.incident_lines(imp):
        local = next(endpoint for endpoint in line.endpoints if endpoint.imp == imp)
        peer = line.peer(local)
        observation = endpoint_observations.get(peer)
        if (
            observation is not None
            and not _expired(observation.observed_at, current, report_interval)
            and observation.matches_topology
            and observation.state == "down"
        ):
            peer_down.append(observation)
    if len(peer_down) >= 2 and len(peer_down) == len(topology.incident_lines(imp)):
        support = _support_sequences(report, *peer_down)
        return ReconciledImp(imp, ImpState.PARTITIONED, support)
    support = _support_sequences(report)
    return ReconciledImp(imp, ImpState.STALE, support)


def _paired_line_state(minus: str, plus: str) -> LineState:
    if minus == plus:
        return {
            "up": LineState.UP,
            "down": LineState.DOWN,
            "looped": LineState.LOOPED,
            "unknown": LineState.UNKNOWN,
        }[minus]
    if "unknown" in {minus, plus}:
        return LineState.UNKNOWN
    if {minus, plus} == {"down", "looped"}:
        return LineState.CONTRADICTORY
    return {
        ("down", "up"): LineState.MINUS_DOWN,
        ("up", "down"): LineState.PLUS_DOWN,
        ("looped", "up"): LineState.MINUS_LOOPED,
        ("up", "looped"): LineState.PLUS_LOOPED,
    }[(minus, plus)]


def _validate_event_order(events: tuple[NccEvent, ...], current: datetime) -> None:
    previous_sequence = -1
    previous_time: datetime | None = None
    for event in events:
        timestamp = _timestamp(event.observed_at, "event.observed_at")
        if event.sequence <= previous_sequence:
            raise ReconciliationError("event sequences must be strictly increasing")
        if previous_time is not None and timestamp < previous_time:
            raise ReconciliationError("event timestamps must be non-decreasing")
        if timestamp > current:
            raise ReconciliationError("event observation time is later than observed_at")
        previous_sequence = event.sequence
        previous_time = timestamp


def _validate_endpoint_event(event: NccEvent, endpoint: Endpoint) -> None:
    if event.source.kind != "imp-trouble-report":
        raise ReconciliationError(
            f"line endpoint event {event.sequence} is not a direct trouble-report observation"
        )
    if event.source.imp != endpoint.imp:
        raise ReconciliationError(
            f"line endpoint event {event.sequence} source IMP does not match its subject"
        )
    if event.state not in _DIRECT_LINE_STATES:
        raise ReconciliationError(
            f"line endpoint event {event.sequence} has unsupported state {event.state!r}"
        )


def _matches_expected_peer(event: NccEvent, line: NominalLine, endpoint: Endpoint) -> bool:
    if event.state == "unknown":
        return True
    reported_peer = event.details.get("neighbor_imp")
    if event.state == "down" and reported_peer is None:
        # The recovered firmware clears its remembered neighbor when it kills a
        # line. The explicitly mapped source endpoint still supplies identity;
        # any neighbor that is present must continue to match the configured peer.
        return True
    return reported_peer == line.peer(endpoint).imp


def _support_sequences(*observations: _EndpointObservation | _ImpObservation | None) -> tuple[int, ...]:
    return tuple(sorted(observation.event.sequence for observation in observations if observation is not None))


def _expired(observed: datetime, current: datetime, interval: timedelta) -> bool:
    return current - observed > interval


def _timestamp(value: str, location: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReconciliationError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").astimezone(
            timezone.utc
        )
    except ValueError as error:
        raise ReconciliationError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error


def _shared_imp_number(identifier: str) -> int:
    prefix, separator, number = identifier.partition(":")
    if prefix != "imp" or separator != ":" or not number.isdecimal():
        raise ReconciliationError(
            f"shared report-line identity does not name an IMP: {identifier!r}"
        )
    return int(number)
