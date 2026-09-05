from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from ncc.harness_process import WRU
from ncc.workspace_shutdown import stop_its, stop_unix


class Guest:
    def __init__(self, replies, initial=b""):
        self.replies = replies
        self.buffer = bytearray(initial)
        self.cursor = 0
        self.sent = []
        self.state = "RUNNING"

    def position(self):
        return len(self.buffer)

    def output_from(self, start):
        return bytes(self.buffer[start:])

    def send(self, data):
        data = data.encode("ascii") if isinstance(data, str) else data
        self.sent.append(data)
        self.buffer.extend(self.replies.get(data, b""))

    def send_slow(self, data, delay=0):
        self.send(data)

    def expect_any(self, patterns, timeout):
        matches = []
        for index, pattern in enumerate(patterns):
            match = re.search(pattern, self.buffer[self.cursor:], re.DOTALL)
            if match is not None:
                matches.append((match.start(), index, match))
        if not matches:
            raise TimeoutError("synthetic missing guest response")
        _, index, match = min(matches)
        self.cursor += match.end()
        return index, match

    def expect(self, pattern, timeout):
        return self.expect_any((pattern,), timeout)[1]


@patch("ncc.workspace_shutdown.time.sleep")
class WorkspaceShutdownTests(unittest.TestCase):
    def test_its_requires_new_guest_completion_before_stopping_cpu(self, _sleep):
        replies = {
            b":lock\r": b"LOCK.156\r\n_",
            b"5kill": b"DO YOU REALLY WANT THE SYSTEM TO GO DOWN?\r\n",
            b"y": b"PLEASE ENTER A BRIEF MESSAGE, ENDED BY ^C\r\n",
            b"\x03": b"SHUTDOWN COMPLETE",
            WRU: b"sim> ",
        }
        guest = Guest(replies, initial=b"old SHUTDOWN COMPLETE")
        stop_its(guest)
        self.assertEqual(guest.sent, [b":lock\r", b"5kill", b"y", b"\x03", WRU])
        self.assertEqual(guest.state, "PROMPT")
        guest = Guest({**replies, b"\x03": b"still shutting down"}, initial=b"old SHUTDOWN COMPLETE")
        with self.assertRaises(TimeoutError):
            stop_its(guest)
        self.assertNotIn(WRU, guest.sent)
        self.assertEqual(guest.state, "RUNNING")

    def test_its_already_finishing_sends_no_more_guest_commands(self, _sleep):
        guest = Guest({b":lock\r": b"SHUTDOWN COMPLETE", WRU: b"sim> "})
        stop_its(guest)
        self.assertEqual(guest.sent, [b":lock\r", WRU])

    def unix(self, *, queue=b"Clock event queue\r\nsim> ", sync=True, echoed_only=False):
        marker = b"ARPANET_WS_" + b"a" * 32
        replies = {
            b"\x7f\r": b"\r\n# ",
            b"echo " + marker + b"\r": (b"echo " + marker + b"\r\n" if echoed_only else b"\r\n" + marker + b"\r\n") + b"# ",
            WRU: b"sim> ",
            b"deposit sr 173030\r": b"sim> ",
            b"kill -1 1\r": b"\r\n# ",
            b"echo $$\r": b"echo $$\r\n00200\r\n# ",
            b"/tmp/helper " + marker + b" 200\r": b"\r\n" + marker + b"\r\n" if sync else b"helper failed",
            b"show queue\r": queue,
        }
        return Guest(replies)

    def test_unix_leaves_historical_client_before_shell_probe(self, _sleep):
        guest = self.unix()
        guest.replies[b"\x7f\r"] = b"\r\n* "
        guest.replies[b"bye\r"] = b"\r\n# "
        stop_unix(guest, "/tmp/helper", "a" * 32)
        self.assertEqual(guest.sent[:2], [b"\x7f\r", b"bye\r"])
        self.assertEqual(guest.state, "PROMPT")

    def test_unix_requires_shell_execution_and_completed_sync(self, _sleep):
        guest = self.unix(echoed_only=True)
        with self.assertRaisesRegex(RuntimeError, "root shell"):
            stop_unix(guest, "/tmp/helper", "a" * 32)
        self.assertNotIn(WRU, guest.sent)
        guest = self.unix(sync=False)
        with self.assertRaises(TimeoutError):
            stop_unix(guest, "/tmp/helper", "a" * 32)
        self.assertEqual(guest.sent.count(WRU), 1)
        self.assertEqual(guest.state, "RUNNING")

    def test_unix_rejects_pending_disk_io_after_sync(self, _sleep):
        guest = self.unix(queue=b"Event queue:\r\n  RL0 at 120\r\nsim> ")
        with self.assertRaisesRegex(RuntimeError, "disk activity"):
            stop_unix(guest, "/tmp/helper", "a" * 32)

    def test_unix_success_leaves_cpu_at_monitor_after_guest_sync(self, _sleep):
        guest = self.unix()
        stop_unix(guest, "/tmp/helper", "a" * 32)
        self.assertEqual(guest.state, "PROMPT")
        self.assertEqual(guest.sent[-1], b"show queue\r")


if __name__ == "__main__":
    unittest.main()
