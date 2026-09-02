#!/usr/bin/env python3
"""Serve one growing or completed NCC result in the passive operator console."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.board_display import NccBoardDisplay, NccBoardError
from ncc.board_server import create_ncc_board_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        type=Path,
        help="named result directory; it may still be growing or not yet exist",
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
        display = NccBoardDisplay(args.results_dir, args.topology)
        server = create_ncc_board_server(display, port=args.port)
    except (NccBoardError, OSError, ValueError) as error:
        print(f"cannot serve NCC operator console: {error}", file=sys.stderr)
        return 1

    host, port = server.server_address
    print(f"NCC operator console: http://{host}:{port}/", flush=True)
    print(f"Watching read-only result: {display.results_dir}", flush=True)
    print("Press Control-C to stop the local console server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
