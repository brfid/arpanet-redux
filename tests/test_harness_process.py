from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "scripts" / "two-its-controller.py"
SPEC = importlib.util.spec_from_file_location("two_its_controller_process", CONTROLLER_PATH)
assert SPEC is not None and SPEC.loader is not None
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


PTY_PROGRAM = """import os
import tty

tty.setraw(0)
os.write(1, b"READY FIRST SECOND\\n")
line = bytearray()
while True:
    byte = os.read(0, 1)
    if byte == b"\\x1c":
        os.write(1, b"sim> ")
        continue
    line.extend(byte)
    if byte == b"\\r":
        if line == b"quit\\r":
            break
        os.write(1, b"RECEIVED:" + bytes(line))
        line.clear()
"""

IMP_PROGRAM = """import signal
import sys
import time

def stop(_signum, _frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
print("IMP CONSOLE", flush=True)
print("IMP DEBUG", file=sys.stderr, flush=True)
while True:
    time.sleep(0.1)
"""


def write_program(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="ascii")
    return path


def wait_for_files(*paths: Path, timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(path.exists() and path.stat().st_size for path in paths):
            return
        time.sleep(0.01)
    raise TimeoutError(f"process output did not appear: {paths!r}")


class HarnessProcessContractTests(unittest.TestCase):
    def test_manifest_append_validates_keys_and_preserves_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            manifest = Path(directory_name) / "run.env"
            manifest.write_text("", encoding="ascii")

            CONTROLLER.append_manifest(manifest, "process.host-106.pid", 1234)
            CONTROLLER.append_manifest(manifest, "path.console", "/tmp/a b")

            expected = "process.host-106.pid=1234\npath.console=/tmp/a b\n"
            self.assertEqual(manifest.read_text(encoding="utf-8"), expected)
            with self.assertRaisesRegex(ValueError, "invalid manifest key"):
                CONTROLLER.append_manifest(manifest, "bad key", "unchanged")
            self.assertEqual(manifest.read_text(encoding="utf-8"), expected)

    def test_pty_process_attributes_io_and_stops_from_running_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            program = write_program(directory, "pty_program.py", PTY_PROGRAM)
            manifest = directory / "run.env"
            manifest.write_text("", encoding="ascii")
            console_log = directory / "console.log"
            sent_log = directory / "sent.log"
            process = CONTROLLER.PtyProcess(
                "host-test",
                Path(sys.executable),
                program,
                directory,
                console_log,
                sent_log,
                manifest,
            )
            self.addCleanup(process.stop, True)

            process.launch(state="BOOTING")
            process.expect("READY", timeout=3)
            index, match = process.expect_any((b"SECOND", b"FIRST"), timeout=1)
            self.assertEqual((index, match.group()), (1, b"FIRST"))
            offset = process.position()
            process.send("PING\r")
            process.expect(b"RECEIVED:PING\r", timeout=3)
            self.assertIn(b"RECEIVED:PING\r", process.output_from(offset))
            process.state = "RUNNING"
            pid = process.process.pid

            process.stop()

            self.assertEqual(process.state, "STOPPED")
            self.assertEqual(process.process.poll(), 0)
            self.assertIsNone(process.master_fd)
            self.assertFalse(process.reader.is_alive())
            self.assertTrue(process.console_stream.closed)
            self.assertTrue(process.sent_stream.closed)
            self.assertEqual(
                manifest.read_text(encoding="utf-8"),
                f"process.host-test.pid={pid}\n",
            )
            sent_lines = sent_log.read_text(encoding="ascii").splitlines()
            self.assertEqual(
                [line.rsplit(" ", 1)[1] for line in sent_lines],
                ["50494e470d", "1c", "717569740d"],
            )
            for line in sent_lines:
                self.assertRegex(
                    line,
                    re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z [0-9a-f]+$"),
                )
            self.assertIn(b"sim> ", console_log.read_bytes())

    def test_pty_force_stop_sends_no_simulator_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            program = write_program(directory, "pty_program.py", PTY_PROGRAM)
            manifest = directory / "run.env"
            manifest.write_text("", encoding="ascii")
            sent_log = directory / "sent.log"
            process = CONTROLLER.PtyProcess(
                "forced-host",
                Path(sys.executable),
                program,
                directory,
                directory / "console.log",
                sent_log,
                manifest,
            )
            self.addCleanup(process.stop, True)

            process.launch(state="RUNNING")
            process.expect("READY", timeout=3)
            process.stop(force=True)

            self.assertEqual(process.state, "STOPPED")
            self.assertIsNotNone(process.process.poll())
            self.assertEqual(sent_log.read_text(encoding="ascii"), "")

    def test_imp_process_owns_logs_liveness_and_bounded_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            program = write_program(directory, "imp_program.py", IMP_PROGRAM)
            manifest = directory / "run.env"
            manifest.write_text("", encoding="ascii")
            process = CONTROLLER.ImpProcess(
                "imp-test",
                Path(sys.executable),
                program,
                directory,
                directory,
                manifest,
            )
            self.addCleanup(process.stop)

            process.launch()
            wait_for_files(process.console_path, process.debug_path)
            process.ensure_alive()
            pid = process.process.pid
            process.stop()

            self.assertEqual(process.process.poll(), 0)
            with self.assertRaisesRegex(RuntimeError, "imp-test exited early"):
                process.ensure_alive()
            self.assertIsNone(process.master_fd)
            self.assertTrue(process.console_stream.closed)
            self.assertTrue(process.debug_stream.closed)
            self.assertEqual(process.console_path.read_bytes(), b"IMP CONSOLE\n")
            self.assertEqual(process.debug_path.read_bytes(), b"IMP DEBUG\n")
            self.assertEqual(
                manifest.read_text(encoding="utf-8"),
                f"process.imp-test.pid={pid}\n",
            )


if __name__ == "__main__":
    unittest.main()
