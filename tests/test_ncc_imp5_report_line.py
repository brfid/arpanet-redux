from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import unittest

from ncc.events import EventSource, NccEvent
from ncc.reconciliation import (
    Endpoint,
    LineState,
    nominal_topology_from_shared,
    reconcile,
)
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
PROJECT_TOPOLOGY = ROOT / "config" / "topologies" / "imp5-ncc-host-interface.json"
STARTED_AT = "2026-08-31T12:00:00Z"
NOW = "2026-08-31T12:01:00Z"
INTERVAL = timedelta(seconds=30)


def line_event(
    *,
    imp: int,
    state: str,
    neighbor_imp: int | None,
    sequence: int,
    observed_at: str = "2026-08-31T12:00:40Z",
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


class Imp5ReportLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shared = load_shared_topology(PROJECT_TOPOLOGY)
        cls.topology = nominal_topology_from_shared(shared)

    def test_maps_the_reciprocal_reports_to_one_configured_line(self) -> None:
        self.assertEqual(len(self.topology.lines), 1)
        line = self.topology.lines[0]
        self.assertEqual(line.id, "binding:imp5-mi1-imp6-mi1")
        self.assertEqual(line.first, Endpoint(imp=5, interface=1))
        self.assertEqual(line.second, Endpoint(imp=6, interface=1))
        self.assertEqual(line.minus_endpoint, Endpoint(imp=5, interface=1))
        self.assertEqual(line.plus_endpoint, Endpoint(imp=6, interface=1))

    def test_reconciles_fresh_reciprocal_agreement(self) -> None:
        result = self._reconcile(
            [
                line_event(imp=5, state="up", neighbor_imp=6, sequence=1),
                line_event(imp=6, state="up", neighbor_imp=5, sequence=2),
            ]
        )

        self.assertEqual(result.lines[0].state, LineState.UP)
        self.assertEqual(result.lines[0].supporting_sequences, (1, 2))

    def test_reconciles_firmware_down_reports_without_remembered_neighbors(self) -> None:
        result = self._reconcile(
            [
                line_event(imp=5, state="down", neighbor_imp=None, sequence=1),
                line_event(imp=6, state="down", neighbor_imp=None, sequence=2),
            ]
        )

        self.assertEqual(result.lines[0].state, LineState.DOWN)
        self.assertEqual(result.lines[0].supporting_sequences, (1, 2))

    def test_requires_the_configured_neighbor_when_an_up_report_omits_it(self) -> None:
        result = self._reconcile(
            [
                line_event(imp=5, state="up", neighbor_imp=None, sequence=1),
                line_event(imp=6, state="up", neighbor_imp=5, sequence=2),
            ]
        )

        self.assertEqual(result.lines[0].state, LineState.CONTRADICTORY)

    def test_reconciles_contradiction_without_relabeling_it_as_down(self) -> None:
        result = self._reconcile(
            [
                line_event(imp=5, state="down", neighbor_imp=31, sequence=1),
                line_event(imp=6, state="up", neighbor_imp=5, sequence=2),
            ]
        )

        self.assertEqual(result.lines[0].state, LineState.CONTRADICTORY)

    def test_keeps_missing_evidence_unknown(self) -> None:
        result = self._reconcile(
            [line_event(imp=5, state="up", neighbor_imp=6, sequence=1)]
        )

        self.assertEqual(result.lines[0].state, LineState.UNKNOWN)
        self.assertEqual(result.lines[0].supporting_sequences, (1,))

    def test_marks_expired_reciprocal_evidence_stale(self) -> None:
        result = self._reconcile(
            [
                line_event(
                    imp=5,
                    state="up",
                    neighbor_imp=6,
                    sequence=1,
                    observed_at="2026-08-31T12:00:10Z",
                ),
                line_event(
                    imp=6,
                    state="up",
                    neighbor_imp=5,
                    sequence=2,
                    observed_at="2026-08-31T12:00:10Z",
                ),
            ]
        )

        self.assertEqual(result.lines[0].state, LineState.STALE)
        self.assertEqual(result.lines[0].supporting_sequences, (1, 2))

    def _reconcile(self, events: list[NccEvent]):
        return reconcile(
            self.topology,
            events,
            started_at=STARTED_AT,
            observed_at=NOW,
            report_interval=INTERVAL,
        )


if __name__ == "__main__":
    unittest.main()
