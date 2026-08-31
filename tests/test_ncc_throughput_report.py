from __future__ import annotations

import unittest

from ncc.events import throughput_report_events
from ncc.report_checksum import report_checksum
from ncc.throughput_report import decode_throughput_report


def sample_words(*, padded: bool = True) -> list[int]:
    words = [0o302]
    words.extend(range(10, 20))
    words.extend(range(100, 140))
    words.append(report_checksum(words))
    if padded:
        words.append(0o7654)
    return words


class ThroughputReportTests(unittest.TestCase):
    def test_decodes_line_and_host_counter_order_with_optional_padding(self) -> None:
        report = decode_throughput_report(sample_words())
        unpadded = decode_throughput_report(sample_words(padded=False))

        self.assertEqual(report.message_type, 0o302)
        self.assertEqual(len(report.lines), 5)
        self.assertEqual(report.lines[0].packets, 10)
        self.assertEqual(report.lines[0].words, 11)
        self.assertEqual(report.lines[-1].interface, 5)
        self.assertEqual(report.lines[-1].packets, 18)
        self.assertEqual(report.hosts[0].host, 0)
        self.assertEqual(report.hosts[0].messages_from_host_to_network, 100)
        self.assertEqual(report.hosts[0].words_from_imp_to_host, 109)
        self.assertEqual(report.hosts[-1].host, 3)
        self.assertEqual(report.hosts[-1].messages_from_host_to_network, 130)
        self.assertEqual(report.hosts[-1].words_from_imp_to_host, 139)
        self.assertEqual(report.checksum_word, report_checksum(sample_words(padded=False)[:-1]))
        self.assertEqual(report.padding_words, (0o7654,))
        self.assertEqual(unpadded.padding_words, ())

    def test_rejects_invalid_shape_type_and_word_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "52 semantic words"):
            decode_throughput_report(sample_words()[:-2])

        wrong_type = sample_words()
        wrong_type[0] = 0o301
        with self.assertRaisesRegex(ValueError, "expected Type 302"):
            decode_throughput_report(wrong_type)

        non_integer = sample_words()
        non_integer[10] = False
        with self.assertRaisesRegex(TypeError, "not an integer"):
            decode_throughput_report(non_integer)

        invalid_checksum = sample_words()
        invalid_checksum[-2] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum is invalid"):
            decode_throughput_report(invalid_checksum)

    def test_emits_one_direct_event_without_claiming_a_rate(self) -> None:
        report = decode_throughput_report(sample_words())
        events = throughput_report_events(
            report,
            source_imp=5,
            observed_at="1975-01-01T00:00:00Z",
            sequence_start=17,
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.sequence, 17)
        self.assertEqual(event.event_type, "imp.throughput-report")
        self.assertEqual(event.source.kind, "imp-throughput-report")
        self.assertEqual(event.details["message_type"], 0o302)
        self.assertEqual(event.details["line_throughput"][0]["packets"], 10)
        self.assertEqual(
            event.details["host_throughput"][3]["words_from_imp_to_host"], 139
        )


if __name__ == "__main__":
    unittest.main()
