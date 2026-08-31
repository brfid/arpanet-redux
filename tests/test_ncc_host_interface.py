from __future__ import annotations

import unittest

from ncc.host_interface import (
    HostInterfaceError,
    HostInterfacePacket,
    PFLG_FINAL,
    PFLG_READY,
    PassiveHostIngress,
)


class HostInterfacePacketTests(unittest.TestCase):
    def test_round_trips_network_order_frame(self) -> None:
        original = HostInterfacePacket(
            sequence=42,
            flags=PFLG_FINAL | PFLG_READY,
            words=(0x0102, 0xA0B0),
        )

        self.assertEqual(HostInterfacePacket.from_bytes(original.to_bytes()), original)

    def test_rejects_missing_flag_word_and_trailing_bytes(self) -> None:
        with self.assertRaisesRegex(HostInterfaceError, "flag word"):
            HostInterfacePacket.from_bytes(b"H316\x00\x00\x00\x00\x00\x00")
        with self.assertRaisesRegex(HostInterfaceError, "expected"):
            HostInterfacePacket.from_bytes(
                HostInterfacePacket(0, PFLG_FINAL, ()).to_bytes() + b"\x00"
            )


class PassiveHostIngressTests(unittest.TestCase):
    def test_ready_packets_retry_until_sent_then_are_monotonic(self) -> None:
        ingress = PassiveHostIngress()

        first = ingress.ready_packet()
        retry = ingress.ready_packet()
        ingress.ready_sent()
        second = ingress.ready_packet()

        self.assertEqual(first.sequence, 0)
        self.assertEqual(retry.sequence, 0)
        self.assertEqual(second.sequence, 1)
        self.assertEqual(first.words, ())
        self.assertEqual(first.flags, PFLG_FINAL | PFLG_READY)

    def test_reassembles_only_finalized_imp_output(self) -> None:
        ingress = PassiveHostIngress()

        first = ingress.receive(HostInterfacePacket(7, PFLG_READY, (0x1111, 0x2222)))
        final = ingress.receive(
            HostInterfacePacket(8, PFLG_FINAL | PFLG_READY, (0x3333,))
        )

        self.assertIsNone(first.message)
        self.assertIsNotNone(final.message)
        assert final.message is not None
        self.assertEqual(final.message.first_sequence, 7)
        self.assertEqual(final.message.final_sequence, 8)
        self.assertEqual(final.message.words, (0x1111, 0x2222, 0x3333))

    def test_flag_only_packet_is_not_message_evidence(self) -> None:
        receipt = PassiveHostIngress().receive(
            HostInterfacePacket(0, PFLG_FINAL | PFLG_READY, ())
        )

        self.assertTrue(receipt.packet.ready)
        self.assertIsNone(receipt.message)

    def test_gap_discards_partial_message(self) -> None:
        ingress = PassiveHostIngress()
        ingress.receive(HostInterfacePacket(10, PFLG_READY, (0x1111,)))
        receipt = ingress.receive(HostInterfacePacket(12, PFLG_FINAL, (0x2222,)))

        self.assertIsNotNone(receipt.message)
        assert receipt.message is not None
        self.assertEqual(receipt.message.words, (0x2222,))
        self.assertEqual(receipt.message.first_sequence, 12)

    def test_rejects_duplicate_and_accepts_a_peer_restart(self) -> None:
        ingress = PassiveHostIngress()
        ingress.receive(HostInterfacePacket(8, PFLG_READY, ()))
        with self.assertRaisesRegex(HostInterfaceError, "sequence 8"):
            ingress.receive(HostInterfacePacket(8, PFLG_READY, ()))

        receipt = ingress.receive(HostInterfacePacket(0, PFLG_FINAL, (0x1111,)))
        self.assertIsNotNone(receipt.message)


if __name__ == "__main__":
    unittest.main()
