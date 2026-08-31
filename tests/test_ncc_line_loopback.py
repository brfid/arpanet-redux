from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from ncc.events import EventSource, NccEvent
from ncc.reconciliation import nominal_topology_from_shared
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = ROOT / "config" / "topologies" / "ncc-alternate-path-fault.json"
EVALUATOR_PATH = ROOT / "scripts" / "ncc-evaluate-line-loopback.py"


def load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "ncc_line_loopback_evaluator", EVALUATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load line-loopback evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_event(
    *,
    imp: int,
    state: str,
    neighbor_imp: int | None,
    sequence: int,
    observed_at: str,
) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type="line-endpoint.state",
        subject=f"imp:{imp}:line:1",
        state=state,
        source=EventSource(kind="imp-trouble-report", imp=imp),
        details={"neighbor_imp": neighbor_imp},
    )


class LineLoopbackEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = load_evaluator()
        cls.topology = nominal_topology_from_shared(load_shared_topology(TOPOLOGY_PATH))

    def test_accepts_a_fresh_up_to_reciprocal_looped_transition(self) -> None:
        result = self.evaluator.evaluate(
            topology=self.topology,
            events=self._events(),
            receiver=self._receiver(),
            reflector=self._reflector(),
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["direct_line"]["pre_loop_state"], "up")
        self.assertEqual(
            result["direct_line"]["pre_loop_supporting_sequences"], [1, 2]
        )
        self.assertEqual(result["direct_line"]["final_state"], "looped")
        self.assertEqual(
            result["direct_line"]["final_supporting_sequences"], [3, 4]
        )
        self.assertEqual(
            result["raw_final_direct_endpoints"],
            {
                "5": {
                    "sequence": 3,
                    "observed_at": "2026-08-31T12:01:00Z",
                    "state": "looped",
                    "neighbor_imp": 5,
                },
                "6": {
                    "sequence": 4,
                    "observed_at": "2026-08-31T12:01:00Z",
                    "state": "looped",
                    "neighbor_imp": 6,
                },
            },
        )

    def test_rejects_configured_peer_as_a_loop_neighbor(self) -> None:
        events = list(self._events())
        events[-2] = line_event(
            imp=5,
            state="looped",
            neighbor_imp=6,
            sequence=3,
            observed_at="2026-08-31T12:01:00Z",
        )
        result = self.evaluator.evaluate(
            topology=self.topology,
            events=events,
            receiver=self._receiver(),
            reflector=self._reflector(),
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["raw-endpoints-final-looped-to-self"])
        self.assertFalse(result["checks"]["direct-line-final-looped"])
        self.assertEqual(result["direct_line"]["final_state"], "contradictory")

    def test_rejects_missing_post_loop_imp6_report_without_changing_line_evidence(self) -> None:
        receiver = self._receiver()
        receiver["trouble_reports"] = [
            report
            for report in receiver["trouble_reports"]
            if not (
                report["source_imp"] == 6
                and report["observed_at"] > "2026-08-31T12:00:30Z"
            )
        ]
        result = self.evaluator.evaluate(
            topology=self.topology,
            events=self._events(),
            receiver=receiver,
            reflector=self._reflector(),
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["post-loop-reports-from-imps-5-and-6"])
        self.assertEqual(result["direct_line"]["final_state"], "looped")

    def test_rejects_a_non_reflector_result(self) -> None:
        reflector = self._reflector()
        reflector["kind"] = "two-ended-udp-cut-relay"
        with self.assertRaisesRegex(ValueError, "reflector.kind"):
            self.evaluator.evaluate(
                topology=self.topology,
                events=self._events(),
                receiver=self._receiver(),
                reflector=reflector,
            )

    @staticmethod
    def _events() -> tuple[NccEvent, ...]:
        return (
            line_event(
                imp=5,
                state="up",
                neighbor_imp=6,
                sequence=1,
                observed_at="2026-08-31T12:00:20Z",
            ),
            line_event(
                imp=6,
                state="up",
                neighbor_imp=5,
                sequence=2,
                observed_at="2026-08-31T12:00:20Z",
            ),
            line_event(
                imp=5,
                state="looped",
                neighbor_imp=5,
                sequence=3,
                observed_at="2026-08-31T12:01:00Z",
            ),
            line_event(
                imp=6,
                state="looped",
                neighbor_imp=6,
                sequence=4,
                observed_at="2026-08-31T12:01:00Z",
            ),
        )

    @staticmethod
    def _receiver() -> dict[str, object]:
        return {
            "started_at": "2026-08-31T12:00:00Z",
            "trouble_reports": [
                {"source_imp": 5, "observed_at": "2026-08-31T12:00:20Z"},
                {"source_imp": 6, "observed_at": "2026-08-31T12:00:20Z"},
                {"source_imp": 7, "observed_at": "2026-08-31T12:00:25Z"},
                {"source_imp": 5, "observed_at": "2026-08-31T12:01:00Z"},
                {"source_imp": 6, "observed_at": "2026-08-31T12:01:00Z"},
            ],
        }

    @staticmethod
    def _reflector() -> dict[str, object]:
        return {
            "version": 1,
            "kind": "two-ended-udp-loop-reflector",
            "loop_started_at": "2026-08-31T12:00:30Z",
            "directions": {
                "a-to-b": {"forwarded": 10, "reflected": 20},
                "b-to-a": {"forwarded": 11, "reflected": 21},
            },
            "unexpected_sources": [],
        }


if __name__ == "__main__":
    unittest.main()
