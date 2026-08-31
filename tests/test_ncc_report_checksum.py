from __future__ import annotations

import unittest

from ncc.report_checksum import has_valid_report_checksum, report_checksum


class ReportChecksumTests(unittest.TestCase):
    def test_builds_a_twos_complement_checksum_over_the_payload_domain(self) -> None:
        payload = (0o303, 0xFFFF, 2)

        checksum = report_checksum(payload)

        self.assertEqual(checksum, 0o177474)
        self.assertTrue(has_valid_report_checksum((*payload, checksum)))

    def test_rejects_a_changed_semantic_word_and_out_of_range_values(self) -> None:
        payload = (0o302, 10, 20)
        complete = (*payload, report_checksum(payload))

        self.assertFalse(has_valid_report_checksum((*complete[:-1], complete[-1] ^ 1)))
        with self.assertRaisesRegex(ValueError, "16-bit range"):
            report_checksum((0x10000,))


if __name__ == "__main__":
    unittest.main()
