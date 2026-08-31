"""Validate the 1973 IMP report checksum domain.

The recovered 1973 sender accumulates the report code and each semantic body
word in a 16-bit accumulator, then emits the two's-complement accumulator as
the final semantic word. The IMP-to-host leader and any trailing pad word are
sent separately and are not part of this checksum domain.
"""

from __future__ import annotations

from typing import Iterable


WORD_MASK = 0xFFFF


def report_checksum(payload_words: Iterable[int]) -> int:
    """Return the 16-bit checksum for report words before their checksum word."""

    total = 0
    for offset, word in enumerate(payload_words):
        _validate_word(offset, word)
        total = (total + word) & WORD_MASK
    return (-total) & WORD_MASK


def has_valid_report_checksum(semantic_words: Iterable[int]) -> bool:
    """Return whether a complete report body sums to zero modulo 16 bits."""

    total = 0
    for offset, word in enumerate(semantic_words):
        _validate_word(offset, word)
        total = (total + word) & WORD_MASK
    return total == 0


def _validate_word(offset: int, word: int) -> None:
    if not isinstance(word, int) or isinstance(word, bool):
        raise TypeError(f"word {offset} is not an integer: {word!r}")
    if not 0 <= word <= WORD_MASK:
        raise ValueError(f"word {offset} is outside the 16-bit range: {word}")
