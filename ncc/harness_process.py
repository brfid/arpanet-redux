"""Owned simulator process and pseudo-terminal lifecycle primitives."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import pty
import re
import signal
import subprocess
import threading
import time
from typing import Callable, Iterator

from ncc.harness_manifest import append_manifest


WRU = b"\x1c"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PtyProcess:
    def __init__(
        self,
        name: str,
        executable: Path,
        config: Path,
        work_dir: Path,
        console_log: Path,
        sent_log: Path,
        manifest: Path,
    ) -> None:
        self.name = name
        self.executable = executable
        self.config = config
        self.work_dir = work_dir
        self.console_log_path = console_log
        self.sent_log_path = sent_log
        self.manifest = manifest
        self.process: subprocess.Popen[bytes] | None = None
        self.master_fd: int | None = None
        self.reader: threading.Thread | None = None
        self.console_stream = None
        self.sent_stream = None
        self.buffer = bytearray()
        self.cursor = 0
        self.eof = False
        self.condition = threading.Condition()
        self.state = "NEW"
        self.watch: ProcessWatch | None = None

    def launch(self, state: str = "BOOTING") -> None:
        try:
            self._launch(state)
        except BaseException:
            self.stop(force=True)
            raise

    def _launch(self, state: str) -> None:
        self.console_stream = self.console_log_path.open("wb", buffering=0)
        self.sent_stream = self.sent_log_path.open("a", encoding="ascii")
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        try:
            self.process = subprocess.Popen(
                [self.executable, self.config],
                cwd=self.work_dir,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            os.close(slave_fd)
        append_manifest(self.manifest, f"process.{self.name}.pid", self.process.pid)
        self.state = state
        self.reader = threading.Thread(
            target=self._read_console,
            name=f"{self.name}-console",
            daemon=True,
        )
        self.reader.start()

    def _read_console(self) -> None:
        assert self.master_fd is not None
        assert self.console_stream is not None
        try:
            while True:
                try:
                    chunk = os.read(self.master_fd, 65536)
                except OSError as error:
                    if error.errno in (errno.EIO, errno.EBADF):
                        break
                    raise
                if not chunk:
                    break
                self.console_stream.write(chunk)
                with self.condition:
                    self.buffer.extend(chunk)
                    self.condition.notify_all()
        finally:
            with self.condition:
                self.eof = True
                self.condition.notify_all()

    def expect(self, pattern: bytes | str, timeout: float) -> re.Match[bytes]:
        _, match = self.expect_any((pattern,), timeout)
        return match

    def expect_any(
        self, patterns: tuple[bytes | str, ...], timeout: float
    ) -> tuple[int, re.Match[bytes]]:
        expressions = [
            re.compile(
                pattern.encode("latin-1") if isinstance(pattern, str) else pattern,
                re.DOTALL,
            )
            for pattern in patterns
        ]
        deadline = time.monotonic() + timeout
        if self.watch is not None:
            self.watch.waiting(f"{self.name} console matching {patterns!r}", timeout)
        with self.condition:
            while True:
                if self.watch is not None:
                    self.watch.check()
                matches = [
                    (match.start(), index, match)
                    for index, expression in enumerate(expressions)
                    if (match := expression.search(self.buffer, self.cursor)) is not None
                ]
                if matches:
                    _, index, match = min(matches, key=lambda item: (item[0], item[1]))
                    self.cursor = match.end()
                    return index, match
                remaining = deadline - time.monotonic()
                if self.eof or self.process is None or self.process.poll() is not None:
                    tail = bytes(self.buffer[-1000:]).decode("latin-1", errors="replace")
                    raise RuntimeError(
                        f"{self.name} exited while waiting for {patterns!r}; "
                        f"exit status={self.process.poll() if self.process is not None else None}; tail={tail!r}"
                    )
                if remaining <= 0:
                    tail = bytes(self.buffer[-1000:]).decode("latin-1", errors="replace")
                    raise TimeoutError(
                        f"{self.name} timed out waiting for {patterns!r}; tail={tail!r}"
                    )
                self.condition.wait(min(remaining, 0.5))

    def send(self, data: bytes | str) -> None:
        encoded = data.encode("latin-1") if isinstance(data, str) else data
        if self.master_fd is None or self.process is None or self.process.poll() is not None:
            raise RuntimeError(f"cannot send to stopped process {self.name}")
        assert self.sent_stream is not None
        self.sent_stream.write(f"{utc_now()} {encoded.hex()}\n")
        self.sent_stream.flush()
        written = 0
        while written < len(encoded):
            written += os.write(self.master_fd, encoded[written:])

    def send_slow(self, data: bytes | str, delay: float = 0.05) -> None:
        encoded = data.encode("latin-1") if isinstance(data, str) else data
        for byte in encoded:
            self.send(bytes((byte,)))
            time.sleep(delay)

    def position(self) -> int:
        with self.condition:
            return len(self.buffer)

    def output_from(self, offset: int) -> bytes:
        with self.condition:
            return bytes(self.buffer[offset:])

    def mark_running_after_banner(self) -> None:
        self.expect("SYSTEM JOB USING THIS CONSOLE", timeout=900)
        self.state = "RUNNING"

    def enter_ddt_and_prove_local_time(self) -> None:
        if self.state != "RUNNING":
            raise RuntimeError(f"{self.name} cannot enter DDT from {self.state}")
        self.send(b"\x1a")
        self.expect("Welcome to ITS!", timeout=300)
        self.send(":time\r")
        self.expect("The time is", timeout=90)
        self.expect("Today is", timeout=30)
        self.expect(rb"KA ITS [0-9]+ has run for", timeout=30)
        self.expect(rb"\r\n\*", timeout=30)

    def stop(self, force: bool = False) -> None:
        self.watch = None
        try:
            self._stop_process(force)
        finally:
            self._close_resources()

    def _stop_process(self, force: bool) -> None:
        process = self.process
        if process is None:
            return
        if process.poll() is None and force:
            process.terminate()
        if process.poll() is None and not force:
            try:
                if self.state == "RUNNING":
                    self.send(WRU)
                    self.expect("sim> ", timeout=3)
                    self.state = "PROMPT"
                if self.state == "PROMPT":
                    self.send("quit\r")
            except (OSError, RuntimeError, TimeoutError):
                pass
        if process.poll() is None:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        self.state = "STOPPED"

    def _close_resources(self) -> None:
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.reader is not None:
            self.reader.join(timeout=1)
        if self.console_stream is not None:
            self.console_stream.close()
        if self.sent_stream is not None:
            self.sent_stream.close()


class ImpProcess:
    def __init__(
        self,
        name: str,
        executable: Path,
        config: Path,
        work_dir: Path,
        results_dir: Path,
        manifest: Path,
    ) -> None:
        self.name = name
        self.executable = executable
        self.config = config
        self.work_dir = work_dir
        self.console_path = results_dir / f"{name}.console.log"
        self.debug_path = results_dir / f"{name}.debug.log"
        self.manifest = manifest
        self.console_stream = None
        self.debug_stream = None
        self.master_fd: int | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self.watch: ProcessWatch | None = None

    def launch(self) -> None:
        try:
            self._launch()
        except BaseException:
            self.stop()
            raise

    def _launch(self) -> None:
        self.console_stream = self.console_path.open("wb")
        self.debug_stream = self.debug_path.open("wb")
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        try:
            self.process = subprocess.Popen(
                [self.executable, self.config],
                cwd=self.work_dir,
                stdin=slave_fd,
                stdout=self.console_stream,
                stderr=self.debug_stream,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            os.close(slave_fd)
        append_manifest(self.manifest, f"process.{self.name}.pid", self.process.pid)

    def ensure_alive(self) -> None:
        if self.watch is not None:
            self.watch.check()
        ensure_process_alive(self)

    def stop(self) -> None:
        self.watch = None
        try:
            self._stop_process()
        finally:
            self._close_resources()

    def _stop_process(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def _close_resources(self) -> None:
        if self.master_fd is not None:
            os.close(self.master_fd)
            self.master_fd = None
        if self.console_stream is not None:
            self.console_stream.close()
        if self.debug_stream is not None:
            self.debug_stream.close()


def ensure_process_alive(process: PtyProcess | ImpProcess) -> None:
    if process.process is None or process.process.poll() is not None:
        status = process.process.poll() if process.process is not None else None
        raise RuntimeError(f"{process.name} exited early (exit status={status})")


class ProcessWatch:
    """Check the live child handles in one controller, including waiting peers."""

    def __init__(
        self,
        processes: tuple[PtyProcess | ImpProcess, ...],
        waiting: Callable[[str, float], None],
    ) -> None:
        self.processes = processes
        self.waiting = waiting
        for process in processes:
            process.watch = self

    def check(self) -> None:
        for item in self.processes:
            if item.process is not None:
                ensure_process_alive(item)

    def sleep(self, seconds: float, condition: str) -> None:
        self.waiting(condition, seconds)
        deadline = time.monotonic() + seconds
        while True:
            self.check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.1))


@contextmanager
def cleanup_signals() -> Iterator[None]:
    """Finish bounded cleanup even when another catchable signal arrives."""

    previous = {}
    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, signal.SIG_IGN)
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def stop_all(
    hosts: tuple[PtyProcess, ...], imps: tuple[ImpProcess, ...], force: bool
) -> None:
    failures = []
    with cleanup_signals():
        # Readiness must not reject simulator-prompt cleanup because a peer has
        # already stopped. Visit every owner even after one stop/close fails.
        for item in (*hosts, *imps):
            item.watch = None
        for item in (*hosts, *imps):
            try:
                if item in hosts:
                    item.stop(force=force)
                else:
                    item.stop()
            except Exception as error:
                failures.append(f"{item.name}: {type(error).__name__}: {error}")
    if failures:
        raise RuntimeError("owned process cleanup failed: " + "; ".join(failures))
