#!/usr/bin/env python3
"""Drive the two-ITS NCP TELNET acceptance test through simulator PTYs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import hashlib
import os
from pathlib import Path
import pty
import re
import signal
import subprocess
import sys
import threading
import time
import traceback


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.live import LiveObservationPublisher
from ncc.topology import two_its_topology


WRU = b"\x1c"
PORT_VARIABLES = (
    "BRFID_IMP6_MI_PORT",
    "BRFID_IMP62_MI_PORT",
    "BRFID_IMP6_HI_PORT",
    "BRFID_HOST_A_IMP_PORT",
    "BRFID_IMP62_HI_PORT",
    "BRFID_HOST_B_IMP_PORT",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h316", required=True, type=Path)
    parser.add_argument("--pdp10-ka", required=True, type=Path)
    parser.add_argument("--mini-root", required=True, type=Path)
    parser.add_argument("--host106-work", required=True, type=Path)
    parser.add_argument("--host176-work", required=True, type=Path)
    parser.add_argument("--imp6-config", required=True, type=Path)
    parser.add_argument("--imp62-config", required=True, type=Path)
    parser.add_argument("--host106-config", required=True, type=Path)
    parser.add_argument("--host176-config", required=True, type=Path)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--ncc-observation-stream", required=True, type=Path)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_manifest(path: Path, key: str, value: str | int) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
        raise ValueError(f"invalid manifest key: {key}")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{key}={value}\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_environment() -> None:
    for name in PORT_VARIABLES:
        value = os.environ.get(name, "")
        if not value.isdigit() or not 1 <= int(value) <= 65535:
            raise ValueError(f"{name} is not a valid UDP port")


def create_host106_attach_config(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="ascii")
    boot_expect = (
        '# Boot the host-106 ITS image and connect its NCP interface to IMP 6.\n'
        'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\n\n'
    )
    if not text.startswith(boot_expect) or not text.endswith("boot ptr\n"):
        raise ValueError("host 106 configuration has an unexpected boot sequence")
    destination.write_text(
        text.removeprefix(boot_expect).removesuffix("boot ptr\n"),
        encoding="ascii",
    )


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

    def launch(self, state: str = "BOOTING") -> None:
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
        with self.condition:
            while True:
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
                        f"{self.name} exited while waiting for {patterns!r}; tail={tail!r}"
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

    def launch(self) -> None:
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
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError(f"{self.name} exited early")

    def stop(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if self.master_fd is not None:
            os.close(self.master_fd)
            self.master_fd = None
        if self.console_stream is not None:
            self.console_stream.close()
        if self.debug_stream is not None:
            self.debug_stream.close()


def wait_for_log_marker(
    imp: ImpProcess, marker: str, timeout: float, offset: int = 0
) -> float:
    deadline = time.monotonic() + timeout
    encoded = marker.encode("latin-1")
    while time.monotonic() < deadline:
        imp.ensure_alive()
        if imp.debug_path.exists() and encoded in imp.debug_path.read_bytes()[offset:]:
            return time.monotonic()
        time.sleep(0.1)
    raise TimeoutError(f"{imp.name} did not report {marker!r} within {timeout}s")


WATCHDOG_PATTERN = re.compile(rb"WDT LIGHTS: changed to ([0-7]{6})")
WATCHDOG_MODEM_DEAD_BITS = {
    "MI1": 0o100000,
    "MI2": 0o040000,
    "MI3": 0o020000,
    "MI4": 0o010000,
}
WATCHDOG_HOST_DEAD_BITS = {
    "HI1": 0o004000,
    "HI2": 0o002000,
    "HI3": 0o001000,
    "HI4": 0o000400,
}


def watchdog_states_from_bytes(data: bytes) -> tuple[int, ...]:
    return tuple(int(match, 8) for match in WATCHDOG_PATTERN.findall(data))


def latest_watchdog(path: Path) -> str | None:
    states = watchdog_states_from_bytes(path.read_bytes())
    return f"{states[-1]:06o}" if states else None


def watchdog_devices_ready(
    state: str | None, *, modem_device: str, host_device: str | None = None
) -> bool:
    """Test only the selected firmware line/host dead bits.

    The recovered 1973 LITT table assigns one active-high dead bit to each of
    modem channels 1-4 and host channels 1-4. A whole light word is therefore
    topology-dependent and cannot be used as a fixed readiness sentinel.
    """

    modem = modem_device.upper()
    if modem not in WATCHDOG_MODEM_DEAD_BITS:
        raise ValueError(f"unsupported watchdog modem device {modem_device!r}")
    mask = WATCHDOG_MODEM_DEAD_BITS[modem]
    if host_device is not None:
        host = host_device.upper()
        if host not in WATCHDOG_HOST_DEAD_BITS:
            raise ValueError(f"unsupported watchdog host device {host_device!r}")
        mask |= WATCHDOG_HOST_DEAD_BITS[host]
    if state is None or re.fullmatch(r"[0-7]{6}", state) is None:
        return False
    return int(state, 8) & mask == 0


def wait_for_watchdog_devices_ready(
    imp: ImpProcess,
    *,
    modem_device: str,
    host_device: str | None = None,
    timeout: float,
) -> tuple[float, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        imp.ensure_alive()
        state = latest_watchdog(imp.debug_path) if imp.debug_path.exists() else None
        if watchdog_devices_ready(
            state, modem_device=modem_device, host_device=host_device
        ):
            assert state is not None
            return time.monotonic(), state
        time.sleep(0.1)
    selected = modem_device.upper()
    if host_device is not None:
        selected += f" and {host_device.upper()}"
    raise TimeoutError(
        f"{imp.name} did not report {selected} ready within {timeout}s; "
        f"latest watchdog state is {latest_watchdog(imp.debug_path)}"
    )


def watchdog_reports_modem_dead(data: bytes, modem_device: str) -> bool:
    modem = modem_device.upper()
    if modem not in WATCHDOG_MODEM_DEAD_BITS:
        raise ValueError(f"unsupported watchdog modem device {modem_device!r}")
    dead_bit = WATCHDOG_MODEM_DEAD_BITS[modem]
    return any(state & dead_bit for state in watchdog_states_from_bytes(data))


def assert_imp_application_evidence(imp: ImpProcess, offset: int) -> None:
    # "Short leader:"/"Long leader:"/"Converted:"/"type=0" were fprintf lines
    # from a hand-instrumented h316_hi.c used only during Trial 10's
    # diagnosis; the clean pinned upstream h316-simh build never emits them,
    # so requiring them here could never pass against promoted media.
    text = imp.debug_path.read_bytes()
    suffix = text[offset:]
    required = (
        b"HI2 MSG: message received",
        b"HI2 MSG: message sent",
    )
    missing = [marker.decode("ascii") for marker in required if marker not in suffix]
    if missing:
        raise RuntimeError(
            f"{imp.name} lacks post-probe evidence: {', '.join(missing)}"
        )
    fatal = re.search(
        rb"HARDWARE ERROR|HOST DOWN|bind error|Can't open Datagram socket|"
        rb"UNRECOVERABLE I/O ERROR|tmxr_put_packet_ln\(\) failed",
        text,
        re.IGNORECASE,
    )
    if fatal is not None:
        raise RuntimeError(
            f"{imp.name} reported a fatal transport condition: "
            f"{fatal.group(0).decode('latin-1')}"
        )
    if latest_watchdog(imp.debug_path) != "075400":
        raise RuntimeError(
            f"{imp.name} readiness regressed to {latest_watchdog(imp.debug_path)}"
        )


def assert_client_application_evidence(output: bytes) -> None:
    required = (
        b"CONNECT",
        b"MIT Dynamic",
        b"Modelling PDP-10",
        b"Welcome to ITS!",
        b"The time is",
        b"Today is",
        b"KA ITS",
        b"has run for",
    )
    missing = [marker.decode("ascii") for marker in required if marker not in output]
    if missing:
        raise RuntimeError(
            "host176 lacks live remote-session evidence: " + ", ".join(missing)
        )
    if re.search(rb"(?:^|[\r\n])(?:CLOSED|ERROR)\b", output, re.IGNORECASE):
        raise RuntimeError("UT reported a close or error before proof completed")


# Below this many words, a matched MI packet (e.g. a bare ready/ack) is too
# generic to rule out independent coincidence on each side of the link; the
# smallest observed application-bearing packet was 5 words.
MIN_CORRELATED_MI_WORDS = 4


def mi_link_messages_from_bytes(
    data: bytes, *, device: str = "MI1"
) -> dict[bytes, set[bytes]]:
    """Reconstruct one exact modem-interface's packet contents by direction."""

    normalized_device = device.upper()
    if re.fullmatch(r"MI[1-5]", normalized_device) is None:
        raise ValueError(f"unsupported H316 modem device {device!r}")
    encoded_device = re.escape(normalized_device.encode("ascii"))
    header_pattern = re.compile(
        encoded_device + rb" MSG: message (sent|received) \(length=(\d+)\)"
    )
    body_pattern = re.compile(encoded_device + rb" MSG: - (.*)")
    messages: dict[bytes, set[bytes]] = {b"sent": set(), b"received": set()}
    direction: bytes | None = None
    remaining = 0
    words: list[bytes] = []
    for line in data.splitlines():
        header = header_pattern.search(line)
        if header is not None:
            direction, remaining = header.group(1), int(header.group(2))
            words = []
            continue
        if direction is None or remaining <= 0:
            continue
        body = body_pattern.search(line)
        if body is None:
            direction = None
            continue
        chunk = body.group(1).split()
        words.extend(chunk)
        remaining -= len(chunk)
        if remaining <= 0:
            messages[direction].add(b" ".join(words))
            direction = None
    return messages


def mi_link_messages(
    path: Path, offset: int, *, device: str = "MI1"
) -> dict[bytes, set[bytes]]:
    return mi_link_messages_from_bytes(path.read_bytes()[offset:], device=device)


def significant(contents: set[bytes]) -> set[bytes]:
    return {content for content in contents if len(content.split()) >= MIN_CORRELATED_MI_WORDS}


def stop_all(
    hosts: tuple[PtyProcess, ...], imps: tuple[ImpProcess, ...], force: bool
) -> None:
    for host in hosts:
        host.stop(force=force)
    for imp in imps:
        imp.stop()


def run(args: argparse.Namespace) -> int:
    validate_environment()
    results_dir = args.results_dir.resolve()
    manifest = args.manifest.resolve()
    attach_config = results_dir / "host106-attach-only.simh"
    create_host106_attach_config(args.host106_config.resolve(), attach_config)
    append_manifest(manifest, "sha256.host106-attach-config", sha256(attach_config))
    append_manifest(manifest, "path.host106-attach-config", attach_config)

    imp6 = ImpProcess(
        "imp6",
        args.h316.resolve(),
        args.imp6_config.resolve(),
        args.mini_root.resolve(),
        results_dir,
        manifest,
    )
    imp62 = ImpProcess(
        "imp62",
        args.h316.resolve(),
        args.imp62_config.resolve(),
        args.mini_root.resolve(),
        results_dir,
        manifest,
    )
    host106 = PtyProcess(
        "host106",
        args.pdp10_ka.resolve(),
        attach_config,
        args.host106_work.resolve(),
        results_dir / "host106.console.log",
        results_dir / "host106.sent.log",
        manifest,
    )
    host176 = PtyProcess(
        "host176",
        args.pdp10_ka.resolve(),
        args.host176_config.resolve(),
        args.host176_work.resolve(),
        results_dir / "host176.console.log",
        results_dir / "host176.sent.log",
        manifest,
    )
    hosts = (host176, host106)
    imps = (imp6, imp62)
    publisher = LiveObservationPublisher(
        args.ncc_observation_stream.resolve(),
        run_id=f"run:{results_dir.name}",
        started_at=utc_now(),
        provenance=[
            {
                "id": "source:two-its-controller",
                "kind": "harness-controller",
            }
        ],
        topology=two_its_topology(),
        stale_after_seconds=90,
    )
    append_manifest(manifest, "ncc.observation_stream", publisher.path)
    outcome = "failed"
    interrupted = False

    def observe(
        category: str,
        subject_id: str,
        state: str,
        details: dict[str, str] | None = None,
    ) -> None:
        publisher.publish(
            category=category,
            subject_id=subject_id,
            state=state,
            source={
                "id": "source:two-its-controller",
                "kind": "harness-controller",
            },
            details=details,
        )

    def interrupt(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        if interrupted:
            return
        interrupted = True
        raise InterruptedError("controller interrupted")

    old_term = signal.signal(signal.SIGTERM, interrupt)
    old_int = signal.signal(signal.SIGINT, interrupt)
    try:
        imp6.launch()
        observe("harness", "imp:6", "started", {"process": "imp6"})
        imp62.launch()
        observe("harness", "imp:62", "started", {"process": "imp62"})
        wait_for_log_marker(imp6, "listening on port", 30)
        observe("harness", "imp:6", "listening", {"marker": "listening-on-port"})
        wait_for_log_marker(imp62, "listening on port", 30)
        observe("harness", "imp:62", "listening", {"marker": "listening-on-port"})

        # Both guest endpoints must bind before the recovered IMPs can send
        # their first host-link NOP after the modem route comes up.
        host176.launch()
        observe("harness", "host:176", "started", {"process": "host176"})
        host106.launch(state="PROMPT")
        observe("harness", "host:106", "started", {"process": "host106"})
        host106.expect("sim> ", timeout=60)
        observe("harness", "host:106", "console-ready", {"state": "PROMPT"})

        imp6_modem_up = wait_for_log_marker(
            imp6, "WDT LIGHTS: changed to 077400", 60
        )
        observe("harness", "imp:6", "modem-ready", {"watchdog_lights": "077400"})
        imp62_modem_up = wait_for_log_marker(
            imp62, "WDT LIGHTS: changed to 077400", 60
        )
        observe("harness", "imp:62", "modem-ready", {"watchdog_lights": "077400"})
        route_settle_deadline = max(imp6_modem_up, imp62_modem_up) + 60
        observe("harness", "link:62-6", "modem-ready", {"watchdog_lights": "077400"})

        host176.mark_running_after_banner()
        observe("harness", "host:176", "running", {"marker": "system-console-banner"})
        host106.send(
            'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\r'
        )
        host106.expect("sim> ", timeout=30)
        host106.send("boot ptr\r")
        host106.state = "BOOTING"
        host106.mark_running_after_banner()
        observe("harness", "host:106", "running", {"marker": "system-console-banner"})
        for imp in imps:
            imp.ensure_alive()

        host106.enter_ddt_and_prove_local_time()
        host176.enter_ddt_and_prove_local_time()
        host106.expect(rb"LOGIN  GUNNER 0", timeout=180)
        host176.expect(rb"LOGIN  GUNNER 0", timeout=180)
        host106.send_slow(":login db\r")
        time.sleep(8)

        wait_for_log_marker(imp6, "WDT LIGHTS: changed to 075400", 1200)
        observe("harness", "imp:6", "host-link-ready", {"watchdog_lights": "075400"})
        wait_for_log_marker(imp62, "WDT LIGHTS: changed to 075400", 1200)
        observe("harness", "imp:62", "host-link-ready", {"watchdog_lights": "075400"})
        remaining = route_settle_deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        for imp in imps:
            imp.ensure_alive()
            if latest_watchdog(imp.debug_path) != "075400":
                raise RuntimeError(
                    f"{imp.name} is not host-link ready: {latest_watchdog(imp.debug_path)}"
                )
        if host106.state != "RUNNING" or host176.state != "RUNNING":
            raise RuntimeError("both KA10 controllers must be RUNNING before UT")
        observe(
            "harness",
            "route:host176-to-host106",
            "host-link-ready",
            {"watchdog_lights": "075400"},
        )

        imp_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        client_offset = host176.position()
        observe("harness", "route:host176-to-host106", "probing")
        host176.send_slow("ut")
        host176.send(b"\x0b")
        host176.expect(rb"UT\.76", timeout=45)
        host176.send_slow("106\r")
        service_match = host106.expect(
            rb"LOGIN  ([0-9]{2}TLNT) 0 HST176", timeout=180
        )
        service_user = service_match.group(1).decode("ascii")

        host176.expect("MIT Dynamic", timeout=60)
        host176.send_slow(b"\x1eTRANSPARENT\r")
        host176.send(b"\x1a")
        host176.expect("Welcome to ITS!", timeout=60)
        remote_user = "NETTST"
        host176.send_slow(f":login {remote_user.lower()}\r")
        host106.expect(rf"LOGIN  {remote_user}", timeout=60)
        host176.send_slow(":time\r")
        host176.expect("The time is", timeout=60)
        host176.expect("Today is", timeout=30)
        host176.expect(rb"KA ITS [0-9]+ has run for", timeout=30)

        token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        token += f"-{os.getpid():X}"
        sentinel = f"ARPANET-REDUX-{token}"
        host106.send_slow(f":osend {remote_user} {sentinel}")
        host106.send(b"\x03")
        host176.expect(re.escape(sentinel.encode("ascii")), timeout=60)
        recovered = sentinel.encode("ascii")
        source_digest = hashlib.sha256(sentinel.encode("ascii")).hexdigest()
        recovered_digest = hashlib.sha256(recovered).hexdigest()
        if recovered_digest != source_digest:
            raise RuntimeError("the recovered sentinel digest does not match")

        client_output = host176.output_from(client_offset)
        assert_client_application_evidence(client_output)
        for imp in imps:
            assert_imp_application_evidence(imp, imp_offsets[imp.name])
        imp6_mi = mi_link_messages(imp6.debug_path, imp_offsets[imp6.name])
        imp62_mi = mi_link_messages(imp62.debug_path, imp_offsets[imp62.name])
        forward_hop = significant(imp6_mi[b"sent"]) & significant(imp62_mi[b"received"])
        return_hop = significant(imp62_mi[b"sent"]) & significant(imp6_mi[b"received"])
        if not forward_hop or not return_hop:
            raise RuntimeError(
                "the two IMPs lack a correlated modem-link (MI1) packet in both directions"
            )

        (results_dir / "sentinel-evidence.txt").write_text(
            "source=host106-console\n"
            "destination=host176-ncp-telnet\n"
            f"service_user={service_user}\n"
            f"remote_user={remote_user}\n"
            f"sentinel={sentinel}\n"
            f"source_sha256={source_digest}\n"
            f"recovered_sha256={recovered_digest}\n",
            encoding="ascii",
        )
        append_manifest(manifest, "application.client", "UT.76")
        append_manifest(manifest, "application.server", "TELSER")
        append_manifest(manifest, "application.sentinel_sha256", source_digest)
        observe(
            "application",
            "route:host176-to-host106",
            "passed",
            {"sentinel_sha256": source_digest},
        )
        outcome = "passed"
        print(f"PASS: two ITS guests exchanged an NCP TELNET payload through two IMPs: {results_dir}")
        return 0
    except TimeoutError:
        observe(
            "missing-evidence",
            "route:host176-to-host106",
            "timeout",
            {"controller": "two-its"},
        )
        raise
    except InterruptedError:
        observe(
            "missing-evidence",
            "route:host176-to-host106",
            "interrupted",
            {"controller": "two-its"},
        )
        raise
    except (OSError, RuntimeError, ValueError):
        observe(
            "harness",
            "route:host176-to-host106",
            "failed",
            {"controller": "two-its"},
        )
        raise
    finally:
        stop_all(hosts, imps, force=interrupted)
        (results_dir / "outcome.txt").write_text(outcome + "\n", encoding="ascii")
        publisher.close()
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (OSError, RuntimeError, TimeoutError, ValueError, InterruptedError):
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
