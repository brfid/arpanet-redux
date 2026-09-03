"""Reusable Network UNIX PDP-11 to ITS harness behavior."""

from __future__ import annotations

from pathlib import Path
import re

# Several generic names remain imported here while the failover and interactive
# controllers migrate from their historical ``BASE.SHARED`` access path. The
# owning modules remain authoritative; this compatibility surface is temporary.
from ncc.harness_config import (
    PORT_VARIABLES,
    create_host106_attach_config,
    validate_environment,
)
from ncc.harness_imp import (
    latest_watchdog,
    mi_link_messages_from_bytes,
    significant,
    wait_for_log_marker,
    wait_for_watchdog_devices_ready,
    watchdog_devices_ready,
    watchdog_reports_modem_dead,
)
from ncc.harness_manifest import append_manifest, read_manifest, sha256
from ncc.harness_process import (
    ImpProcess,
    PtyProcess,
    ensure_process_alive,
    stop_all,
    utc_now,
)


TIME_PATTERN = rb"The time is [0-9]{1,2}:[0-9]{2}:[0-9]{2} [A-Z]{2,5}\."
DATE_PATTERN = (
    rb"Today is [A-Za-z]+, the [0-9]{1,2}(?:st|nd|rd|th) "
    rb"of [A-Za-z]+, [0-9]{4}\."
)
UPTIME_PATTERN = rb"KA ITS [0-9]+ has run for [^\r\n]+\."
SERVICE_PATTERN = rb"LOGIN  ([0-9]{2}TLNT) 0 HST176"
FATAL_SESSION = re.compile(
    rb"Host is Unavailable|Connection (?:closed|lost)|(?:^|[\r\n])CLOSED\b|"
    rb"transport error|tmxr_put_packet_ln\(\) failed",
    re.IGNORECASE,
)
FATAL_TRANSPORT = re.compile(
    rb"bind error|Can't open Datagram socket|UNRECOVERABLE I/O ERROR|"
    rb"tmxr_put_packet_ln\(\) failed|HARDWARE ERROR|HOST DOWN",
    re.IGNORECASE,
)


def ordered_pattern_failures(data: bytes) -> list[str]:
    patterns = (
        ("Connection open", rb"Connection open"),
        ("ITS machine greeting", rb"MIT Dynamic[\s\S]*?Modelling PDP-10"),
        ("ITS monitor greeting", rb"KA ITS\.[0-9]+\. DDT\.[0-9]+\."),
        ("ITS TTY assignment", rb"TTY [0-9]+"),
        ("ITS welcome banner", rb"Welcome to ITS!"),
        ("remote time", TIME_PATTERN),
        ("remote date", DATE_PATTERN),
        ("remote uptime", UPTIME_PATTERN),
    )
    failures: list[str] = []
    position = 0
    for label, pattern in patterns:
        match = re.search(pattern, data[position:], re.DOTALL)
        if match is None:
            failures.append(f"missing ordered {label} evidence")
            continue
        position += match.end()
    return failures


def application_evidence_failures(
    pdp11_output: bytes,
    its_output: bytes,
    imp6_output: bytes,
    imp62_output: bytes,
    *,
    imp6_mi_device: str = "mi1",
    imp62_mi_device: str = "mi1",
) -> list[str]:
    failures = ordered_pattern_failures(pdp11_output)
    if FATAL_SESSION.search(pdp11_output):
        failures.append("PDP-11 session reported a premature close or transport failure")
    if re.search(SERVICE_PATTERN, its_output) is None:
        failures.append("ITS lacks the incoming HST176 TELNET service job")

    for name, output, modem_device in (
        ("imp6", imp6_output, imp6_mi_device),
        ("imp62", imp62_output, imp62_mi_device),
    ):
        for marker in (b"HI2 MSG: message received", b"HI2 MSG: message sent"):
            if marker not in output:
                failures.append(
                    f"{name} lacks post-probe {marker.decode('ascii')} evidence"
                )
        if FATAL_TRANSPORT.search(output):
            failures.append(f"{name} reported a fatal transport condition")
        if watchdog_reports_modem_dead(output, modem_device):
            failures.append(f"{name} reported a post-probe modem-line-dead transition")

    imp6_mi = mi_link_messages_from_bytes(imp6_output, device=imp6_mi_device)
    imp62_mi = mi_link_messages_from_bytes(imp62_output, device=imp62_mi_device)
    forward = significant(imp6_mi[b"sent"]) & significant(
        imp62_mi[b"received"]
    )
    returned = significant(imp62_mi[b"sent"]) & significant(
        imp6_mi[b"received"]
    )
    if not forward:
        failures.append("missing correlated post-probe IMP 6 to IMP 62 traffic")
    if not returned:
        failures.append("missing correlated post-probe IMP 62 to IMP 6 traffic")
    return failures


def wait_for_prompt(process: PtyProcess, timeout: float = 30) -> None:
    process.expect(rb"\r\n# ?", timeout=timeout)


def create_host106_observation_config(source: Path, destination: Path) -> None:
    """Create the normal attach-only config with observation-only IMP tracing."""

    create_host106_attach_config(source, destination)
    with destination.open("a", encoding="ascii") as stream:
        stream.write("set -f debug stdout\nset imp debug=ASSEMBLY\n")


def boot_pdp11(process: PtyProcess) -> None:
    if process.state != "PROMPT":
        raise RuntimeError(f"{process.name} cannot boot from {process.state}")
    process.send("boot rl0\r")
    process.state = "BOOTING"
    process.expect("!", timeout=15)
    process.send("green\r")
    process.expect("login:", timeout=30)
    process.send("root\r")
    wait_for_prompt(process, timeout=15)
    process.state = "RUNNING"


def stop_and_record(
    results_dir: Path,
    hosts: tuple[PtyProcess, ...],
    imps: tuple[ImpProcess, ...],
    force: bool,
) -> None:
    stop_all(hosts, imps, force=force)
    records = []
    survivors = []
    for item in (*hosts, *imps):
        process = item.process
        pid = process.pid if process is not None else 0
        status = process.poll() if process is not None else None
        records.append(f"{item.name}.pid={pid}\n{item.name}.exit_status={status}\n")
        if process is not None and status is None:
            survivors.append(item.name)
    (results_dir / "cleanup-evidence.txt").write_text(
        "".join(records) + f"surviving_owned_processes={len(survivors)}\n",
        encoding="ascii",
    )
    if survivors:
        raise RuntimeError(
            "owned simulator processes survived cleanup: " + ", ".join(survivors)
        )
