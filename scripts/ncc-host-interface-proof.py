#!/usr/bin/env python3
"""Passively prove an H316 IMP host-interface attachment.

Bind this process to the configured NCC-side UDP port before starting the IMP.
It sends only flag-only ready packets and records frame metadata plus digests of
completed IMP output.  It never sends NCP, 1822, simulator-console, or process
control traffic, so a successful run proves the interface boundary rather than
an application exchange.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.host_interface import (
    HostInterfaceError,
    HostInterfacePacket,
    IngressMessage,
    PassiveHostIngress,
)
from ncc.imp_to_host import (
    ImpToHostMessageError,
    decode_imp_to_host_message,
    trouble_report_events_from_imp_to_host_message,
)
from ncc.shared_topology import SharedTopologyValidationError, load_shared_topology
from ncc.trouble_report import TROUBLE_REPORT_TYPES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-port", type=int)
    parser.add_argument("--imp-port", type=int)
    parser.add_argument("--topology", type=Path)
    parser.add_argument("--interface-id")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--ready-interval", type=float, default=1.0)
    parser.add_argument("--require-message", action="store_true")
    parser.add_argument("--require-trouble-report", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.topology) != bool(args.interface_id):
        parser.error("--topology and --interface-id must be used together")
    if args.topology is None and (args.listen_port is None or args.imp_port is None):
        parser.error("supply both ports or one shared --topology interface")
    if args.topology is not None and (args.listen_port is not None or args.imp_port is not None):
        parser.error("shared topology and explicit ports cannot be combined")
    for port in (args.listen_port, args.imp_port):
        if port is not None and not 0 < port < 65536:
            parser.error("ports must be in the range 1..65535")
    if args.duration <= 0:
        parser.error("--duration must be positive")
    if args.ready_interval <= 0:
        parser.error("--ready-interval must be positive")
    return args


def message_record(message: IngressMessage) -> dict[str, int | str]:
    payload = b"".join(struct.pack(">H", word) for word in message.words)
    return {
        "first_sequence": message.first_sequence,
        "final_sequence": message.final_sequence,
        "word_count": len(message.words),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def connection_details(args: argparse.Namespace) -> tuple[int, int, dict[str, object]]:
    """Resolve either direct ports or the one binding in a shared topology."""

    if args.topology is None:
        assert args.listen_port is not None and args.imp_port is not None
        return args.listen_port, args.imp_port, {}
    topology = load_shared_topology(args.topology)
    binding = topology.interface(args.interface_id)
    return (
        _environment_port(binding.host_listen_environment),
        _environment_port(binding.imp_listen_environment),
        {
            "topology_id": topology.id,
            "interface_id": binding.id,
            "proof_requirements": list(topology.proof_requirements),
        },
    )


def _environment_port(name: str) -> int:
    value = os.environ.get(name)
    if value is None or not value.isdecimal() or not 0 < int(value) < 65536:
        raise SharedTopologyValidationError(
            f"{name} must hold a port in the range 1..65535"
        )
    return int(value)


def main() -> int:
    args = parse_args()
    try:
        listen_port, imp_port, binding_metadata = connection_details(args)
    except SharedTopologyValidationError as error:
        print(f"cannot resolve host-interface proof ports: {error}", file=sys.stderr)
        return 1
    ingress = PassiveHostIngress()
    packets: list[dict[str, int | bool]] = []
    messages: list[tuple[IngressMessage, str]] = []
    ready_sent = 0
    imp_ready_received = 0
    started_at = datetime.now(timezone.utc)
    deadline = time.monotonic() + args.duration
    next_ready = time.monotonic()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.bind((args.host, listen_port))
        connection.connect((args.host, imp_port))
        connection.settimeout(0.2)
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_ready:
                ready_packet = ingress.ready_packet()
                try:
                    connection.send(ready_packet.to_bytes())
                except ConnectionRefusedError:
                    # The receiver intentionally starts before the IMP so the
                    # first datagram can race an unopened loopback socket.
                    pass
                else:
                    ingress.ready_sent()
                    ready_sent += 1
                next_ready = now + args.ready_interval
            try:
                received = connection.recv(65535)
            except (ConnectionRefusedError, socket.timeout):
                continue
            try:
                receipt = ingress.receive(HostInterfacePacket.from_bytes(received))
            except HostInterfaceError as error:
                print(f"host-interface proof rejected a frame: {error}", file=sys.stderr)
                return 1
            if receipt.packet.ready:
                imp_ready_received += 1
            packets.append(
                {
                    "sequence": receipt.packet.sequence,
                    "final": receipt.packet.final,
                    "ready": receipt.packet.ready,
                    "word_count": len(receipt.packet.words),
                }
            )
            if receipt.message is not None:
                messages.append(
                    (
                        receipt.message,
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    )
                )

    trouble_reports = []
    next_event_sequence = 1
    for message, observed_at in messages:
        try:
            parsed = decode_imp_to_host_message(message)
        except ImpToHostMessageError:
            continue
        if not parsed.body_words or parsed.body_words[0] not in TROUBLE_REPORT_TYPES:
            continue
        try:
            events = trouble_report_events_from_imp_to_host_message(
                message,
                observed_at=observed_at,
                sequence_start=next_event_sequence,
            )
        except ImpToHostMessageError as error:
            print(f"host-interface proof rejected a trouble report: {error}", file=sys.stderr)
            return 1
        next_event_sequence += len(events)
        trouble_reports.append(
            {
                "first_sequence": message.first_sequence,
                "final_sequence": message.final_sequence,
                "observed_at": observed_at,
                "source_imp": parsed.leader.source_imp,
                "message_type": parsed.body_words[0],
                "events": [event.to_dict() for event in events],
            }
        )

    result = {
        "version": 2,
        "kind": "passive-h316-host-interface-proof",
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "duration_seconds": args.duration,
        "host_ready_packets_sent": ready_sent,
        "imp_ready_packets_received": imp_ready_received,
        "received_packets": packets,
        "complete_messages": [message_record(message) for message, _ in messages],
        "trouble_reports": trouble_reports,
    }
    result.update(binding_metadata)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")

    proof_requirements = binding_metadata.get("proof_requirements", [])
    require_message = args.require_message or "complete-imp-message-received" in proof_requirements
    if ready_sent == 0:
        print("host-interface proof did not send the host ready signal", file=sys.stderr)
        return 1
    if imp_ready_received == 0:
        print("host-interface proof did not receive the IMP ready signal", file=sys.stderr)
        return 1
    if require_message and not messages:
        print("host-interface proof did not receive a complete IMP message", file=sys.stderr)
        return 1
    if args.require_trouble_report and not trouble_reports:
        print("host-interface proof did not decode a 1973 trouble report", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
