from __future__ import annotations

from datetime import timedelta
import unittest

from ncc.events import EventSource, NccEvent
from ncc.reconciliation import (
    Endpoint,
    ImpState,
    LineState,
    NominalLine,
    NominalTopology,
    ReconciliationError,
    reconcile,
)


STARTED_AT = "2026-08-30T12:00:00Z"
NOW = "2026-08-30T12:01:00Z"
INTERVAL = timedelta(seconds=30)


def line_event(
    *,
    imp: int,
    interface: int,
    state: str,
    neighbor_imp: int | None,
    sequence: int,
    observed_at: str = "2026-08-30T12:00:40Z",
) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type="line-endpoint.state",
        subject=f"imp:{imp}:line:{interface}",
        state=state,
        source=EventSource(kind="imp-trouble-report", imp=imp),
        details={"neighbor_imp": neighbor_imp},
    )


def report_event(
    *,
    imp: int,
    sequence: int,
    observed_at: str = "2026-08-30T12:00:40Z",
) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type="imp.report",
        subject=f"imp:{imp}",
        state="received",
        source=EventSource(kind="imp-trouble-report", imp=imp),
    )


def two_imp_topology() -> NominalTopology:
    return NominalTopology(
        (
            NominalLine(
                "line:5-31",
                Endpoint(imp=5, interface=1),
                Endpoint(imp=31, interface=2),
            ),
        )
    )


class ReconciliationTests(unittest.TestCase):
    def test_pairs_fresh_endpoint_observations_into_minus_and_plus_states(self) -> None:
        topology = two_imp_topology()
        cases = [
            ("down", 31, "up", 5, LineState.MINUS_DOWN),
            ("up", 31, "down", 5, LineState.PLUS_DOWN),
            ("looped", 5, "up", 5, LineState.MINUS_LOOPED),
            ("up", 31, "looped", 31, LineState.PLUS_LOOPED),
            ("down", 31, "down", 5, LineState.DOWN),
            ("looped", 5, "looped", 31, LineState.LOOPED),
            ("up", 31, "up", 5, LineState.UP),
        ]
        for minus_state, minus_neighbor, plus_state, plus_neighbor, expected in cases:
            with self.subTest(minus_state=minus_state, plus_state=plus_state):
                result = reconcile(
                    topology,
                    [
                        line_event(
                            imp=5,
                            interface=1,
                            state=minus_state,
                            neighbor_imp=minus_neighbor,
                            sequence=1,
                        ),
                        line_event(
                            imp=31,
                            interface=2,
                            state=plus_state,
                            neighbor_imp=plus_neighbor,
                            sequence=2,
                        ),
                    ],
                    started_at=STARTED_AT,
                    observed_at=NOW,
                    report_interval=INTERVAL,
                )
                line = result.lines[0]
                self.assertEqual(line.state, expected)
                self.assertEqual(line.supporting_sequences, (1, 2))

    def test_accepts_only_self_neighbor_for_looped_endpoint(self) -> None:
        cases = [
            ("looped", 5, LineState.MINUS_LOOPED),
            ("looped", 31, LineState.CONTRADICTORY),
            ("looped", 6, LineState.CONTRADICTORY),
            ("looped", None, LineState.CONTRADICTORY),
            ("up", 5, LineState.CONTRADICTORY),
            ("down", 5, LineState.CONTRADICTORY),
        ]
        for state, neighbor_imp, expected in cases:
            with self.subTest(state=state, neighbor_imp=neighbor_imp):
                result = reconcile(
                    two_imp_topology(),
                    [
                        line_event(
                            imp=5,
                            interface=1,
                            state=state,
                            neighbor_imp=neighbor_imp,
                            sequence=1,
                        ),
                        line_event(
                            imp=31,
                            interface=2,
                            state="up",
                            neighbor_imp=5,
                            sequence=2,
                        ),
                    ],
                    started_at=STARTED_AT,
                    observed_at=NOW,
                    report_interval=INTERVAL,
                )
                self.assertEqual(result.lines[0].state, expected)

    def test_rejects_topology_mismatch_without_relabeling_it_as_network_down(self) -> None:
        result = reconcile(
            two_imp_topology(),
            [
                line_event(
                    imp=5,
                    interface=1,
                    state="down",
                    neighbor_imp=6,
                    sequence=1,
                ),
                line_event(
                    imp=31,
                    interface=2,
                    state="up",
                    neighbor_imp=5,
                    sequence=2,
                ),
            ],
            started_at=STARTED_AT,
            observed_at=NOW,
            report_interval=INTERVAL,
        )
        self.assertEqual(result.lines[0].state, LineState.CONTRADICTORY)

    def test_missing_and_expired_observations_remain_unknown_or_stale(self) -> None:
        topology = two_imp_topology()
        missing = reconcile(
            topology,
            [],
            started_at=STARTED_AT,
            observed_at="2026-08-30T12:00:20Z",
            report_interval=INTERVAL,
        )
        self.assertEqual(missing.lines[0].state, LineState.UNKNOWN)

        incomplete = reconcile(
            topology,
            [
                line_event(
                    imp=5,
                    interface=1,
                    state="down",
                    neighbor_imp=31,
                    sequence=1,
                )
            ],
            started_at=STARTED_AT,
            observed_at=NOW,
            report_interval=INTERVAL,
        )
        self.assertEqual(incomplete.lines[0].state, LineState.UNKNOWN)
        self.assertEqual({item.imp: item.state for item in incomplete.imps}[31], ImpState.STALE)

        stale = reconcile(
            topology,
            [
                line_event(
                    imp=5,
                    interface=1,
                    state="down",
                    neighbor_imp=31,
                    sequence=1,
                    observed_at="2026-08-30T12:00:10Z",
                ),
                line_event(
                    imp=31,
                    interface=2,
                    state="down",
                    neighbor_imp=5,
                    sequence=2,
                    observed_at="2026-08-30T12:00:10Z",
                ),
            ],
            started_at=STARTED_AT,
            observed_at=NOW,
            report_interval=INTERVAL,
        )
        self.assertEqual(stale.lines[0].state, LineState.STALE)

    def test_uses_multiple_fresh_peer_reports_for_partition_inference(self) -> None:
        topology = NominalTopology(
            (
                NominalLine("line:5-31", Endpoint(5, 1), Endpoint(31, 1)),
                NominalLine("line:6-31", Endpoint(6, 1), Endpoint(31, 2)),
            )
        )
        result = reconcile(
            topology,
            [
                report_event(imp=5, sequence=1),
                report_event(imp=6, sequence=2),
                line_event(
                    imp=5,
                    interface=1,
                    state="down",
                    neighbor_imp=31,
                    sequence=3,
                ),
                line_event(
                    imp=6,
                    interface=1,
                    state="down",
                    neighbor_imp=31,
                    sequence=4,
                ),
            ],
            started_at=STARTED_AT,
            observed_at=NOW,
            report_interval=INTERVAL,
        )
        imp_states = {item.imp: item for item in result.imps}
        self.assertEqual(imp_states[5].state, ImpState.UP)
        self.assertEqual(imp_states[6].state, ImpState.UP)
        self.assertEqual(imp_states[31].state, ImpState.PARTITIONED)
        self.assertEqual(imp_states[31].supporting_sequences, (3, 4))

    def test_requires_event_order_and_matching_source_identity(self) -> None:
        with self.assertRaisesRegex(ReconciliationError, "strictly increasing"):
            reconcile(
                two_imp_topology(),
                [
                    line_event(
                        imp=5,
                        interface=1,
                        state="up",
                        neighbor_imp=31,
                        sequence=2,
                    ),
                    line_event(
                        imp=31,
                        interface=2,
                        state="up",
                        neighbor_imp=5,
                        sequence=1,
                    ),
                ],
                started_at=STARTED_AT,
                observed_at=NOW,
                report_interval=INTERVAL,
            )

        bad_source = NccEvent(
            sequence=1,
            observed_at="2026-08-30T12:00:40Z",
            event_type="line-endpoint.state",
            subject="imp:5:line:1",
            state="up",
            source=EventSource("imp-trouble-report", 31),
            details={"neighbor_imp": 31},
        )
        with self.assertRaisesRegex(ReconciliationError, "source IMP"):
            reconcile(
                two_imp_topology(),
                [bad_source],
                started_at=STARTED_AT,
                observed_at=NOW,
                report_interval=INTERVAL,
            )

        bad_report = NccEvent(
            sequence=1,
            observed_at="2026-08-30T12:00:40Z",
            event_type="imp.report",
            subject="imp:31",
            state="received",
            source=EventSource("imp-trouble-report", 5),
        )
        with self.assertRaisesRegex(ReconciliationError, "source IMP"):
            reconcile(
                two_imp_topology(),
                [bad_report],
                started_at=STARTED_AT,
                observed_at=NOW,
                report_interval=INTERVAL,
            )


if __name__ == "__main__":
    unittest.main()
