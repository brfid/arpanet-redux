from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ncc.two_its_summary import TwoItsSummaryError, summarize_two_its_result


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "ncc"
SCRIPT = ROOT / "scripts" / "ncc-summarize-two-its.py"


class TwoItsSummaryTests(unittest.TestCase):
    def test_adapts_passing_formal_result_without_embedding_the_sentinel(self) -> None:
        summary = summarize_two_its_result(FIXTURES / "two-its-result-passing")
        document = summary.to_dict()

        self.assertEqual(summary.run_id, "run:two-its-result-passing")
        self.assertEqual(document["run"]["outcome"], "passed")
        self.assertEqual(
            [gate["verdict"] for gate in document["gates"]], ["passed", "passed"]
        )
        self.assertEqual(document["derived_states"][0]["state"], "up")
        self.assertNotIn("ARPANET-REDUX-FIXTURE", summary.to_json())
        self.assertEqual(
            document["observations"][1]["details"]["sentinel_sha256"],
            "1c4ac51cb63defaa004b8b9855d42f018880c5ac2de2177dc62bbc2472f4e32b",
        )

    def test_adapts_a_failed_formal_result_to_incomplete_not_network_down(self) -> None:
        summary = summarize_two_its_result(FIXTURES / "two-its-result-incomplete")
        document = summary.to_dict()

        self.assertEqual(document["run"]["outcome"], "incomplete")
        self.assertEqual(document["derived_states"][0]["state"], "incomplete")
        self.assertEqual(
            [gate["verdict"] for gate in document["gates"]],
            ["inconclusive", "inconclusive"],
        )

    def test_rejects_pass_claim_when_sentinel_evidence_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = Path(directory_name) / "two-its-result-passing"
            shutil.copytree(FIXTURES / "two-its-result-passing", result)
            evidence = result / "sentinel-evidence.txt"
            evidence.write_text(
                evidence.read_text(encoding="ascii").replace(
                    "recovered_sha256=1c4ac51cb63defaa004b8b9855d42f018880c5ac2de2177dc62bbc2472f4e32b",
                    "recovered_sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(TwoItsSummaryError, "digests do not agree"):
                summarize_two_its_result(result)

    def test_rejects_manifest_and_controller_outcome_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = Path(directory_name) / "two-its-result-passing"
            shutil.copytree(FIXTURES / "two-its-result-passing", result)
            (result / "outcome.txt").write_text("failed\n", encoding="ascii")
            with self.assertRaisesRegex(TwoItsSummaryError, "does not match"):
                summarize_two_its_result(result)

    def test_rejects_incomplete_or_dirty_manifest_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = Path(directory_name) / "two-its-result-passing"
            shutil.copytree(FIXTURES / "two-its-result-passing", result)
            manifest = result / "runtime" / "run.env"
            original = manifest.read_text(encoding="ascii")
            manifest.write_text(
                original.replace("repository.tracked_dirty=0", "repository.tracked_dirty=1"),
                encoding="ascii",
            )
            with self.assertRaisesRegex(TwoItsSummaryError, "clean project repository"):
                summarize_two_its_result(result)

            manifest.write_text(
                original.replace(
                    "source.h316-simh.tracked_dirty=0",
                    "source.h316-simh.tracked_dirty=1",
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(TwoItsSummaryError, "clean source"):
                summarize_two_its_result(result)

            manifest.write_text(
                "\n".join(
                    line
                    for line in original.splitlines()
                    if not line.startswith("finished_utc=")
                )
                + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(TwoItsSummaryError, "finished_utc"):
                summarize_two_its_result(result)

    def test_accepts_an_interrupted_nonzero_formal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = Path(directory_name) / "two-its-result-incomplete"
            shutil.copytree(FIXTURES / "two-its-result-incomplete", result)
            manifest = result / "runtime" / "run.env"
            manifest.write_text(
                manifest.read_text(encoding="ascii").replace("exit_status=1", "exit_status=130"),
                encoding="ascii",
            )
            summary = summarize_two_its_result(result)
            self.assertEqual(summary.to_dict()["run"]["outcome"], "incomplete")

    def test_read_only_command_writes_a_summary_to_standard_output(self) -> None:
        result = subprocess.run(
            [sys.executable, SCRIPT, FIXTURES / "two-its-result-passing"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"outcome": "passed"', result.stdout)
        self.assertNotIn("ARPANET-REDUX-FIXTURE", result.stdout)


if __name__ == "__main__":
    unittest.main()
