#!/usr/bin/env python3
"""Hold distinct dual-stack loopback UDP ports while a run is prepared."""

from __future__ import annotations

import argparse
import errno
import os
from pathlib import Path
import signal
import socket
import sys
import threading
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--lock-root", type=Path, required=True)
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--attempts-per-port", type=int, default=128)
    parser.add_argument("--require-ipv6", action="store_true")
    return parser.parse_args()


def validate(args: argparse.Namespace) -> None:
    if args.count < 1:
        raise ValueError("--count must be positive")
    if args.owner_pid < 1:
        raise ValueError("--owner-pid must be positive")
    if args.attempts_per_port < 1:
        raise ValueError("--attempts-per-port must be positive")


def pid_exists(pid: int) -> bool:
    if pid < 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def metadata_values(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="ascii").splitlines():
            name, separator, value = line.partition("=")
            if separator and value.isdecimal():
                values[name] = int(value)
    except (OSError, UnicodeError):
        return {}
    return values


def reclaim_if_abandoned(lock: Path) -> bool:
    owner_file = lock / "owner"
    values = metadata_values(owner_file)
    if values:
        if pid_exists(values.get("owner_pid", 0)) or pid_exists(values.get("lease_pid", 0)):
            return False
    else:
        try:
            if time.time() - lock.stat().st_mtime < 3600:
                return False
        except OSError:
            return False
    try:
        owner_file.unlink()
    except FileNotFoundError:
        pass
    try:
        lock.rmdir()
    except OSError:
        return False
    return True


def write_text_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def ipv6_available(required: bool) -> bool:
    if not socket.has_ipv6:
        if required:
            raise RuntimeError("Python reports that IPv6 is unavailable")
        return False
    probe = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    try:
        probe.bind(("::", 0))
    except OSError:
        if required:
            raise RuntimeError("IPv6 UDP bind is unavailable")
        return False
    finally:
        probe.close()
    return True


def claim_one(
    args: argparse.Namespace, use_ipv6: bool
) -> tuple[int, Path, socket.socket, socket.socket | None]:
    for _ in range(args.attempts_per_port):
        ipv4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ipv6: socket.socket | None = None
        lock: Path | None = None
        try:
            ipv4.bind(("0.0.0.0", 0))
            port = ipv4.getsockname()[1]
            lock = args.lock_root / f"udp-{port}.lock"
            try:
                lock.mkdir(mode=0o700)
            except FileExistsError:
                if not reclaim_if_abandoned(lock):
                    ipv4.close()
                    continue
                lock.mkdir(mode=0o700)

            if use_ipv6:
                ipv6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                ipv6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                ipv6.bind(("::", port))
            owner_file = lock / "owner"
            owner_file.write_text(
                f"owner_pid={args.owner_pid}\nlease_pid={os.getpid()}\nport={port}\n",
                encoding="ascii",
            )
            os.chmod(owner_file, 0o600)
            return port, lock, ipv4, ipv6
        except OSError as error:
            ipv4.close()
            if ipv6 is not None:
                ipv6.close()
            if lock is not None:
                try:
                    (lock / "owner").unlink()
                except FileNotFoundError:
                    pass
                try:
                    lock.rmdir()
                except OSError:
                    pass
            if error.errno in (errno.EADDRINUSE, errno.EACCES):
                continue
            raise
    raise RuntimeError("could not reserve another dual-stack UDP port")


def cleanup_locks(locks: list[Path]) -> None:
    for lock in locks:
        try:
            (lock / "owner").unlink()
        except FileNotFoundError:
            pass
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass


def close_sockets(sockets: list[socket.socket]) -> None:
    while sockets:
        sockets.pop().close()


def main() -> int:
    args = parse_args()
    release_requested = threading.Event()
    stop_requested = threading.Event()

    def request_release(_signum: int, _frame: object) -> None:
        release_requested.set()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    signal.signal(signal.SIGUSR1, request_release)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGHUP, request_stop)

    locks: list[Path] = []
    sockets: list[socket.socket] = []
    try:
        validate(args)
        use_ipv6 = ipv6_available(args.require_ipv6)
        if args.lock_root.is_symlink():
            raise ValueError("--lock-root must not be a symbolic link")
        args.lock_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not args.lock_root.is_dir() or args.lock_root.stat().st_uid != os.getuid():
            raise ValueError("--lock-root must be a directory owned by the current user")
        os.chmod(args.lock_root, 0o700)
        ports: list[int] = []
        for _ in range(args.count):
            port, lock, ipv4, ipv6 = claim_one(args, use_ipv6)
            ports.append(port)
            locks.append(lock)
            sockets.append(ipv4)
            if ipv6 is not None:
                sockets.append(ipv6)

        released_file = args.ready_file.with_name(f"{args.ready_file.name}.released")
        families = "ipv4,ipv6" if use_ipv6 else "ipv4"
        lines = [f"count={len(ports)}", f"families={families}", f"released={released_file}"]
        lines.extend(f"port_{index}={port}" for index, port in enumerate(ports))
        write_text_atomic(args.ready_file, "\n".join(lines) + "\n")
        print(" ".join(str(port) for port in ports), flush=True)

        released = False
        while not stop_requested.wait(0.1):
            if not pid_exists(args.owner_pid):
                break
            if release_requested.is_set() and not released:
                close_sockets(sockets)
                write_text_atomic(released_file, "released=1\n")
                released = True
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"reserve-udp-ports.py: {error}", file=sys.stderr)
        return 1
    finally:
        close_sockets(sockets)
        cleanup_locks(locks)


if __name__ == "__main__":
    raise SystemExit(main())
