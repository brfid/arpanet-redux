from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ncc.live import (
    LiveObservationPublisher,
    LiveObservationStreamError,
    read_live_observation_stream,
)
from ncc.topology import two_its_topology


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ncc-live-snapshot.py"
SOURCE = {"id": "source:controller", "kind": "harness-controller"}
PROVENANCE = [{"id": "source:controller", "kind": "harness-controller"}]


class LiveObservationTests(unittest.TestCase):
    def _publisher(self, path: Path) -> LiveObservationPublisher:
        return LiveObservationPublisher(
            path,
            run_id="run:live-fixture",
            started_at="2026-08-30T12:00:00Z",
            provenance=PROVENANCE,
            topology=two_its_topology(),
            stale_after_seconds=30,
        )

    def test_snapshot_preserves_topology_and_marks_old_direct_state_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "ncc-observations.jsonl"
            publisher = self._publisher(path)
            publisher.publish(
                category="harness",
                subject_id="imp:6",
                state="ready",
                source=SOURCE,
                observed_at="2026-08-30T12:00:10Z",
            )
            publisher.publish(
                category="harness",
                subject_id="link:62-6",
                state="modem-ready",
                source=SOURCE,
                observed_at="2026-08-30T12:00:20Z",
            )
            publisher.close()

            stream = read_live_observation_stream(path)
            snapshot = stream.snapshot(
                datetime(2026, 8, 30, 12, 0, 50, tzinfo=timezone.utc)
            )

            self.assertEqual(stream.run_id, "run:live-fixture")
            self.assertEqual(snapshot.current_states["imp:6"], "stale")
            self.assertEqual(snapshot.last_known_states["imp:6"], "ready")
            self.assertEqual(snapshot.current_states["link:62-6"], "modem-ready")
            self.assertEqual(snapshot.stale_subject_ids, ("imp:6",))
            self.assertEqual(
                snapshot.topology["routes"][0]["id"], "route:host176-to-host106"
            )

    def test_reader_ignores_a_writer_partial_final_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "ncc-observations.jsonl"
            publisher = self._publisher(path)
            publisher.publish(
                category="harness",
                subject_id="imp:6",
                state="started",
                source=SOURCE,
                observed_at="2026-08-30T12:00:10Z",
            )
            publisher.close()
            with path.open("a", encoding="utf-8") as stream:
                stream.write('{"incomplete":')

            stream = read_live_observation_stream(path)
            self.assertEqual(len(stream.to_dict()["observations"]), 1)

    def test_publisher_rejects_observation_outside_the_shared_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "ncc-observations.jsonl"
            publisher = self._publisher(path)
            with self.assertRaisesRegex(LiveObservationStreamError, "unknown topology"):
                publisher.publish(
                    category="harness",
                    subject_id="imp:999",
                    state="started",
                    source=SOURCE,
                    observed_at="2026-08-30T12:00:10Z",
                )
            publisher.close()

            stream = read_live_observation_stream(path)
            self.assertEqual(stream.to_dict()["observations"], [])

    def test_reader_rejects_a_boolean_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "ncc-observations.jsonl"
            publisher = self._publisher(path)
            publisher.close()
            header = json.loads(path.read_text(encoding="utf-8"))
            header["schema_version"] = True
            path.write_text(json.dumps(header) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(LiveObservationStreamError, "schema version"):
                read_live_observation_stream(path)

    def test_snapshot_command_is_passive_and_deterministic_at_a_given_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "ncc-observations.jsonl"
            publisher = self._publisher(path)
            publisher.publish(
                category="harness",
                subject_id="imp:6",
                state="ready",
                source=SOURCE,
                observed_at="2026-08-30T12:00:10Z",
            )
            publisher.close()

            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    path,
                    "--at",
                    "2026-08-30T12:00:41Z",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["current_states"]["imp:6"], "stale")
            self.assertEqual(output["last_known_states"]["imp:6"], "ready")
            self.assertNotIn("process", result.stdout)


if __name__ == "__main__":
    unittest.main()
