#!/usr/bin/env python3
"""Minimal external peer for the IMP11-A device's UDP wire format, used
to prove genuine two-process delivery rather than the guest receiving
its own transmissions back (see "Starting the NCP daemon" in
docs/research/imp11a-device.md for why that distinction matters and
how the wire format was independently determined by reading
H316/h316_udp.c before writing this).

Wire format: a UDP_PACKET is magic "H316" (4 bytes), a per-link
monotonic sequence number (4 bytes), a word count (2 bytes), then that
many big-endian 16-bit data words. The first data word is a flags word
(PFLG_FINAL=1, PFLG_READY=2); the rest, if any, is message content.

This is not a peer NCP/IMP implementation: it only sends a periodic
READY-flagged keepalive and logs whatever it receives, undecoded
beyond the wire-level header. Bind --peer-port to the exact port the
guest's ATTACH IMP string names as its remote, and point --guest-port
at the guest's local (listen) port; both hosts should be given as
explicit 127.0.0.1, not "localhost", to avoid an IPv4/IPv6 loopback
mismatch (see the doc).

Research-phase tool: exploratory, not wired into any make target or
test.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import time

MAGIC = struct.unpack(">I", b"H316")[0]
PFLG_FINAL = 1
PFLG_READY = 2


def build_packet(seq: int, words: list[int]) -> bytes:
    return struct.pack(">II H", MAGIC, seq, len(words)) + b"".join(
        struct.pack(">H", w) for w in words
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peer-port", type=int, required=True,
                         help="local port this peer binds to; must equal "
                              "the guest's configured *remote* port")
    parser.add_argument("--guest-port", type=int, required=True,
                         help="the guest's configured local (listen) port")
    parser.add_argument("--guest-host", default="127.0.0.1")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=25.0)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", args.peer_port))
    sock.settimeout(0.2)

    seq = 0
    deadline = time.time() + args.duration
    next_send = time.time()
    while time.time() < deadline:
        now = time.time()
        if now >= next_send:
            pkt = build_packet(seq, [PFLG_FINAL | PFLG_READY])
            sock.sendto(pkt, (args.guest_host, args.guest_port))
            print(f"[peer] sent READY keepalive seq={seq}", file=sys.stderr)
            seq += 1
            next_send = now + args.interval
        try:
            data, addr = sock.recvfrom(65535)
            if len(data) >= 10:
                magic, rseq, count = struct.unpack(">IIH", data[:10])
                words = struct.unpack(f">{count}H", data[10:10 + 2 * count]) if count else ()
                print(f"[peer] recv from {addr}: seq={rseq} count={count} words={words}",
                      file=sys.stderr)
            else:
                print(f"[peer] recv short packet from {addr}: {data!r}", file=sys.stderr)
        except socket.timeout:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
