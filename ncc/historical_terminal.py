"""Shared safe character-terminal adapter for Network UNIX controllers."""

from __future__ import annotations

from contextlib import contextmanager
import os
import re
import select
import termios
import time
from typing import Callable, Iterator, NamedTuple, Protocol, TextIO

from .harness_process import utc_now
from .terminal_session import DEFAULT_MAX_CHUNK_BYTES, TerminalSessionRecorder


LOCAL_EXIT = 0x1D
LOCAL_FAILOVER_CUT = 0x1E
SIMULATOR_WRU = 0x1C


class CharacterTerminalProcess(Protocol):
    """Minimum PTY surface used by the safe terminal adapter."""

    process: object | None

    def output_from(self, offset: int) -> bytes: ...

    def send(self, data: bytes | str) -> None: ...


class BootDisplay:
    """Print stable elapsed boot milestones without terminal control codes."""

    def __init__(
        self,
        output: TextIO,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.output = output
        self.clock = clock
        self.started = clock()

    def milestone(self, state: str, component: str, detail: str) -> None:
        elapsed = max(0, int(self.clock() - self.started))
        self.output.write(
            f"  [{elapsed:>3}s] {state:<5} {component:<20} {detail}\n"
        )
        self.output.flush()


class PreparedTerminalInput(NamedTuple):
    """One local input read after applying the declared terminal profile."""

    forwarded: bytes
    exit_requested: bool
    cut_requested: bool
    blocked_wru: int
    rejected_non_seven_bit: int


class SafeTeletypeRenderer:
    """Render a 7-bit teletype profile without terminal escape injection."""

    def __init__(self) -> None:
        self._suppress_line_feed = False

    def render(self, data: bytes) -> bytes:
        rendered = bytearray()
        for byte in data:
            if byte == 0x0D:
                rendered.extend(b"\n")
                self._suppress_line_feed = True
                continue
            if byte == 0x0A:
                if not self._suppress_line_feed:
                    rendered.extend(b"\n")
                self._suppress_line_feed = False
                continue
            self._suppress_line_feed = False
            if byte in (0x07, 0x08, 0x09) or 0x20 <= byte <= 0x7E:
                rendered.append(byte)
            else:
                rendered.extend(f"\\x{byte:02x}".encode("ascii"))
        return bytes(rendered)


class HistoricalConsoleProjection:
    """Hide project instrumentation while preserving its retained raw bytes."""

    _NOISE_PREFIXES = (b"SKTRACE ", b"PBTRACE ")
    _PROMPT_NOISE_PREFIXES = (b"* SKTRACE ", b"* PBTRACE ")

    def __init__(self) -> None:
        self._line_start = True
        self._dropping = False
        self._pending = bytearray()
        self._visible_prompt = b""

    def _candidates(self) -> tuple[bytes, ...]:
        if self._visible_prompt == b"*":
            return (b" SKTRACE ", b" PBTRACE ")
        if self._visible_prompt == b"* ":
            return self._NOISE_PREFIXES
        return self._NOISE_PREFIXES + self._PROMPT_NOISE_PREFIXES

    def project(self, data: bytes) -> bytes:
        projected = bytearray()
        for byte in data:
            if self._dropping:
                if byte == 0x0A:
                    self._dropping = False
                    self._line_start = True
                    self._visible_prompt = b""
                continue
            if self._line_start:
                self._pending.append(byte)
                pending = bytes(self._pending)
                candidates = self._candidates()
                if pending in candidates:
                    if (
                        not self._visible_prompt
                        and pending in self._PROMPT_NOISE_PREFIXES
                    ):
                        projected.extend(b"* ")
                    self._pending.clear()
                    self._dropping = True
                    self._visible_prompt = b""
                    continue
                if any(candidate.startswith(pending) for candidate in candidates):
                    continue
                projected.extend(self._pending)
                self._line_start = byte == 0x0A
                self._pending.clear()
                self._visible_prompt = b""
                continue
            projected.append(byte)
            if byte == 0x0A:
                self._line_start = True
        return bytes(projected)

    def flush_pending(self, *, force: bool = False) -> bytes:
        """Make a prompt visible when no following byte disambiguates it."""

        pending = bytes(self._pending)
        if not pending:
            return b""
        if not force:
            if not self._visible_prompt and pending in {b"*", b"* "}:
                self._pending.clear()
                self._visible_prompt = pending
                return pending
            if self._visible_prompt == b"*" and pending == b" ":
                self._pending.clear()
                self._visible_prompt = b"* "
                return pending
            if any(candidate.startswith(pending) for candidate in self._candidates()):
                return b""
        self._pending.clear()
        self._line_start = pending.endswith(b"\n")
        self._visible_prompt = b""
        return pending


def prepare_terminal_input(
    data: bytes, *, enable_failover_cut: bool = False
) -> PreparedTerminalInput:
    """Map a modern keyboard to the bounded historical teletype profile."""

    forwarded = bytearray()
    blocked_wru = 0
    rejected_non_seven_bit = 0
    exit_requested = False
    cut_requested = False
    for byte in data:
        if byte == LOCAL_EXIT:
            exit_requested = True
            break
        if enable_failover_cut and byte == LOCAL_FAILOVER_CUT:
            cut_requested = True
            break
        if byte == SIMULATOR_WRU:
            blocked_wru += 1
            continue
        if byte > 0x7F:
            rejected_non_seven_bit += 1
            continue
        if byte == 0x0A:
            forwarded.append(0x0D)
        elif byte == 0x7F:
            forwarded.append(0x08)
        else:
            forwarded.append(byte)
    return PreparedTerminalInput(
        forwarded=bytes(forwarded),
        exit_requested=exit_requested,
        cut_requested=cut_requested,
        blocked_wru=blocked_wru,
        rejected_non_seven_bit=rejected_non_seven_bit,
    )


@contextmanager
def operator_terminal_mode(file_descriptor: int) -> Iterator[None]:
    """Use character input while preserving output processing and restore it."""

    if not os.isatty(file_descriptor):
        raise RuntimeError("historical terminal mode requires an interactive TTY")
    original = termios.tcgetattr(file_descriptor)
    configured = list(original)
    configured[6] = list(original[6])
    configured[0] &= ~(
        termios.BRKINT
        | termios.ICRNL
        | termios.INPCK
        | termios.ISTRIP
        | termios.IXON
    )
    configured[2] = (configured[2] & ~termios.CSIZE) | termios.CS8
    configured[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
    configured[6][termios.VMIN] = 1
    configured[6][termios.VTIME] = 0
    termios.tcsetattr(file_descriptor, termios.TCSAFLUSH, configured)
    try:
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSAFLUSH, original)


def write_all(file_descriptor: int, data: bytes) -> None:
    """Write the complete byte string to a terminal file descriptor."""

    offset = 0
    while offset < len(data):
        offset += os.write(file_descriptor, data[offset:])


def network_unix_prompt_offset(data: bytes) -> int:
    """Return the start of the last exact Network UNIX root prompt."""

    matches = tuple(re.finditer(rb"\r\n# ?", data))
    if not matches:
        raise RuntimeError("Network UNIX root prompt is unavailable for terminal handoff")
    return matches[-1].start() + 2


def run_character_terminal(
    pdp11: CharacterTerminalProcess,
    recorder: TerminalSessionRecorder,
    *,
    input_fd: int,
    output_fd: int,
    start_offset: int,
    max_input_bytes: int,
    max_output_bytes: int,
    on_cut_request: Callable[[str], bytes] | None = None,
    poll_seconds: float = 0.05,
) -> str:
    """Relay bounded characters while the controller retains sole PTY ownership."""

    position = start_offset
    input_bytes = 0
    output_bytes = 0
    renderer = SafeTeletypeRenderer()
    projection = HistoricalConsoleProjection()

    def flush_projection(*, force: bool = False) -> None:
        pending = projection.flush_pending(force=force)
        if pending:
            write_all(output_fd, renderer.render(pending))

    def relay_output() -> str | None:
        nonlocal position, output_bytes
        available = pdp11.output_from(position)
        if not available:
            return None
        if output_bytes + len(available) > max_output_bytes:
            return "output-limit"
        recorder.bytes("pdp11-to-operator", available, observed_at=utc_now())
        output_bytes += len(available)
        position += len(available)
        write_all(output_fd, renderer.render(projection.project(available)))
        return None

    while True:
        limit_reason = relay_output()
        if limit_reason is not None:
            return limit_reason
        process = pdp11.process
        if process is None or process.poll() is not None:
            flush_projection(force=True)
            return "process-exit"
        readable, _, _ = select.select((input_fd,), (), (), poll_seconds)
        if not readable:
            flush_projection()
            continue
        incoming = os.read(input_fd, DEFAULT_MAX_CHUNK_BYTES)
        if not incoming:
            flush_projection(force=True)
            return "input-eof"
        prepared = prepare_terminal_input(
            incoming,
            enable_failover_cut=on_cut_request is not None,
        )
        observed_at = utc_now()
        if prepared.blocked_wru:
            recorder.control(
                "blocked-simulator-wru",
                observed_at=observed_at,
                count=prepared.blocked_wru,
            )
            write_all(
                output_fd,
                b"\n[local] Control-\\ is reserved for safe simulator cleanup.\n",
            )
        if prepared.rejected_non_seven_bit:
            recorder.control(
                "rejected-non-seven-bit",
                observed_at=observed_at,
                count=prepared.rejected_non_seven_bit,
            )
            write_all(output_fd, b"\n[local] This terminal profile accepts 7-bit input.\n")
        if prepared.forwarded:
            if input_bytes + len(prepared.forwarded) > max_input_bytes:
                return "input-limit"
            recorder.bytes(
                "operator-to-pdp11",
                prepared.forwarded,
                observed_at=observed_at,
            )
            pdp11.send(prepared.forwarded)
            input_bytes += len(prepared.forwarded)
        if prepared.cut_requested:
            assert on_cut_request is not None
            write_all(
                output_fd,
                b"\n[local] Checking the pre-cut transaction and requesting the direct-link cut ...\n",
            )
            response = on_cut_request(observed_at)
            if response:
                write_all(output_fd, response)
        if prepared.exit_requested:
            time.sleep(0.05)
            limit_reason = relay_output()
            flush_projection(force=True)
            return limit_reason or "operator-exit"
