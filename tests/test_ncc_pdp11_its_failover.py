from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = ROOT / "scripts" / "ncc-evaluate-pdp11-its-failover.py"
SMOKE_PATH = ROOT / "scripts" / "smoke-ncc-pdp11-its-failover.sh"


def load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "ncc_evaluate_pdp11_its_failover", EVALUATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load failover evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_event(
    imp: int, line: int, state: str, neighbor: int | None
) -> dict[str, object]:
    return {
        "version": 1,
        "type": "line-endpoint.state",
        "subject": f"imp:{imp}:line:{line}",
        "state": state,
        "details": {"neighbor_imp": neighbor},
    }


def report(
    imp: int,
    observed_at: str,
    events: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "source_imp": imp,
        "observed_at": observed_at,
        "events": events,
    }


class ApplicationFailoverEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = load_evaluator()

    def test_accepts_failover_but_retains_report_lines_as_candidates(self) -> None:
        result = self.evaluate()

        self.assertTrue(result["passed"])
        candidate = result["discovered_report_mapping"]
        self.assertFalse(candidate["promoted_to_topology"])
        self.assertEqual(
            candidate["direct_application_link"],
            {
                "imp62_report_line": 1,
                "imp6_report_line": 3,
                "pre_cut_state": "up",
                "post_cut_state": "down",
            },
        )
        self.assertEqual(
            candidate["alternate_application_link"]["imp62_report_line"],
            2,
        )
        self.assertEqual(
            candidate["alternate_application_link"]["imp7_report_line"],
            3,
        )

    def test_rejects_application_success_without_the_typed_alternate_route(
        self,
    ) -> None:
        journey = self.journey()
        journey["route_id"] = "route:host176-to-host106"

        result = self.evaluate(journey=journey)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["typed-alternate-journey"])

    def test_rejects_a_missing_reciprocal_down_report(self) -> None:
        receiver = self.receiver()
        receiver["trouble_reports"] = [
            item
            for item in receiver["trouble_reports"]
            if not (
                item["source_imp"] == 6
                and item["observed_at"] == "2026-09-01T12:01:20Z"
            )
        ]

        with self.assertRaisesRegex(ValueError, "reciprocal post-cut down"):
            self.evaluate(receiver=receiver)

    def test_rejects_an_ambiguous_report_line_candidate(self) -> None:
        receiver = self.receiver()
        receiver["trouble_reports"][0]["events"].append(line_event(62, 4, "up", 6))

        with self.assertRaisesRegex(ValueError, "one unique line"):
            self.evaluate(receiver=receiver)

    def test_harness_owns_one_cut_relay_and_reserves_every_bound_port(self) -> None:
        source = SMOKE_PATH.read_text(encoding="utf-8")

        self.assertIn('reserve-udp-ports.py" 18', source)
        self.assertIn('--cut-request "$cut_request"', source)
        self.assertIn('--cut-state "$cut_state"', source)
        self.assertIn('--imp7-debug "$results_dir/imp7.debug.log"', source)
        self.assertIn("ncc-evaluate-pdp11-its-failover.py", source)

    def evaluate(
        self,
        *,
        receiver: dict[str, object] | None = None,
        journey: dict[str, object] | None = None,
    ):
        return self.evaluator.evaluate(
            receiver=receiver or self.receiver(),
            relay={
                "cut_mode": "request-file",
                "fault_started_at": "2026-09-01T12:01:00Z",
                "directions": {
                    "a-to-b": {"forwarded": 10, "dropped": 20},
                    "b-to-a": {"forwarded": 11, "dropped": 21},
                },
                "unexpected_sources": [],
            },
            cut_state={
                "state": "cut",
                "fault_started_at": "2026-09-01T12:01:00Z",
            },
            application={
                "connection_open": "1",
                "pre_cut_remote_time": "structured",
                "cut_acknowledged": "1",
                "session_survived_cut": "1",
                "post_cut_remote_time": "structured",
            },
            journey=journey or self.journey(),
            cleanup={"surviving_owned_processes": "0"},
            outcome="passed",
            manifest=self.manifest(),
            identities={
                "topology_id": "topology:ncc-pdp11-its-application-failover",
                "receiver_topology_id": "topology:ncc-pdp11-its-application-failover",
                "run_id": "failover-run",
                "journey_run_id": "failover-run",
            },
        )

    @staticmethod
    def receiver() -> dict[str, object]:
        before = "2026-09-01T12:00:20Z"
        after = "2026-09-01T12:01:20Z"
        return {
            "topology_id": "topology:ncc-pdp11-its-application-failover",
            "trouble_reports": [
                report(62, before, [line_event(62, 1, "up", 6)]),
                report(6, before, [line_event(6, 3, "up", 62)]),
                report(5, after, [line_event(5, 1, "up", 6)]),
                report(
                    6,
                    after,
                    [
                        line_event(6, 3, "down", None),
                        line_event(6, 2, "up", 7),
                    ],
                ),
                report(
                    7,
                    after,
                    [
                        line_event(7, 3, "up", 62),
                        line_event(7, 2, "up", 6),
                    ],
                ),
                report(
                    62,
                    after,
                    [
                        line_event(62, 1, "down", None),
                        line_event(62, 2, "up", 7),
                    ],
                ),
            ],
        }

    @staticmethod
    def journey() -> dict[str, object]:
        return {
            "journey_id": "journey:network-unix-telnet-post-cut",
            "route_id": "route:host176-to-host106-alternate",
            "observation_count": 14,
            "state": "missing-boundary",
            "first_boundary": "boundary:request:8",
        }

    @staticmethod
    def manifest() -> dict[str, str]:
        return {
            "repository.tracked_dirty": "0",
            "source.arpanet-in-a-box.tracked_dirty": "0",
            "source.network-unix-v6.tracked_dirty": "0",
            "source.h316-simh.tracked_dirty": "0",
            "source.ka10-simh.tracked_dirty": "0",
            "source.imp11a-simh.tracked_dirty": "0",
            "cleanup.outer-runtime": "passed",
        }


if __name__ == "__main__":
    unittest.main()
