from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

from ncc.replay import replay_frames
from ncc.run_summary import load_run_summary
from ncc.viewer import render_summary_html


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ncc" / "run-summary-passing.json"
NETWORK_FIXTURE = (
    ROOT / "tests" / "fixtures" / "ncc" / "run-summary-network-behavior-v2.json"
)
SCRIPT = ROOT / "scripts" / "ncc-render-summary.py"


class ReplayAndViewerTests(unittest.TestCase):
    def test_replay_preserves_the_validated_observation_order(self) -> None:
        summary = load_run_summary(FIXTURE)
        frames = replay_frames(summary)

        self.assertEqual([frame.sequence for frame in frames], [1, 2, 3, 4])
        self.assertEqual(frames[0].known_states, {"imp:62": "ready"})
        self.assertEqual(
            frames[-1].known_states["route:host176-to-host106"], "passed"
        )

    def test_viewer_marks_configured_topology_and_exposes_traceability(self) -> None:
        summary = load_run_summary(FIXTURE)
        page = render_summary_html(summary)

        self.assertIn("Signal ribbon", page)
        self.assertIn("Fixed logical positions are configured facts", page)
        self.assertIn("This viewer is read-only", page)
        self.assertIn('class="ribbon state-up"', page)
        self.assertIn("gate:two-its-application", page)
        self.assertIn("observation:3, observation:4", page)
        self.assertIn("const frames =", page)

    def test_command_renders_a_self_contained_html_document(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT, FIXTURE],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("<!doctype html>"))
        self.assertIn("Observation replay", result.stdout)
        self.assertNotIn("http://", result.stdout)
        self.assertNotIn("https://", result.stdout)

    def test_viewer_exposes_network_gate_and_derived_link_state(self) -> None:
        summary = load_run_summary(NETWORK_FIXTURE)
        page = render_summary_html(summary)

        self.assertIn("network-behavior", page)
        self.assertIn("derived:direct-line", page)
        self.assertIn(
            'class="link state-looped" data-subject="link:imp5-imp6-direct"',
            page,
        )


if __name__ == "__main__":
    unittest.main()
