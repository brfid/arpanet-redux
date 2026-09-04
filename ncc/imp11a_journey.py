"""Strict adapter for versioned IMP11-A input-DMA evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass


_PREFIX = rb"DBG\((\d+)\)> IMP INPUT: IMP "
_MESSAGE = re.compile(
    _PREFIX + rb"INPUT-MESSAGE version=1 message=(\d+)\Z"
)
_DMA = re.compile(
    _PREFIX
    + rb"INPUT-DMA version=1 message=(\d+) word=(\d+) "
    + rb"address=([0-7]{6}) wire=([0-7]{6}) guest=([0-7]{6})\Z"
)
_COMPLETE = re.compile(
    _PREFIX + rb"INPUT-COMPLETE version=1 message=(\d+) words=(\d+)\Z"
)
_MARKER = b"IMP INPUT-"


class Imp11aTraceError(ValueError):
    """Raised when an IMP11-A trace cannot prove one complete DMA message."""


@dataclass(frozen=True)
class Imp11aInputWord:
    """One network-order word written to PDP-11 memory by the IMP11-A."""

    word_index: int
    dma_address: int
    wire_value: int
    guest_value: int
    store_tick: int


@dataclass(frozen=True)
class Imp11aInputMessage:
    """One complete input message reconstructed only from post-store records."""

    source_local_sequence: int
    start_tick: int
    complete_tick: int
    words: tuple[Imp11aInputWord, ...]

    @property
    def wire_words(self) -> tuple[int, ...]:
        return tuple(word.wire_value for word in self.words)


@dataclass
class _PendingMessage:
    sequence: int
    start_tick: int
    words: list[Imp11aInputWord]


def parse_imp11a_trace(content: bytes) -> tuple[Imp11aInputMessage, ...]:
    """Parse complete version-1 message, post-store DMA, and completion groups."""

    if not isinstance(content, bytes):
        raise TypeError("IMP11-A trace content must be bytes")
    messages: list[Imp11aInputMessage] = []
    pending: _PendingMessage | None = None
    previous_sequence: int | None = None
    previous_tick: int | None = None

    for line in content.splitlines():
        if _MARKER not in line:
            continue
        marker_start = line.find(b"DBG(")
        record = line[marker_start:] if marker_start >= 0 else line

        message_match = _MESSAGE.fullmatch(record)
        if message_match is not None:
            if pending is not None:
                raise Imp11aTraceError(
                    "new IMP11-A input message interrupts an incomplete message"
                )
            tick, sequence = (
                int(message_match.group(index)) for index in range(1, 3)
            )
            if sequence <= 0:
                raise Imp11aTraceError("IMP11-A input message sequence is not positive")
            if previous_sequence is not None and sequence != previous_sequence + 1:
                raise Imp11aTraceError(
                    "IMP11-A input message sequence is not contiguous"
                )
            _require_monotonic_tick(previous_tick, tick)
            pending = _PendingMessage(sequence, tick, [])
            previous_sequence = sequence
            previous_tick = tick
            continue

        dma_match = _DMA.fullmatch(record)
        if dma_match is not None:
            if pending is None:
                raise Imp11aTraceError("IMP11-A DMA store has no pending message")
            tick, sequence, word_index = (
                int(dma_match.group(index)) for index in range(1, 4)
            )
            dma_address = int(dma_match.group(4), 8)
            wire_value = int(dma_match.group(5), 8)
            guest_value = int(dma_match.group(6), 8)
            if sequence != pending.sequence:
                raise Imp11aTraceError("IMP11-A DMA store changes message identity")
            if word_index != len(pending.words):
                raise Imp11aTraceError("IMP11-A DMA word index is not contiguous")
            if dma_address > 0o777776 or dma_address % 2:
                raise Imp11aTraceError("IMP11-A DMA address is invalid")
            if wire_value > 0o177777 or guest_value > 0o177777:
                raise Imp11aTraceError("IMP11-A DMA word is not 16 bits")
            if guest_value != _pdp11_memory_word(wire_value):
                raise Imp11aTraceError(
                    "IMP11-A DMA guest value does not match the wire word"
                )
            _require_monotonic_tick(previous_tick, tick)
            pending.words.append(
                Imp11aInputWord(
                    word_index=word_index,
                    dma_address=dma_address,
                    wire_value=wire_value,
                    guest_value=guest_value,
                    store_tick=tick,
                )
            )
            previous_tick = tick
            continue

        complete_match = _COMPLETE.fullmatch(record)
        if complete_match is not None:
            if pending is None:
                raise Imp11aTraceError(
                    "IMP11-A input completion has no pending message"
                )
            tick, sequence, word_count = (
                int(complete_match.group(index)) for index in range(1, 4)
            )
            if sequence != pending.sequence:
                raise Imp11aTraceError(
                    "IMP11-A input completion changes message identity"
                )
            if word_count <= 0 or word_count != len(pending.words):
                raise Imp11aTraceError(
                    "IMP11-A input completion has the wrong word count"
                )
            _require_monotonic_tick(previous_tick, tick)
            messages.append(
                Imp11aInputMessage(
                    source_local_sequence=sequence,
                    start_tick=pending.start_tick,
                    complete_tick=tick,
                    words=tuple(pending.words),
                )
            )
            pending = None
            previous_tick = tick
            continue

        raise Imp11aTraceError("malformed or unsupported IMP11-A trace record")

    if pending is not None:
        raise Imp11aTraceError("IMP11-A trace ends with an incomplete message")
    return tuple(messages)


def _pdp11_memory_word(wire_value: int) -> int:
    return ((wire_value << 8) & 0xFFFF) | (wire_value >> 8)


def _require_monotonic_tick(previous: int | None, current: int) -> None:
    if previous is not None and current < previous:
        raise Imp11aTraceError("IMP11-A simulator tick moved backward")
