#!/usr/bin/env python3
"""Serve one completed NCC/application coexistence result as a passive desk."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.coexistence_display import CoexistenceDisplay, CoexistenceDisplayError
from ncc.coexistence_server import create_coexistence_display_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        type=Path,
        help="read-only completed coexistence result directory",
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
        default=8767,
        help="127.0.0.1 TCP port (default: 8767; use 0 to allocate one)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        display = CoexistenceDisplay(args.results_dir, args.topology)
        server = create_coexistence_display_server(display, port=args.port)
    except (CoexistenceDisplayError, OSError, ValueError) as error:
        print(f"cannot serve passive coexistence desk: {error}", file=sys.stderr)
        return 1

    host, port = server.server_address
    print(f"Passive NCC coexistence desk: http://{host}:{port}/", flush=True)
    print(f"Validated read-only result: {display.results_dir}", flush=True)
    print("Press Control-C to stop the local presentation server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
