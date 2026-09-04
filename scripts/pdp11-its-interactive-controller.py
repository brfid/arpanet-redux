#!/usr/bin/env python3
"""Operate one bounded interactive Network UNIX-to-ITS TELNET session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import traceback
from typing import TextIO


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.harness_config import create_host106_attach_config, validate_environment
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
    utc_now,
)
from ncc.historical_terminal import (
    BootDisplay,
    HistoricalConsoleProjection,
    SafeTeletypeRenderer,
    network_unix_prompt_offset,
    operator_terminal_mode,
    prepare_terminal_input,
    run_character_terminal,
)
from ncc.interactive_telnet import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    DEFAULT_MAX_COMMAND_BYTES,
    DEFAULT_MAX_COMMANDS,
    DEFAULT_MAX_RESPONSE_BYTES,
    InteractiveTelnetRecorder,
    InteractiveTelnetStreamError,
    read_interactive_telnet_stream,
    validate_operator_command,
)
from ncc.pdp11_its_harness import (
    DATE_PATTERN,
    FATAL_SESSION,
    FATAL_TRANSPORT,
    SERVICE_PATTERN,
    TIME_PATTERN,
    UPTIME_PATTERN,
    boot_pdp11,
    stop_and_record,
    wait_for_prompt,
)
from ncc.pdp11_its_journey import pdp11_its_modem_devices
from ncc.shared_topology import shared_topology_from_mapping
from ncc.terminal_session import (
    DEFAULT_MAX_CHUNK_BYTES,
    DEFAULT_MAX_INPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    TerminalSessionRecorder,
    TerminalSessionStreamError,
    read_terminal_session_stream,
)

ITS_DDT_PROMPT = rb"\r\n\*"
REMOTE_BANNER = re.compile(rb"MIT Dynamic[\s\S]*?Happy hacking!\r\n")
NETWORK_UNIX_TELNET_BANNER = b"UNIX User Telnet -- Ver I.5"


class InteractiveSessionFailure(RuntimeError):
    """Raised after a failed command has been retained in the transcript."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h316", required=True, type=Path)
    parser.add_argument("--pdp10-ka", required=True, type=Path)
    parser.add_argument("--pdp11", required=True, type=Path)
    parser.add_argument("--mini-root", required=True, type=Path)
    parser.add_argument("--host106-work", required=True, type=Path)
    parser.add_argument("--pdp11-work", required=True, type=Path)
    parser.add_argument("--imp6-config", required=True, type=Path)
    parser.add_argument("--imp62-config", required=True, type=Path)
    parser.add_argument("--host106-config", required=True, type=Path)
    parser.add_argument("--pdp11-config", required=True, type=Path)
    parser.add_argument("--topology", required=True, type=Path)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mode", choices=("line", "terminal"), default="line")
    parser.add_argument("--route-settle", type=float, default=60.0)
    parser.add_argument("--daemon-settle", type=float, default=12.0)
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--max-command-bytes",
        type=int,
        default=DEFAULT_MAX_COMMAND_BYTES,
    )
    parser.add_argument("--max-commands", type=int, default=DEFAULT_MAX_COMMANDS)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
    )
    parser.add_argument(
        "--max-terminal-input-bytes",
        type=int,
        default=DEFAULT_MAX_INPUT_BYTES,
    )
    parser.add_argument(
        "--max-terminal-output-bytes",
        type=int,
        default=DEFAULT_MAX_OUTPUT_BYTES,
    )
    parser.add_argument(
        "--max-terminal-chunk-bytes",
        type=int,
        default=DEFAULT_MAX_CHUNK_BYTES,
    )
    return parser.parse_args()


def interactive_evidence_failures(
    pdp11_output: bytes,
    its_output: bytes,
    imp6_output: bytes,
    imp62_output: bytes,
    *,
    completed_commands: int,
    imp6_mi_device: str = "mi1",
    imp62_mi_device: str = "mi1",
) -> list[str]:
    """Check connection, command, and exact post-start transport evidence."""

    patterns = (
        ("Connection open", rb"Connection open"),
        ("ITS machine greeting", rb"MIT Dynamic[\s\S]*?Modelling PDP-10"),
        ("ITS monitor greeting", rb"KA ITS\.[0-9]+\. DDT\.[0-9]+\."),
        ("ITS TTY assignment", rb"TTY [0-9]+"),
        ("ITS welcome banner", rb"Welcome to ITS!"),
        ("ITS DDT prompt", ITS_DDT_PROMPT),
    )
    failures: list[str] = []
    position = 0
    for label, pattern in patterns:
        match = re.search(pattern, pdp11_output[position:], re.DOTALL)
        if match is None:
            failures.append(f"missing ordered {label} evidence")
            continue
        position += match.end()
    if completed_commands < 1:
        failures.append("interactive session completed no prompt-framed command")
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
                    f"{name} lacks interactive {marker.decode('ascii')} evidence"
                )
        if FATAL_TRANSPORT.search(output):
            failures.append(f"{name} reported a fatal transport condition")
        if watchdog_reports_modem_dead(output, modem_device):
            failures.append(f"{name} reported an interactive modem-line-dead transition")

    imp6_mi = mi_link_messages_from_bytes(imp6_output, device=imp6_mi_device)
    imp62_mi = mi_link_messages_from_bytes(imp62_output, device=imp62_mi_device)
    forward = significant(imp6_mi[b"sent"]) & significant(imp62_mi[b"received"])
    returned = significant(imp62_mi[b"sent"]) & significant(imp6_mi[b"received"])
    if not forward:
        failures.append("missing correlated interactive IMP 6 to IMP 62 traffic")
    if not returned:
        failures.append("missing correlated interactive IMP 62 to IMP 6 traffic")
    return failures


def terminal_connection_evidence_failures(
    pdp11_output: bytes,
    its_output: bytes,
    imp6_output: bytes,
    imp62_output: bytes,
    *,
    imp6_mi_device: str = "mi1",
    imp62_mi_device: str = "mi1",
) -> list[str]:
    """Close evidence only when the operator actually opened historical TELNET."""

    patterns = (
        ("Network UNIX TELNET command interface", NETWORK_UNIX_TELNET_BANNER),
        ("connection attempt", rb"Attempting Connection"),
        ("Connection open", rb"Connection open"),
        ("ITS machine greeting", rb"MIT Dynamic[\s\S]*?Modelling PDP-10"),
        ("ITS monitor greeting", rb"KA ITS\.[0-9]+\. DDT\.[0-9]+\."),
        ("ITS TTY assignment", rb"TTY [0-9]+"),
        ("ITS welcome banner", rb"Welcome to ITS!"),
    )
    failures: list[str] = []
    position = 0
    for label, pattern in patterns:
        match = re.search(pattern, pdp11_output[position:], re.DOTALL)
        if match is None:
            failures.append(f"missing ordered {label} evidence")
            continue
        position += match.end()
    if re.search(SERVICE_PATTERN, its_output) is None:
        failures.append("ITS lacks the incoming HST176 TELNET service job")

    for name, output, modem_device in (
        ("imp6", imp6_output, imp6_mi_device),
        ("imp62", imp62_output, imp62_mi_device),
    ):
        for marker in (b"HI2 MSG: message received", b"HI2 MSG: message sent"):
            if marker not in output:
                failures.append(
                    f"{name} lacks terminal {marker.decode('ascii')} evidence"
                )
        if FATAL_TRANSPORT.search(output):
            failures.append(f"{name} reported a fatal transport condition")
        if watchdog_reports_modem_dead(output, modem_device):
            failures.append(f"{name} reported a terminal modem-line-dead transition")

    imp6_mi = mi_link_messages_from_bytes(imp6_output, device=imp6_mi_device)
    imp62_mi = mi_link_messages_from_bytes(imp62_output, device=imp62_mi_device)
    forward = significant(imp6_mi[b"sent"]) & significant(imp62_mi[b"received"])
    returned = significant(imp62_mi[b"sent"]) & significant(imp6_mi[b"received"])
    if not forward:
        failures.append("missing correlated terminal IMP 6 to IMP 62 traffic")
    if not returned:
        failures.append("missing correlated terminal IMP 62 to IMP 6 traffic")
    return failures


def historical_fidelity_facts(
    input_bytes: bytes, output_bytes: bytes
) -> dict[str, bool]:
    """Recognize only the bounded Gate 4J client exercises."""

    facts = {
        "client_started": NETWORK_UNIX_TELNET_BANNER in output_bytes,
        "connection_open": b"Connection open" in output_bytes,
        "remote_time": all(
            re.search(pattern, output_bytes) is not None
            for pattern in (
                TIME_PATTERN,
                DATE_PATTERN,
                UPTIME_PATTERN,
            )
        ),
        "ayt_yes": (
            b"^ayt\r" in input_bytes
            and re.search(rb"\^ayt\r\nYES", output_bytes) is not None
        ),
        "message_mode": (
            b"^msg\r" in input_bytes and b" Msgmode\r\n" in output_bytes
        ),
        "character_mode": (
            b"^character\r" in input_bytes and b" Charmode\r\n" in output_bytes
        ),
    }
    facts["fidelity_complete"] = all(facts.values())
    return facts


def render_console_capture(captured: bytes) -> str:
    """Render Latin-1 console bytes without emitting terminal control codes."""

    normalized = captured.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    rendered: list[str] = []
    for byte in normalized:
        if byte in (0x09, 0x0A) or 0x20 <= byte <= 0x7E:
            rendered.append(chr(byte))
        else:
            rendered.append(f"\\x{byte:02x}")
    return "".join(rendered)


def _bounded_capture(data: bytes, limit: int) -> tuple[bytes, bool]:
    if len(data) <= limit:
        return data, False
    return data[:limit], True


def run_operator_session(
    pdp11: object,
    recorder: InteractiveTelnetRecorder,
    *,
    input_stream: TextIO,
    output_stream: TextIO,
    command_timeout: int,
    max_commands: int,
    max_response_bytes: int,
) -> str:
    """Forward printable lines and retain each response through the DDT prompt."""

    completed = 0
    while completed < max_commands:
        output_stream.write("its> ")
        output_stream.flush()
        line = input_stream.readline()
        if line == "":
            output_stream.write("\nInput closed; ending the TELNET session.\n")
            output_stream.flush()
            return "input-eof"
        command = line.removesuffix("\n").removesuffix("\r")
        if command == "/quit":
            return "operator-quit"
        if command == "/help":
            output_stream.write(
                "Send one printable, prompt-returning ITS DDT line; try :TIME. "
                "Local commands: /help, /quit. This session is line-oriented; "
                "paged, full-screen, and character-at-a-time programs are not "
                "supported yet.\n"
            )
            output_stream.flush()
            continue
        try:
            command = validate_operator_command(command, recorder.max_command_bytes)
        except InteractiveTelnetStreamError as error:
            output_stream.write(f"Local input rejected: {error}\n")
            output_stream.flush()
            continue

        response_offset = pdp11.position()
        command_id = recorder.command(command, observed_at=utc_now())
        started = time.monotonic()
        pdp11.send(command + "\r")
        try:
            event, match = pdp11.expect_any(
                (ITS_DDT_PROMPT, FATAL_SESSION.pattern),
                timeout=command_timeout,
            )
        except TimeoutError:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            captured, truncated = _bounded_capture(
                pdp11.output_from(response_offset), max_response_bytes
            )
            recorder.result(
                command_id,
                observed_at=utc_now(),
                status="response-limit" if truncated else "timeout",
                elapsed_ms=elapsed_ms,
                captured=captured,
                truncated=truncated,
            )
            raise InteractiveSessionFailure(
                f"ITS did not return to its DDT prompt within {command_timeout} seconds"
            )
        except InterruptedError:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            captured, truncated = _bounded_capture(
                pdp11.output_from(response_offset), max_response_bytes
            )
            recorder.result(
                command_id,
                observed_at=utc_now(),
                status="response-limit" if truncated else "interrupted",
                elapsed_ms=elapsed_ms,
                captured=captured,
                truncated=truncated,
            )
            raise

        elapsed_ms = int((time.monotonic() - started) * 1000)
        frame_length = match.end() - response_offset
        captured, truncated = _bounded_capture(
            pdp11.output_from(response_offset)[:frame_length], max_response_bytes
        )
        if truncated:
            recorder.result(
                command_id,
                observed_at=utc_now(),
                status="response-limit",
                elapsed_ms=elapsed_ms,
                captured=captured,
                truncated=True,
            )
            raise InteractiveSessionFailure(
                f"ITS response exceeded the {max_response_bytes}-byte capture limit"
            )
        if event != 0:
            recorder.result(
                command_id,
                observed_at=utc_now(),
                status="session-closed",
                elapsed_ms=elapsed_ms,
                captured=captured,
            )
            raise InteractiveSessionFailure(
                "guest TELNET reported a closed or failed session"
            )
        recorder.result(
            command_id,
            observed_at=utc_now(),
            status="complete",
            elapsed_ms=elapsed_ms,
            captured=captured,
        )
        output_stream.write(render_console_capture(captured))
        if not captured.endswith((b"\n", b"\r")):
            output_stream.write("\n")
        output_stream.flush()
        completed += 1

    output_stream.write(f"Command limit ({max_commands}) reached; ending the session.\n")
    output_stream.flush()
    return "max-commands"


def run(args: argparse.Namespace) -> int:
    validate_environment()
    for value, name in (
        (args.command_timeout, "command timeout"),
        (args.max_command_bytes, "maximum command bytes"),
        (args.max_commands, "maximum commands"),
        (args.max_response_bytes, "maximum response bytes"),
        (args.max_terminal_input_bytes, "maximum terminal input bytes"),
        (args.max_terminal_output_bytes, "maximum terminal output bytes"),
        (args.max_terminal_chunk_bytes, "maximum terminal chunk bytes"),
    ):
        if value < 1:
            raise ValueError(f"{name} must be positive")

    results_dir = args.results_dir.resolve()
    manifest = args.manifest.resolve()
    topology_path = args.topology.resolve()
    topology_document = json.loads(topology_path.read_text(encoding="utf-8"))
    shared_topology = shared_topology_from_mapping(topology_document)
    imp62_mi_device, imp6_mi_device = pdp11_its_modem_devices(shared_topology)
    attach_config = results_dir / "host106-attach-only.simh"
    create_host106_attach_config(args.host106_config.resolve(), attach_config)
    append_manifest(
        manifest, "sha256.host106-attach-config", sha256(attach_config)
    )
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
    pdp11 = PtyProcess(
        "pdp11",
        args.pdp11.resolve(),
        args.pdp11_config.resolve(),
        args.pdp11_work.resolve(),
        results_dir / "pdp11.console.log",
        results_dir / "pdp11.sent.log",
        manifest,
    )
    hosts = (pdp11, host106)
    imps = (imp6, imp62)
    outcome = "failed"
    interrupted = False
    recorder: InteractiveTelnetRecorder | TerminalSessionRecorder | None = None
    transcript_terminal = False
    display = BootDisplay(sys.stdout)

    def interrupt(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        if interrupted:
            return
        interrupted = True
        raise InterruptedError("interactive TELNET controller interrupted")

    old_term = signal.signal(signal.SIGTERM, interrupt)
    old_int = signal.signal(signal.SIGINT, interrupt)
    try:
        display.milestone("START", "IMP backbone", "launching IMP 62 and IMP 6")
        imp6.launch()
        imp62.launch()
        wait_for_log_marker(imp6, "listening on port", 30)
        wait_for_log_marker(imp62, "listening on port", 30)
        display.milestone("READY", "IMP backbone", "both H316 transports listening")

        display.milestone(
            "START", "Historical hosts", "launching PDP-11 and KA10 simulators"
        )
        host106.launch(state="PROMPT")
        pdp11.launch(state="PROMPT")
        host106.expect("sim> ", timeout=60)
        pdp11.expect("sim> ", timeout=60)
        display.milestone(
            "READY", "Simulator consoles", "PDP-11 and KA10 attached"
        )

        display.milestone("WAIT", "IMP trunk", "bringing up IMP 62 <-> IMP 6")
        imp6_modem_up, _ = wait_for_watchdog_devices_ready(
            imp6, modem_device=imp6_mi_device, timeout=60
        )
        imp62_modem_up, _ = wait_for_watchdog_devices_ready(
            imp62, modem_device=imp62_mi_device, timeout=60
        )
        route_settle_deadline = max(imp6_modem_up, imp62_modem_up) + args.route_settle
        display.milestone("READY", "IMP trunk", "inter-IMP modem path up")

        display.milestone("BOOT", "ITS 106", "starting KA10/ITS and local DDT")
        host106.send(
            'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\r'
        )
        host106.expect("sim> ", timeout=30)
        host106.send("boot ptr\r")
        host106.state = "BOOTING"
        host106.mark_running_after_banner()
        host106.enter_ddt_and_prove_local_time()
        display.milestone("READY", "ITS 106", "DDT and local :TIME responsive")

        display.milestone(
            "BOOT", "Network UNIX 176", "starting PDP-11 and launching NCP"
        )
        boot_pdp11(pdp11)
        pdp11.send("/usr/net/etc/smalldaemon &\r")
        wait_for_prompt(pdp11, timeout=15)
        time.sleep(args.daemon_settle)
        display.milestone(
            "READY", "Network UNIX 176", "guest booted; NCP daemon launched"
        )

        display.milestone(
            "WAIT", "ARPANET route", "bringing up host links and settling routes"
        )
        wait_for_watchdog_devices_ready(
            imp6,
            modem_device=imp6_mi_device,
            host_device="hi2",
            timeout=120,
        )
        wait_for_watchdog_devices_ready(
            imp62,
            modem_device=imp62_mi_device,
            host_device="hi2",
            timeout=120,
        )
        remaining = route_settle_deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        for imp, modem_device in (
            (imp6, imp6_mi_device),
            (imp62, imp62_mi_device),
        ):
            imp.ensure_alive()
            latest = latest_watchdog(imp.debug_path)
            if not watchdog_devices_ready(
                latest, modem_device=modem_device, host_device="hi2"
            ):
                raise RuntimeError(
                    f"{imp.name} selected modem/host path is not ready: {latest}"
                )
        for host in hosts:
            ensure_process_alive(host)
            if host.state != "RUNNING":
                raise RuntimeError(f"{host.name} is not RUNNING before TELNET")
        display.milestone(
            "READY", "ARPANET route", "host 176 -> IMP 62 -> IMP 6 -> host 106"
        )

        imp_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        pdp11_offset = pdp11.position()
        host106_offset = host106.position()
        for name, offset in (
            ("imp6", imp_offsets["imp6"]),
            ("imp62", imp_offsets["imp62"]),
            ("pdp11-console", pdp11_offset),
            ("host106-console", host106_offset),
        ):
            append_manifest(manifest, f"application.offset.{name}", offset)

        if args.mode == "terminal":
            manifest_values = read_manifest(manifest)
            transcript_path = results_dir / "terminal-session.jsonl"
            recorder = TerminalSessionRecorder(
                transcript_path,
                run_id=results_dir.name,
                started_at=manifest_values["started_utc"],
                repository_revision=manifest_values["repository.revision"],
                max_input_bytes=args.max_terminal_input_bytes,
                max_output_bytes=args.max_terminal_output_bytes,
                max_chunk_bytes=args.max_terminal_chunk_bytes,
            )
            terminal_start_offset = network_unix_prompt_offset(
                pdp11.output_from(0)
            )
            display.milestone(
                "READY", "Host terminal", "Network UNIX root shell on host 176"
            )
            print("\nHISTORICAL TERMINAL READY")
            print("  You are on Network UNIX host 176.")
            print("  Start its preserved client:  /usr/bin/telnet")
            print("  At the client '* ' prompt:   connect - -h 106")
            print("  While connected, '^' is the client's literal command prefix;")
            print("  for example: ^ayt, ^character, ^msg, or ^close.")
            print("  Press Control-] to stop the complete simulation cleanly.\n")
            sys.stdout.flush()
            input_fd = sys.stdin.fileno()
            output_fd = sys.stdout.fileno()
            if not os.isatty(output_fd):
                raise RuntimeError(
                    "historical terminal mode requires output attached to a TTY"
                )
            try:
                with operator_terminal_mode(input_fd):
                    session_reason = run_character_terminal(
                        pdp11,
                        recorder,
                        input_fd=input_fd,
                        output_fd=output_fd,
                        start_offset=terminal_start_offset,
                        max_input_bytes=args.max_terminal_input_bytes,
                        max_output_bytes=args.max_terminal_output_bytes,
                    )
            except InterruptedError:
                recorder.complete(observed_at=utc_now(), reason="interrupted")
                transcript_terminal = True
                raise
            except (OSError, RuntimeError, TerminalSessionStreamError):
                recorder.complete(observed_at=utc_now(), reason="failed")
                transcript_terminal = True
                raise
            else:
                recorder.complete(
                    observed_at=utc_now(), reason=session_reason
                )
                transcript_terminal = True
            finally:
                recorder.close()

            if session_reason not in {"operator-exit", "input-eof"}:
                raise InteractiveSessionFailure(
                    f"historical terminal stopped because of {session_reason}"
                )

            display.milestone(
                "CHECK", "Evidence", "validating terminal bytes and observed claims"
            )
            transcript = read_terminal_session_stream(transcript_path)
            if not transcript.is_terminal or transcript.end_reason != session_reason:
                raise RuntimeError("historical terminal transcript is not complete")

            pdp11_output = pdp11.output_from(pdp11_offset)
            its_output = host106.output_from(host106_offset)
            imp_end_offsets = {
                imp.name: imp.debug_path.stat().st_size for imp in imps
            }
            imp6_output = imp6.debug_path.read_bytes()[
                imp_offsets["imp6"] : imp_end_offsets["imp6"]
            ]
            imp62_output = imp62.debug_path.read_bytes()[
                imp_offsets["imp62"] : imp_end_offsets["imp62"]
            ]
            fidelity = historical_fidelity_facts(
                transcript.input_bytes, transcript.output_bytes
            )
            client_started = fidelity["client_started"]
            connection_open = fidelity["connection_open"]
            remote_time = fidelity["remote_time"]
            ayt_yes = fidelity["ayt_yes"]
            message_mode = fidelity["message_mode"]
            character_mode = fidelity["character_mode"]
            fidelity_complete = fidelity["fidelity_complete"]
            service_match = re.search(SERVICE_PATTERN, its_output)
            service_user = (
                service_match.group(1).decode("ascii")
                if service_match is not None
                else None
            )
            failures: list[str] = []
            if connection_open:
                failures.extend(
                    terminal_connection_evidence_failures(
                        pdp11_output,
                        its_output,
                        imp6_output,
                        imp62_output,
                        imp6_mi_device=imp6_mi_device,
                        imp62_mi_device=imp62_mi_device,
                    )
                )
                for imp, modem_device in (
                    (imp6, imp6_mi_device),
                    (imp62, imp62_mi_device),
                ):
                    latest = latest_watchdog(imp.debug_path)
                    if not watchdog_devices_ready(
                        latest, modem_device=modem_device, host_device="hi2"
                    ):
                        failures.append(f"{imp.name} did not remain host-link ready")
            elif service_user is not None:
                failures.append(
                    "ITS service evidence exists without PDP-11 Connection open evidence"
                )
            if failures:
                raise RuntimeError("; ".join(failures))

            for name in ("imp6", "imp62"):
                append_manifest(
                    manifest,
                    f"application.offset.end.{name}",
                    imp_end_offsets[name],
                )
            append_manifest(manifest, "path.terminal-session", transcript_path)
            append_manifest(
                manifest,
                "sha256.terminal-session",
                sha256(transcript_path),
            )
            append_manifest(
                manifest, "terminal.input-bytes", len(transcript.input_bytes)
            )
            append_manifest(
                manifest, "terminal.output-bytes", len(transcript.output_bytes)
            )
            append_manifest(
                manifest, "terminal.profile", "seven-bit-safe-teletype"
            )
            append_manifest(manifest, "terminal.simulator-wru-forwarded", 0)
            append_manifest(
                manifest, "application.client-started", int(client_started)
            )
            append_manifest(
                manifest, "application.connection-open", int(connection_open)
            )
            append_manifest(
                manifest, "application.remote-time", int(remote_time)
            )
            append_manifest(manifest, "application.ayt-yes", int(ayt_yes))
            append_manifest(
                manifest, "application.message-mode", int(message_mode)
            )
            append_manifest(
                manifest, "application.character-mode", int(character_mode)
            )
            append_manifest(
                manifest,
                "application.historical-fidelity-complete",
                int(fidelity_complete),
            )
            append_manifest(
                manifest, "application.session-mode", "character-oriented"
            )
            if connection_open:
                assert service_user is not None
                append_manifest(
                    manifest, "application.client", "network-unix-telnet"
                )
                append_manifest(manifest, "application.server", "TELSER")
                append_manifest(
                    manifest, "application.service_user", service_user
                )

            evidence = (
                "session_mode=character-oriented\n"
                "terminal_profile=seven-bit-safe-teletype\n"
                "simulator_wru_forwarded=0\n"
                f"guest_telnet_client_started={int(client_started)}\n"
                f"connection_open={int(connection_open)}\n"
                f"its_service_user={service_user or 'not-observed'}\n"
                f"remote_time={int(remote_time)}\n"
                f"ayt_yes={int(ayt_yes)}\n"
                f"message_mode={int(message_mode)}\n"
                f"character_mode={int(character_mode)}\n"
                f"historical_fidelity_complete={int(fidelity_complete)}\n"
                "correlated_inter_imp_traffic="
                f"{'both-directions' if connection_open else 'not-observed'}\n"
            )
            (results_dir / "application-evidence.txt").write_text(
                evidence, encoding="ascii"
            )
            outcome = "passed"
            if connection_open:
                display.milestone(
                    "READY",
                    "Evidence",
                    f"historical client reached ITS service job {service_user}",
                )
            else:
                display.milestone(
                    "READY",
                    "Evidence",
                    "host terminal retained; no TELNET connection claimed",
                )
            return 0

        display.milestone(
            "OPEN", "TELNET", "Network UNIX host 176 -> ITS host 106"
        )
        pdp11.send("/usr/bin/telnet - -h 106\r")
        event, _ = pdp11.expect_any(
            (rb"Connection open", rb"Host is Unavailable"), timeout=60
        )
        if event != 0:
            raise RuntimeError("guest TELNET reported Host is Unavailable")
        service_match = host106.expect(SERVICE_PATTERN, timeout=120)
        service_user = service_match.group(1).decode("ascii")
        pdp11.expect(rb"MIT Dynamic[\s\S]*?Modelling PDP-10", timeout=60)
        pdp11.expect(rb"TTY [0-9]+", timeout=60)
        pdp11.expect("Welcome to ITS!", timeout=60)
        pdp11.expect("Happy hacking!\r\n", timeout=30)

        manifest_values = read_manifest(manifest)
        transcript_path = results_dir / "interactive-telnet.jsonl"
        recorder = InteractiveTelnetRecorder(
            transcript_path,
            run_id=results_dir.name,
            started_at=manifest_values["started_utc"],
            repository_revision=manifest_values["repository.revision"],
            service_user=service_user,
            command_timeout_seconds=args.command_timeout,
            max_command_bytes=args.max_command_bytes,
            max_commands=args.max_commands,
            max_response_bytes=args.max_response_bytes,
        )

        connection_output = pdp11.output_from(pdp11_offset)
        banner = REMOTE_BANNER.search(connection_output)
        display.milestone(
            "READY", "TELNET", f"connected to ITS service job {service_user}"
        )
        print("\nSESSION READY")
        print("  Network UNIX 176 -> IMP 62 -> IMP 6 -> ITS 106")
        print(f"  ITS TELSER service job: {service_user}\n")
        if banner is not None:
            print(render_console_capture(banner.group(0)), end="")
        print("Type /help for local help or /quit to close cleanly.")

        try:
            session_reason = run_operator_session(
                pdp11,
                recorder,
                input_stream=sys.stdin,
                output_stream=sys.stdout,
                command_timeout=args.command_timeout,
                max_commands=args.max_commands,
                max_response_bytes=args.max_response_bytes,
            )
        except InterruptedError:
            recorder.complete(observed_at=utc_now(), reason="interrupted")
            transcript_terminal = True
            raise
        except (InteractiveSessionFailure, OSError, RuntimeError, TimeoutError):
            recorder.complete(observed_at=utc_now(), reason="failed")
            transcript_terminal = True
            raise
        else:
            recorder.complete(observed_at=utc_now(), reason=session_reason)
            transcript_terminal = True
        finally:
            recorder.close()

        display.milestone(
            "CHECK", "Evidence", "validating transcript and two-IMP traffic"
        )
        transcript = read_interactive_telnet_stream(transcript_path)
        if (
            not transcript.is_terminal
            or transcript.failed_commands
            or transcript.completed_commands < 1
        ):
            raise RuntimeError(
                "interactive TELNET transcript lacks a completed prompt-framed command"
            )

        pdp11_output = pdp11.output_from(pdp11_offset)
        its_output = host106.output_from(host106_offset)
        imp_end_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        imp6_output = imp6.debug_path.read_bytes()[
            imp_offsets["imp6"] : imp_end_offsets["imp6"]
        ]
        imp62_output = imp62.debug_path.read_bytes()[
            imp_offsets["imp62"] : imp_end_offsets["imp62"]
        ]
        failures = interactive_evidence_failures(
            pdp11_output,
            its_output,
            imp6_output,
            imp62_output,
            completed_commands=transcript.completed_commands,
            imp6_mi_device=imp6_mi_device,
            imp62_mi_device=imp62_mi_device,
        )
        for imp, modem_device in (
            (imp6, imp6_mi_device),
            (imp62, imp62_mi_device),
        ):
            latest = latest_watchdog(imp.debug_path)
            if not watchdog_devices_ready(
                latest, modem_device=modem_device, host_device="hi2"
            ):
                failures.append(f"{imp.name} did not remain host-link ready")
        if failures:
            raise RuntimeError("; ".join(failures))

        for name in ("imp6", "imp62"):
            append_manifest(
                manifest, f"application.offset.end.{name}", imp_end_offsets[name]
            )
        append_manifest(manifest, "path.interactive-telnet", transcript_path)
        append_manifest(
            manifest, "sha256.interactive-telnet", sha256(transcript_path)
        )
        append_manifest(
            manifest,
            "application.interactive-commands",
            transcript.completed_commands,
        )
        append_manifest(
            manifest, "application.prompt-framing", "its-ddt-star"
        )
        append_manifest(manifest, "application.client", "network-unix-telnet")
        append_manifest(manifest, "application.server", "TELSER")
        append_manifest(manifest, "application.service_user", service_user)
        append_manifest(
            manifest, "application.session-mode", "interactive-line-oriented"
        )

        evidence = (
            "connection_open=1\n"
            f"its_service_user={service_user}\n"
            "session_mode=interactive-line-oriented\n"
            "prompt_framing=its-ddt-star\n"
            f"interactive_commands_completed={transcript.completed_commands}\n"
            "imp6_interactive_traffic=1\n"
            "imp62_interactive_traffic=1\n"
            "correlated_inter_imp_traffic=both-directions\n"
        )
        (results_dir / "application-evidence.txt").write_text(
            evidence, encoding="ascii"
        )
        outcome = "passed"
        display.milestone(
            "READY",
            "Evidence",
            f"{transcript.completed_commands} command(s); traffic correlated both ways",
        )
        return 0
    finally:
        if recorder is not None and not transcript_terminal:
            try:
                recorder.complete(
                    observed_at=utc_now(),
                    reason="interrupted" if interrupted else "failed",
                )
            except (
                InteractiveTelnetStreamError,
                TerminalSessionStreamError,
                OSError,
            ):
                pass
            recorder.close()
        display.milestone(
            "STOP", "Simulators", "stopping owned PDP-11, KA10, and H316 processes"
        )
        stop_and_record(results_dir, hosts, imps, force=interrupted)
        (results_dir / "outcome.txt").write_text(outcome + "\n", encoding="ascii")
        display.milestone("DONE", "Cleanup", "all owned simulator processes stopped")
        if outcome == "passed":
            print(f"\nResult retained at {results_dir}", flush=True)
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except InterruptedError:
        print("Interactive TELNET session interrupted; cleanup completed.", file=sys.stderr)
        return 130
    except (
        InteractiveSessionFailure,
        InteractiveTelnetStreamError,
        TerminalSessionStreamError,
        OSError,
        RuntimeError,
        TimeoutError,
        ValueError,
    ):
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
