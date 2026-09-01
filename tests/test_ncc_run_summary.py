from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from ncc.run_summary import (
    RUN_SUMMARY_SCHEMA_VERSION,
    RunSummaryValidationError,
    load_run_summary,
    run_summary_from_mapping,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "ncc"


class RunSummaryTests(unittest.TestCase):
    def test_loads_passing_missing_and_partition_fixtures(self) -> None:
        expected = {
            "run-summary-passing.json": (1, "fixture:two-its-passing", "passed", "up"),
            "run-summary-missing-observation.json": (
                1,
                "fixture:missing-observation",
                "incomplete",
                "unknown",
            ),
            "run-summary-partition.json": (
                1,
                "fixture:partition-like",
                "failed",
                "partitioned",
            ),
        }
        for filename, (schema_version, run_id, outcome, path_state) in expected.items():
            with self.subTest(filename=filename):
                summary = load_run_summary(FIXTURES / filename)
                document = summary.to_dict()
                self.assertEqual(summary.run_id, run_id)
                self.assertEqual(document["schema_version"], schema_version)
                self.assertEqual(document["run"]["outcome"], outcome)
                self.assertEqual(document["derived_states"][-1]["state"], path_state)

    def test_accepts_version_two_network_behavior_with_complete_support(self) -> None:
        summary = load_run_summary(FIXTURES / "run-summary-network-behavior-v2.json")
        document = summary.to_dict()

        self.assertEqual(document["schema_version"], RUN_SUMMARY_SCHEMA_VERSION)
        self.assertEqual(document["derived_states"][0]["state"], "looped")
        self.assertEqual(document["gates"][0]["kind"], "network-behavior")

    def test_version_two_network_pass_requires_harness_and_support_closure(self) -> None:
        document = json.loads(
            (FIXTURES / "run-summary-network-behavior-v2.json").read_text(
                encoding="utf-8"
            )
        )
        document["gates"][0]["evidence_observation_ids"].remove(
            "observation:imp5-looped"
        )
        with self.assertRaisesRegex(
            RunSummaryValidationError, "complete derived-state support closure"
        ):
            run_summary_from_mapping(document)

        document = json.loads(
            (FIXTURES / "run-summary-network-behavior-v2.json").read_text(
                encoding="utf-8"
            )
        )
        document["observations"][-1]["state"] = "failed"
        with self.assertRaisesRegex(
            RunSummaryValidationError, "passed harness observation"
        ):
            run_summary_from_mapping(document)

    def test_version_one_does_not_silently_accept_version_two_line_states(self) -> None:
        document = json.loads(
            (FIXTURES / "run-summary-passing.json").read_text(encoding="utf-8")
        )
        document["derived_states"][-1]["state"] = "looped"
        with self.assertRaisesRegex(RunSummaryValidationError, "must be one of"):
            run_summary_from_mapping(document)

    def test_serialization_is_deterministic_and_does_not_share_mutable_state(self) -> None:
        summary = load_run_summary(FIXTURES / "run-summary-passing.json")
        first = summary.to_dict()
        first["run"]["id"] = "mutated"
        self.assertEqual(summary.run_id, "fixture:two-its-passing")
        self.assertEqual(summary.to_json(), summary.to_json())
        self.assertEqual(json.loads(summary.to_json())["run"]["id"], summary.run_id)

    def test_rejects_gate_assertion_without_passing_application_evidence(self) -> None:
        with self.assertRaisesRegex(
            RunSummaryValidationError, "passes without passed application evidence"
        ):
            load_run_summary(FIXTURES / "run-summary-assertion-mismatch.json")

    def test_rejects_unknown_fields_and_noncontiguous_observation_order(self) -> None:
        document = json.loads(
            (FIXTURES / "run-summary-passing.json").read_text(encoding="utf-8")
        )
        document["unexpected"] = True
        with self.assertRaisesRegex(RunSummaryValidationError, "unknown fields"):
            run_summary_from_mapping(document)

        document.pop("unexpected")
        document["observations"][1]["sequence"] = 3
        with self.assertRaisesRegex(RunSummaryValidationError, "sequence must be 2"):
            run_summary_from_mapping(document)

        document["observations"][1]["sequence"] = 2
        document["schema_version"] = True
        with self.assertRaisesRegex(RunSummaryValidationError, "schema_version must be"):
            run_summary_from_mapping(document)

    def test_rejects_non_integer_sequence_and_non_json_details(self) -> None:
        document = json.loads(
            (FIXTURES / "run-summary-passing.json").read_text(encoding="utf-8")
        )
        document["observations"][0]["sequence"] = True
        with self.assertRaisesRegex(RunSummaryValidationError, "sequence must be 1"):
            run_summary_from_mapping(document)

        document["observations"][0]["sequence"] = 1
        document["observations"][0]["details"] = {"rate": math.inf}
        with self.assertRaisesRegex(RunSummaryValidationError, "non-finite"):
            run_summary_from_mapping(document)

        document["observations"][0]["details"] = {"words": (1, 2)}
        with self.assertRaisesRegex(RunSummaryValidationError, "only JSON values"):
            run_summary_from_mapping(document)


if __name__ == "__main__":
    unittest.main()
