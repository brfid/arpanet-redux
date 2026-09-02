"""Strict adapter for versioned KA10 IMP input-assembly evidence."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass


_PREFIX = rb"DBG\((\d+)\)> IMP ASSEMBLY: IMP "
_MESSAGE = re.compile(
    _PREFIX + rb"INPUT-MESSAGE version=1 message=(\d+) bits=(\d+)\Z"
)
_ASSEMBLY = re.compile(
    _PREFIX
    + rb"INPUT-ASSEMBLY version=1 message=(\d+) word=(\d+) "
    + rb"message_bits=(\d+) start=(\d+) width=(\d+) valid=(\d+) "
    + rb"last=([01]) value=([0-7]{12})\Z"
)
_CONSUME = re.compile(
    _PREFIX
    + rb"INPUT-CONSUME version=1 message=(\d+) word=(\d+) width=(\d+) "
    + rb"valid=(\d+) last=([01]) value=([0-7]{12}) PC=([0-7]+)\Z"
)
_MARKER = b"IMP INPUT-"
_NEW_FORMAT_FLAG = 0x0F00
_NEW_TRACE = 0x08
_NEW_OCTAL = 0x04
_NEW_FOR_IMP = 252
_NEW_PRIORITY = 0x80
_OLD_PRIORITY = 0x08
_OLD_FOR_IMP = 0x04
_OLD_TRACE = 0x02
_OLD_OCTAL = 0x01
_REGULAR = 0
_UNCONTROLLED = 3
_NOP = 4


class Ka10ImpTraceError(ValueError):
    """Raised when a KA10 input trace cannot prove exact guest consumption."""


@dataclass(frozen=True)
class Ka10ImpInputWord:
    """One assembled KA10 word paired with the guest DATAI that consumed it."""

    word_index: int
    start_bit: int
    width: int
    valid_bits: int
    last: bool
    value: int
    assembly_tick: int
    consume_tick: int
    program_counter: int


@dataclass(frozen=True)
class Ka10ImpInputMessage:
    """One complete NCP input message reconstructed from consumed word records."""

    source_local_sequence: int
    receive_tick: int
    bit_count: int
    words: tuple[Ka10ImpInputWord, ...]
    content: bytes


@dataclass
class _PendingAssembly:
    tick: int
    word_index: int
    start_bit: int
    width: int
    valid_bits: int
    last: bool
    value: int


@dataclass
class _PendingMessage:
    sequence: int
    receive_tick: int
    bit_count: int
    words: list[Ka10ImpInputWord]
    assembly: _PendingAssembly | None = None


def parse_ka10_imp_trace(content: bytes) -> tuple[Ka10ImpInputMessage, ...]:
    """Parse complete version-1 receive, assembly, and DATAI record groups."""

    if not isinstance(content, bytes):
        raise TypeError("KA10 IMP trace content must be bytes")
    messages: list[Ka10ImpInputMessage] = []
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
                raise Ka10ImpTraceError("new KA10 input message interrupts an incomplete message")
            tick, sequence, bit_count = (
                int(message_match.group(index)) for index in range(1, 4)
            )
            if bit_count <= 0 or bit_count % 8:
                raise Ka10ImpTraceError("KA10 input message size is not positive whole octets")
            if previous_sequence is not None and sequence != previous_sequence + 1:
                raise Ka10ImpTraceError("KA10 input message sequence is not contiguous")
            _require_monotonic_tick(previous_tick, tick)
            pending = _PendingMessage(sequence, tick, bit_count, [])
            previous_sequence = sequence
            previous_tick = tick
            continue

        assembly_match = _ASSEMBLY.fullmatch(record)
        if assembly_match is not None:
            if pending is None or pending.assembly is not None:
                raise Ka10ImpTraceError("KA10 assembly has no unique pending message")
            (
                tick,
                sequence,
                word_index,
                message_bits,
                start_bit,
                width,
                valid_bits,
                last,
            ) = (int(assembly_match.group(index)) for index in range(1, 9))
            value = int(assembly_match.group(9), 8)
            if sequence != pending.sequence or message_bits != pending.bit_count:
                raise Ka10ImpTraceError("KA10 assembly changes its message identity or size")
            if word_index != len(pending.words):
                raise Ka10ImpTraceError("KA10 assembly word index is not contiguous")
            expected_start = sum(word.width for word in pending.words)
            if start_bit != expected_start:
                raise Ka10ImpTraceError("KA10 assembly start bit is not contiguous")
            if width not in (32, 36) or (width == 32 and value & 0xF):
                raise Ka10ImpTraceError("KA10 assembly width or alignment is invalid")
            expected_valid = min(width, max(pending.bit_count - start_bit, 0))
            expected_last = start_bit + width >= pending.bit_count
            if valid_bits != expected_valid or bool(last) != expected_last:
                raise Ka10ImpTraceError("KA10 assembly valid-bit or last-word state is invalid")
            _require_monotonic_tick(previous_tick, tick)
            pending.assembly = _PendingAssembly(
                tick,
                word_index,
                start_bit,
                width,
                valid_bits,
                bool(last),
                value,
            )
            previous_tick = tick
            continue

        consume_match = _CONSUME.fullmatch(record)
        if consume_match is not None:
            if pending is None or pending.assembly is None:
                raise Ka10ImpTraceError("KA10 DATAI consumption has no pending assembly")
            tick, sequence, word_index, width, valid_bits, last = (
                int(consume_match.group(index)) for index in range(1, 7)
            )
            value = int(consume_match.group(7), 8)
            program_counter = int(consume_match.group(8), 8)
            assembly = pending.assembly
            if (
                sequence != pending.sequence
                or word_index != assembly.word_index
                or width != assembly.width
                or valid_bits != assembly.valid_bits
                or bool(last) != assembly.last
                or value != assembly.value
            ):
                raise Ka10ImpTraceError("KA10 DATAI consumption does not match its assembly")
            _require_monotonic_tick(previous_tick, tick)
            pending.words.append(
                Ka10ImpInputWord(
                    word_index=word_index,
                    start_bit=assembly.start_bit,
                    width=width,
                    valid_bits=valid_bits,
                    last=bool(last),
                    value=value,
                    assembly_tick=assembly.tick,
                    consume_tick=tick,
                    program_counter=program_counter,
                )
            )
            pending.assembly = None
            previous_tick = tick
            if bool(last):
                reconstructed = _reconstruct(pending)
                messages.append(
                    Ka10ImpInputMessage(
                        source_local_sequence=pending.sequence,
                        receive_tick=pending.receive_tick,
                        bit_count=pending.bit_count,
                        words=tuple(pending.words),
                        content=reconstructed,
                    )
                )
                pending = None
            continue

        raise Ka10ImpTraceError("malformed or unsupported KA10 IMP trace record")

    if pending is not None:
        raise Ka10ImpTraceError("KA10 IMP trace ends with an incomplete message")
    return tuple(messages)


def ka10_message_as_nosc_words(message: Ka10ImpInputMessage) -> tuple[int, ...]:
    """Invert the pinned canonical short-to-long 1822 leader conversion."""

    if message.bit_count < 96 or message.bit_count % 16:
        raise Ka10ImpTraceError("KA10 message is not a whole canonical long leader")
    long_words = struct.unpack(f">{len(message.content) // 2}H", message.content)
    if long_words[0] != _NEW_FORMAT_FLAG:
        raise Ka10ImpTraceError("KA10 message lacks the canonical new-format flag")
    new_flags = (long_words[1] >> 8) & 0x0F
    message_type = long_words[1] & 0xFF
    host_type = (long_words[2] >> 8) & 0xFF
    host = long_words[2] & 0xFF
    imp = long_words[3]
    identifier = (long_words[4] & 0xFFF0) >> 4
    subtype = long_words[4] & 0x0F
    data_bits = long_words[5]
    if long_words[1] & 0xF000 or new_flags & ~(_NEW_TRACE | _NEW_OCTAL):
        raise Ka10ImpTraceError("KA10 long leader has unsupported flag bits")
    if host_type & 0x7F != 7 or imp > 63 or message_type > 0x0F:
        raise Ka10ImpTraceError("KA10 long leader has a noncanonical address or type")
    if data_bits % 16 or data_bits > message.bit_count - 96:
        raise Ka10ImpTraceError("KA10 long leader has an invalid data length")
    padding_bits = message.bit_count - 96 - data_bits
    if padding_bits % 16:
        raise Ka10ImpTraceError("KA10 long leader padding is not whole words")
    padding_words = padding_bits // 16
    if any(long_words[6 : 6 + padding_words]):
        raise Ka10ImpTraceError("KA10 long leader padding is not zero")
    data_words = long_words[6 + padding_words :]
    if len(data_words) * 16 != data_bits:
        raise Ka10ImpTraceError("KA10 long leader data does not match its declared length")

    old_flags = 0
    if new_flags & _NEW_TRACE:
        old_flags |= _OLD_TRACE
    if new_flags & _NEW_OCTAL:
        old_flags |= _OLD_OCTAL
    if host >= _NEW_FOR_IMP:
        old_flags |= _OLD_FOR_IMP
        host -= _NEW_FOR_IMP
    if host > 3:
        raise Ka10ImpTraceError("KA10 long leader host cannot map to the short form")
    if host_type & _NEW_PRIORITY:
        old_flags |= _OLD_PRIORITY
    if message_type == _REGULAR and subtype == _UNCONTROLLED:
        message_type = _UNCONTROLLED
        subtype = 0
    elif message_type == _NOP:
        subtype = 0
    first = (old_flags << 12) | (message_type << 8) | (host << 6) | imp
    second = (identifier << 4) | subtype
    return (first, second, *data_words)


def _reconstruct(pending: _PendingMessage) -> bytes:
    bit_count = 0
    value = 0
    for word in pending.words:
        if word.valid_bits:
            chunk = word.value >> (36 - word.valid_bits)
            value = (value << word.valid_bits) | chunk
            bit_count += word.valid_bits
    if bit_count != pending.bit_count:
        raise Ka10ImpTraceError("KA10 consumed words do not cover the complete message")
    return value.to_bytes(bit_count // 8, "big")


def _require_monotonic_tick(previous: int | None, current: int) -> None:
    if previous is not None and current < previous:
        raise Ka10ImpTraceError("KA10 simulator tick moved backward")
