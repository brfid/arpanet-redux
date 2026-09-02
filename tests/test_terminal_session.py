from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ncc.terminal_session import (
    TerminalSessionRecorder,
    TerminalSessionStreamError,
    read_terminal_session_stream,
)


class TerminalSessionTests(unittest.TestCase):
    def test_round_trip_preserves_directional_bytes_and_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "terminal-session.jsonl"
            recorder = TerminalSessionRecorder(
                path,
                run_id="terminal-test",
                started_at="2026-09-01T12:00:00Z",
                repository_revision="1" * 40,
                max_chunk_bytes=3,
            )
            recorder.bytes(
                "pdp11-to-operator", b"UNIX\r\n", observed_at="2026-09-01T12:00:01Z"
            )
            recorder.bytes(
                "operator-to-pdp11", b"telnet\r", observed_at="2026-09-01T12:00:02Z"
            )
            recorder.control(
                "blocked-simulator-wru",
                observed_at="2026-09-01T12:00:03Z",
            )
            recorder.complete(
                observed_at="2026-09-01T12:00:04Z", reason="operator-exit"
            )
            recorder.close()

            stream = read_terminal_session_stream(path)

            self.assertEqual(stream.output_bytes, b"UNIX\r\n")
            self.assertEqual(stream.input_bytes, b"telnet\r")
            self.assertEqual(stream.controls, (("blocked-simulator-wru", 1),))
            self.assertTrue(stream.is_terminal)
            self.assertEqual(stream.end_reason, "operator-exit")
            self.assertEqual(stream.header["terminal"]["mode"], "character-oriented")

    def test_digest_tampering_and_records_after_end_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "terminal-session.jsonl"
            recorder = TerminalSessionRecorder(
                path,
                run_id="terminal-test",
                started_at="2026-09-01T12:00:00Z",
                repository_revision="2" * 40,
            )
            recorder.bytes(
                "operator-to-pdp11", b"x", observed_at="2026-09-01T12:00:01Z"
            )
            recorder.complete(observed_at="2026-09-01T12:00:02Z", reason="input-eof")
            recorder.close()

            records = [json.loads(line) for line in path.read_text().splitlines()]
            records[1]["sha256"] = "0" * 64
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            with self.assertRaisesRegex(TerminalSessionStreamError, "digest"):
                read_terminal_session_stream(path)

            records[1]["sha256"] = __import__("hashlib").sha256(b"x").hexdigest()
            records.append(records[1])
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            with self.assertRaisesRegex(TerminalSessionStreamError, "after session-end"):
                read_terminal_session_stream(path)

    def test_limits_and_interrupted_tail_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "terminal-session.jsonl"
            recorder = TerminalSessionRecorder(
                path,
                run_id="terminal-test",
                started_at="2026-09-01T12:00:00Z",
                repository_revision="3" * 40,
                max_input_bytes=2,
                max_output_bytes=2,
                max_chunk_bytes=2,
            )
            recorder.bytes(
                "operator-to-pdp11", b"ab", observed_at="2026-09-01T12:00:01Z"
            )
            with self.assertRaisesRegex(TerminalSessionStreamError, "input exceeds"):
                recorder.bytes(
                    "operator-to-pdp11", b"c", observed_at="2026-09-01T12:00:02Z"
                )
            recorder.close()
            with path.open("a") as stream:
                stream.write('{"record_type":')

            parsed = read_terminal_session_stream(path)

            self.assertEqual(parsed.input_bytes, b"ab")
            self.assertFalse(parsed.is_terminal)
            self.assertTrue(parsed.has_incomplete_final_record)

    def test_boolean_sequences_and_counts_do_not_alias_integers(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "terminal-session.jsonl"
            recorder = TerminalSessionRecorder(
                path,
                run_id="terminal-test",
                started_at="2026-09-01T12:00:00Z",
                repository_revision="4" * 40,
            )
            recorder.bytes(
                "operator-to-pdp11", b"x", observed_at="2026-09-01T12:00:01Z"
            )
            recorder.complete(observed_at="2026-09-01T12:00:02Z", reason="input-eof")
            recorder.close()
            records = [json.loads(line) for line in path.read_text().splitlines()]

            records[1]["sequence"] = True
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            with self.assertRaisesRegex(TerminalSessionStreamError, "ordering"):
                read_terminal_session_stream(path)

            records[1]["sequence"] = 1
            records[2]["input_bytes"] = True
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            with self.assertRaisesRegex(TerminalSessionStreamError, "counts"):
                read_terminal_session_stream(path)


if __name__ == "__main__":
    unittest.main()
