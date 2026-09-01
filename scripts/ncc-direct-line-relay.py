#!/usr/bin/env python3
"""Relay one simulated modem cable, then cut it without releasing either port."""

from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import socket
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relay-a-port", type=int, required=True)
    parser.add_argument("--relay-b-port", type=int, required=True)
    parser.add_argument("--peer-a-port", type=int, required=True)
    parser.add_argument("--peer-b-port", type=int, required=True)
    cut = parser.add_mutually_exclusive_group(required=True)
    cut.add_argument("--forward-seconds", type=float)
    cut.add_argument("--cut-request", type=Path)
    parser.add_argument("--cut-state", type=Path)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("relay_a_port", "relay_b_port", "peer_a_port", "peer_b_port"):
        value = getattr(args, name)
        if not 0 < value < 65536:
            parser.error(f"--{name.replace('_', '-')} must be in 1..65535")
    if args.forward_seconds is not None and args.forward_seconds <= 0:
        parser.error("--forward-seconds must be positive")
    if args.duration <= 0:
        parser.error("durations must be positive")
    if (args.cut_request is None) != (args.cut_state is None):
        parser.error("--cut-request and --cut-state must be supplied together")
    return args


def write_json_atomic(path: Path, value: object) -> None:
    """Publish one small control record without exposing a partial write."""

    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def forwarding_enabled(
    *,
    elapsed: float,
    forward_seconds: float | None,
    cut_request: Path | None,
) -> bool:
    """Return the relay state for one loop iteration."""

    if cut_request is not None:
        return not cut_request.exists()
    if forward_seconds is None:
        raise ValueError("elapsed cut mode requires forward_seconds")
    return elapsed < forward_seconds


def publish_cut_state(path: Path, fault_started_at: str) -> None:
    """Atomically acknowledge the exact moment the relay entered cut state."""

    write_json_atomic(
        path,
        {
            "version": 1,
            "kind": "two-ended-udp-cut-state",
            "state": "cut",
            "fault_started_at": fault_started_at,
        },
    )


def main() -> int:
    args = parse_args()
    if args.cut_request is not None and args.cut_request.exists():
        raise SystemExit("cut request already exists before relay startup")
    if args.cut_state is not None and args.cut_state.exists():
        raise SystemExit("cut state already exists before relay startup")
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    started_at = utc_now()
    started_monotonic = time.monotonic()
    fault_started_at: str | None = None
    unexpected_sources: list[dict[str, object]] = []
    directions = {
        "a-to-b": {"received": 0, "forwarded": 0, "dropped": 0, "bytes": 0},
        "b-to-a": {"received": 0, "forwarded": 0, "dropped": 0, "bytes": 0},
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
            ("a-to-b", args.peer_a_port, relay_b, args.peer_b_port),
        )
        selector.register(
            relay_b,
            selectors.EVENT_READ,
            ("b-to-a", args.peer_b_port, relay_a, args.peer_a_port),
        )
        while not stopping:
            elapsed = time.monotonic() - started_monotonic
            if elapsed >= args.duration:
                break
            forwarding = forwarding_enabled(
                elapsed=elapsed,
                forward_seconds=args.forward_seconds,
                cut_request=args.cut_request,
            )
            if not forwarding and fault_started_at is None:
                fault_started_at = utc_now()
                if args.cut_state is not None:
                    publish_cut_state(args.cut_state, fault_started_at)
            for key, _mask in selector.select(timeout=0.1):
                direction, expected_source_port, output_socket, target_port = key.data
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
                    output_socket.sendto(payload, ("127.0.0.1", target_port))
                    counters["forwarded"] += 1
                else:
                    counters["dropped"] += 1

    result = {
        "version": 1,
        "kind": "two-ended-udp-cut-relay",
        "started_at": started_at,
        "finished_at": utc_now(),
        "requested_duration_seconds": args.duration,
        "forward_seconds": args.forward_seconds,
        "cut_mode": "elapsed" if args.cut_request is None else "request-file",
        "fault_started_at": fault_started_at,
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
    missing_requested_cut = args.cut_request is not None and fault_started_at is None
    return 1 if unexpected_sources or missing_requested_cut else 0


if __name__ == "__main__":
    raise SystemExit(main())
