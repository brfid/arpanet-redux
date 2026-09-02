"""Build synthetic retained historical-line results for source-only tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ncc.events import EventSource, NccEvent
from ncc.historical_events import HistoricalEventRecorder
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_LINE_TOPOLOGY = (
    ROOT / "config" / "topologies" / "ncc-alternate-path-fault.json"
)


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


def create_historical_line_result(root: Path, *, final_state: str) -> Path:
    result_path = root / f"synthetic-{final_state}-result"
    runtime = result_path / "runtime"
    runtime.mkdir(parents=True)
    shared = load_shared_topology(HISTORICAL_LINE_TOPOLOGY)
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
        "sha256.shared-topology": topology_digest(),
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


def topology_digest() -> str:
    return hashlib.sha256(HISTORICAL_LINE_TOPOLOGY.read_bytes()).hexdigest()


def file_digests(result_path: Path) -> dict[str, str]:
    return {
        str(path.relative_to(result_path)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(result_path.rglob("*"))
        if path.is_file()
    }
