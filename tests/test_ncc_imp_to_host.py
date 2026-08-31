from __future__ import annotations

import unittest

from ncc.host_interface import IngressMessage
from ncc.imp_to_host import (
    ImpToHostMessageError,
    decode_imp_to_host_message,
    decode_old_style_imp_to_host_leader,
    decode_throughput_report_imp_to_host_message,
    decode_trouble_report_imp_to_host_message,
    throughput_report_events_from_imp_to_host_message,
    trouble_report_events_from_imp_to_host_message,
)
from ncc.report_checksum import report_checksum


def old_style_imp_leader(
    *,
    source_imp: int = 5,
    source_host: int = 3,
    message_type: int = 0,
    message_id: int = 0o1234,
    subtype: int = 0,
    from_imp: bool = True,
) -> tuple[int, int]:
    first = (
        (0x4000 if from_imp else 0)
        | (message_type << 8)
        | (source_host << 6)
        | source_imp
    )
    second = (message_id << 4) | subtype
    return first, second


def trouble_report_body(*, message_type: int = 0o301, padded: bool = True) -> tuple[int, ...]:
    payload = (message_type,) + (0,) * 29
    words = payload + (report_checksum(payload),)
    return words + ((0,) if padded else ())


def trouble_report_message(
    *, report_message_type: int = 0o301, **leader_kwargs: int | bool
) -> IngressMessage:
    return IngressMessage(
        first_sequence=17,
        final_sequence=19,
        words=old_style_imp_leader(**leader_kwargs)
        + trouble_report_body(message_type=report_message_type),
    )


def throughput_report_message(**leader_kwargs: int | bool) -> IngressMessage:
    payload = (0o302,) + (0,) * 50
    body = payload + (report_checksum(payload), 0)
    return IngressMessage(
        first_sequence=20,
        final_sequence=24,
        words=old_style_imp_leader(**leader_kwargs) + body,
    )


class OldStyleImpToHostLeaderTests(unittest.TestCase):
    def test_decodes_the_documented_fields_and_fake_host_mapping(self) -> None:
        leader = decode_old_style_imp_to_host_leader(
            old_style_imp_leader(
                source_imp=5,
                source_host=3,
                message_type=0,
                message_id=0o1234,
                subtype=7,
            )
        )

        self.assertTrue(leader.from_imp)
        self.assertEqual(leader.message_type, 0)
        self.assertEqual(leader.source_host_field, 3)
        self.assertEqual(leader.source_host, 255)
        self.assertEqual(leader.source_imp, 5)
        self.assertEqual(leader.message_id, 0o1234)
        self.assertEqual(leader.subtype, 7)

    def test_rejects_a_non_two_word_or_non_16_bit_leader(self) -> None:
        with self.assertRaisesRegex(ImpToHostMessageError, "exactly two"):
            decode_old_style_imp_to_host_leader((0,))
        with self.assertRaisesRegex(ImpToHostMessageError, "16-bit range"):
            decode_old_style_imp_to_host_leader((0, 0x10000))


class TroubleReportImpToHostMessageTests(unittest.TestCase):
    def test_decodes_body_after_two_word_leader_and_attributes_source_imp(self) -> None:
        message = trouble_report_message()
        parsed = decode_imp_to_host_message(message)
        decoded = decode_trouble_report_imp_to_host_message(message)
        events = trouble_report_events_from_imp_to_host_message(
            message,
            observed_at="1975-01-01T00:00:00Z",
            sequence_start=40,
        )

        self.assertEqual(parsed.body_words, trouble_report_body())
        self.assertEqual(decoded.message.leader.source_imp, 5)
        self.assertEqual(decoded.report.message_type, 0o301)
        self.assertEqual([event.sequence for event in events], list(range(40, 50)))
        self.assertEqual(events[0].source.imp, 5)
        self.assertEqual(events[0].subject, "imp:5")

    def test_rejects_leaders_that_cannot_prove_a_reporting_imp(self) -> None:
        with self.assertRaisesRegex(ImpToHostMessageError, "IMP-originated"):
            decode_trouble_report_imp_to_host_message(trouble_report_message(from_imp=False))
        with self.assertRaisesRegex(ImpToHostMessageError, "regular"):
            decode_trouble_report_imp_to_host_message(trouble_report_message(message_type=3))
        with self.assertRaisesRegex(ImpToHostMessageError, "omits a source IMP"):
            decode_trouble_report_imp_to_host_message(trouble_report_message(source_imp=0))

    def test_rejects_an_incomplete_leader_or_a_non_trouble_report_body(self) -> None:
        missing_leader = IngressMessage(1, 1, (0o301,))
        with self.assertRaisesRegex(ImpToHostMessageError, "two-word"):
            decode_trouble_report_imp_to_host_message(missing_leader)

        wrong_body = IngressMessage(
            1,
            1,
            old_style_imp_leader() + (0o302,) + (0,) * 30,
        )
        with self.assertRaisesRegex(ImpToHostMessageError, "expected a 1973 trouble-report"):
            decode_trouble_report_imp_to_host_message(wrong_body)

    def test_decodes_the_patched_type303_form_without_rewriting_its_code(self) -> None:
        message = trouble_report_message(report_message_type=0o303)

        decoded = decode_trouble_report_imp_to_host_message(message)
        events = trouble_report_events_from_imp_to_host_message(
            message,
            observed_at="1975-01-01T00:00:00Z",
        )

        self.assertEqual(decoded.report.message_type, 0o303)
        self.assertEqual(events[0].details["message_type"], 0o303)

    def test_decodes_type302_throughput_after_the_two_word_leader(self) -> None:
        message = throughput_report_message()

        decoded = decode_throughput_report_imp_to_host_message(message)
        events = throughput_report_events_from_imp_to_host_message(
            message,
            observed_at="1975-01-01T00:00:00Z",
            sequence_start=60,
        )

        self.assertEqual(decoded.message.leader.source_imp, 5)
        self.assertEqual(decoded.report.message_type, 0o302)
        self.assertEqual(len(decoded.report.lines), 5)
        self.assertEqual(len(decoded.report.hosts), 4)
        self.assertEqual(events[0].sequence, 60)
        self.assertEqual(events[0].event_type, "imp.throughput-report")
        self.assertEqual(events[0].source.imp, 5)


if __name__ == "__main__":
    unittest.main()
