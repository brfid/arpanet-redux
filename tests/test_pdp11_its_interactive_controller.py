from __future__ import annotations

import importlib.util
from io import StringIO
import os
from pathlib import Path
import re
import tempfile
import termios
import unittest

from ncc.interactive_telnet import (
    InteractiveTelnetRecorder,
    read_interactive_telnet_stream,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdp11-its-interactive-controller.py"
SPEC = importlib.util.spec_from_file_location(
    "pdp11_its_interactive_controller", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)

FORWARD = b"000377 003003 000347 000000 174033"
RETURNED = b"000000 037001 005000 177777 134201"
VALID_PDP11 = (
    b"Connection open\r\n"
    b"MIT Dynamic Modelling PDP-10\r\n"
    b"KA ITS.1652. DDT.1549.\r\n"
    b"TTY 53\r\nWelcome to ITS!\r\n"
    b":TIME\r\nThe time is 08:00:01 EDT.\r\n*"
)
VALID_HISTORICAL_TERMINAL = (
    b" UNIX User Telnet -- Ver I.5\r\n* connect - -h 106\r\n"
    b"Attempting Connection \r\nConnection open\r\n"
    b"MIT Dynamic Modelling PDP-10\r\n"
    b"KA ITS.1652. DDT.1549.\r\n"
    b"TTY 53\r\nWelcome to ITS!\r\nHappy hacking!\r\n"
)
VALID_ITS = b"LOGIN  53TLNT 0 HST176 08:00:00\r\n"
VALID_IMP6 = (
    b"HI2 MSG: message received\nHI2 MSG: message sent\n"
    b"MI1 MSG: message sent (length=5)\nMI1 MSG: - " + FORWARD + b" \n"
    b"MI1 MSG: message received (length=5)\nMI1 MSG: - " + RETURNED + b" \n"
)
VALID_IMP62 = (
    b"HI2 MSG: message received\nHI2 MSG: message sent\n"
    b"MI1 MSG: message received (length=5)\nMI1 MSG: - " + FORWARD + b" \n"
    b"MI1 MSG: message sent (length=5)\nMI1 MSG: - " + RETURNED + b" \n"
)


class FakePdp11:
    def __init__(self, responses: list[bytes], *, timeout: bool = False) -> None:
        self.buffer = bytearray()
        self.cursor = 0
        self.responses = list(responses)
        self.timeout = timeout
        self.sent: list[str] = []

    def position(self) -> int:
        return len(self.buffer)

    def send(self, data: str) -> None:
        self.sent.append(data)
        if self.responses:
            self.buffer.extend(self.responses.pop(0))

    def expect_any(
        self, patterns: tuple[bytes, ...], timeout: float
    ) -> tuple[int, re.Match[bytes]]:
        del timeout
        if self.timeout:
            raise TimeoutError("synthetic timeout")
        matches = []
        for index, pattern in enumerate(patterns):
            match = re.compile(pattern, re.DOTALL).search(self.buffer, self.cursor)
            if match is not None:
                matches.append((match.start(), index, match))
        if not matches:
            raise AssertionError("synthetic response did not match")
        _, index, match = min(matches, key=lambda item: (item[0], item[1]))
        self.cursor = match.end()
        return index, match

    def output_from(self, offset: int) -> bytes:
        return bytes(self.buffer[offset:])


def recorder(path: Path) -> InteractiveTelnetRecorder:
    return InteractiveTelnetRecorder(
        path,
        run_id="pdp11-its-interactive-controller-test",
        started_at="2026-09-01T12:00:00Z",
        repository_revision="1" * 40,
        service_user="53TLNT",
    )


class InteractiveControllerTests(unittest.TestCase):
    def test_boot_display_is_line_stable_and_shows_elapsed_milestones(self) -> None:
        ticks = iter((100.0, 101.9, 104.2))
        output = StringIO()
        display = CONTROLLER.BootDisplay(output, clock=lambda: next(ticks))

        display.milestone("START", "IMP backbone", "launching two IMPs")
        display.milestone("READY", "IMP backbone", "transports listening")

        self.assertEqual(
            output.getvalue(),
            "  [  1s] START IMP backbone         launching two IMPs\n"
            "  [  4s] READY IMP backbone         transports listening\n",
        )
        self.assertNotRegex(output.getvalue(), r"\x1b|\r")

    def test_accepts_prompt_framed_command_and_correlated_imp_traffic(self) -> None:
        self.assertEqual(
            CONTROLLER.interactive_evidence_failures(
                VALID_PDP11,
                VALID_ITS,
                VALID_IMP6,
                VALID_IMP62,
                completed_commands=1,
            ),
            [],
        )

    def test_missing_prompt_or_command_and_one_sided_imp_traffic_fail(self) -> None:
        failures = CONTROLLER.interactive_evidence_failures(
            VALID_PDP11.replace(b"\r\n*", b""),
            VALID_ITS,
            VALID_IMP6,
            b"",
            completed_commands=0,
        )
        self.assertTrue(any("DDT prompt" in failure for failure in failures))
        self.assertTrue(any("completed no" in failure for failure in failures))
        self.assertTrue(any("imp62 lacks" in failure for failure in failures))

    def test_operator_loop_handles_local_help_and_retains_exact_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "interactive-telnet.jsonl"
            writer = recorder(path)
            process = FakePdp11(
                [b":TIME\r\nThe time is 08:00:01 EDT.\r\n:KILL \r\n*"]
            )
            output = StringIO()

            reason = CONTROLLER.run_operator_session(
                process,
                writer,
                input_stream=StringIO("/help\n:TIME\n/quit\n"),
                output_stream=output,
                command_timeout=60,
                max_commands=10,
                max_response_bytes=1024,
            )
            writer.complete(
                observed_at="2026-09-01T12:00:03Z", reason=reason
            )
            writer.close()
            stream = read_interactive_telnet_stream(path)

            self.assertEqual(reason, "operator-quit")
            self.assertEqual(process.sent, [":TIME\r"])
            self.assertEqual(stream.completed_commands, 1)
            self.assertEqual(
                stream.exchanges[0].captured,
                b":TIME\r\nThe time is 08:00:01 EDT.\r\n:KILL \r\n*",
            )
            self.assertIn("Local commands", output.getvalue())
            self.assertIn("try :TIME", output.getvalue())
            self.assertIn("line-oriented", output.getvalue())
            self.assertIn("The time is", output.getvalue())

    def test_timeout_is_retained_and_aborts_the_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "interactive-telnet.jsonl"
            writer = recorder(path)
            process = FakePdp11([b":HANG\r\npartial"], timeout=True)

            with self.assertRaisesRegex(
                CONTROLLER.InteractiveSessionFailure, "did not return"
            ):
                CONTROLLER.run_operator_session(
                    process,
                    writer,
                    input_stream=StringIO(":HANG\n"),
                    output_stream=StringIO(),
                    command_timeout=1,
                    max_commands=10,
                    max_response_bytes=1024,
                )
            writer.complete(
                observed_at="2026-09-01T12:00:03Z", reason="failed"
            )
            writer.close()
            stream = read_interactive_telnet_stream(path)

            self.assertEqual(stream.failed_commands, 1)
            self.assertEqual(stream.exchanges[0].status, "timeout")
            self.assertEqual(stream.exchanges[0].captured, b":HANG\r\npartial")

    def test_console_renderer_escapes_control_bytes(self) -> None:
        self.assertEqual(
            CONTROLLER.render_console_capture(b"hello\r\n\x1bworld\x00"),
            "hello\n\\x1bworld\\x00",
        )

    def test_terminal_input_reserves_local_controls_and_maps_teletype_keys(self) -> None:
        prepared = CONTROLLER.prepare_terminal_input(
            b"a\n\x7f\x1c\x80b\x1dignored"
        )

        self.assertEqual(prepared.forwarded, b"a\r\x08b")
        self.assertTrue(prepared.exit_requested)
        self.assertEqual(prepared.blocked_wru, 1)
        self.assertEqual(prepared.rejected_non_seven_bit, 1)

    def test_operator_terminal_mode_is_character_oriented_and_restores_attributes(self) -> None:
        master_fd, slave_fd = os.openpty()
        try:
            original = termios.tcgetattr(slave_fd)
            with CONTROLLER.operator_terminal_mode(slave_fd):
                configured = termios.tcgetattr(slave_fd)
                self.assertEqual(configured[3] & termios.ICANON, 0)
                self.assertEqual(configured[3] & termios.ECHO, 0)
                self.assertEqual(configured[3] & termios.ISIG, 0)
                self.assertEqual(configured[1], original[1])
            self.assertEqual(termios.tcgetattr(slave_fd), original)
        finally:
            os.close(master_fd)
            os.close(slave_fd)

    def test_safe_teletype_renderer_handles_split_crlf_and_escapes_controls(self) -> None:
        renderer = CONTROLLER.SafeTeletypeRenderer()

        self.assertEqual(renderer.render(b"one\r"), b"one\n")
        self.assertEqual(renderer.render(b"\ntwo\x08\x1b\xff"), b"two\x08\\x1b\\xff")

    def test_historical_projection_hides_only_known_instrumentation_lines(self) -> None:
        projection = CONTROLLER.HistoricalConsoleProjection()

        self.assertEqual(projection.project(b"PB"), b"")
        self.assertEqual(
            projection.project(
                b"TRACE hidden\r\nordinary output\r\n* SKTRACE hidden too\r\n* "
            ),
            b"ordinary output\r\n* ",
        )
        self.assertEqual(projection.flush_pending(), b"* ")

    def test_network_unix_prompt_offset_retains_the_real_prompt(self) -> None:
        data = b"boot\r\n# first\r\n# "

        offset = CONTROLLER.network_unix_prompt_offset(data)

        self.assertEqual(data[offset:], b"# ")

    def test_historical_client_connection_closes_over_transport_evidence(self) -> None:
        self.assertEqual(
            CONTROLLER.terminal_connection_evidence_failures(
                VALID_HISTORICAL_TERMINAL,
                VALID_ITS,
                VALID_IMP6,
                VALID_IMP62,
            ),
            [],
        )

        failures = CONTROLLER.terminal_connection_evidence_failures(
            VALID_HISTORICAL_TERMINAL.replace(
                CONTROLLER.NETWORK_UNIX_TELNET_BANNER, b""
            ),
            VALID_ITS,
            VALID_IMP6,
            VALID_IMP62,
        )
        self.assertTrue(any("command interface" in failure for failure in failures))

    def test_historical_fidelity_facts_require_real_client_controls_and_time(self) -> None:
        input_bytes = b"/usr/bin/telnet\rconnect - -h 106\r:TIME\r^ayt\r^msg\r^character\r"
        output_bytes = (
            VALID_HISTORICAL_TERMINAL
            + b":TIME\r\nThe time is 22:00:03 EDT.\r\n"
            + b"Today is Monday, the 1st of September, 2025.\r\n"
            + b"KA ITS 1652 has run for 1 minute.\r\n"
            + b"^ayt\r\nYES^msg\r\n Msgmode\r\n^character\r\n Charmode\r\n"
        )

        facts = CONTROLLER.historical_fidelity_facts(input_bytes, output_bytes)

        self.assertTrue(facts["fidelity_complete"])
        self.assertFalse(
            CONTROLLER.historical_fidelity_facts(
                input_bytes.replace(b"^ayt\r", b""), output_bytes
            )["fidelity_complete"]
        )


if __name__ == "__main__":
    unittest.main()
