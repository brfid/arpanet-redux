"""Narrow H316 HI/MI trace adapter for message-journey observations."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .message_journey import (
    BoundaryDirection,
    DecodedMessage,
    ExternalEvidenceReference,
    JourneyLeg,
    MessageJourneyObservation,
    ObservationProvenance,
)

_MESSAGE = re.compile(
    r"DBG\((\d+)\)> ((?:HI|MI)[1-4]) MSG: message (sent|received) \(length=(\d+)\)"
)
_WORDS = re.compile(r"DBG\((\d+)\)> ((?:HI|MI)[1-4]) MSG: - (.*)")
_REPEAT = re.compile(r"DBG\((\d+)\)> same as above \((\d+) times\)")
_UDP = re.compile(
    r"DBG\((\d+)\)> ((?:HI|MI)[1-4]) UDP: link \d+ - packet (sent|received) "
    r"\(sequence=(\d+), length=\d+\)"
)
_RECEIVE_DONE = re.compile(
    r"DBG\((\d+)\)> ((?:HI|MI)[1-4]) IO: receive done \(message #(\d+),"
)


class H316TraceError(ValueError):
    """Raised when an H316 trace transfer is not safe to adapt."""


@dataclass(frozen=True)
class H316TraceTransfer:
    """One directly logged H316 HI/MI transfer, before protocol interpretation."""

    source_local_sequence: int
    simulator_tick: int
    device: str
    action: str
    declared_word_count: int
    words: tuple[int, ...]
    transport_sequence: int | None
    message_number: int | None
    complete: bool

    def __post_init__(self) -> None:
        if self.action not in {"sent", "received"}:
            raise H316TraceError(f"unsupported H316 transfer action {self.action!r}")
        if not re.fullmatch(r"(?:HI|MI)[1-4]", self.device):
            raise H316TraceError(f"unsupported H316 device {self.device!r}")


@dataclass
class _PendingTransfer:
    simulator_tick: int
    device: str
    action: str
    declared_word_count: int
    words: list[int]
    transport_sequence: int | None = None
    message_number: int | None = None
    compressed: bool = False


def parse_h316_trace(lines: Iterable[str]) -> tuple[H316TraceTransfer, ...]:
    """Parse only the established H316 HI/MI MSG trace grammar.

    Compressed ``same as above`` records remain present but are marked
    incomplete, so an adapter cannot silently use words the trace did not show.
    Consecutive received HI chunks with the same firmware message number are
    reassembled after parsing.
    """

    pending: _PendingTransfer | None = None
    records: list[_PendingTransfer] = []
    last_received_transport: dict[tuple[int, str], int] = {}

    def finish() -> None:
        nonlocal pending
        if pending is not None:
            records.append(pending)
            pending = None

    for line in lines:
        udp_match = _UDP.search(line)
        if udp_match:
            tick = int(udp_match.group(1))
            device = udp_match.group(2)
            action = udp_match.group(3)
            sequence = int(udp_match.group(4))
            if action == "received":
                last_received_transport[(tick, device)] = sequence
            elif pending is not None and pending.device == device and pending.action == "sent":
                pending.transport_sequence = sequence
            continue

        message_match = _MESSAGE.search(line)
        if message_match:
            finish()
            tick = int(message_match.group(1))
            device = message_match.group(2)
            action = message_match.group(3)
            pending = _PendingTransfer(
                simulator_tick=tick,
                device=device,
                action=action,
                declared_word_count=int(message_match.group(4)),
                words=[],
                transport_sequence=last_received_transport.pop((tick, device), None),
            )
            continue

        words_match = _WORDS.search(line)
        if words_match and pending is not None:
            if int(words_match.group(1)) == pending.simulator_tick and words_match.group(2) == pending.device:
                for token in words_match.group(3).split():
                    if not re.fullmatch(r"[0-7]{6}", token):
                        pending.compressed = True
                        continue
                    pending.words.append(int(token, 8))
            continue

        repeat_match = _REPEAT.search(line)
        if repeat_match and pending is not None and int(repeat_match.group(1)) == pending.simulator_tick:
            pending.compressed = True
            continue

        done_match = _RECEIVE_DONE.search(line)
        if (
            done_match
            and pending is not None
            and pending.action == "received"
            and done_match.group(2) == pending.device
        ):
            pending.message_number = int(done_match.group(3))
            finish()

    finish()
    transfers = tuple(
        H316TraceTransfer(
            source_local_sequence=index,
            simulator_tick=record.simulator_tick,
            device=record.device,
            action=record.action,
            declared_word_count=record.declared_word_count,
            words=tuple(record.words),
            transport_sequence=record.transport_sequence,
            message_number=record.message_number,
            complete=not record.compressed and len(record.words) == record.declared_word_count,
        )
        for index, record in enumerate(records, start=1)
    )
    return _reassemble_received_chunks(transfers)


def observation_from_h316_transfer(
    transfer: H316TraceTransfer,
    *,
    observation_id: str,
    journey_id: str,
    leg: JourneyLeg,
    component_id: str,
    interface_id: str,
    direction: BoundaryDirection,
    decoded: DecodedMessage,
    fingerprint: str,
    provenance_id: str,
    external_evidence: Sequence[ExternalEvidenceReference] = (),
) -> MessageJourneyObservation:
    """Adapt one complete H316 transfer after a caller safely decodes its words."""

    if not transfer.complete:
        raise H316TraceError("cannot adapt an incomplete or compressed H316 transfer")
    expected_action = "received" if direction == BoundaryDirection.INGRESS else "sent"
    if transfer.action != expected_action:
        raise H316TraceError(
            f"H316 transfer action {transfer.action!r} contradicts {direction.value!r}"
        )
    return MessageJourneyObservation(
        id=observation_id,
        journey_id=journey_id,
        leg=leg,
        component_id=component_id,
        interface_id=interface_id,
        direction=direction,
        source_local_sequence=transfer.source_local_sequence,
        decoded=decoded,
        correlation_fingerprint=fingerprint,
        provenance=ObservationProvenance(id=provenance_id, kind="h316-hi-mi-trace"),
        simulator_tick=transfer.simulator_tick,
        transport_sequence=transfer.transport_sequence,
        external_evidence=tuple(external_evidence),
    )


def _reassemble_received_chunks(
    transfers: tuple[H316TraceTransfer, ...],
) -> tuple[H316TraceTransfer, ...]:
    reassembled: list[H316TraceTransfer] = []
    for transfer in transfers:
        if (
            reassembled
            and transfer.action == "received"
            and transfer.message_number is not None
            and reassembled[-1].action == "received"
            and reassembled[-1].device == transfer.device
            and reassembled[-1].message_number == transfer.message_number
        ):
            previous = reassembled.pop()
            reassembled.append(
                H316TraceTransfer(
                    source_local_sequence=previous.source_local_sequence,
                    simulator_tick=previous.simulator_tick,
                    device=previous.device,
                    action=previous.action,
                    declared_word_count=previous.declared_word_count + transfer.declared_word_count,
                    words=previous.words + transfer.words,
                    transport_sequence=previous.transport_sequence,
                    message_number=previous.message_number,
                    complete=previous.complete and transfer.complete,
                )
            )
            continue
        reassembled.append(transfer)
    return tuple(reassembled)
