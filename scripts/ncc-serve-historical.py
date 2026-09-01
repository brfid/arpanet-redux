#!/usr/bin/env python3
"""Serve one growing historical NCC sidecar through a passive local display."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.historical_display import HistoricalDisplayError, HistoricalDisplayObserver
from ncc.historical_server import create_historical_display_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        type=Path,
        help="read-only result directory containing historical-events.jsonl",
    )
    parser.add_argument(
        "--topology",
        required=True,
        type=Path,
        help="project-authored shared topology used by the run",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="127.0.0.1 TCP port (default: 8765; use 0 to allocate one)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        observer = HistoricalDisplayObserver(
            args.results_dir / "historical-events.jsonl",
            args.topology,
            results_dir=args.results_dir,
        )
        observer.snapshot()
        server = create_historical_display_server(observer, port=args.port)
    except (HistoricalDisplayError, OSError, ValueError) as error:
        print(f"cannot serve passive NCC display: {error}", file=sys.stderr)
        return 1

    host, port = server.server_address
    print(f"Passive NCC display: http://{host}:{port}/", flush=True)
    print(f"Watching read-only sidecar: {observer.stream_path}", flush=True)
    print("Press Control-C to stop the local observer.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
