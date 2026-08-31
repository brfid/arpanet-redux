from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ncc.events import EventSource, NccEvent
from ncc.historical_events import (
    HistoricalEventRecorder,
    HistoricalEventStreamError,
    read_historical_event_stream,
    replay_historical_event_stream,
)


TOPOLOGY = {
    "components": [
        {
            "id": "host:ncc",
            "kind": "observer",
            "label": "NCC receiver",
            "position": {"x": 0, "y": 0},
            "endpoints": [{"id": "host:ncc:1822", "label": "1822"}],
        },
        {
            "id": "imp:5",
            "kind": "imp",
            "label": "IMP 5",
            "position": {"x": 1, "y": 0},
            "endpoints": [{"id": "imp:5:host:0", "label": "Host 0"}],
        },
    ],
    "links": [{"id": "link:ncc-imp5", "endpoints": ["host:ncc:1822", "imp:5:host:0"]}],
    "routes": [{"id": "route:ncc-to-imp5", "components": ["host:ncc", "imp:5"]}],
}
PROVENANCE = [{"id": "source:passive-receiver", "kind": "project-authored"}]
SOURCE = EventSource(kind="imp-trouble-report", imp=5)


def event(
    sequence: int,
    event_type: str,
    subject: str,
    state: str,
    *,
    observed_at: str = "2026-08-31T12:00:01Z",
) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type=event_type,
        subject=subject,
        state=state,
        source=SOURCE,
        details={"message_type": 0o303} if event_type == "imp.report" else {},
    )


def throughput_event(sequence: int) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at="2026-08-31T12:00:01Z",
        event_type="imp.throughput-report",
        subject="imp:5",
        state="received",
        source=EventSource(kind="imp-throughput-report", imp=5),
        details={"message_type": 0o302},
    )


class HistoricalEventStreamTests(unittest.TestCase):
    def _recorder(self, path: Path) -> HistoricalEventRecorder:
        return HistoricalEventRecorder(
            path,
            run_id="run:passive-report-fixture",
            started_at="2026-08-31T12:00:00Z",
            topology_id="topology:imp5-ncc-host-interface-proof",
            interface_id="binding:ncc-host0-imp5",
            topology=TOPOLOGY,
            provenance=PROVENANCE,
        )

    def test_records_validated_events_and_replays_direct_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append(
                (
                    event(1, "imp.report", "imp:5", "received"),
                    event(2, "host-interface.state", "imp:5:host:0", "up"),
                    event(3, "line-endpoint.state", "imp:5:line:1", "unknown"),
                    throughput_event(4),
                )
            )
            recorder.close()

            stream = read_historical_event_stream(path)
            frames = replay_historical_event_stream(stream)

            self.assertEqual(stream.run_id, "run:passive-report-fixture")
            self.assertEqual([item.sequence for item in stream.events], [1, 2, 3, 4])
            self.assertEqual(frames[-1].known_states["imp:5:host:0"], "up")
            self.assertEqual(frames[-1].known_states["imp:5:line:1"], "unknown")
            self.assertEqual(frames[0].details["message_type"], 0o303)
            self.assertEqual(frames[-1].event_type, "imp.throughput-report")
            self.assertEqual(frames[-1].source.kind, "imp-throughput-report")

    def test_reads_existing_version_one_trouble_report_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((event(1, "imp.report", "imp:5", "received"),))
            recorder.close()
            lines = path.read_text(encoding="utf-8").splitlines()
            header = json.loads(lines[0])
            header["schema_version"] = 1
            path.write_text(
                "\n".join((json.dumps(header), *lines[1:])) + "\n",
                encoding="utf-8",
            )

            self.assertEqual(len(read_historical_event_stream(path).events), 1)

    def test_rejects_a_throughput_event_claimed_as_version_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((throughput_event(1),))
            recorder.close()
            lines = path.read_text(encoding="utf-8").splitlines()
            header = json.loads(lines[0])
            header["schema_version"] = 1
            path.write_text(
                "\n".join((json.dumps(header), *lines[1:])) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(HistoricalEventStreamError, "schema version 2"):
                read_historical_event_stream(path)

    def test_rejects_event_order_and_preserves_the_prior_valid_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((event(1, "imp.report", "imp:5", "received"),))
            with self.assertRaisesRegex(HistoricalEventStreamError, "sequence 2"):
                recorder.append((event(3, "host-interface.state", "imp:5:host:0", "up"),))
            recorder.close()

            self.assertEqual(len(read_historical_event_stream(path).events), 1)

    def test_rejects_a_subject_or_source_outside_the_shared_topology(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            with self.assertRaisesRegex(HistoricalEventStreamError, "invalid host-interface subject"):
                recorder.append((event(1, "host-interface.state", "imp:5:host:4", "up"),))
            unknown_imp_event = NccEvent(
                sequence=1,
                observed_at="2026-08-31T12:00:01Z",
                event_type="imp.report",
                subject="imp:9",
                state="received",
                source=EventSource(kind="imp-trouble-report", imp=9),
            )
            with self.assertRaisesRegex(HistoricalEventStreamError, "unknown topology IMP 9"):
                recorder.append((unknown_imp_event,))
            recorder.close()

            contents = path.read_text(encoding="utf-8")
            self.assertEqual(len(contents.splitlines()), 1)

    def test_reader_ignores_an_interrupted_final_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "historical-events.jsonl"
            recorder = self._recorder(path)
            recorder.append((event(1, "imp.report", "imp:5", "received"),))
            recorder.close()
            with path.open("a", encoding="utf-8") as stream:
                stream.write('{"incomplete":')

            self.assertEqual(len(read_historical_event_stream(path).events), 1)


if __name__ == "__main__":
    unittest.main()
