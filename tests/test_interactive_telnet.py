from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ncc.interactive_telnet import (
    InteractiveTelnetRecorder,
    InteractiveTelnetStreamError,
    read_interactive_telnet_stream,
    validate_operator_command,
)


REVISION = "1" * 40
STARTED = "2026-09-01T12:00:00Z"


def recorder(path: Path, **limits: int) -> InteractiveTelnetRecorder:
    return InteractiveTelnetRecorder(
        path,
        run_id="pdp11-its-interactive-test",
        started_at=STARTED,
        repository_revision=REVISION,
        service_user="53TLNT",
        **limits,
    )


class InteractiveTelnetStreamTests(unittest.TestCase):
    def test_round_trips_attributed_prompt_framed_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "interactive-telnet.jsonl"
            writer = recorder(path)
            first = writer.command(":TIME", observed_at="2026-09-01T12:00:01Z")
            writer.result(
                first,
                observed_at="2026-09-01T12:00:02Z",
                status="complete",
                elapsed_ms=120,
                captured=b":TIME\r\nThe time is 08:00:01 EDT.\r\n*",
            )
            second = writer.command(":WHO", observed_at="2026-09-01T12:00:03Z")
            writer.result(
                second,
                observed_at="2026-09-01T12:00:04Z",
                status="complete",
                elapsed_ms=80,
                captured=b":WHO\r\n53 TLNT HST176\r\n*",
            )
            writer.complete(
                observed_at="2026-09-01T12:00:05Z", reason="operator-quit"
            )
            writer.close()

            stream = read_interactive_telnet_stream(path)

            self.assertTrue(stream.is_terminal)
            self.assertEqual(stream.end_reason, "operator-quit")
            self.assertEqual(stream.completed_commands, 2)
            self.assertEqual(stream.failed_commands, 0)
            self.assertEqual(stream.exchanges[0].command, ":TIME")
            self.assertEqual(stream.exchanges[1].prompt_id, "its-ddt-star")
            self.assertEqual(
                stream.to_dict()["exchanges"][0]["captured_latin1"],
                ":TIME\r\nThe time is 08:00:01 EDT.\r\n*",
            )

    def test_reader_ignores_only_an_interrupted_final_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "interactive-telnet.jsonl"
            writer = recorder(path)
            command_id = writer.command(
                ":TIME", observed_at="2026-09-01T12:00:01Z"
            )
            writer.result(
                command_id,
                observed_at="2026-09-01T12:00:02Z",
                status="complete",
                elapsed_ms=1,
                captured=b":TIME\r\n*",
            )
            writer.complete(
                observed_at="2026-09-01T12:00:03Z", reason="input-eof"
            )
            writer.close()
            path.write_bytes(path.read_bytes()[:-1])

            stream = read_interactive_telnet_stream(path)

            self.assertFalse(stream.is_terminal)
            self.assertTrue(stream.has_incomplete_final_record)
            self.assertEqual(stream.completed_commands, 1)

    def test_digest_tampering_and_records_after_end_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "interactive-telnet.jsonl"
            writer = recorder(path)
            command_id = writer.command(
                ":TIME", observed_at="2026-09-01T12:00:01Z"
            )
            writer.result(
                command_id,
                observed_at="2026-09-01T12:00:02Z",
                status="complete",
                elapsed_ms=1,
                captured=b":TIME\r\n*",
            )
            writer.complete(
                observed_at="2026-09-01T12:00:03Z", reason="operator-quit"
            )
            writer.close()
            lines = path.read_text(encoding="utf-8").splitlines()
            result = json.loads(lines[2])
            result["captured_latin1"] = "changed\r\n*"
            lines[2] = json.dumps(result, separators=(",", ":"), sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                InteractiveTelnetStreamError, "byte count|digest"
            ):
                read_interactive_telnet_stream(path)

            lines[2] = json.dumps(
                {
                    **result,
                    "captured_latin1": ":TIME\r\n*",
                    "captured_bytes": 8,
                    "captured_sha256": "0" * 64,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            path.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                InteractiveTelnetStreamError, "digest|after session-end"
            ):
                read_interactive_telnet_stream(path)

    def test_failed_result_stops_further_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "interactive-telnet.jsonl"
            writer = recorder(path)
            command_id = writer.command(
                ":HANG", observed_at="2026-09-01T12:00:01Z"
            )
            writer.result(
                command_id,
                observed_at="2026-09-01T12:01:01Z",
                status="timeout",
                elapsed_ms=60_000,
                captured=b":HANG\r\n",
            )
            with self.assertRaisesRegex(
                InteractiveTelnetStreamError, "after a failed result"
            ):
                writer.command(":TIME", observed_at="2026-09-01T12:01:02Z")
            writer.complete(
                observed_at="2026-09-01T12:01:03Z", reason="failed"
            )
            writer.close()

            stream = read_interactive_telnet_stream(path)
            self.assertEqual(stream.failed_commands, 1)
            self.assertEqual(stream.end_reason, "failed")

    def test_operator_lines_are_printable_ascii_and_bounded(self) -> None:
        self.assertEqual(validate_operator_command(":TIME"), ":TIME")
        for invalid in ("", "   ", "snowman \N{SNOWMAN}", "line\nfeed", "\x1bG"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(InteractiveTelnetStreamError):
                    validate_operator_command(invalid)
        with self.assertRaisesRegex(InteractiveTelnetStreamError, "4-byte"):
            validate_operator_command("12345", 4)


if __name__ == "__main__":
    unittest.main()
