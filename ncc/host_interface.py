"""Passive framing for the H316 simulator's host-interface transport.

This module deliberately stops at the transport boundary.  It proves that a
project-authored NCC receiver can maintain the host-ready signal and preserve
complete IMP-to-host messages without sending an NCP or 1822 control message.
The later receiver owns leader interpretation and Type 301 decoding.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct


MAGIC = b"H316"
PFLG_FINAL = 0o1
PFLG_READY = 0o2
_HEADER = struct.Struct(">4sIH")
_WORD = struct.Struct(">H")


class HostInterfaceError(ValueError):
    """Raised when a host-interface datagram cannot safely be accepted."""


@dataclass(frozen=True)
class HostInterfacePacket:
    """One simulator host-interface datagram, with the transport flag removed."""

    sequence: int
    flags: int
    words: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.sequence <= 0xFFFFFFFF:
            raise HostInterfaceError("sequence must be an unsigned 32-bit value")
        if not 0 <= self.flags <= 0xFFFF:
            raise HostInterfaceError("flags must be an unsigned 16-bit value")
        if any(not 0 <= word <= 0xFFFF for word in self.words):
            raise HostInterfaceError("words must be unsigned 16-bit values")

    @property
    def final(self) -> bool:
        """Whether this packet ends the current host-interface message."""

        return bool(self.flags & PFLG_FINAL)

    @property
    def ready(self) -> bool:
        """Whether the transmitting endpoint reports itself ready."""

        return bool(self.flags & PFLG_READY)

    def to_bytes(self) -> bytes:
        """Encode the simulator's network-order UDP payload."""

        count = 1 + len(self.words)
        return _HEADER.pack(MAGIC, self.sequence, count) + _WORD.pack(
            self.flags
        ) + b"".join(_WORD.pack(word) for word in self.words)

    @classmethod
    def from_bytes(cls, value: bytes) -> HostInterfacePacket:
        """Decode exactly one complete simulator UDP payload."""

        if len(value) < _HEADER.size:
            raise HostInterfaceError("datagram is shorter than the H316 header")
        magic, sequence, count = _HEADER.unpack_from(value)
        if magic != MAGIC:
            raise HostInterfaceError("datagram does not carry the H316 magic")
        if count == 0:
            raise HostInterfaceError("datagram omits the required flag word")
        expected = _HEADER.size + count * _WORD.size
        if len(value) != expected:
            raise HostInterfaceError(
                f"datagram length is {len(value)}, expected {expected} for {count} words"
            )
        values = struct.unpack_from(f">{count}H", value, _HEADER.size)
        return cls(sequence=sequence, flags=values[0], words=tuple(values[1:]))


@dataclass(frozen=True)
class IngressMessage:
    """One complete message assembled from one or more host-interface packets."""

    first_sequence: int
    final_sequence: int
    words: tuple[int, ...]


@dataclass(frozen=True)
class IngressReceipt:
    """The direct result of accepting one packet at the passive boundary."""

    packet: HostInterfacePacket
    message: IngressMessage | None


class PassiveHostIngress:
    """Maintain readiness and reassemble IMP output without transmitting data.

    The receiver sends only a flag-only ready packet.  Payload words flow in
    the other direction and remain opaque here, which keeps NCP, leader, and
    report-version decisions out of the transport proof.
    """

    def __init__(self) -> None:
        self._next_ready_sequence = 0
        self._last_received_sequence: int | None = None
        self._first_message_sequence: int | None = None
        self._message_words: list[int] = []

    def ready_packet(self) -> HostInterfacePacket:
        """Return the pending flag-only packet that asserts host readiness.

        The caller must acknowledge a successful transport send with
        :meth:`ready_sent`.  Keeping the sequence number stable across a
        startup send failure lets the H316 peer receive the required initial
        sequence zero instead of an accidental gap.
        """

        return HostInterfacePacket(
            sequence=self._next_ready_sequence,
            flags=PFLG_FINAL | PFLG_READY,
            words=(),
        )

    def ready_sent(self) -> None:
        """Advance after the pending ready packet reached the UDP transport."""

        self._next_ready_sequence += 1

    def receive(self, packet: HostInterfacePacket) -> IngressReceipt:
        """Accept one IMP-to-host packet and emit a message only when complete.

        A sequence restart at zero is permitted because the pinned simulator
        uses that value to resynchronize after its peer restarts.  A duplicate
        or backwards packet is rejected.  A gap while a message is in progress
        discards that incomplete message: absence is not evidence of a valid
        report.
        """

        self._check_sequence(packet.sequence)
        if self._last_received_sequence is not None and packet.sequence > self._last_received_sequence + 1:
            self._discard_partial_message()
        self._last_received_sequence = packet.sequence

        if not packet.words:
            return IngressReceipt(packet=packet, message=None)

        if self._first_message_sequence is None:
            self._first_message_sequence = packet.sequence
        self._message_words.extend(packet.words)
        if not packet.final:
            return IngressReceipt(packet=packet, message=None)

        message = IngressMessage(
            first_sequence=self._first_message_sequence,
            final_sequence=packet.sequence,
            words=tuple(self._message_words),
        )
        self._discard_partial_message()
        return IngressReceipt(packet=packet, message=message)

    def _check_sequence(self, sequence: int) -> None:
        if self._last_received_sequence is None:
            return
        if sequence == 0:
            self._discard_partial_message()
            return
        if sequence <= self._last_received_sequence:
            raise HostInterfaceError(
                f"received sequence {sequence} after {self._last_received_sequence}"
            )

    def _discard_partial_message(self) -> None:
        self._first_message_sequence = None
        self._message_words.clear()
