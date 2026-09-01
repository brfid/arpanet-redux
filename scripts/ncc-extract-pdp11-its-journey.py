#!/usr/bin/env python3
"""Write a typed message journey from one retained formal Gate 4H result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.message_journey import ObservationProvenance
from ncc.pdp11_its_journey import (
    transaction_window_source,
    write_pdp11_its_journey_stream,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "result_dir",
        type=Path,
        help="read-only completed Gate 4H result directory",
    )
    parser.add_argument(
        "topology",
        type=Path,
        help="project-authored shared topology used by the run",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="new message-journey JSONL path; existing files are rejected",
    )
    return parser.parse_args()


def read_manifest(path: Path) -> dict[str, str]:
    """Read the formal line-oriented manifest without interpreting its paths."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ValueError(f"could not read formal manifest {path}: {error}") from error
    values: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if "=" not in line:
            raise ValueError(f"formal manifest line {number} has no '=' separator")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"formal manifest line {number} has an invalid or duplicate key")
        values[key] = value
    return values


def require_formal_pass(
    manifest: dict[str, str],
    application: dict[str, str],
    cleanup: dict[str, str],
) -> None:
    """Require the terminal evidence markers written by the formal shell."""

    manifest_expected = {
        "format": "1",
        "topology": "pdp11-its-telnet",
        "cleanup.outer-runtime": "passed",
        "outcome": "passed",
        "exit_status": "0",
        "application.remote_time": "structured",
    }
    application_expected = {
        "connection_open": "1",
        "its_greeting": "1",
        "remote_time": "structured",
        "imp6_post_probe_traffic": "1",
        "imp62_post_probe_traffic": "1",
        "correlated_inter_imp_traffic": "both-directions",
    }
    cleanup_expected = {
        "surviving_owned_processes": "0",
    }
    mismatches = [
        f"run.env:{key}"
        for key, value in manifest_expected.items()
        if manifest.get(key) != value
    ]
    mismatches.extend(
        f"application-evidence.txt:{key}"
        for key, value in application_expected.items()
        if application.get(key) != value
    )
    mismatches.extend(
        f"cleanup-evidence.txt:{key}"
        for key, value in cleanup_expected.items()
        if cleanup.get(key) != value
    )
    service_user = application.get("its_service_user", "")
    if (
        not service_user.endswith("TLNT")
        or not service_user[:-4].isdigit()
        or manifest.get("application.service_user") != service_user
    ):
        mismatches.append("application-evidence.txt:its_service_user")
    if mismatches:
        raise ValueError(
            "result is not a completed passing formal PDP-11/ITS run: "
            + ", ".join(sorted(mismatches))
        )


def read_trace_window(
    result_dir: Path,
    manifest: dict[str, str],
    source: str,
) -> tuple[Path, int, int, bytes]:
    """Read one exact retained byte range, using a recorded end when present."""

    path = result_dir / f"{source}.debug.log"
    try:
        start = int(manifest[f"application.offset.{source}"])
        end = int(
            manifest.get(f"application.offset.end.{source}", str(path.stat().st_size))
        )
    except (KeyError, OSError, ValueError) as error:
        raise ValueError(f"result has an invalid {source} transaction window") from error
    size = path.stat().st_size
    if not 0 <= start <= end <= size:
        raise ValueError(f"result has an out-of-range {source} transaction window")
    with path.open("rb") as stream:
        stream.seek(start)
        content = stream.read(end - start)
    if len(content) != end - start:
        raise ValueError(f"result changed while reading the {source} transaction window")
    return path, start, end, content


def main() -> int:
    args = parse_args()
    result_dir = args.result_dir.resolve()
    output = args.output.resolve()
    if output == result_dir or result_dir in output.parents:
        raise ValueError("message-journey output must be outside the retained result")
    manifest = read_manifest(result_dir / "runtime" / "run.env")
    application = read_manifest(result_dir / "application-evidence.txt")
    cleanup = read_manifest(result_dir / "cleanup-evidence.txt")
    try:
        outcome = (result_dir / "outcome.txt").read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise ValueError("could not read formal outcome.txt") from error
    if outcome != "passed\n":
        raise ValueError("result does not have the exact formal passing outcome")
    require_formal_pass(manifest, application, cleanup)
    topology_document = json.loads(args.topology.read_text(encoding="utf-8"))
    traces = {
        source: read_trace_window(result_dir, manifest, source)
        for source in ("imp6", "imp62")
    }
    provenance = (
        ObservationProvenance(
            "source:controller",
            "formal-pdp11-its-controller",
            manifest["repository.revision"],
        ),
        ObservationProvenance(
            "source:h316",
            "h316-simh",
            manifest["source.h316-simh.revision"],
        ),
    )
    window = tuple(
        transaction_window_source(
            source_id=f"source:{source}",
            artifact=path.name,
            start_offset=start,
            end_offset=end,
            content=content,
        )
        for source, (path, start, end, content) in traces.items()
    )
    stream = write_pdp11_its_journey_stream(
        output,
        run_id=result_dir.name,
        started_at=manifest["started_utc"],
        provenance=provenance,
        topology_document=topology_document,
        transaction_window=window,
        imp6_trace=traces["imp6"][3],
        imp62_trace=traces["imp62"][3],
        h316_revision=manifest["source.h316-simh.revision"],
    )
    expected_digest = manifest.get("sha256.message-journey")
    actual_digest = hashlib.sha256(output.read_bytes()).hexdigest()
    if expected_digest is not None and actual_digest != expected_digest:
        raise ValueError(
            "derived message-journey sidecar disagrees with the retained manifest digest"
        )
    print(
        json.dumps(
            {
                "run_id": stream.run_id,
                "observation_count": len(stream.observations),
                "state": stream.diagnosis.state.value,
                "first_boundary_id": stream.diagnosis.first_boundary_id,
                "output": str(output),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
