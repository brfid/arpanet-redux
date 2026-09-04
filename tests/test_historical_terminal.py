from __future__ import annotations

import os
import unittest

from ncc.historical_terminal import (
    LOCAL_FAILOVER_CUT,
    prepare_terminal_input,
    run_character_terminal,
)


class HistoricalTerminalTests(unittest.TestCase):
    def test_cut_control_is_reserved_only_in_failover_mode(self) -> None:
        direct = prepare_terminal_input(b"a" + bytes((LOCAL_FAILOVER_CUT,)) + b"b")
        failover = prepare_terminal_input(
            b"a" + bytes((LOCAL_FAILOVER_CUT,)) + b"ignored",
            enable_failover_cut=True,
        )

        self.assertEqual(direct.forwarded, b"a" + bytes((LOCAL_FAILOVER_CUT,)) + b"b")
        self.assertFalse(direct.cut_requested)
        self.assertEqual(failover.forwarded, b"a")
        self.assertTrue(failover.cut_requested)
        self.assertFalse(failover.exit_requested)

    def test_character_relay_keeps_cut_local_and_calls_its_owner(self) -> None:
        class RunningProcess:
            @staticmethod
            def poll() -> None:
                return None

        class Guest:
            process = RunningProcess()

            def __init__(self) -> None:
                self.sent: list[bytes] = []

            @staticmethod
            def output_from(_offset: int) -> bytes:
                return b""

            def send(self, data: bytes) -> None:
                self.sent.append(data)

        class Recorder:
            @staticmethod
            def bytes(_direction: str, _data: bytes, *, observed_at: str) -> None:
                del observed_at

            @staticmethod
            def control(_control: str, *, observed_at: str, count: int = 1) -> None:
                del observed_at, count

        input_read, input_write = os.pipe()
        output_read, output_write = os.pipe()
        guest = Guest()
        cut_requests: list[str] = []
        try:
            os.write(input_write, bytes((LOCAL_FAILOVER_CUT,)))
            os.close(input_write)
            input_write = -1

            reason = run_character_terminal(
                guest,
                Recorder(),
                input_fd=input_read,
                output_fd=output_write,
                start_offset=0,
                max_input_bytes=1024,
                max_output_bytes=1024,
                on_cut_request=lambda observed_at: (
                    cut_requests.append(observed_at) or b"cut accepted\n"
                ),
            )
            os.close(output_write)
            output_write = -1
            displayed = os.read(output_read, 4096)
        finally:
            os.close(input_read)
            os.close(output_read)
            if input_write >= 0:
                os.close(input_write)
            if output_write >= 0:
                os.close(output_write)

        self.assertEqual(reason, "input-eof")
        self.assertEqual(guest.sent, [])
        self.assertEqual(len(cut_requests), 1)
        self.assertIn(b"cut accepted", displayed)


if __name__ == "__main__":
    unittest.main()
