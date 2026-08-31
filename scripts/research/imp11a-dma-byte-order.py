#!/usr/bin/env python3
"""Exercise IMP11-A DMA byte order and input continuation with a real PDP-11 CPU.

The test queues a network-order regular-message word (000106) at the UDP
peer, then executes PDP-11 instructions that program the input DMA channel.
It requires guest memory to contain 043000: the byte sequence 00,106 the
NOSC driver's leader parser expects.  The same instruction stream sends that
guest word through output DMA and requires the peer to receive 000106.

The test then sends a six-word non-final frame into a two-word guest buffer.
It requires the adapter to retain four surplus words, complete the first DMA
with zero IWC and no ENDMSG, continue the second DMA without a premature
completion, and preserve its residual IWC until an empty final frame raises
ENDMSG.

Research-phase regression only: it needs an externally built IMP11-A PDP-11
simulator and is intentionally not part of the source-only project test
target.
"""
from __future__ import annotations

import argparse
import re
import socket
import struct
import time

import pexpect


MAGIC = struct.unpack(">I", b"H316")[0]
PFLG_FINAL = 1
PFLG_READY = 2
WIRE_RRP_FIRST_WORD = 0o000106
PDP11_LEADER_WORD = 0o043000
IMP_GO = 0o000001
IMP_WRTENBL = 0o000010
IMP_IENAB = 0o000100
IMP_MASRDY = 0o002000
IMP_ENDMSG = 0o004000
IMP_IWC = 0o172430
IMP_SPI = 0o172432
IMP_ISTAT = 0o172434
INPUT_VECTOR = 0o000274
INPUT_HANDLER = 0o000600
INTERRUPT_COUNTER = 0o004100
BUFFER_SENTINEL = 0o165252
CONTINUATION_WIRE_WORDS = (
    0o001002,
    0o003004,
    0o005006,
    0o007010,
    0o011012,
    0o013014,
)


def packet(sequence: int, words: list[int]) -> bytes:
    return struct.pack(">IIH", MAGIC, sequence, len(words)) + b"".join(
        struct.pack(">H", word) for word in words
    )


def command(child: pexpect.spawn, text: str) -> str:
    child.sendline(text)
    child.expect_exact("sim>", timeout=10)
    return child.before


def run_for(child: pexpect.spawn, address: int, seconds: float) -> None:
    """Run a bounded CPU loop, tolerating an early interrupt-driven HALT."""
    child.sendline(f"go {address:06o}")
    try:
        child.expect_exact("sim>", timeout=seconds)
    except pexpect.TIMEOUT:
        child.sendcontrol("e")
        child.expect_exact("sim>", timeout=5)


def pick_local_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


def deposit_words(child: pexpect.spawn, address: int, words: tuple[int, ...]) -> None:
    for offset, word in enumerate(words):
        command(child, f"deposit -o {address + 2 * offset:06o} {word:06o}")


def examine_word(child: pexpect.spawn, address: int) -> int:
    output = command(child, f"examine -o {address:06o}")
    match = re.search(r":\s*([0-7]{1,6})\s*$", output, re.MULTILINE)
    if match is None:
        raise AssertionError(f"could not parse PDP-11 word at {address:06o}: {output!r}")
    return int(match.group(1), 8)


def input_dma_program(
    buffer_address: int,
    requested_words: int,
    wait_for_interrupt: bool,
) -> tuple[int, ...]:
    return (
        0o012737, buffer_address, IMP_SPI,
        0o012737, (-requested_words) & 0xFFFF, IMP_IWC,
        0o012737, IMP_GO | IMP_WRTENBL | IMP_IENAB, IMP_ISTAT,
        0o000230,  # SPL 0 forces synchronous interrupt-priority recalculation.
        0o000777 if wait_for_interrupt else 0o000000,
    )


def input_state_program(
    iwc_result_address: int,
    istat_result_address: int,
) -> tuple[int, ...]:
    return (
        0o013737, IMP_IWC, iwc_result_address,
        0o013737, IMP_ISTAT, istat_result_address,
        0o000000,
    )


def saved_input_state(
    child: pexpect.spawn,
    program_address: int,
    buffer_address: int,
    requested_words: int,
    iwc_result_address: int,
    istat_result_address: int,
    wait_for_interrupt: bool = False,
) -> tuple[int, int]:
    deposit_words(
        child,
        program_address,
        input_dma_program(buffer_address, requested_words, wait_for_interrupt),
    )
    stop_output = command(child, f"go {program_address:06o}")
    if wait_for_interrupt and examine_word(child, INTERRUPT_COUNTER) != 1:
        pc_output = command(child, "examine -o pc")
        vector_output = command(child, f"examine -o {INPUT_VECTOR:06o}")
        handler_output = command(child, f"examine -m {INPUT_HANDLER:06o}-{INPUT_HANDLER + 4:06o}")
        raise AssertionError(
            "input IRQ did not run the counter handler: "
            f"stop={stop_output!r} pc={pc_output!r} vector={vector_output!r} "
            f"handler={handler_output!r}"
        )
    return current_input_state(
        child,
        program_address,
        iwc_result_address,
        istat_result_address,
    )


def current_input_state(
    child: pexpect.spawn,
    program_address: int,
    iwc_result_address: int,
    istat_result_address: int,
) -> tuple[int, int]:
    deposit_words(
        child,
        program_address,
        input_state_program(iwc_result_address, istat_result_address),
    )
    command(child, f"go {program_address:06o}")
    return (
        examine_word(child, iwc_result_address),
        examine_word(child, istat_result_address),
    )


def assert_memory_words(
    child: pexpect.spawn,
    address: int,
    wire_words: tuple[int, ...],
) -> None:
    for offset, wire_word in enumerate(wire_words):
        expected = ((wire_word << 8) | (wire_word >> 8)) & 0xFFFF
        actual = examine_word(child, address + 2 * offset)
        if actual != expected:
            raise AssertionError(
                f"input DMA word {offset} was {actual:06o}, expected {expected:06o}"
            )


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
        command(child, "reset imp")
        command(child, f"attach imp {guest_port}:127.0.0.1:{peer_port}")
        command(child, "deposit -o sp 010000")
        command(child, "deposit -o psw 000000")
        deposit_words(child, INPUT_VECTOR, (INPUT_HANDLER, 0o000000))
        deposit_words(child, INPUT_HANDLER, (0o005237, INTERRUPT_COUNTER, 0o000000))
        command(child, f"deposit -o {INTERRUPT_COUNTER:06o} 000000")

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
        deposit_words(child, 0o1000, program)
        command(child, "go 1000")

        outbound, _ = peer.recvfrom(65535)
        magic, sequence, count = struct.unpack(">IIH", outbound[:10])
        words = struct.unpack(f">{count}H", outbound[10:10 + 2 * count])
        if magic != MAGIC or sequence != 0 or words != (PFLG_FINAL | PFLG_READY, WIRE_RRP_FIRST_WORD):
            raise AssertionError(f"unexpected output UDP frame: sequence={sequence} words={words!r}")

        memory_word = examine_word(child, 0o2002)
        if memory_word != PDP11_LEADER_WORD:
            raise AssertionError(
                f"input DMA did not store PDP-11 leader word {PDP11_LEADER_WORD:06o}: "
                f"{memory_word:06o}"
            )

        # The first two-word DMA must fill without ENDMSG and retain the
        # remaining four words of the same non-final UDP frame.
        peer.sendto(
            packet(1, [PFLG_READY, *CONTINUATION_WIRE_WORDS]),
            ("127.0.0.1", guest_port),
        )
        time.sleep(0.1)
        first_iwc, first_istat = saved_input_state(
            child, 0o1000, 0o3000, 2, 0o4000, 0o4002, wait_for_interrupt=True
        )
        assert_memory_words(child, 0o3000, CONTINUATION_WIRE_WORDS[:2])
        if first_iwc != 0:
            raise AssertionError(f"full first input buffer left IWC {first_iwc:06o}, expected 000000")
        if first_istat & (IMP_GO | IMP_WRTENBL | IMP_ENDMSG):
            raise AssertionError(
                f"full non-final input buffer completed with unexpected ISTAT {first_istat:06o}"
            )
        first_interrupts = examine_word(child, INTERRUPT_COUNTER)
        if first_interrupts != 1:
            raise AssertionError(
                f"full first input buffer raised {first_interrupts} interrupts, expected 1"
            )

        # A six-word second buffer receives the four retained words, but must
        # remain pending with a -2 residual until the message's final marker.
        command(child, f"deposit -o 003014 {BUFFER_SENTINEL:06o}")
        command(child, f"deposit -o 003016 {BUFFER_SENTINEL:06o}")
        second_iwc, second_istat = saved_input_state(
            child, 0o1000, 0o3004, 6, 0o4004, 0o4006
        )
        assert_memory_words(child, 0o3004, CONTINUATION_WIRE_WORDS[2:])
        expected_residual = (-2) & 0xFFFF
        if second_iwc != expected_residual:
            raise AssertionError(
                f"partial second input buffer left IWC {second_iwc:06o}, "
                f"expected {expected_residual:06o}"
            )
        if second_istat & IMP_ENDMSG:
            raise AssertionError(f"non-final partial input raised ENDMSG in ISTAT {second_istat:06o}")
        if (second_istat & (IMP_GO | IMP_WRTENBL)) != (IMP_GO | IMP_WRTENBL):
            raise AssertionError(f"partial input completed prematurely with ISTAT {second_istat:06o}")
        if not second_istat & IMP_MASRDY:
            raise AssertionError(
                f"partial input lost READY before the poll probe; ISTAT {second_istat:06o}"
            )
        second_interrupts = examine_word(child, INTERRUPT_COUNTER)
        if second_interrupts != 1:
            raise AssertionError(
                f"partial non-final input raised a premature interrupt; count={second_interrupts}"
            )

        # Prove an ordinary scheduled poll cannot complete the partial DMA.
        # A no-data, non-READY packet gives that poll a visible side effect:
        # MASRDY must clear while the residual, pending bits, and IRQ count
        # remain unchanged.  This separates that behavior from the final
        # marker tested below instead of queueing FINAL before the first poll.
        peer.sendto(packet(2, [0]), ("127.0.0.1", guest_port))
        command(child, "deposit -o 001400 000777")  # BR . while the poller runs
        run_for(child, 0o1400, 0.25)
        polled_iwc, polled_istat = current_input_state(
            child, 0o1000, 0o4010, 0o4012
        )
        if polled_iwc != expected_residual:
            raise AssertionError(
                f"ordinary poll changed IWC to {polled_iwc:06o}, "
                f"expected {expected_residual:06o}"
            )
        if polled_istat & (IMP_ENDMSG | IMP_MASRDY):
            raise AssertionError(
                f"ordinary poll did not consume the non-READY probe cleanly: "
                f"ISTAT {polled_istat:06o}"
            )
        if (polled_istat & (IMP_GO | IMP_WRTENBL)) != (IMP_GO | IMP_WRTENBL):
            raise AssertionError(f"ordinary poll completed partial DMA: ISTAT {polled_istat:06o}")
        polled_interrupts = examine_word(child, INTERRUPT_COUNTER)
        if polled_interrupts != 1:
            raise AssertionError(
                f"ordinary poll raised a premature interrupt; count={polled_interrupts}"
            )

        peer.sendto(
            packet(3, [PFLG_FINAL | PFLG_READY]),
            ("127.0.0.1", guest_port),
        )
        time.sleep(0.05)
        command(child, "go 001400")
        final_iwc, final_istat = current_input_state(
            child, 0o1000, 0o4014, 0o4016
        )
        if final_iwc != expected_residual:
            raise AssertionError(
                f"empty final marker changed IWC to {final_iwc:06o}, "
                f"expected {expected_residual:06o}"
            )
        if final_istat & (IMP_GO | IMP_WRTENBL):
            raise AssertionError(f"final marker left input pending with ISTAT {final_istat:06o}")
        if not final_istat & IMP_ENDMSG:
            raise AssertionError(f"final marker did not raise ENDMSG in ISTAT {final_istat:06o}")
        final_interrupts = examine_word(child, INTERRUPT_COUNTER)
        if final_interrupts != 2:
            raise AssertionError(
                f"empty final marker left interrupt count {final_interrupts}, expected 2"
            )
        for address in (0o3014, 0o3016):
            actual = examine_word(child, address)
            if actual != BUFFER_SENTINEL:
                raise AssertionError(
                    f"empty final marker overwrote sentinel at {address:06o}: {actual:06o}"
                )

        print(
            "IMP11-A DMA regression passed: byte order, retained surplus, "
            "residual IWC, and ENDMSG timing"
        )
        return 0
    finally:
        try:
            command(child, "quit")
        except (pexpect.EOF, pexpect.ExceptionPexpect):
            pass
        peer.close()


if __name__ == "__main__":
    raise SystemExit(_main())
