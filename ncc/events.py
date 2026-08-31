"""Topology-neutral events emitted from historical NCC telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .throughput_report import ThroughputReport
from .trouble_report import TroubleReport


@dataclass(frozen=True)
class EventSource:
    """Where an NCC observation came from."""

    kind: str
    imp: int


@dataclass(frozen=True)
class NccEvent:
    """Versioned event suitable for a recorder or live visualization."""

    sequence: int
    observed_at: str
    event_type: str
    subject: str
    state: str
    source: EventSource
    details: Mapping[str, Any] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sequence": self.sequence,
            "observed_at": self.observed_at,
            "type": self.event_type,
            "subject": self.subject,
            "state": self.state,
            "source": {"kind": self.source.kind, "imp": self.source.imp},
            "details": dict(self.details),
        }


def trouble_report_events(
    report: TroubleReport,
    *,
    source_imp: int,
    observed_at: str,
    sequence_start: int = 1,
) -> tuple[NccEvent, ...]:
    """Translate one report into facts that do not require a topology model."""

    if source_imp <= 0:
        raise ValueError(f"source IMP must be positive, got {source_imp}")
    if sequence_start < 0:
        raise ValueError(f"sequence_start must be non-negative, got {sequence_start}")

    source = EventSource(kind="imp-trouble-report", imp=source_imp)
    events = [
        NccEvent(
            sequence=sequence_start,
            observed_at=observed_at,
            event_type="imp.report",
            subject=f"imp:{source_imp}",
            state="received",
            source=source,
            details={
                "message_type": report.message_type,
                "imp_version": report.imp_version,
                "free_buffers": report.free_buffers,
                "store_and_forward_buffers": report.store_and_forward_buffers,
                "reassembly_buffers": report.reassembly_buffers,
                "allocate_buffers": report.allocate_buffers,
            },
        )
    ]

    for host in range(4):
        events.append(
            NccEvent(
                sequence=sequence_start + len(events),
                observed_at=observed_at,
                event_type="host-interface.state",
                subject=f"imp:{source_imp}:host:{host}",
                state="up" if report.host_up(host) else "down",
                source=source,
            )
        )

    for line in report.lines:
        events.append(
            NccEvent(
                sequence=sequence_start + len(events),
                observed_at=observed_at,
                event_type="line-endpoint.state",
                subject=f"imp:{source_imp}:line:{line.interface}",
                state=line.state.value,
                source=source,
                details={
                    "neighbor_imp": line.neighbor_imp,
                    "routing_messages_sent": line.routing_messages_sent,
                    "routing_messages_missed": line.routing_messages_missed,
                },
            )
        )

    return tuple(events)


def throughput_report_events(
    report: ThroughputReport,
    *,
    source_imp: int,
    observed_at: str,
    sequence_start: int = 1,
) -> tuple[NccEvent, ...]:
    """Translate one throughput report without deriving rates or topology state."""

    if source_imp <= 0:
        raise ValueError(f"source IMP must be positive, got {source_imp}")
    if sequence_start < 0:
        raise ValueError(f"sequence_start must be non-negative, got {sequence_start}")
    source = EventSource(kind="imp-throughput-report", imp=source_imp)
    return (
        NccEvent(
            sequence=sequence_start,
            observed_at=observed_at,
            event_type="imp.throughput-report",
            subject=f"imp:{source_imp}",
            state="received",
            source=source,
            details={
                "message_type": report.message_type,
                "line_throughput": [
                    {
                        "interface": line.interface,
                        "packets": line.packets,
                        "words": line.words,
                    }
                    for line in report.lines
                ],
                "host_throughput": [
                    {
                        "host": host.host,
                        "messages_from_host_to_network": host.messages_from_host_to_network,
                        "messages_from_network_to_host": host.messages_from_network_to_host,
                        "packets_from_host_to_network": host.packets_from_host_to_network,
                        "packets_from_network_to_host": host.packets_from_network_to_host,
                        "messages_from_host_to_local_host": host.messages_from_host_to_local_host,
                        "messages_from_local_host_to_host": host.messages_from_local_host_to_host,
                        "packets_from_host_to_local_host": host.packets_from_host_to_local_host,
                        "packets_from_local_host_to_host": host.packets_from_local_host_to_host,
                        "words_from_host_to_imp": host.words_from_host_to_imp,
                        "words_from_imp_to_host": host.words_from_imp_to_host,
                    }
                    for host in report.hosts
                ],
                "checksum_word": report.checksum_word,
                "padding_words": list(report.padding_words),
            },
        ),
    )
