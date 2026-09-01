#!/usr/bin/env python3
"""Serve one growing NCC message-journey sidecar through a passive local display."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.journey_display import JourneyDisplayError, JourneyDisplayObserver
from ncc.journey_server import create_journey_display_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stream",
        type=Path,
        help="read-only message-journey.jsonl sidecar",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8766,
        help="127.0.0.1 TCP port (default: 8766; use 0 to allocate one)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        observer = JourneyDisplayObserver(args.stream)
        observer.snapshot()
        server = create_journey_display_server(observer, port=args.port)
    except (JourneyDisplayError, OSError, ValueError) as error:
        print(f"cannot serve passive NCC journey display: {error}", file=sys.stderr)
        return 1

    host, port = server.server_address
    print(f"Passive NCC journey display: http://{host}:{port}/", flush=True)
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
