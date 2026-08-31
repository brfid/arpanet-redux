"""Decode the fixed-format 1973 Type 302 IMP throughput report.

The report carries cumulative counters rather than a rate calculation. Its
field order follows the recovered 1973 report-construction loop; this module
preserves the counters and checksum without inferring an interval or reset
semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .report_checksum import has_valid_report_checksum


THROUGHPUT_REPORT_TYPE = 0o302
LINE_COUNT = 5
HOST_COUNT = 4
HOST_COUNTER_COUNT = 10
SEMANTIC_WORD_COUNT = 1 + (LINE_COUNT * 2) + (HOST_COUNT * HOST_COUNTER_COUNT) + 1
PADDED_WORD_COUNT = SEMANTIC_WORD_COUNT + 1


@dataclass(frozen=True)
class LineThroughput:
    """Cumulative packet and word counters for one local modem line."""

    interface: int
    packets: int
    words: int


@dataclass(frozen=True)
class HostThroughput:
    """The ten cumulative traffic counters for one real host interface."""

    host: int
    messages_from_host_to_network: int
    messages_from_network_to_host: int
    packets_from_host_to_network: int
    packets_from_network_to_host: int
    messages_from_host_to_local_host: int
    messages_from_local_host_to_host: int
    packets_from_host_to_local_host: int
    packets_from_local_host_to_host: int
    words_from_host_to_imp: int
    words_from_imp_to_host: int


@dataclass(frozen=True)
class ThroughputReport:
    """Decoded counters from one 1973 Type 302 throughput report."""

    message_type: int
    lines: tuple[LineThroughput, ...]
    hosts: tuple[HostThroughput, ...]
    checksum_word: int
    padding_words: tuple[int, ...]


def decode_throughput_report(raw_words: Iterable[int]) -> ThroughputReport:
    """Decode a 52-word report, optionally followed by its 53rd pad word.

    The 16-bit checksum covers the report code and every semantic body word,
    but excludes the separately sent old-style leader and optional pad word.
    The report exposes cumulative values only; neither its interval nor reset
    behavior is established by the selected primary evidence.
    """

    words = tuple(raw_words)
    if len(words) not in (SEMANTIC_WORD_COUNT, PADDED_WORD_COUNT):
        raise ValueError(
            "Type 302 throughput reports require 52 semantic words "
            f"and may contain one pad word; got {len(words)}"
        )
    for offset, word in enumerate(words):
        if not isinstance(word, int) or isinstance(word, bool):
            raise TypeError(f"word {offset} is not an integer: {word!r}")
        if not 0 <= word <= 0xFFFF:
            raise ValueError(f"word {offset} is outside the 16-bit range: {word}")
    if words[0] != THROUGHPUT_REPORT_TYPE:
        raise ValueError(
            f"expected Type 302 ({THROUGHPUT_REPORT_TYPE:#o}), got {words[0]:#o}"
        )

    if not has_valid_report_checksum(words[:SEMANTIC_WORD_COUNT]):
        raise ValueError("Type 302 checksum is invalid")

    cursor = 1
    lines: list[LineThroughput] = []
    for interface in range(1, LINE_COUNT + 1):
        lines.append(
            LineThroughput(
                interface=interface,
                packets=words[cursor],
                words=words[cursor + 1],
            )
        )
        cursor += 2

    hosts: list[HostThroughput] = []
    for host in range(HOST_COUNT):
        hosts.append(
            HostThroughput(
                host=host,
                messages_from_host_to_network=words[cursor],
                messages_from_network_to_host=words[cursor + 1],
                packets_from_host_to_network=words[cursor + 2],
                packets_from_network_to_host=words[cursor + 3],
                messages_from_host_to_local_host=words[cursor + 4],
                messages_from_local_host_to_host=words[cursor + 5],
                packets_from_host_to_local_host=words[cursor + 6],
                packets_from_local_host_to_host=words[cursor + 7],
                words_from_host_to_imp=words[cursor + 8],
                words_from_imp_to_host=words[cursor + 9],
            )
        )
        cursor += HOST_COUNTER_COUNT

    return ThroughputReport(
        message_type=words[0],
        lines=tuple(lines),
        hosts=tuple(hosts),
        checksum_word=words[cursor],
        padding_words=words[cursor + 1 :],
    )
