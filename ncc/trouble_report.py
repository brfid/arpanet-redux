"""Decode the fixed-format 1973 IMP trouble report.

The field order follows the 1973 IMP program listing.  This module deliberately
retains words whose detailed semantics are not yet established instead of
guessing at them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .report_checksum import has_valid_report_checksum


TROUBLE_REPORT_TYPE = 0o301
PATCHED_TROUBLE_REPORT_TYPE = 0o303
TROUBLE_REPORT_TYPES = frozenset((TROUBLE_REPORT_TYPE, PATCHED_TROUBLE_REPORT_TYPE))
SEMANTIC_WORD_COUNT = 31
PADDED_WORD_COUNT = 32
LINE_COUNT = 5

_LINE_DOWN = 0o100000
_LINE_LOOPED = 0o040000
_LINE_NEIGHBOR_MASK = 0o077
_LINE_MISSED_MASK = 0o377

_HOST_UP_MASKS = (0o100000, 0o040000, 0o020000, 0o010000)


class LineState(str, Enum):
    """State directly supportable from one IMP's line-status word."""

    UP = "up"
    DOWN = "down"
    LOOPED = "looped"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LineReport:
    """One modem-line entry in a trouble report."""

    interface: int
    routing_messages_sent: int
    neighbor_imp: int | None
    state: LineState
    routing_messages_missed: int
    raw_status_word: int


@dataclass(frozen=True)
class TroubleReport:
    """Decoded semantic fields from a 1973 IMP trouble report."""

    message_type: int
    anomaly_word: int
    restart_reload_word: int
    halt_pc: int
    halt_a: int
    halt_x: int
    free_buffers: int
    store_and_forward_buffers: int
    reassembly_buffers: int
    allocate_buffers: int
    imp_version: int
    host_configuration: int
    tip_version: int
    host_interface_tested: int
    test_messages_sent: int
    test_messages_received: int
    lines: tuple[LineReport, ...]
    line_speeds_word: int
    trap_pc: int
    trap_a: int
    trap_x: int
    checksum_word: int
    padding_words: tuple[int, ...]

    def host_up(self, host: int) -> bool:
        """Return the reported state for host interface 0 through 3."""

        if not 0 <= host < len(_HOST_UP_MASKS):
            raise ValueError(f"host interface must be 0..3, got {host}")
        return bool(self.anomaly_word & _HOST_UP_MASKS[host])


def _decode_line(interface: int, sent: int, status: int) -> LineReport:
    neighbor_number = (status >> 8) & _LINE_NEIGHBOR_MASK
    neighbor_imp = neighbor_number or None

    if status & _LINE_DOWN:
        state = LineState.DOWN
    elif status & _LINE_LOOPED:
        state = LineState.LOOPED
    elif neighbor_imp is not None:
        state = LineState.UP
    else:
        state = LineState.UNKNOWN

    return LineReport(
        interface=interface,
        routing_messages_sent=sent,
        neighbor_imp=neighbor_imp,
        state=state,
        routing_messages_missed=status & _LINE_MISSED_MASK,
        raw_status_word=status,
    )


def decode_trouble_report(raw_words: Iterable[int]) -> TroubleReport:
    """Decode a 31-word report, optionally followed by its 32nd pad word.

    The preserved original report code is Type 301. The 1973 patch set changes
    that first word to Type 303 while leaving the report construction intact,
    so both codes use this one fixed field layout. The emitted report retains
    its actual wire code in ``message_type`` rather than being normalized.

    The 16-bit checksum covers the report code and every semantic body word,
    but excludes the separately sent old-style leader and optional pad word.
    """

    words = tuple(raw_words)
    if len(words) not in (SEMANTIC_WORD_COUNT, PADDED_WORD_COUNT):
        raise ValueError(
            "1973 trouble reports require 31 semantic words "
            f"and may contain one pad word; got {len(words)}"
        )

    for offset, word in enumerate(words):
        if not isinstance(word, int) or isinstance(word, bool):
            raise TypeError(f"word {offset} is not an integer: {word!r}")
        if not 0 <= word <= 0xFFFF:
            raise ValueError(f"word {offset} is outside the 16-bit range: {word}")

    if words[0] not in TROUBLE_REPORT_TYPES:
        raise ValueError(
            "expected a 1973 trouble-report code "
            f"({TROUBLE_REPORT_TYPE:#o} or {PATCHED_TROUBLE_REPORT_TYPE:#o}), "
            f"got {words[0]:#o}"
        )

    if not has_valid_report_checksum(words[:SEMANTIC_WORD_COUNT]):
        raise ValueError("1973 trouble-report checksum is invalid")

    cursor = 16
    lines: list[LineReport] = []
    for interface in range(1, LINE_COUNT + 1):
        lines.append(_decode_line(interface, words[cursor], words[cursor + 1]))
        cursor += 2

    return TroubleReport(
        message_type=words[0],
        anomaly_word=words[1],
        restart_reload_word=words[2],
        halt_pc=words[3],
        halt_a=words[4],
        halt_x=words[5],
        free_buffers=words[6],
        store_and_forward_buffers=words[7],
        reassembly_buffers=words[8],
        allocate_buffers=words[9],
        imp_version=words[10],
        host_configuration=words[11],
        tip_version=words[12],
        host_interface_tested=words[13],
        test_messages_sent=words[14],
        test_messages_received=words[15],
        lines=tuple(lines),
        line_speeds_word=words[26],
        trap_pc=words[27],
        trap_a=words[28],
        trap_x=words[29],
        checksum_word=words[30],
        padding_words=words[31:],
    )
