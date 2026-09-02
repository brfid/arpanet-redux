from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ncc.historical_summary import (
    HistoricalLineSummaryError,
    summarize_historical_line_result,
)
from tests.support.historical_line_result import (
    HISTORICAL_LINE_TOPOLOGY as TOPOLOGY,
    create_historical_line_result,
    file_digests,
    topology_digest,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ncc-summarize-historical-line.py"


class HistoricalLineSummaryTests(unittest.TestCase):
    def test_adapts_supported_fault_result_without_mapping_alternate_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result_path = create_historical_line_result(
                Path(directory_name), final_state="down"
            )

            summary = summarize_historical_line_result(result_path, TOPOLOGY)
            document = summary.to_dict()

            self.assertEqual(document["schema_version"], 2)
            self.assertEqual(document["run"]["outcome"], "passed")
            direct = next(
                state
                for state in document["derived_states"]
                if state["subject_id"] == "link:imp5-imp6-direct"
            )
            self.assertEqual(direct["state"], "down")
            self.assertEqual(
                direct["supporting_observation_ids"],
                ["observation:historical:8", "observation:historical:10"],
            )
            self.assertEqual(document["gates"][0]["kind"], "network-behavior")
            historical_subjects = {
                observation.get("details", {})
                .get("historical_event", {})
                .get("subject")
                for observation in document["observations"]
            }
            self.assertNotIn("imp:7:line:1", historical_subjects)

    def test_adapts_supported_loopback_result_and_command_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result_path = create_historical_line_result(
                Path(directory_name), final_state="looped"
            )
            before = file_digests(result_path)

            result = subprocess.run(
                [sys.executable, SCRIPT, result_path, "--topology", TOPOLOGY],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            direct = next(
                state
                for state in document["derived_states"]
                if state["subject_id"] == "link:imp5-imp6-direct"
            )
            self.assertEqual(direct["state"], "looped")
            self.assertEqual(before, file_digests(result_path))

    def test_rejects_topology_digest_and_reducer_verdict_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result_path = create_historical_line_result(
                Path(directory_name), final_state="down"
            )
            manifest_path = result_path / "runtime" / "run.env"
            manifest = manifest_path.read_text(encoding="ascii")
            manifest_path.write_text(
                manifest.replace(
                    f"sha256.shared-topology={topology_digest()}",
                    f"sha256.shared-topology={'0' * 64}",
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(
                HistoricalLineSummaryError, "topology digest"
            ):
                summarize_historical_line_result(result_path, TOPOLOGY)

            manifest_path.write_text(manifest, encoding="ascii")
            verdict_path = result_path / "verdict.json"
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
            verdict["direct_line"]["final_supporting_sequences"] = [8, 9]
            verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
            with self.assertRaisesRegex(
                HistoricalLineSummaryError, "supporting sequences disagree"
            ):
                summarize_historical_line_result(result_path, TOPOLOGY)

    def test_rejects_unclean_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result_path = create_historical_line_result(
                Path(directory_name), final_state="down"
            )
            manifest_path = result_path / "runtime" / "run.env"
            original = manifest_path.read_text(encoding="ascii")
            manifest_path.write_text(
                original.replace(
                    "repository.tracked_dirty=0", "repository.tracked_dirty=1"
                ),
                encoding="ascii",
            )

            with self.assertRaisesRegex(
                HistoricalLineSummaryError, "clean project repository"
            ):
                summarize_historical_line_result(result_path, TOPOLOGY)

            manifest_path.write_text(
                original.replace(
                    "source.h316-simh.tracked_dirty=0",
                    "source.h316-simh.tracked_dirty=1",
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(HistoricalLineSummaryError, "clean source"):
                summarize_historical_line_result(result_path, TOPOLOGY)

if __name__ == "__main__":
    unittest.main()
