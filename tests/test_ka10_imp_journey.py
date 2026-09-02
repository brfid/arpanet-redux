from __future__ import annotations

import struct
import unittest

from ncc.ka10_imp_journey import (
    Ka10ImpTraceError,
    ka10_message_as_nosc_words,
    parse_ka10_imp_trace,
)


SHORT_MESSAGE = (
    0o000176,
    0o000000,
    0o000010,
    0o000012,
    0o000001,
    0o000000,
    0o002000,
    0o000000,
    0o000027,
    0o001000,
)


def canonical_long_message(*, padding_words: int = 5) -> bytes:
    data = SHORT_MESSAGE[2:]
    words = (
        0x0F00,
        0,
        0x0701,
        0x003E,
        0,
        len(data) * 16,
        *((0,) * padding_words),
        *data,
    )
    return struct.pack(f">{len(words)}H", *words)


def input_trace(content: bytes, *, sequence: int = 7) -> bytes:
    bit_text = "".join(f"{byte:08b}" for byte in content)
    bit_count = len(bit_text)
    tick = 1_000
    lines = [
        f"DBG({tick})> IMP ASSEMBLY: IMP INPUT-MESSAGE version=1 "
        f"message={sequence} bits={bit_count}"
    ]
    start = 0
    word_index = 0
    while True:
        width = 36 if start < 216 else 32
        valid = min(width, max(bit_count - start, 0))
        last = int(start + width >= bit_count)
        chunk = bit_text[start : start + valid]
        value = (int(chunk, 2) if chunk else 0) << (36 - valid)
        tick += 100
        lines.append(
            f"DBG({tick})> IMP ASSEMBLY: IMP INPUT-ASSEMBLY version=1 "
            f"message={sequence} word={word_index} message_bits={bit_count} "
            f"start={start} width={width} valid={valid} last={last} "
            f"value={value:012o}"
        )
        tick += 100
        lines.append(
            f"DBG({tick})> IMP ASSEMBLY: IMP INPUT-CONSUME version=1 "
            f"message={sequence} word={word_index} width={width} valid={valid} "
            f"last={last} value={value:012o} PC=53301"
        )
        if last:
            break
        start += width
        word_index += 1
    return ("console noise\r\n" + "\r\n".join(lines) + "\r\n").encode("ascii")


class Ka10ImpJourneyTests(unittest.TestCase):
    def test_reconstructs_only_paired_consumed_words_and_canonical_short_form(self) -> None:
        content = canonical_long_message()

        messages = parse_ka10_imp_trace(input_trace(content))

        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.source_local_sequence, 7)
        self.assertEqual(message.bit_count, 304)
        self.assertEqual(message.content, content)
        self.assertEqual([word.width for word in message.words], [36] * 6 + [32] * 3)
        self.assertEqual(message.words[-1].valid_bits, 24)
        self.assertEqual(ka10_message_as_nosc_words(message), SHORT_MESSAGE)

    def test_rejects_a_consume_record_that_differs_from_assembly(self) -> None:
        trace = input_trace(canonical_long_message())
        changed = trace.replace(
            b"INPUT-CONSUME version=1 message=7 word=0 width=36 valid=36 "
            b"last=0 value=036000000000",
            b"INPUT-CONSUME version=1 message=7 word=0 width=36 valid=36 "
            b"last=0 value=036000000001",
            1,
        )

        with self.assertRaisesRegex(Ka10ImpTraceError, "does not match"):
            parse_ka10_imp_trace(changed)

    def test_rejects_an_unknown_version_and_an_incomplete_message(self) -> None:
        trace = input_trace(canonical_long_message())
        with self.assertRaisesRegex(Ka10ImpTraceError, "malformed or unsupported"):
            parse_ka10_imp_trace(trace.replace(b"INPUT-MESSAGE version=1", b"INPUT-MESSAGE version=2", 1))

        last_record = trace.rfind(b"DBG(")
        with self.assertRaisesRegex(Ka10ImpTraceError, "incomplete message"):
            parse_ka10_imp_trace(trace[:last_record])

    def test_rejects_nonzero_long_leader_padding(self) -> None:
        content = bytearray(canonical_long_message())
        content[12] = 1
        message = parse_ka10_imp_trace(input_trace(bytes(content)))[0]

        with self.assertRaisesRegex(Ka10ImpTraceError, "padding is not zero"):
            ka10_message_as_nosc_words(message)

    def test_accepts_a_message_ending_on_an_exact_word_boundary(self) -> None:
        content = bytes(range(35))

        message = parse_ka10_imp_trace(input_trace(content))[0]

        self.assertEqual(message.content, content)
        self.assertEqual([word.width for word in message.words], [36] * 6 + [32] * 2)
        self.assertEqual(message.words[-1].valid_bits, 32)
        self.assertTrue(message.words[-1].last)


if __name__ == "__main__":
    unittest.main()
