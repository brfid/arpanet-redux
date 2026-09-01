from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ncc.events import EventSource, NccEvent
from ncc.historical_events import HistoricalEventRecorder
from ncc.historical_summary import (
    HistoricalLineSummaryError,
    summarize_historical_line_result,
)
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "config" / "topologies" / "ncc-alternate-path-fault.json"
SCRIPT = ROOT / "scripts" / "ncc-summarize-historical-line.py"


def report_event(imp: int, sequence: int, observed_at: str) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type="imp.report",
        subject=f"imp:{imp}",
        state="received",
        source=EventSource(kind="imp-trouble-report", imp=imp),
        details={"message_type": 0o303},
    )


def line_event(
    imp: int,
    sequence: int,
    observed_at: str,
    *,
    state: str,
    neighbor_imp: int | None,
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


class HistoricalLineSummaryTests(unittest.TestCase):
    def test_adapts_supported_fault_result_without_mapping_alternate_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result_path = self._result(Path(directory_name), final_state="down")

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
            result_path = self._result(Path(directory_name), final_state="looped")
            before = self._file_digests(result_path)

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
            self.assertEqual(before, self._file_digests(result_path))

    def test_rejects_topology_digest_and_reducer_verdict_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result_path = self._result(Path(directory_name), final_state="down")
            manifest_path = result_path / "runtime" / "run.env"
            manifest = manifest_path.read_text(encoding="ascii")
            manifest_path.write_text(
                manifest.replace(
                    f"sha256.shared-topology={self._topology_digest()}",
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
            result_path = self._result(Path(directory_name), final_state="down")
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

    def _result(self, root: Path, *, final_state: str) -> Path:
        result_path = root / f"synthetic-{final_state}-result"
        runtime = result_path / "runtime"
        runtime.mkdir(parents=True)
        shared = load_shared_topology(TOPOLOGY)
        recorder = HistoricalEventRecorder(
            result_path / "historical-events.jsonl",
            run_id=result_path.name,
            started_at="2026-08-31T12:00:05Z",
            topology_id=shared.id,
            interface_id="binding:ncc-host0-imp5",
            topology=shared.topology,
            provenance=[{"id": "source:test-receiver", "kind": "synthetic-fixture"}],
        )
        final_neighbor_5 = 5 if final_state == "looped" else None
        final_neighbor_6 = 6 if final_state == "looped" else None
        recorder.append(
            (
                report_event(5, 1, "2026-08-31T12:00:20Z"),
                line_event(
                    5,
                    2,
                    "2026-08-31T12:00:20Z",
                    state="up",
                    neighbor_imp=6,
                ),
                report_event(6, 3, "2026-08-31T12:00:21Z"),
                line_event(
                    6,
                    4,
                    "2026-08-31T12:00:21Z",
                    state="up",
                    neighbor_imp=5,
                ),
                report_event(7, 5, "2026-08-31T12:00:40Z"),
                line_event(
                    7,
                    6,
                    "2026-08-31T12:00:40Z",
                    state="down",
                    neighbor_imp=None,
                ),
                report_event(5, 7, "2026-08-31T12:01:00Z"),
                line_event(
                    5,
                    8,
                    "2026-08-31T12:01:00Z",
                    state=final_state,
                    neighbor_imp=final_neighbor_5,
                ),
                report_event(6, 9, "2026-08-31T12:01:01Z"),
                line_event(
                    6,
                    10,
                    "2026-08-31T12:01:01Z",
                    state=final_state,
                    neighbor_imp=final_neighbor_6,
                ),
            )
        )
        recorder.close()

        if final_state == "looped":
            verdict_kind = "ncc-line-loopback-verdict"
            manifest_topology = "ncc-line-loopback"
            mechanism_key = "process.direct-reflector.exit-status"
            pre_state_key = "pre_loop_state"
            pre_support_key = "pre_loop_supporting_sequences"
            final_check = "direct-line-final-looped"
        else:
            verdict_kind = "ncc-alternate-path-fault-verdict"
            manifest_topology = "ncc-alternate-path-fault"
            mechanism_key = "process.direct-relay.exit-status"
            pre_state_key = "pre_fault_state"
            pre_support_key = "pre_fault_supporting_sequences"
            final_check = "direct-line-final-down"
        verdict = {
            "version": 1,
            "kind": verdict_kind,
            "passed": True,
            "checks": {"direct-line-pre-up": True, final_check: True},
            "direct_line": {
                "id": "binding:imp5-mi1-imp6-mi1",
                pre_state_key: "up",
                pre_support_key: [2, 4],
                "final_state": final_state,
                "final_supporting_sequences": [8, 10],
            },
        }
        verdict_path = result_path / "verdict.json"
        verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
        manifest = {
            "format": "1",
            "topology": manifest_topology,
            "started_utc": "2026-08-31T12:00:00Z",
            "finished_utc": "2026-08-31T12:01:10Z",
            "outcome": "passed",
            "exit_status": "0",
            "repository.revision": "a" * 40,
            "repository.tracked_dirty": "0",
            "source.arpanet-in-a-box.revision": "c" * 40,
            "source.arpanet-in-a-box.tracked_dirty": "0",
            "source.h316-simh.revision": "b" * 40,
            "source.h316-simh.tracked_dirty": "0",
            "sha256.shared-topology": self._topology_digest(),
            "process.receiver.exit-status": "0",
            mechanism_key: "0",
            "result.verdict": str(verdict_path),
            "result.verdict-exit-status": "0",
            "cleanup.completed": "1",
        }
        (runtime / "run.env").write_text(
            "".join(f"{key}={value}\n" for key, value in manifest.items()),
            encoding="ascii",
        )
        return result_path

    @staticmethod
    def _topology_digest() -> str:
        return hashlib.sha256(TOPOLOGY.read_bytes()).hexdigest()

    @staticmethod
    def _file_digests(result_path: Path) -> dict[str, str]:
        return {
            str(path.relative_to(result_path)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(result_path.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
