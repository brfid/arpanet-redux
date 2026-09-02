from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from ncc.message_journey import (
    BoundaryAssessmentState,
    JourneyState,
    ObservationProvenance,
)
from ncc.message_journey_stream import (
    MessageJourneyStreamError,
    MessageJourneyStreamRecorder,
    read_message_journey_stream,
)
from ncc.pdp11_its_journey import (
    Pdp11ItsJourneyError,
    extract_pdp11_its_journey,
    transaction_window_source,
    write_pdp11_its_journey_stream,
)
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = ROOT / "config" / "topologies" / "pdp11-its-telnet.json"
COEXISTENCE_TOPOLOGY_PATH = (
    ROOT / "config" / "topologies" / "ncc-pdp11-its-coexistence.json"
)

REQUEST = (
    0o000106,
    0o000000,
    0o000010,
    0o000012,
    0o000001,
    0o000000,
    0o002000,
    0o000000,
    0o000027,
    0o001000,
)
REQUEST_AT_IMP6 = (0o000176, *REQUEST[1:])
REQUEST_MI = (
    0o100373,
    0o011564,
    REQUEST[0],
    0o001176,
    *REQUEST[1:],
    0o160761,
)
REPLY = (
    0o000176,
    0o000000,
    0o000010,
    0o000015,
    0o000000,
    0o000000,
    0o001000,
    0o000000,
    0o013400,
    0o000004,
    0o000040,
    0o000000,
    0o000000,
)
REPLY_AT_IMP62 = (0o000106, *REPLY[1:])
REPLY_MI = (
    0o000376,
    0o007064,
    REPLY[0],
    0o000106,
    *REPLY[1:],
    0o153341,
)


def trace_record(
    tick: int,
    device: str,
    action: str,
    words: tuple[int, ...],
    transport_sequence: int,
    message_number: int,
) -> list[str]:
    lines = []
    if action == "received":
        lines.append(
            f"DBG({tick})> {device} UDP: link 0 - packet received "
            f"(sequence={transport_sequence}, length={len(words)})"
        )
    lines.extend(
        (
            f"DBG({tick})> {device} MSG: message {action} (length={len(words)})",
            f"DBG({tick})> {device} MSG: - "
            + " ".join(f"{word:06o}" for word in words)
            + " ",
        )
    )
    if action == "received":
        lines.append(
            f"DBG({tick})> {device} IO: receive done "
            f"(message #{message_number}, intreq=000004)"
        )
    else:
        lines.append(
            f"DBG({tick})> {device} UDP: link 0 - packet sent "
            f"(sequence={transport_sequence}, length={len(words)})"
        )
    return lines


def synthetic_traces() -> tuple[bytes, bytes]:
    imp62_lines = [
        *trace_record(10, "HI2", "received", REQUEST, 783, 260),
        *trace_record(20, "MI1", "sent", REQUEST_MI, 1131, 261),
        *trace_record(30, "MI1", "received", REPLY_MI, 1140, 262),
        *trace_record(40, "HI2", "sent", REPLY_AT_IMP62, 269, 263),
    ]
    imp6_lines = [
        *trace_record(11, "MI1", "received", REQUEST_MI, 1131, 360),
        *trace_record(21, "HI2", "sent", REQUEST_AT_IMP6, 9, 361),
        *trace_record(31, "HI2", "received", REPLY, 6, 362),
        *trace_record(41, "MI1", "sent", REPLY_MI, 1140, 363),
    ]
    return (
        ("\n".join(imp6_lines) + "\n").encode("ascii"),
        ("\n".join(imp62_lines) + "\n").encode("ascii"),
    )


def synthetic_ka10_trace(*, sequence: int = 7, start_tick: int = 2_000) -> bytes:
    data = REQUEST_AT_IMP6[2:]
    long_words = (
        0x0F00,
        0,
        0x0701,
        0x003E,
        0,
        len(data) * 16,
        0,
        0,
        0,
        0,
        0,
        *data,
    )
    content = struct.pack(f">{len(long_words)}H", *long_words)
    bit_text = "".join(f"{byte:08b}" for byte in content)
    bit_count = len(bit_text)
    tick = start_tick
    lines = [
        f"DBG({tick})> IMP ASSEMBLY: IMP INPUT-MESSAGE version=1 "
        f"message={sequence} bits={bit_count}"
    ]
    start = 0
    word_index = 0
    while True:
        width = 36 if start < 216 else 32
        valid = min(width, max(bit_count - start, 0))
        last = int(start + width >= bit_count)
        chunk = bit_text[start : start + valid]
        value = (int(chunk, 2) if chunk else 0) << (36 - valid)
        tick += 100
        lines.append(
            f"DBG({tick})> IMP ASSEMBLY: IMP INPUT-ASSEMBLY version=1 "
            f"message={sequence} word={word_index} message_bits={bit_count} "
            f"start={start} width={width} valid={valid} last={last} "
            f"value={value:012o}"
        )
        tick += 100
        lines.append(
            f"DBG({tick})> IMP ASSEMBLY: IMP INPUT-CONSUME version=1 "
            f"message={sequence} word={word_index} width={width} valid={valid} "
            f"last={last} value={value:012o} PC=53301"
        )
        if last:
            break
        start += width
        word_index += 1
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


class Pdp11ItsJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = load_shared_topology(TOPOLOGY_PATH)
        self.imp6, self.imp62 = synthetic_traces()

    def extraction(self):
        return extract_pdp11_its_journey(
            self.topology,
            imp6_trace=self.imp6,
            imp62_trace=self.imp62,
            h316_revision="a" * 40,
        )

    def test_extracts_ten_proven_boundaries_and_stops_at_host_delivery(self) -> None:
        extraction = self.extraction()

        self.assertEqual(len(extraction.observations), 10)
        self.assertEqual(extraction.diagnosis.state, JourneyState.MISSING_BOUNDARY)
        self.assertEqual(
            extraction.diagnosis.first_boundary_id, "boundary:request:6"
        )
        states = {
            item.boundary.id: item.state for item in extraction.diagnosis.boundaries
        }
        self.assertEqual(states["boundary:request:6"], BoundaryAssessmentState.MISSING)
        self.assertEqual(states["boundary:reply:6"], BoundaryAssessmentState.MISSING)
        self.assertTrue(
            all(
                state == BoundaryAssessmentState.OBSERVED
                for identifier, state in states.items()
                if identifier not in {"boundary:request:6", "boundary:reply:6"}
            )
        )

    def test_ka10_consumption_closes_only_request_ingress(self) -> None:
        extraction = extract_pdp11_its_journey(
            self.topology,
            imp6_trace=self.imp6,
            imp62_trace=self.imp62,
            ka10_trace=synthetic_ka10_trace(),
            ka10_revision="c" * 40,
        )

        self.assertEqual(len(extraction.observations), 11)
        self.assertEqual(extraction.diagnosis.state, JourneyState.MISSING_BOUNDARY)
        self.assertEqual(extraction.diagnosis.first_boundary_id, "boundary:reply:6")
        observation = extraction.observations[5]
        self.assertEqual(observation.id, "observation:request:6")
        self.assertEqual(observation.provenance.kind, "ka10-imp-trace")
        self.assertEqual(observation.provenance.revision, "c" * 40)
        self.assertEqual(observation.decoded.leader_format, "ka10-long-1822-ncp")
        self.assertEqual(
            observation.correlation_fingerprint,
            extraction.expected.request.correlation_fingerprint,
        )

    def test_ka10_trace_requires_one_exact_consumed_request(self) -> None:
        with self.assertRaisesRegex(Pdp11ItsJourneyError, "exactly one"):
            extract_pdp11_its_journey(
                self.topology,
                imp6_trace=self.imp6,
                imp62_trace=self.imp62,
                ka10_trace=synthetic_ka10_trace()
                + synthetic_ka10_trace(sequence=8, start_tick=5_000),
            )

        changed = synthetic_ka10_trace().replace(
            b"INPUT-CONSUME version=1 message=7 word=0 width=36 valid=36 "
            b"last=0 value=036000000000",
            b"INPUT-CONSUME version=1 message=7 word=0 width=36 valid=36 "
            b"last=0 value=036000000001",
            1,
        )
        with self.assertRaisesRegex(Pdp11ItsJourneyError, "invalid KA10"):
            extract_pdp11_its_journey(
                self.topology,
                imp6_trace=self.imp6,
                imp62_trace=self.imp62,
                ka10_trace=changed,
            )

    def test_preserves_direct_and_connected_peer_authority_and_transport_ids(self) -> None:
        observations = self.extraction().observations

        self.assertEqual(
            [item.provenance.kind for item in observations].count(
                "h316-connected-peer-delivery"
            ),
            2,
        )
        self.assertEqual(
            [item.provenance.kind for item in observations].count("h316-hi-mi-trace"),
            8,
        )
        self.assertEqual(
            [item.transport_sequence for item in observations[:5]],
            [783, 783, 1131, 1131, 9],
        )
        self.assertEqual(
            [item.transport_sequence for item in observations[5:]],
            [6, 6, 1140, 1140, 269],
        )
        request_fingerprints = {
            item.correlation_fingerprint for item in observations[:5]
        }
        reply_fingerprints = {
            item.correlation_fingerprint for item in observations[5:]
        }
        self.assertEqual(len(request_fingerprints), 1)
        self.assertEqual(len(reply_fingerprints), 1)
        self.assertNotEqual(request_fingerprints, reply_fingerprints)

    def test_repeated_later_reply_uses_the_first_exact_transport_identity(self) -> None:
        repeated_imp6 = self.imp6 + (
            "\n".join(trace_record(51, "HI2", "received", REPLY, 7, 364))
            + "\n"
        ).encode("ascii")
        repeated_imp62 = self.imp62 + (
            "\n".join(trace_record(60, "HI2", "sent", REPLY_AT_IMP62, 270, 365))
            + "\n"
        ).encode("ascii")

        extraction = extract_pdp11_its_journey(
            self.topology,
            imp6_trace=repeated_imp6,
            imp62_trace=repeated_imp62,
        )

        reply_hi = extraction.observations[6]
        self.assertEqual(reply_hi.transport_sequence, 6)

    def test_uses_each_topology_bound_modem_device_on_the_same_route(self) -> None:
        coexistence_topology = load_shared_topology(COEXISTENCE_TOPOLOGY_PATH)
        imp6_mi3 = self.imp6.replace(b"MI1", b"MI3")

        extraction = extract_pdp11_its_journey(
            coexistence_topology,
            imp6_trace=imp6_mi3,
            imp62_trace=self.imp62,
        )

        self.assertEqual(len(extraction.observations), 10)
        self.assertEqual(
            extraction.diagnosis.first_boundary_id, "boundary:request:6"
        )

    def test_changed_or_incomplete_mi_packet_cannot_become_a_boundary(self) -> None:
        changed = self.imp62.replace(b"001000 160761", b"001001 160761", 1)
        with self.assertRaisesRegex(Pdp11ItsJourneyError, "missing an exact"):
            extract_pdp11_its_journey(
                self.topology,
                imp6_trace=self.imp6,
                imp62_trace=changed,
            )

        compressed = self.imp62.replace(
            b"000027 001000 ", b"000027 \nDBG(10)> same as above (1 times)\n", 1
        )
        with self.assertRaises(Pdp11ItsJourneyError):
            extract_pdp11_its_journey(
                self.topology,
                imp6_trace=self.imp6,
                imp62_trace=compressed,
            )

    def test_transaction_window_digest_requires_exact_offsets(self) -> None:
        source = transaction_window_source(
            source_id="source:imp6",
            artifact="imp6.debug.log",
            start_offset=100,
            end_offset=100 + len(self.imp6),
            content=self.imp6,
        )
        self.assertEqual(source.end_offset - source.start_offset, len(self.imp6))
        with self.assertRaisesRegex(Pdp11ItsJourneyError, "offsets"):
            transaction_window_source(
                source_id="source:imp6",
                artifact="imp6.debug.log",
                start_offset=100,
                end_offset=101,
                content=self.imp6,
            )


class MessageJourneyStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = load_shared_topology(TOPOLOGY_PATH)
        self.topology_document = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
        self.imp6, self.imp62 = synthetic_traces()
        self.extraction = extract_pdp11_its_journey(
            self.topology,
            imp6_trace=self.imp6,
            imp62_trace=self.imp62,
        )

    def record(self, path: Path) -> None:
        recorder = MessageJourneyStreamRecorder(
            path,
            run_id="pdp11-its-telnet-test",
            started_at="2026-09-01T12:00:00Z",
            provenance=(
                ObservationProvenance(
                    "source:controller", "formal-pdp11-its-controller", "b" * 40
                ),
            ),
            topology_document=self.topology_document,
            expected=self.extraction.expected,
            transaction_window=(
                transaction_window_source(
                    source_id="source:imp6",
                    artifact="imp6.debug.log",
                    start_offset=100,
                    end_offset=100 + len(self.imp6),
                    content=self.imp6,
                ),
                transaction_window_source(
                    source_id="source:imp62",
                    artifact="imp62.debug.log",
                    start_offset=200,
                    end_offset=200 + len(self.imp62),
                    content=self.imp62,
                ),
            ),
        )
        try:
            recorder.publish(self.extraction.observations)
            recorder.complete()
        finally:
            recorder.close()

    def test_round_trip_includes_the_bounded_ka10_source_and_observation(self) -> None:
        ka10 = synthetic_ka10_trace()
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            stream = write_pdp11_its_journey_stream(
                path,
                run_id="pdp11-its-telnet-ka10-test",
                started_at="2026-09-02T20:00:00Z",
                provenance=(
                    ObservationProvenance(
                        "source:controller", "formal-pdp11-its-controller", "b" * 40
                    ),
                    ObservationProvenance(
                        "source:host106-imp", "ka10-imp-trace", "c" * 40
                    ),
                ),
                topology_document=self.topology_document,
                transaction_window=(
                    transaction_window_source(
                        source_id="source:imp6",
                        artifact="imp6.debug.log",
                        start_offset=0,
                        end_offset=len(self.imp6),
                        content=self.imp6,
                    ),
                    transaction_window_source(
                        source_id="source:imp62",
                        artifact="imp62.debug.log",
                        start_offset=0,
                        end_offset=len(self.imp62),
                        content=self.imp62,
                    ),
                    transaction_window_source(
                        source_id="source:host106-imp",
                        artifact="host106.console.log",
                        start_offset=0,
                        end_offset=len(ka10),
                        content=ka10,
                    ),
                ),
                imp6_trace=self.imp6,
                imp62_trace=self.imp62,
                ka10_trace=ka10,
                ka10_revision="c" * 40,
            )

            self.assertEqual(len(stream.observations), 11)
            self.assertEqual(stream.diagnosis.first_boundary_id, "boundary:reply:6")
            self.assertEqual(len(stream.transaction_window), 3)

    def test_round_trip_recomputes_the_terminal_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self.record(path)

            stream = read_message_journey_stream(path)

            self.assertTrue(stream.is_terminal)
            self.assertFalse(stream.has_incomplete_final_record)
            self.assertEqual(stream.observations, self.extraction.observations)
            self.assertEqual(stream.diagnosis, self.extraction.diagnosis)
            self.assertEqual(
                stream.to_dict()["header"]["record_order"],
                "emission-only-no-global-clock",
            )

    def test_incomplete_final_record_is_ignored_until_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self.record(path)
            complete = path.read_text(encoding="utf-8")
            lines = complete.splitlines()
            path.write_text("\n".join(lines[:-1]) + "\n" + lines[-1][:24], encoding="utf-8")

            stream = read_message_journey_stream(path)

            self.assertFalse(stream.is_terminal)
            self.assertTrue(stream.has_incomplete_final_record)
            self.assertEqual(stream.observations, self.extraction.observations)
            self.assertEqual(stream.diagnosis, self.extraction.diagnosis)

            path.write_text(complete, encoding="utf-8")
            completed = read_message_journey_stream(path)
            self.assertTrue(completed.is_terminal)
            self.assertFalse(completed.has_incomplete_final_record)

    def test_record_after_terminal_diagnosis_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self.record(path)
            records = path.read_text(encoding="utf-8").splitlines()
            path.write_text(
                "\n".join((*records, records[1])) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MessageJourneyStreamError, "after"):
                read_message_journey_stream(path)

    def test_tampered_terminal_diagnosis_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self.record(path)
            records = [
                json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            ]
            records[-1]["diagnosis"]["state"] = "complete"
            path.write_text(
                "".join(
                    json.dumps(item, separators=(",", ":"), sort_keys=True) + "\n"
                    for item in records
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MessageJourneyStreamError, "disagrees"):
                read_message_journey_stream(path)

    def test_progressive_prefix_has_a_deterministic_current_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "message-journey.jsonl"
            self.record(path)
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(lines[:5]) + "\n", encoding="utf-8")

            stream = read_message_journey_stream(path)

            self.assertFalse(stream.is_terminal)
            self.assertEqual(len(stream.observations), 4)
            self.assertEqual(stream.diagnosis.state, JourneyState.MISSING_BOUNDARY)
            self.assertEqual(stream.diagnosis.first_boundary_id, "boundary:request:5")


class Pdp11ItsJourneyCommandTests(unittest.TestCase):
    def test_read_only_result_adapter_writes_only_the_requested_sidecar(self) -> None:
        imp6, imp62 = synthetic_traces()
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            result = directory / "pdp11-its-telnet-test"
            runtime = result / "runtime"
            runtime.mkdir(parents=True)
            (result / "imp6.debug.log").write_bytes(imp6 + b"\xffignored tail")
            (result / "imp62.debug.log").write_bytes(imp62 + b"\xffignored tail")
            (runtime / "run.env").write_text(
                "format=1\n"
                "topology=pdp11-its-telnet\n"
                "started_utc=2026-09-01T12:00:00Z\n"
                f"repository.revision={'a' * 40}\n"
                f"source.h316-simh.revision={'b' * 40}\n"
                "application.offset.imp6=0\n"
                "application.offset.imp62=0\n"
                f"application.offset.end.imp6={len(imp6)}\n"
                f"application.offset.end.imp62={len(imp62)}\n"
                "application.service_user=53TLNT\n"
                "application.remote_time=structured\n"
                "cleanup.outer-runtime=passed\n"
                "outcome=passed\n"
                "exit_status=0\n",
                encoding="ascii",
            )
            (result / "application-evidence.txt").write_text(
                "connection_open=1\n"
                "its_service_user=53TLNT\n"
                "its_greeting=1\n"
                "remote_time=structured\n"
                "imp6_post_probe_traffic=1\n"
                "imp62_post_probe_traffic=1\n"
                "correlated_inter_imp_traffic=both-directions\n",
                encoding="ascii",
            )
            (result / "cleanup-evidence.txt").write_text(
                "surviving_owned_processes=0\n",
                encoding="ascii",
            )
            (result / "outcome.txt").write_text("passed\n", encoding="ascii")
            original_files = sorted(
                path.relative_to(result) for path in result.rglob("*") if path.is_file()
            )
            output = directory / "message-journey.jsonl"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "ncc-extract-pdp11-its-journey.py"),
                    str(result),
                    str(TOPOLOGY_PATH),
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                sorted(path.relative_to(result) for path in result.rglob("*") if path.is_file()),
                original_files,
            )
            stream = read_message_journey_stream(output)
            self.assertEqual(len(stream.observations), 10)
            self.assertTrue(stream.is_terminal)
            self.assertEqual(
                [item.end_offset for item in stream.transaction_window],
                [len(imp6), len(imp62)],
            )

            forbidden_output = result / "derived-message-journey.jsonl"
            rejected = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "ncc-extract-pdp11-its-journey.py"),
                    str(result),
                    str(TOPOLOGY_PATH),
                    str(forbidden_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(forbidden_output.exists())


if __name__ == "__main__":
    unittest.main()
