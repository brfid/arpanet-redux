from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ncc.events import EventSource, NccEvent
from ncc.historical_display import HistoricalDisplayObserver
from ncc.historical_events import (
    HistoricalEventRecorder,
    read_historical_event_stream,
)
from ncc.historical_server import (
    CONTENT_SECURITY_POLICY,
    historical_display_response,
)
from ncc.historical_viewer import render_historical_display_html
from ncc.run_summary import run_summary_from_mapping
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "config" / "topologies" / "ncc-alternate-path-fault.json"
AT = datetime(2026, 8, 31, 12, 0, 40, tzinfo=timezone.utc)


def line_event(
    imp: int,
    sequence: int,
    *,
    state: str = "up",
    neighbor_imp: int | None = None,
    observed_at: str = "2026-08-31T12:00:10Z",
) -> NccEvent:
    if neighbor_imp is None and state == "up":
        neighbor_imp = 6 if imp == 5 else 5
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type="line-endpoint.state",
        subject=f"imp:{imp}:line:1",
        state=state,
        source=EventSource(kind="imp-trouble-report", imp=imp),
        details={"neighbor_imp": neighbor_imp},
    )


class HistoricalDisplayObserverTests(unittest.TestCase):
    def test_progressive_partial_record_becomes_visible_only_after_newline(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((line_event(5, 1),))
            recorder.close()
            observer = HistoricalDisplayObserver(path, TOPOLOGY)

            first = observer.snapshot(AT).to_dict()
            self.assertEqual(first["stream"]["complete_event_count"], 1)
            self.assertEqual(first["reconciled"]["lines"][0]["state"], "unknown")

            second_record = json.dumps(
                line_event(6, 2).to_dict(), separators=(",", ":"), sort_keys=True
            )
            split = len(second_record) // 2
            with path.open("a", encoding="utf-8") as stream:
                stream.write(second_record[:split])
            partial = observer.snapshot(AT).to_dict()
            self.assertTrue(partial["stream"]["incomplete_final_record"])
            self.assertEqual(partial["stream"]["complete_event_count"], 1)

            with path.open("a", encoding="utf-8") as stream:
                stream.write(second_record[split:] + "\n")
            complete = observer.snapshot(AT).to_dict()
            self.assertFalse(complete["stream"]["incomplete_final_record"])
            self.assertEqual(complete["stream"]["complete_event_count"], 2)
            self.assertEqual(complete["stream"]["change"], "appended")
            self.assertEqual(complete["reconciled"]["lines"][0]["state"], "up")
            self.assertEqual(
                complete["reconciled"]["lines"][0]["supporting_observation_ids"],
                ["observation:historical:1", "observation:historical:2"],
            )

    def test_fixed_clock_is_deterministic_and_staleness_boundary_is_strict(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((line_event(5, 1), line_event(6, 2)))
            recorder.close()
            observer = HistoricalDisplayObserver(path, TOPOLOGY)

            at_boundary = observer.snapshot(AT)
            repeated = observer.snapshot(AT)
            self.assertEqual(at_boundary.to_json(), repeated.to_json())
            self.assertEqual(
                at_boundary.to_dict()["reconciled"]["lines"][0]["state"], "up"
            )

            expired = observer.snapshot(
                datetime(2026, 8, 31, 12, 0, 40, 1, tzinfo=timezone.utc)
            ).to_dict()
            self.assertEqual(expired["reconciled"]["lines"][0]["state"], "stale")
            self.assertEqual(
                [endpoint["last_known_state"] for endpoint in expired["direct"]["endpoints"]],
                ["up", "up"],
            )

    def test_repeats_direction_and_contradiction_remain_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append(
                (
                    line_event(5, 1),
                    line_event(6, 2),
                    line_event(5, 3, state="down", observed_at="2026-08-31T12:00:20Z"),
                    line_event(6, 4, observed_at="2026-08-31T12:00:20Z"),
                )
            )
            observer = HistoricalDisplayObserver(path, TOPOLOGY)
            directional = observer.snapshot(AT).to_dict()
            self.assertEqual(
                directional["reconciled"]["lines"][0]["state"], "minus-down"
            )
            self.assertEqual(
                directional["reconciled"]["lines"][0]["supporting_sequences"],
                [3, 4],
            )

            recorder.append(
                (
                    line_event(
                        5,
                        5,
                        neighbor_imp=7,
                        observed_at="2026-08-31T12:00:21Z",
                    ),
                    line_event(6, 6, observed_at="2026-08-31T12:00:21Z"),
                )
            )
            recorder.close()
            contradiction = observer.snapshot(AT).to_dict()
            self.assertEqual(
                contradiction["reconciled"]["lines"][0]["state"],
                "contradictory",
            )
            minus = contradiction["direct"]["endpoints"][0]
            self.assertEqual(minus["direction"], "minus")
            self.assertFalse(minus["topology_match"])
            self.assertEqual(minus["details"]["neighbor_imp"], 7)
            self.assertEqual(
                minus["state_authority"], "in-memory topology comparison"
            )

    def test_stream_generations_detect_truncation_restart_and_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            path = root / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((line_event(5, 1), line_event(6, 2)))
            recorder.close()
            original_lines = path.read_text(encoding="utf-8").splitlines()
            observer = HistoricalDisplayObserver(path, TOPOLOGY)
            self.assertEqual(observer.snapshot(AT).to_dict()["stream"]["change"], "initial")

            path.write_text("\n".join(original_lines[:2]) + "\n", encoding="utf-8")
            truncated = observer.snapshot(AT).to_dict()["stream"]
            self.assertEqual(truncated["change"], "truncated")
            self.assertEqual(truncated["generation"], 2)

            replacement = root / "replacement.jsonl"
            self._write_stream(replacement, "run:display-fixture", (line_event(5, 1),))
            replacement.replace(path)
            restarted = observer.snapshot(AT).to_dict()["stream"]
            self.assertEqual(restarted["change"], "restarted")
            self.assertEqual(restarted["generation"], 3)

            changed = root / "identity-change.jsonl"
            self._write_stream(changed, "run:new-generation", (line_event(5, 1),))
            changed.replace(path)
            identity = observer.snapshot(AT).to_dict()["stream"]
            self.assertEqual(identity["change"], "identity-changed")
            self.assertEqual(identity["generation"], 4)

    def test_same_inode_append_during_read_retries_before_snapshotting(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((line_event(5, 1),))
            recorder.close()
            reads = 0

            def append_during_first_read(candidate: Path):
                nonlocal reads
                stream = read_historical_event_stream(candidate)
                reads += 1
                if reads == 1:
                    with candidate.open("a", encoding="utf-8") as output:
                        output.write('{"incomplete":')
                return stream

            with patch(
                "ncc.historical_display.read_historical_event_stream",
                side_effect=append_during_first_read,
            ):
                snapshot = HistoricalDisplayObserver(path, TOPOLOGY).snapshot(AT)

            self.assertEqual(reads, 2)
            self.assertTrue(snapshot.to_dict()["stream"]["incomplete_final_record"])
            self.assertEqual(snapshot.to_dict()["stream"]["complete_event_count"], 1)

    def test_terminal_handoff_requires_exact_state_and_support_agreement(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = Path(directory_name) / "synthetic-loopback"
            (result / "runtime").mkdir(parents=True)
            path = result / "historical-events.jsonl"
            recorder = self._recorder(path, result.name)
            recorder.append(
                (
                    line_event(5, 1, state="looped", neighbor_imp=5),
                    line_event(6, 2, state="looped", neighbor_imp=6),
                )
            )
            recorder.close()
            (result / "runtime" / "run.env").write_text(
                "finished_utc=2026-08-31T12:00:40Z\n"
                "outcome=passed\n"
                "exit_status=0\n"
                "cleanup.completed=1\n"
                "result.verdict-exit-status=0\n",
                encoding="ascii",
            )
            (result / "verdict.json").write_text("{}\n", encoding="utf-8")
            matching = self._summary("looped", [1, 2])

            with patch(
                "ncc.historical_display.summarize_historical_line_result",
                return_value=matching,
            ):
                snapshot = HistoricalDisplayObserver(
                    path, TOPOLOGY, results_dir=result
                ).snapshot(AT)

            self.assertEqual(snapshot.mode, "completed")
            self.assertIs(snapshot.completed_summary, matching)
            self.assertEqual(snapshot.to_dict()["completion"]["status"], "matched")
            self.assertEqual(
                snapshot.to_dict()["completion"]["summary_lines"][0][
                    "supporting_observation_ids"
                ],
                ["observation:historical:1", "observation:historical:2"],
            )

            mismatch = self._summary("down", [1, 2])
            with patch(
                "ncc.historical_display.summarize_historical_line_result",
                return_value=mismatch,
            ):
                rejected = HistoricalDisplayObserver(
                    path, TOPOLOGY, results_dir=result
                ).snapshot(AT)
            self.assertEqual(rejected.mode, "completion-mismatch")
            self.assertIn("live but", rejected.to_dict()["completion"]["issues"][0])

            support_mismatch = self._summary("looped", [1])
            with patch(
                "ncc.historical_display.summarize_historical_line_result",
                return_value=support_mismatch,
            ):
                rejected_support = HistoricalDisplayObserver(
                    path, TOPOLOGY, results_dir=result
                ).snapshot(AT)
            self.assertEqual(rejected_support.mode, "completion-mismatch")
            self.assertIn(
                "live support",
                " ".join(rejected_support.to_dict()["completion"]["issues"]),
            )

            wrong_run = self._summary("looped", [1, 2], run_id="run:other-run")
            with patch(
                "ncc.historical_display.summarize_historical_line_result",
                return_value=wrong_run,
            ):
                rejected_identity = HistoricalDisplayObserver(
                    path, TOPOLOGY, results_dir=result
                ).snapshot(AT)
            self.assertEqual(rejected_identity.mode, "completion-mismatch")
            self.assertIn(
                "run identity",
                " ".join(rejected_identity.to_dict()["completion"]["issues"]),
            )

    def test_browser_shell_encodes_authority_and_direction_without_a_js_reducer(self) -> None:
        page = render_historical_display_html(load_shared_topology(TOPOLOGY))
        original_page = render_historical_display_html(
            load_shared_topology(
                ROOT / "config" / "topologies" / "imp5-ncc-host-interface.json"
            )
        )

        self.assertIn("Passive NCC line desk", page)
        self.assertIn("NCC receiver (host 0)", page)
        self.assertIn("Alternate-path IMP 7", page)
        self.assertIn('data-direction="minus"', page)
        self.assertIn('data-direction="plus"', page)
        self.assertIn("direct historical report", page)
        self.assertIn("in-memory reconciliation", page)
        self.assertIn("State authority: in-memory absence classification", page)
        self.assertIn("state-minus-down", page)
        self.assertIn("configured only", page)
        self.assertIn("Incomplete final JSONL record ignored", page)
        self.assertNotIn("reconcile(", page)
        self.assertNotIn("neighbor_imp ===", page)
        self.assertNotIn("WebSocket", page)
        self.assertIn('cy="215.0"', original_page)

    def test_loopback_application_is_get_only_and_serves_resolved_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((line_event(5, 1), line_event(6, 2)))
            recorder.close()
            observer = HistoricalDisplayObserver(path, TOPOLOGY)
            page_text = render_historical_display_html(observer.shared_topology)

            page = historical_display_response(observer, page_text, "GET", "/")
            self.assertEqual(page.status, 200)
            self.assertIn("Passive NCC line desk", page.body)
            self.assertIn("default-src 'self'", CONTENT_SECURITY_POLICY)

            api = historical_display_response(
                observer, page_text, "GET", "/api/snapshot"
            )
            document = json.loads(api.body)
            self.assertEqual(api.status, 200)
            self.assertEqual(document["reconciled"]["lines"][0]["state"], "stale")
            self.assertEqual(
                document["direct"]["endpoints"][0]["authority"],
                "direct historical-network observation",
            )
            self.assertEqual(
                document["direct"]["endpoints"][0]["state_authority"],
                "in-memory report-freshness classification",
            )
            self.assertEqual(
                document["reconciled"]["lines"][0]["authority"],
                "in-memory reconciliation",
            )
            self.assertIn(
                "link:imp5-imp7-alternate",
                document["configured"]["configured_only_link_ids"],
            )

            mutation = historical_display_response(
                observer, page_text, "POST", "/api/snapshot"
            )
            self.assertEqual(mutation.status, 405)
            self.assertEqual(mutation.headers["Allow"], "GET, HEAD")

            completed = historical_display_response(
                observer, page_text, "GET", "/completed"
            )
            self.assertEqual(completed.status, 409)

    @staticmethod
    def _recorder(path: Path, run_id: str = "run:display-fixture") -> HistoricalEventRecorder:
        topology = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
        return HistoricalEventRecorder(
            path,
            run_id=run_id,
            started_at="2026-08-31T12:00:00Z",
            topology_id=topology["id"],
            interface_id="binding:ncc-host0-imp5",
            topology=topology["topology"],
            provenance=[{"id": "source:test-receiver", "kind": "synthetic-fixture"}],
        )

    def _write_stream(
        self,
        path: Path,
        run_id: str,
        events: tuple[NccEvent, ...],
    ) -> None:
        recorder = self._recorder(path, run_id)
        recorder.append(events)
        recorder.close()

    @staticmethod
    def _summary(
        state: str,
        support: list[int],
        *,
        run_id: str = "run:synthetic-loopback",
    ):
        topology = json.loads(TOPOLOGY.read_text(encoding="utf-8"))["topology"]
        observation_ids = [f"observation:historical:{sequence}" for sequence in support]
        endpoint_states = [
            {
                "id": "observation:historical:1",
                "sequence": 1,
                "observed_at": "2026-08-31T12:00:10Z",
                "category": "historical-network",
                "subject_id": "imp:5:mi1",
                "state": state,
                "source": {"id": "source:imp:5", "kind": "imp-trouble-report"},
            },
            {
                "id": "observation:historical:2",
                "sequence": 2,
                "observed_at": "2026-08-31T12:00:10Z",
                "category": "historical-network",
                "subject_id": "imp:6:mi1",
                "state": state,
                "source": {"id": "source:imp:6", "kind": "imp-trouble-report"},
            },
        ]
        harness = {
            "id": "observation:harness-outcome",
            "sequence": 3,
            "observed_at": "2026-08-31T12:00:40Z",
            "category": "harness",
            "subject_id": "link:imp5-imp6-direct",
            "state": "passed",
            "source": {"id": "source:evaluator", "kind": "supported-result-evaluator"},
        }
        return run_summary_from_mapping(
            {
                "schema_version": 2,
                "run": {
                    "id": run_id,
                    "started_at": "2026-08-31T12:00:00Z",
                    "finished_at": "2026-08-31T12:00:40Z",
                    "outcome": "passed",
                    "provenance": [{"id": "source:test", "kind": "synthetic-fixture"}],
                },
                "topology": topology,
                "observations": [*endpoint_states, harness],
                "derived_states": [
                    {
                        "id": "derived:historical-line:direct",
                        "subject_id": "link:imp5-imp6-direct",
                        "state": state,
                        "basis": "inference",
                        "supporting_observation_ids": observation_ids,
                    }
                ],
                "gates": [
                    {
                        "id": "gate:test-network",
                        "kind": "network-behavior",
                        "assertion": "The mapped line reached its expected state.",
                        "verdict": "passed",
                        "evidence_observation_ids": [
                            *observation_ids,
                            "observation:harness-outcome",
                        ],
                        "evidence_derived_state_ids": [
                            "derived:historical-line:direct"
                        ],
                    }
                ],
            }
        )


if __name__ == "__main__":
    unittest.main()
