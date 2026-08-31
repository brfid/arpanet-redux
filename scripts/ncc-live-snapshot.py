#!/usr/bin/env python3
"""Print one passive current-state snapshot of an NCC observation stream."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.live import LiveObservationStreamError, read_live_observation_stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("stream", type=Path)
    parser.add_argument(
        "--at",
        help="RFC 3339 UTC snapshot time, for deterministic inspection",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        stream = read_live_observation_stream(args.stream)
        snapshot_time = _parse_snapshot_time(args.at) if args.at else None
        snapshot = stream.snapshot(snapshot_time)
    except (LiveObservationStreamError, ValueError) as error:
        print(f"cannot read NCC live observation stream: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n")
    return 0


def _parse_snapshot_time(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("--at must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError("--at must be an RFC 3339 UTC timestamp") from error


if __name__ == "__main__":
    raise SystemExit(main())
