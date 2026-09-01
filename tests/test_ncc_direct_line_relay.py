from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELAY = ROOT / "scripts" / "ncc-direct-line-relay.py"


def load_relay():
    spec = importlib.util.spec_from_file_location("ncc_direct_line_relay", RELAY)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load direct-line relay")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DirectLineRelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.relay = load_relay()

    def test_request_file_changes_state_and_acknowledges_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            request = directory / "cut.request"
            state = directory / "cut.state.json"
            self.assertTrue(
                self.relay.forwarding_enabled(
                    elapsed=500,
                    forward_seconds=None,
                    cut_request=request,
                )
            )
            request.write_text("cut\n", encoding="ascii")
            self.assertFalse(
                self.relay.forwarding_enabled(
                    elapsed=500,
                    forward_seconds=None,
                    cut_request=request,
                )
            )
            self.relay.publish_cut_state(state, "2026-09-01T12:00:00Z")

            cut = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(cut["state"], "cut")
            self.assertEqual(cut["kind"], "two-ended-udp-cut-state")
            self.assertEqual(cut["fault_started_at"], "2026-09-01T12:00:00Z")
            self.assertEqual(list(directory.glob("*.tmp")), [])

    def test_elapsed_mode_retains_the_old_transition(self) -> None:
        self.assertTrue(
            self.relay.forwarding_enabled(
                elapsed=44.9,
                forward_seconds=45,
                cut_request=None,
            )
        )
        self.assertFalse(
            self.relay.forwarding_enabled(
                elapsed=45,
                forward_seconds=45,
                cut_request=None,
            )
        )

    def test_time_mode_keeps_the_existing_command_contract(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(RELAY), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("--forward-seconds", completed.stdout)
        self.assertIn("--cut-request", completed.stdout)


if __name__ == "__main__":
    unittest.main()
