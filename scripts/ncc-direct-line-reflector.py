#!/usr/bin/env python3
"""Forward one simulated modem cable, then reflect each endpoint to itself."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import selectors
import signal
import socket
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relay-a-port", type=int, required=True)
    parser.add_argument("--relay-b-port", type=int, required=True)
    parser.add_argument("--peer-a-port", type=int, required=True)
    parser.add_argument("--peer-b-port", type=int, required=True)
    parser.add_argument("--forward-seconds", type=float, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("relay_a_port", "relay_b_port", "peer_a_port", "peer_b_port"):
        value = getattr(args, name)
        if not 0 < value < 65536:
            parser.error(f"--{name.replace('_', '-')} must be in 1..65535")
    if args.forward_seconds <= 0 or args.duration <= 0:
        parser.error("durations must be positive")
    if args.forward_seconds >= args.duration:
        parser.error("--forward-seconds must be shorter than --duration")
    return args


def main() -> int:
    args = parse_args()
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    started_at = utc_now()
    started_monotonic = time.monotonic()
    loop_started_at: str | None = None
    unexpected_sources: list[dict[str, object]] = []
    directions = {
        "a-to-b": {"received": 0, "forwarded": 0, "reflected": 0, "bytes": 0},
        "b-to-a": {"received": 0, "forwarded": 0, "reflected": 0, "bytes": 0},
    }

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as relay_a, socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM
    ) as relay_b:
        relay_a.bind(("127.0.0.1", args.relay_a_port))
        relay_b.bind(("127.0.0.1", args.relay_b_port))
        relay_a.setblocking(False)
        relay_b.setblocking(False)
        selector = selectors.DefaultSelector()
        selector.register(
            relay_a,
            selectors.EVENT_READ,
            (
                "a-to-b",
                args.peer_a_port,
                relay_b,
                args.peer_b_port,
                args.peer_a_port,
            ),
        )
        selector.register(
            relay_b,
            selectors.EVENT_READ,
            (
                "b-to-a",
                args.peer_b_port,
                relay_a,
                args.peer_a_port,
                args.peer_b_port,
            ),
        )
        while not stopping:
            elapsed = time.monotonic() - started_monotonic
            if elapsed >= args.duration:
                break
            forwarding = elapsed < args.forward_seconds
            if not forwarding and loop_started_at is None:
                loop_started_at = utc_now()
            for key, _mask in selector.select(timeout=0.1):
                (
                    direction,
                    expected_source_port,
                    forward_socket,
                    forward_target_port,
                    reflect_target_port,
                ) = key.data
                payload, source = key.fileobj.recvfrom(65535)
                counters = directions[direction]
                counters["received"] += 1
                counters["bytes"] += len(payload)
                if source != ("127.0.0.1", expected_source_port):
                    unexpected_sources.append(
                        {
                            "direction": direction,
                            "host": source[0],
                            "port": source[1],
                            "observed_at": utc_now(),
                        }
                    )
                    continue
                if forwarding:
                    forward_socket.sendto(
                        payload, ("127.0.0.1", forward_target_port)
                    )
                    counters["forwarded"] += 1
                else:
                    key.fileobj.sendto(
                        payload, ("127.0.0.1", reflect_target_port)
                    )
                    counters["reflected"] += 1

    result = {
        "version": 1,
        "kind": "two-ended-udp-loop-reflector",
        "started_at": started_at,
        "finished_at": utc_now(),
        "requested_duration_seconds": args.duration,
        "forward_seconds": args.forward_seconds,
        "loop_started_at": loop_started_at,
        "ports": {
            "relay_a": args.relay_a_port,
            "relay_b": args.relay_b_port,
            "peer_a": args.peer_a_port,
            "peer_b": args.peer_b_port,
        },
        "directions": directions,
        "unexpected_sources": unexpected_sources,
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 1 if unexpected_sources else 0


if __name__ == "__main__":
    raise SystemExit(main())
