"""Recovered-IMP readiness and modem-interface evidence primitives."""

from __future__ import annotations

from pathlib import Path
import re
import time

from ncc.harness_process import ImpProcess


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
    return {
        content
        for content in contents
        if len(content.split()) >= MIN_CORRELATED_MI_WORDS
    }
