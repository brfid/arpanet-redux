from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
from simh_shutdown import quit_simh_cleanly  # noqa: E402


class FakeChild:
    def __init__(self, *, fail_before_prompt: bool = False) -> None:
        self.events: list[tuple[object, ...]] = []
        self.fail_before_prompt = fail_before_prompt

    def sendcontrol(self, character: str) -> None:
        self.events.append(("sendcontrol", character))

    def expect_exact(self, pattern: str, *, timeout: float) -> None:
        self.events.append(("expect_exact", pattern, timeout))
        if pattern == "sim>" and self.fail_before_prompt:
            raise RuntimeError("monitor prompt absent")

    def sendline(self, line: str) -> None:
        self.events.append(("sendline", line))

    def expect(self, pattern: object, *, timeout: float) -> None:
        self.events.append(("expect", pattern, timeout))


class SimhShutdownTests(unittest.TestCase):
    def test_waits_for_monitor_and_goodbye_before_eof(self) -> None:
        child = FakeChild()
        eof = object()

        quit_simh_cleanly(child, eof, timeout=7)

        self.assertEqual(
            child.events,
            [
                ("sendcontrol", "e"),
                ("expect_exact", "sim>", 7),
                ("sendline", "quit"),
                ("expect_exact", "Goodbye", 7),
                ("expect", eof, 7),
            ],
        )

    def test_never_sends_quit_before_the_monitor_prompt(self) -> None:
        child = FakeChild(fail_before_prompt=True)

        with self.assertRaisesRegex(RuntimeError, "monitor prompt absent"):
            quit_simh_cleanly(child, object())

        self.assertEqual(
            child.events,
            [
                ("sendcontrol", "e"),
                ("expect_exact", "sim>", 15),
            ],
        )


if __name__ == "__main__":
    unittest.main()
