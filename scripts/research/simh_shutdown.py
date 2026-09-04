"""Strict helpers for ending an interactive SIMH session."""

from __future__ import annotations


def quit_simh_cleanly(
    child: object, eof_pattern: object, timeout: float = 15
) -> None:
    """Stop the CPU, wait for the monitor, and require a clean exit."""

    child.sendcontrol("e")
    child.expect_exact("sim>", timeout=timeout)
    child.sendline("quit")
    child.expect_exact("Goodbye", timeout=timeout)
    child.expect(eof_pattern, timeout=timeout)
