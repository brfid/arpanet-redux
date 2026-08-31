"""Interpret old-style IMP-to-host leaders before 1973 report decoding.

The pinned 1973 firmware emits the two-word leader retained in Appendix A of
the January 1976 revision of BBN Report 1822.  This module keeps that leader
separate from the H316 UDP transport and from the report body: the transport
reassembles a complete message, this module identifies its reporting IMP, and
the existing decoder interprets the versioned report payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .events import NccEvent, throughput_report_events, trouble_report_events
from .host_interface import IngressMessage
from .throughput_report import ThroughputReport, decode_throughput_report
from .trouble_report import TroubleReport, decode_trouble_report


OLD_STYLE_LEADER_WORD_COUNT = 2
_PRIORITY = 0x8000
_FROM_IMP = 0x4000
_TRACE = 0x2000
_OCTAL = 0x1000
_MESSAGE_TYPE_MASK = 0x0F00
_MESSAGE_TYPE_SHIFT = 8
_SOURCE_HOST_MASK = 0x00C0
_SOURCE_HOST_SHIFT = 6
_SOURCE_IMP_MASK = 0x003F
_MESSAGE_ID_MASK = 0xFFF0
_MESSAGE_ID_SHIFT = 4
_SUBTYPE_MASK = 0x000F


class ImpToHostMessageError(ValueError):
    """Raised when a completed host message is not a supported 1973 report."""


@dataclass(frozen=True)
class OldStyleImpToHostLeader:
    """The two-word pre-1976 IMP-to-host leader from BBN Report 1822."""

    priority: bool
    from_imp: bool
    trace: bool
    octal: bool
    message_type: int
    source_host_field: int
    source_imp: int
    message_id: int
    subtype: int

    @property
    def source_host(self) -> int:
        """Return the source host, including the documented fake-host mapping."""

        if self.from_imp:
            return 252 + self.source_host_field
        return self.source_host_field


@dataclass(frozen=True)
class ImpToHostMessage:
    """One complete H316 ingress message split into leader and body."""

    first_sequence: int
    final_sequence: int
    leader: OldStyleImpToHostLeader
    body_words: tuple[int, ...]


@dataclass(frozen=True)
class ImpToHostTroubleReport:
    """A 1973 trouble report with its separately validated IMP-to-host leader."""

    message: ImpToHostMessage
    report: TroubleReport


@dataclass(frozen=True)
class ImpToHostThroughputReport:
    """A Type 302 report with its separately validated IMP-to-host leader."""

    message: ImpToHostMessage
    report: ThroughputReport


def decode_old_style_imp_to_host_leader(words: Iterable[int]) -> OldStyleImpToHostLeader:
    """Decode exactly the two words of the 1973-compatible IMP-to-host leader."""

    first, second = _leader_words(words)
    return OldStyleImpToHostLeader(
        priority=bool(first & _PRIORITY),
        from_imp=bool(first & _FROM_IMP),
        trace=bool(first & _TRACE),
        octal=bool(first & _OCTAL),
        message_type=(first & _MESSAGE_TYPE_MASK) >> _MESSAGE_TYPE_SHIFT,
        source_host_field=(first & _SOURCE_HOST_MASK) >> _SOURCE_HOST_SHIFT,
        source_imp=first & _SOURCE_IMP_MASK,
        message_id=(second & _MESSAGE_ID_MASK) >> _MESSAGE_ID_SHIFT,
        subtype=second & _SUBTYPE_MASK,
    )


def decode_imp_to_host_message(message: IngressMessage) -> ImpToHostMessage:
    """Separate a reassembled 1973 IMP-to-host message into leader and body."""

    if len(message.words) < OLD_STYLE_LEADER_WORD_COUNT:
        raise ImpToHostMessageError(
            "IMP-to-host message omits the required two-word old-style leader"
        )
    return ImpToHostMessage(
        first_sequence=message.first_sequence,
        final_sequence=message.final_sequence,
        leader=decode_old_style_imp_to_host_leader(message.words[:2]),
        body_words=message.words[OLD_STYLE_LEADER_WORD_COUNT:],
    )


def decode_trouble_report_imp_to_host_message(
    message: IngressMessage,
) -> ImpToHostTroubleReport:
    """Decode one genuine 1973 trouble report and retain its source leader.

    A report code is a body format, not an IMP-to-host leader message type. The
    completed message must therefore carry an IMP-originated regular leader,
    then a supported 1973 report body. A source IMP of zero cannot support an
    attributed NCC observation and is rejected rather than substituted from
    topology.
    """

    decoded = decode_imp_to_host_message(message)
    _require_reporting_imp(decoded, "trouble report")
    try:
        report = decode_trouble_report(decoded.body_words)
    except (TypeError, ValueError) as error:
        raise ImpToHostMessageError(f"invalid 1973 trouble-report body: {error}") from error
    return ImpToHostTroubleReport(message=decoded, report=report)


def decode_throughput_report_imp_to_host_message(
    message: IngressMessage,
) -> ImpToHostThroughputReport:
    """Decode one genuine Type 302 report and retain its source leader."""

    decoded = decode_imp_to_host_message(message)
    _require_reporting_imp(decoded, "throughput report")
    try:
        report = decode_throughput_report(decoded.body_words)
    except (TypeError, ValueError) as error:
        raise ImpToHostMessageError(f"invalid Type 302 body: {error}") from error
    return ImpToHostThroughputReport(message=decoded, report=report)


def trouble_report_events_from_imp_to_host_message(
    message: IngressMessage,
    *,
    observed_at: str,
    sequence_start: int = 1,
) -> tuple[NccEvent, ...]:
    """Emit direct 1973 trouble-report observations using the leader source."""

    decoded = decode_trouble_report_imp_to_host_message(message)
    return trouble_report_events(
        decoded.report,
        source_imp=decoded.message.leader.source_imp,
        observed_at=observed_at,
        sequence_start=sequence_start,
    )


def throughput_report_events_from_imp_to_host_message(
    message: IngressMessage,
    *,
    observed_at: str,
    sequence_start: int = 1,
) -> tuple[NccEvent, ...]:
    """Emit a direct Type 302 observation using the leader's source IMP."""

    decoded = decode_throughput_report_imp_to_host_message(message)
    return throughput_report_events(
        decoded.report,
        source_imp=decoded.message.leader.source_imp,
        observed_at=observed_at,
        sequence_start=sequence_start,
    )


def _require_reporting_imp(decoded: ImpToHostMessage, label: str) -> None:
    leader = decoded.leader
    if not leader.from_imp:
        raise ImpToHostMessageError(f"{label} requires an IMP-originated leader")
    if leader.message_type != 0:
        raise ImpToHostMessageError(
            f"{label} requires a regular IMP-to-host leader message type"
        )
    if leader.source_imp == 0:
        raise ImpToHostMessageError(f"{label} leader omits a source IMP")


def _leader_words(words: Iterable[int]) -> tuple[int, int]:
    values = tuple(words)
    if len(values) != OLD_STYLE_LEADER_WORD_COUNT:
        raise ImpToHostMessageError(
            "old-style IMP-to-host leader requires exactly two 16-bit words"
        )
    for index, word in enumerate(values):
        if not isinstance(word, int) or isinstance(word, bool):
            raise ImpToHostMessageError(f"leader word {index} is not an integer")
        if not 0 <= word <= 0xFFFF:
            raise ImpToHostMessageError(
                f"leader word {index} is outside the 16-bit range"
            )
    return values[0], values[1]
