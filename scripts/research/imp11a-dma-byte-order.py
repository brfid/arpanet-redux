#!/usr/bin/env python3
"""Exercise both IMP11-A DMA byte-order boundaries with a real PDP-11 CPU.

The test queues a network-order regular-message word (000106) at the UDP
peer, then executes PDP-11 instructions that program the input DMA channel.
It requires guest memory to contain 043000: the byte sequence 00,106 the
NOSC driver's leader parser expects.  The same instruction stream sends that
guest word through output DMA and requires the peer to receive 000106.

Research-phase regression only: it needs an externally built IMP11-A PDP-11
simulator and is intentionally not part of the source-only project test
target.
"""
from __future__ import annotations

import argparse
import socket
import struct
import time

import pexpect


MAGIC = struct.unpack(">I", b"H316")[0]
PFLG_FINAL = 1
PFLG_READY = 2
WIRE_RRP_FIRST_WORD = 0o000106
PDP11_LEADER_WORD = 0o043000


def packet(sequence: int, words: list[int]) -> bytes:
    return struct.pack(">IIH", MAGIC, sequence, len(words)) + b"".join(
        struct.pack(">H", word) for word in words
    )


def command(child: pexpect.spawn, text: str) -> str:
    child.sendline(text)
    child.expect_exact("sim>", timeout=10)
    return child.before


def pick_local_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdp11", required=True, help="external IMP11-A PDP-11 binary")
    args = parser.parse_args()

    peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    peer.bind(("127.0.0.1", 0))
    peer_port = int(peer.getsockname()[1])
    guest_port = pick_local_port()
    peer.settimeout(5)
    child = pexpect.spawn(args.pdp11, encoding="utf-8", timeout=10)
    try:
        child.expect_exact("sim>")
        command(child, "set cpu 11/34 64k")
        command(child, "set imp enabled")
        command(child, f"attach imp {guest_port}:127.0.0.1:{peer_port}")

        # Queue input before the CPU arms the device.  imp_check_input() runs
        # synchronously when the guest writes GO|WRTENBL, so delivery cannot
        # be confused with debugger register writes or an asynchronous poll.
        peer.sendto(packet(0, [PFLG_FINAL, WIRE_RRP_FIRST_WORD]),
                    ("127.0.0.1", guest_port))
        time.sleep(0.1)

        # MOV #imm,@#addr for output SPO/OWC/OSTAT then input SPI/IWC/ISTAT;
        # HALT returns control to SIMH after the actual bus transactions.
        program = (
            0o012737, 0o002000, 0o172412,
            0o012737, 0o177777, 0o172410,
            0o012737, 0o000005, 0o172414,
            0o012737, 0o002002, 0o172432,
            0o012737, 0o177777, 0o172430,
            0o012737, 0o000011, 0o172434,
            0o000000,
        )
        command(child, f"deposit -o 2000 {PDP11_LEADER_WORD:06o}")
        for offset, word in enumerate(program):
            command(child, f"deposit -o {0o1000 + 2 * offset:06o} {word:06o}")
        command(child, "go 1000")

        outbound, _ = peer.recvfrom(65535)
        magic, sequence, count = struct.unpack(">IIH", outbound[:10])
        words = struct.unpack(f">{count}H", outbound[10:10 + 2 * count])
        if magic != MAGIC or sequence != 0 or words != (PFLG_FINAL | PFLG_READY, WIRE_RRP_FIRST_WORD):
            raise AssertionError(f"unexpected output UDP frame: sequence={sequence} words={words!r}")

        memory = command(child, "examine -o 2002")
        if f"{PDP11_LEADER_WORD:06o}" not in memory:
            raise AssertionError(f"input DMA did not store PDP-11 leader word {PDP11_LEADER_WORD:06o}: {memory!r}")
        print("IMP11-A DMA byte-order regression passed: output=000106 input-memory=043000")
        return 0
    finally:
        try:
            command(child, "quit")
        except (pexpect.EOF, pexpect.ExceptionPexpect):
            pass
        peer.close()


if __name__ == "__main__":
    raise SystemExit(_main())
