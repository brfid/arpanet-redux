import unittest

from ncc.events import trouble_report_events
from ncc.trouble_report import LineState, decode_trouble_report


def sample_words(*, padded: bool = True) -> list[int]:
    words = [
        0o301,
        0o100000 | 0o020000 | 0o000100 | 0o000020,
        0o123,
        0o1000,
        0o2000,
        0o3000,
        10,
        11,
        12,
        13,
        0o3050,
        0o17,
        0,
        2,
        21,
        20,
        7,
        (6 << 8) | 0o3,
        9,
        0o100000 | (31 << 8) | 0o12,
        4,
        0o040000 | (5 << 8),
        0,
        0,
        0o377,
        (62 << 8) | 0o377,
        0o12345,
        0o4000,
        0o5000,
        0o6000,
        0o7777,
    ]
    if padded:
        words.append(0)
    return words


class TroubleReportTests(unittest.TestCase):
    def test_decodes_semantic_fields_and_optional_padding(self) -> None:
        report = decode_trouble_report(sample_words())

        self.assertEqual(report.message_type, 0o301)
        self.assertEqual(
            (
                report.free_buffers,
                report.store_and_forward_buffers,
                report.reassembly_buffers,
                report.allocate_buffers,
            ),
            (10, 11, 12, 13),
        )
        self.assertEqual(report.padding_words, (0,))
        self.assertTrue(report.host_up(0))
        self.assertFalse(report.host_up(1))
        self.assertTrue(report.host_up(2))
        self.assertFalse(report.host_up(3))

        self.assertEqual(report.lines[0].state, LineState.UP)
        self.assertEqual(report.lines[0].neighbor_imp, 6)
        self.assertEqual(report.lines[0].routing_messages_sent, 7)
        self.assertEqual(report.lines[0].routing_messages_missed, 3)
        self.assertEqual(report.lines[1].state, LineState.DOWN)
        self.assertEqual(report.lines[1].neighbor_imp, 31)
        self.assertEqual(report.lines[2].state, LineState.LOOPED)
        self.assertEqual(report.lines[3].state, LineState.UNKNOWN)
        self.assertIsNone(report.lines[3].neighbor_imp)
        self.assertEqual(report.lines[4].neighbor_imp, 62)

        unpadded = decode_trouble_report(sample_words(padded=False))
        self.assertEqual(unpadded.padding_words, ())

    def test_rejects_invalid_shape_type_and_words(self) -> None:
        with self.assertRaisesRegex(ValueError, "31 semantic words"):
            decode_trouble_report(sample_words()[:-2])

        wrong_type = sample_words()
        wrong_type[0] = 0o302
        with self.assertRaisesRegex(ValueError, "expected Type 301"):
            decode_trouble_report(wrong_type)

        invalid_word = sample_words()
        invalid_word[4] = 0x10000
        with self.assertRaisesRegex(ValueError, "16-bit range"):
            decode_trouble_report(invalid_word)

        non_integer = sample_words()
        non_integer[4] = True
        with self.assertRaisesRegex(TypeError, "not an integer"):
            decode_trouble_report(non_integer)

        with self.assertRaisesRegex(ValueError, "host interface"):
            decode_trouble_report(sample_words()).host_up(4)

    def test_emits_topology_neutral_events(self) -> None:
        report = decode_trouble_report(sample_words())
        events = trouble_report_events(
            report,
            source_imp=5,
            observed_at="1975-01-01T00:00:00Z",
            sequence_start=40,
        )

        self.assertEqual(len(events), 10)
        self.assertEqual([event.sequence for event in events], list(range(40, 50)))
        self.assertEqual(events[0].subject, "imp:5")
        self.assertEqual(events[1].subject, "imp:5:host:0")
        self.assertEqual(events[1].state, "up")
        self.assertEqual(events[5].subject, "imp:5:line:1")
        self.assertEqual(events[5].state, "up")
        self.assertEqual(events[5].details["neighbor_imp"], 6)
        self.assertEqual(events[5].to_dict()["source"], {"kind": "imp-trouble-report", "imp": 5})


if __name__ == "__main__":
    unittest.main()
