#!/usr/bin/env python3
"""Assert ordered application and IMP evidence in retained smoke logs."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


ROUTER_SEND = re.compile(
    r"^IMP: Send #\d+: type 0/REGULAR, destination 004, 6 words\.$"
)
ROUTER_DEAD = re.compile(
    r"^IMP: Receive #\d+: type 7/DEAD, source 004, 2 words\.$"
)
ROUTER_FLAGS = "IMP: flags 00, link 000, id 00, subtype 01."
ROUTER_DIAGNOSTIC = "NCP: Host 004 is not up."
SHORT_REGULAR = "Short leader: flags=0, type=0, host=0, imp=76, id=0, sub=0"
LONG_REGULAR = "Long leader: flags=0, type=0, handling=0, host=0, imp=76, id=0, sub=0, length=0"


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def has_router_dead_sequence(lines: list[str]) -> bool:
    for send_index, line in enumerate(lines):
        if not ROUTER_SEND.fullmatch(line):
            continue
        window_end = min(len(lines), send_index + 20)
        for dead_index in range(send_index + 1, window_end):
            if not ROUTER_DEAD.fullmatch(lines[dead_index]):
                continue
            if lines[dead_index + 1 : dead_index + 3] == [
                ROUTER_FLAGS,
                ROUTER_DIAGNOSTIC,
            ]:
                return True
    return False


def has_completed_pair(lines: list[str], first: str, following: list[str]) -> bool:
    width = len(following)
    for index, line in enumerate(lines):
        if line == first and lines[index + 1 : index + 1 + width] == following:
            return True
    return False


def assert_router_dead(ncp_log: Path, ping_log: Path) -> list[str]:
    failures = []
    if not has_router_dead_sequence(read_lines(ncp_log)):
        failures.append("missing ordered host-004 DEAD/subtype-01 diagnostic sequence")
    ping_text = ping_log.read_text(encoding="utf-8", errors="replace")
    if "Host is not up." not in ping_text:
        failures.append("missing host-dead application diagnostic")
    if "NCP PING host 004" not in ping_text:
        failures.append("host-dead application log does not identify host 004")
    return failures


def assert_mixed_conversion(imp_log: Path, ping_log: Path) -> list[str]:
    failures = []
    lines = read_lines(imp_log)
    if not has_completed_pair(
        lines,
        SHORT_REGULAR,
        ["Next will not be the first packet.", "Send 16 words"],
    ):
        failures.append("missing completed short-to-long regular-message conversion")
    if not has_completed_pair(
        lines,
        LONG_REGULAR,
        ["Host port 2 padding: 5", "Converted: 8 words"],
    ):
        failures.append("missing completed long-to-short regular-message conversion")
    ping_text = ping_log.read_text(encoding="utf-8", errors="replace")
    if "Reply from host 106: seq=3" not in ping_text:
        failures.append("missing third application echo reply from host 106")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    router = subparsers.add_parser("router-dead")
    router.add_argument("ncp_log", type=Path)
    router.add_argument("ping_log", type=Path)
    mixed = subparsers.add_parser("mixed-conversion")
    mixed.add_argument("imp_log", type=Path)
    mixed.add_argument("ping_log", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.mode == "router-dead":
            failures = assert_router_dead(args.ncp_log, args.ping_log)
        else:
            failures = assert_mixed_conversion(args.imp_log, args.ping_log)
    except OSError as error:
        print(f"log evidence check failed: {error}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"{args.mode}: ordered evidence OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
