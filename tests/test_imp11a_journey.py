from __future__ import annotations

import unittest

from ncc.imp11a_journey import Imp11aTraceError, parse_imp11a_trace


REPLY_WORDS = (
    0o000106,
    0o000000,
    0o000010,
    0o000015,
    0o000000,
    0o000000,
    0o001000,
    0o000000,
    0o013400,
    0o000004,
    0o000040,
    0o000000,
    0o000000,
)


def pdp11_word(wire: int) -> int:
    return ((wire << 8) & 0xFFFF) | (wire >> 8)


def input_trace(
    words: tuple[int, ...] = REPLY_WORDS,
    *,
    sequence: int = 41,
    start_tick: int = 1_000,
) -> bytes:
    lines = [
        f"DBG({start_tick})> IMP INPUT: IMP INPUT-MESSAGE version=1 "
        f"message={sequence}"
    ]
    tick = start_tick
    for index, wire in enumerate(words):
        tick += 10
        address = 0o123050 + index * 2 if index < 4 else 0o123564 + (index - 4) * 2
        lines.append(
            f"DBG({tick})> IMP INPUT: IMP INPUT-DMA version=1 "
            f"message={sequence} word={index} address={address:06o} "
            f"wire={wire:06o} guest={pdp11_word(wire):06o}"
        )
    tick += 10
    lines.append(
        f"DBG({tick})> IMP INPUT: IMP INPUT-COMPLETE version=1 "
        f"message={sequence} words={len(words)}"
    )
    return ("console noise\r\n" + "\r\n".join(lines) + "\r\n").encode("ascii")


class Imp11aJourneyTests(unittest.TestCase):
    def test_reconstructs_complete_post_store_dma_message(self) -> None:
        messages = parse_imp11a_trace(input_trace())

        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.source_local_sequence, 41)
        self.assertEqual(message.start_tick, 1_000)
        self.assertEqual(message.complete_tick, 1_140)
        self.assertEqual(message.wire_words, REPLY_WORDS)
        self.assertEqual(message.words[0].dma_address, 0o123050)
        self.assertEqual(message.words[4].dma_address, 0o123564)

    def test_accepts_contiguous_complete_messages(self) -> None:
        trace = input_trace(sequence=41) + input_trace(
            (0o002506, 0), sequence=42, start_tick=2_000
        )

        messages = parse_imp11a_trace(trace)

        self.assertEqual([message.source_local_sequence for message in messages], [41, 42])

    def test_rejects_changed_guest_value_and_noncontiguous_word(self) -> None:
        trace = input_trace()
        with self.assertRaisesRegex(Imp11aTraceError, "guest value"):
            parse_imp11a_trace(
                trace.replace(b"wire=000106 guest=043000", b"wire=000106 guest=043001", 1)
            )

        with self.assertRaisesRegex(Imp11aTraceError, "word index"):
            parse_imp11a_trace(trace.replace(b"message=41 word=1", b"message=41 word=2", 1))

        with self.assertRaisesRegex(Imp11aTraceError, "not 16 bits"):
            parse_imp11a_trace(
                trace.replace(
                    b"wire=000106 guest=043000",
                    b"wire=400106 guest=043400",
                    1,
                )
            )

    def test_rejects_unknown_version_and_incomplete_message(self) -> None:
        trace = input_trace()
        with self.assertRaisesRegex(Imp11aTraceError, "malformed or unsupported"):
            parse_imp11a_trace(
                trace.replace(b"INPUT-MESSAGE version=1", b"INPUT-MESSAGE version=2", 1)
            )

        completion = trace.rfind(b"DBG(")
        with self.assertRaisesRegex(Imp11aTraceError, "incomplete message"):
            parse_imp11a_trace(trace[:completion])

    def test_rejects_wrong_completion_count_and_sequence_gap(self) -> None:
        trace = input_trace()
        with self.assertRaisesRegex(Imp11aTraceError, "wrong word count"):
            parse_imp11a_trace(trace.replace(b"message=41 words=13", b"message=41 words=12", 1))

        with self.assertRaisesRegex(Imp11aTraceError, "sequence is not contiguous"):
            parse_imp11a_trace(trace + input_trace(sequence=43, start_tick=2_000))

    def test_rejects_invalid_dma_address_and_backward_tick(self) -> None:
        trace = input_trace()
        with self.assertRaisesRegex(Imp11aTraceError, "DMA address"):
            parse_imp11a_trace(trace.replace(b"address=123050", b"address=123051", 1))

        with self.assertRaisesRegex(Imp11aTraceError, "tick moved backward"):
            parse_imp11a_trace(trace.replace(b"DBG(1020)>", b"DBG(1009)>", 1))


if __name__ == "__main__":
    unittest.main()
