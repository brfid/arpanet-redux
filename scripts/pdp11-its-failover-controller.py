#!/usr/bin/env python3
"""Drive one same-session Network UNIX-to-ITS application-link failover."""

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


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.harness_config import create_host106_attach_config, validate_environment
from ncc.harness_imp import (
    latest_watchdog,
    wait_for_log_marker,
    watchdog_devices_ready,
    watchdog_reports_modem_dead,
)
from ncc.harness_manifest import append_manifest, read_manifest, sha256
from ncc.harness_process import ImpProcess, PtyProcess, ensure_process_alive, utc_now
from ncc.historical_terminal import (
    BootDisplay,
    network_unix_prompt_offset,
    operator_terminal_mode,
    run_character_terminal,
)
from ncc.message_journey import ObservationProvenance
from ncc.pdp11_its_harness import (
    DATE_PATTERN,
    FATAL_SESSION,
    SERVICE_PATTERN,
    TIME_PATTERN,
    UPTIME_PATTERN,
    application_evidence_failures,
    boot_pdp11,
    stop_and_record,
    wait_for_prompt,
)
from ncc.pdp11_its_failover_journey import (
    pdp11_its_failover_modem_devices,
    write_pdp11_its_failover_journey_stream,
)
from ncc.pdp11_its_journey import (
    pdp11_its_modem_devices,
    transaction_window_source,
    write_pdp11_its_journey_stream,
)
from ncc.shared_topology import shared_topology_from_mapping
from ncc.terminal_session import (
    DEFAULT_MAX_CHUNK_BYTES,
    DEFAULT_MAX_INPUT_BYTES,
    DEFAULT_MAX_OUTPUT_BYTES,
    TerminalSessionRecorder,
    TerminalSessionStreamError,
    read_terminal_session_stream,
)

_FATAL_POST_CUT_TRANSPORT = re.compile(
    rb"bind error|Can't open Datagram socket|UNRECOVERABLE I/O ERROR|"
    rb"tmxr_put_packet_ln\(\) failed|HARDWARE ERROR",
    re.IGNORECASE,
)
NETWORK_UNIX_HOST106_READY_PATTERN = rb"SKTRACE hh h=106 bytes=1 op=15"
NETWORK_UNIX_TELNET_BANNER = b"UNIX User Telnet -- Ver I.5"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h316", required=True, type=Path)
    parser.add_argument("--pdp10-ka", required=True, type=Path)
    parser.add_argument("--pdp11", required=True, type=Path)
    parser.add_argument("--mini-root", required=True, type=Path)
    parser.add_argument("--host106-work", required=True, type=Path)
    parser.add_argument("--pdp11-work", required=True, type=Path)
    parser.add_argument("--imp6-config", required=True, type=Path)
    parser.add_argument("--imp62-config", required=True, type=Path)
    parser.add_argument("--imp7-debug", required=True, type=Path)
    parser.add_argument("--host106-config", required=True, type=Path)
    parser.add_argument("--pdp11-config", required=True, type=Path)
    parser.add_argument("--topology", required=True, type=Path)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cut-request", required=True, type=Path)
    parser.add_argument("--cut-state", required=True, type=Path)
    parser.add_argument("--mode", choices=("automatic", "terminal"), default="automatic")
    parser.add_argument("--route-settle", type=float, default=60.0)
    parser.add_argument("--post-cut-settle", type=float, default=60.0)
    parser.add_argument("--daemon-settle", type=float, default=12.0)
    parser.add_argument("--ncp-ready-timeout", type=float, default=120.0)
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
    args = parser.parse_args()
    if (
        args.route_settle <= 0
        or args.post_cut_settle <= 0
        or args.daemon_settle <= 0
        or args.ncp_ready_timeout <= 0
        or args.max_terminal_input_bytes <= 0
        or args.max_terminal_output_bytes <= 0
        or args.max_terminal_chunk_bytes <= 0
    ):
        parser.error("settle durations must be positive")
    return args


def wait_for_network_unix_host106_ready(
    process: PtyProcess, timeout: float
) -> re.Match[bytes]:
    """Wait until Network UNIX consumes host 106's Reset Reply.

    The retained guest emits ``SKTRACE`` from the NCP daemon's host-host
    decoder. Opcode 15 is octal RRP; the preserved daemon handles it by
    marking the remote host alive before returning from that decoder.
    """

    return process.expect(NETWORK_UNIX_HOST106_READY_PATTERN, timeout=timeout)


def devices_ready(
    state: str | None,
    modem_devices: tuple[str, ...],
    *,
    host_device: str | None = None,
) -> bool:
    return all(
        watchdog_devices_ready(
            state,
            modem_device=device,
            host_device=host_device,
        )
        for device in modem_devices
    )


def wait_for_imp_devices_ready(
    imp: ImpProcess,
    modem_devices: tuple[str, ...],
    *,
    host_device: str | None = None,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        imp.ensure_alive()
        state = latest_watchdog(imp.debug_path) if imp.debug_path.exists() else None
        if devices_ready(state, modem_devices, host_device=host_device):
            return
        time.sleep(0.1)
    raise TimeoutError(
        f"{imp.name} did not report {', '.join(modem_devices)} ready; "
        f"latest watchdog state is {latest_watchdog(imp.debug_path)}"
    )


def wait_for_trace_devices_ready(
    path: Path,
    modem_devices: tuple[str, ...],
    *,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = latest_watchdog(path) if path.exists() else None
        if devices_ready(state, modem_devices):
            return
        time.sleep(0.1)
    state = latest_watchdog(path) if path.exists() else None
    raise TimeoutError(
        f"outer IMP trace did not report {', '.join(modem_devices)} ready; "
        f"latest watchdog state is {state}"
    )


def wait_for_post_cut_state(
    imp: ImpProcess,
    *,
    direct_device: str,
    alternate_device: str,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        imp.ensure_alive()
        state = latest_watchdog(imp.debug_path)
        direct_dead = not watchdog_devices_ready(
            state,
            modem_device=direct_device,
        )
        alternate_ready = watchdog_devices_ready(
            state,
            modem_device=alternate_device,
            host_device="hi2",
        )
        if direct_dead and alternate_ready:
            return
        time.sleep(0.1)
    raise TimeoutError(
        f"{imp.name} did not reach direct-dead/alternate-ready state; "
        f"latest watchdog state is {latest_watchdog(imp.debug_path)}"
    )


def wait_for_cut_state(path: Path, timeout: float = 10.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            if (
                value.get("version") != 1
                or value.get("kind") != "two-ended-udp-cut-state"
                or value.get("state") != "cut"
                or not isinstance(value.get("fault_started_at"), str)
            ):
                raise ValueError("relay cut acknowledgement is malformed")
            return value
        time.sleep(0.05)
    raise TimeoutError("relay did not acknowledge the requested application-link cut")


def post_cut_application_failures(
    pdp11_output: bytes,
    imp6_output: bytes,
    imp7_output: bytes,
    imp62_output: bytes,
    *,
    imp6_alternate_device: str,
    imp7_in_device: str,
    imp7_out_device: str,
    imp62_alternate_device: str,
) -> list[str]:
    failures: list[str] = []
    for label, pattern in (
        ("remote time", TIME_PATTERN),
        ("remote date", DATE_PATTERN),
        ("remote uptime", UPTIME_PATTERN),
    ):
        if re.search(pattern, pdp11_output, re.DOTALL) is None:
            failures.append(f"missing post-cut {label} evidence")
    if FATAL_SESSION.search(pdp11_output):
        failures.append("PDP-11 TELNET session closed or failed after the cut")
    for name, output, devices in (
        ("imp6", imp6_output, (imp6_alternate_device,)),
        ("imp7", imp7_output, (imp7_in_device, imp7_out_device)),
        ("imp62", imp62_output, (imp62_alternate_device,)),
    ):
        if _FATAL_POST_CUT_TRANSPORT.search(output):
            failures.append(f"{name} reported a fatal post-cut transport condition")
        for device in devices:
            if watchdog_reports_modem_dead(output, device):
                failures.append(f"{name} reported alternate device {device} dead")
    for name, output in (("imp6", imp6_output), ("imp62", imp62_output)):
        for marker in (b"HI2 MSG: message received", b"HI2 MSG: message sent"):
            if marker not in output:
                failures.append(
                    f"{name} lacks post-cut {marker.decode('ascii')} evidence"
                )
    return failures


def interactive_pre_cut_failures(
    pdp11_output: bytes,
    its_output: bytes,
    imp6_output: bytes,
    imp62_output: bytes,
    *,
    imp6_direct_device: str,
    imp62_direct_device: str,
) -> list[str]:
    """Require one historical-client transaction before accepting a cut key."""

    failures = application_evidence_failures(
        pdp11_output,
        its_output,
        imp6_output,
        imp62_output,
        imp6_mi_device=imp6_direct_device,
        imp62_mi_device=imp62_direct_device,
    )
    if NETWORK_UNIX_TELNET_BANNER not in pdp11_output:
        failures.append("missing Network UNIX TELNET command interface")
    if pdp11_output.count(b"Connection open") != 1:
        failures.append("pre-cut terminal must contain exactly one open connection")
    return failures


def interactive_post_cut_failures(
    complete_pdp11_output: bytes,
    post_cut_pdp11_output: bytes,
    imp6_output: bytes,
    imp7_output: bytes,
    imp62_output: bytes,
    *,
    imp6_alternate_device: str,
    imp7_in_device: str,
    imp7_out_device: str,
    imp62_alternate_device: str,
) -> list[str]:
    """Require alternate-route service without a second TELNET connection."""

    failures = post_cut_application_failures(
        post_cut_pdp11_output,
        imp6_output,
        imp7_output,
        imp62_output,
        imp6_alternate_device=imp6_alternate_device,
        imp7_in_device=imp7_in_device,
        imp7_out_device=imp7_out_device,
        imp62_alternate_device=imp62_alternate_device,
    )
    if complete_pdp11_output.count(b"Connection open") != 1:
        failures.append("interactive failover did not retain exactly one TELNET connection")
    return failures


def _window(
    *,
    source_id: str,
    path: Path,
    start: int,
    end: int,
    content: bytes,
):
    return transaction_window_source(
        source_id=source_id,
        artifact=path.name,
        start_offset=start,
        end_offset=end,
        content=content,
    )


def run_interactive_failover_terminal(
    *,
    args: argparse.Namespace,
    results_dir: Path,
    manifest: Path,
    topology_document: dict[str, object],
    pdp11: PtyProcess,
    host106: PtyProcess,
    imp6: ImpProcess,
    imp62: ImpProcess,
    imp7_debug: Path,
    imp6_direct: str,
    imp62_direct: str,
    imp6_alternate: str,
    imp7_in: str,
    imp7_out: str,
    imp62_alternate: str,
    pre_offsets: dict[str, int],
    pre_pdp11_offset: int,
    pre_host106_offset: int,
    cut_request: Path,
    cut_state_path: Path,
    display: BootDisplay,
) -> None:
    """Run and validate one human-operated same-session link failover."""

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
        failover=True,
    )
    terminal_complete = False
    cut: dict[str, object] = {}
    post_paths = {
        "imp6": imp6.debug_path,
        "imp7": imp7_debug,
        "imp62": imp62.debug_path,
    }

    def request_cut(observed_at: str) -> bytes:
        if cut:
            recorder.control(
                "application-link-cut-already-requested",
                observed_at=observed_at,
            )
            return b"[local] The direct link is already cut.\n"

        pre_end = {
            "imp6": imp6.debug_path.stat().st_size,
            "imp62": imp62.debug_path.stat().st_size,
        }
        pre_traces = {
            "imp6": imp6.debug_path.read_bytes()[
                pre_offsets["imp6"] : pre_end["imp6"]
            ],
            "imp62": imp62.debug_path.read_bytes()[
                pre_offsets["imp62"] : pre_end["imp62"]
            ],
        }
        pdp11_output = pdp11.output_from(pre_pdp11_offset)
        its_output = host106.output_from(pre_host106_offset)
        failures = interactive_pre_cut_failures(
            pdp11_output,
            its_output,
            pre_traces["imp6"],
            pre_traces["imp62"],
            imp6_direct_device=imp6_direct,
            imp62_direct_device=imp62_direct,
        )
        if failures:
            recorder.control(
                "application-link-cut-not-ready",
                observed_at=observed_at,
            )
            detail = "; ".join(failures[:3]).encode("ascii", "replace")
            return b"[local] Cut not made: " + detail + b".\n"

        service_match = re.search(SERVICE_PATTERN, its_output)
        assert service_match is not None
        recorder.control(
            "application-link-cut-requested",
            observed_at=observed_at,
        )
        with cut_request.open("x", encoding="ascii") as stream:
            stream.write("cut application link\n")
        cut_state = wait_for_cut_state(cut_state_path)
        append_manifest(manifest, "application.cut-requested", 1)
        append_manifest(
            manifest,
            "application.fault-started-at",
            str(cut_state["fault_started_at"]),
        )
        wait_for_post_cut_state(
            imp6,
            direct_device=imp6_direct,
            alternate_device=imp6_alternate,
            timeout=120,
        )
        wait_for_post_cut_state(
            imp62,
            direct_device=imp62_direct,
            alternate_device=imp62_alternate,
            timeout=120,
        )
        time.sleep(args.post_cut_settle)
        wait_for_trace_devices_ready(
            imp7_debug,
            (imp7_in, imp7_out),
            timeout=10,
        )
        for host in (pdp11, host106):
            ensure_process_alive(host)
        cut.update(
            {
                "state": cut_state,
                "service_user": service_match.group(1).decode("ascii"),
                "pre_end": pre_end,
                "pre_traces": pre_traces,
                "post_offsets": {
                    name: path.stat().st_size for name, path in post_paths.items()
                },
                "post_pdp11_offset": pdp11.position(),
            }
        )
        return (
            b"[local] Direct IMP 62 / IMP 6 link cut; "
            b"the alternate route through IMP 7 is ready.\n"
            b"[local] Enter one :TIME, wait for its complete response, "
            b"then press Control-] to finish.\n"
        )

    terminal_start_offset = network_unix_prompt_offset(pdp11.output_from(0))
    display.milestone("READY", "Host terminal", "Network UNIX root shell on host 176")
    print("\nINTERACTIVE FAILOVER TERMINAL READY")
    print("  Start the preserved client:  /usr/bin/telnet")
    print("  At its '* ' prompt:          connect - -h 106")
    print("  Before cutting:              enter :TIME and wait for the response")
    print("  Cut the direct link:         press Control-^")
    print("  After alternate-route ready: enter :TIME and wait for the response")
    print("  Finish and validate:         press Control-]\n")
    sys.stdout.flush()
    input_fd = sys.stdin.fileno()
    output_fd = sys.stdout.fileno()
    if not os.isatty(output_fd):
        raise RuntimeError("interactive failover terminal requires output attached to a TTY")
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
                on_cut_request=request_cut,
            )
    except InterruptedError:
        recorder.complete(observed_at=utc_now(), reason="interrupted")
        terminal_complete = True
        raise
    except (OSError, RuntimeError, TerminalSessionStreamError):
        recorder.complete(observed_at=utc_now(), reason="failed")
        terminal_complete = True
        raise
    else:
        recorder.complete(observed_at=utc_now(), reason=session_reason)
        terminal_complete = True
    finally:
        if not terminal_complete:
            try:
                recorder.complete(observed_at=utc_now(), reason="failed")
            except (OSError, TerminalSessionStreamError):
                pass
        recorder.close()

    if session_reason not in {"operator-exit", "input-eof"}:
        raise RuntimeError(f"interactive failover terminal stopped because of {session_reason}")
    if not cut:
        raise RuntimeError("operator exited before an application-link cut was accepted")

    display.milestone("CHECK", "Evidence", "validating same-session alternate-route use")
    transcript = read_terminal_session_stream(transcript_path)
    cut_controls = sum(
        count
        for control, count in transcript.controls
        if control == "application-link-cut-requested"
    )
    if (
        not transcript.is_terminal
        or transcript.end_reason != session_reason
        or transcript.header["schema_version"] != 2
        or cut_controls != 1
    ):
        raise RuntimeError("interactive failover terminal transcript is incomplete")

    post_offsets = cut["post_offsets"]
    assert isinstance(post_offsets, dict)
    post_end = {name: path.stat().st_size for name, path in post_paths.items()}
    post_traces = {
        name: path.read_bytes()[int(post_offsets[name]) : post_end[name]]
        for name, path in post_paths.items()
    }
    post_pdp11_offset = int(cut["post_pdp11_offset"])
    failures = interactive_post_cut_failures(
        pdp11.output_from(pre_pdp11_offset),
        pdp11.output_from(post_pdp11_offset),
        post_traces["imp6"],
        post_traces["imp7"],
        post_traces["imp62"],
        imp6_alternate_device=imp6_alternate,
        imp7_in_device=imp7_in,
        imp7_out_device=imp7_out,
        imp62_alternate_device=imp62_alternate,
    )
    for host in (pdp11, host106):
        ensure_process_alive(host)
    if failures:
        raise RuntimeError("; ".join(failures))

    provenance = (
        ObservationProvenance(
            "source:controller",
            "pdp11-its-failover-controller",
            manifest_values["repository.revision"],
        ),
        ObservationProvenance(
            "source:h316",
            "h316-simh",
            manifest_values["source.h316-simh.revision"],
        ),
    )
    pre_traces = cut["pre_traces"]
    pre_end = cut["pre_end"]
    assert isinstance(pre_traces, dict) and isinstance(pre_end, dict)
    pre_journey_path = results_dir / "pre-cut-message-journey.jsonl"
    pre_journey = write_pdp11_its_journey_stream(
        pre_journey_path,
        run_id=results_dir.name,
        started_at=manifest_values["started_utc"],
        provenance=provenance,
        topology_document=topology_document,
        transaction_window=tuple(
            _window(
                source_id=f"source:{name}:pre-cut",
                path=path,
                start=pre_offsets[name],
                end=int(pre_end[name]),
                content=pre_traces[name],
            )
            for name, path in (("imp6", imp6.debug_path), ("imp62", imp62.debug_path))
        ),
        imp6_trace=pre_traces["imp6"],
        imp62_trace=pre_traces["imp62"],
        h316_revision=manifest_values["source.h316-simh.revision"],
    )
    journey_path = results_dir / "message-journey.jsonl"
    journey = write_pdp11_its_failover_journey_stream(
        journey_path,
        run_id=results_dir.name,
        started_at=manifest_values["started_utc"],
        provenance=provenance,
        topology_document=topology_document,
        transaction_window=tuple(
            _window(
                source_id=f"source:{name}:post-cut",
                path=post_paths[name],
                start=int(post_offsets[name]),
                end=post_end[name],
                content=post_traces[name],
            )
            for name in ("imp6", "imp7", "imp62")
        ),
        imp6_trace=post_traces["imp6"],
        imp7_trace=post_traces["imp7"],
        imp62_trace=post_traces["imp62"],
        h316_revision=manifest_values["source.h316-simh.revision"],
    )
    if len(pre_journey.observations) != 10 or len(journey.observations) != 14:
        raise RuntimeError("interactive failover journeys have unexpected observation counts")

    for label, path in (
        ("terminal-session", transcript_path),
        ("pre-cut-message-journey", pre_journey_path),
        ("message-journey", journey_path),
    ):
        append_manifest(manifest, f"path.{label}", path)
        append_manifest(manifest, f"sha256.{label}", sha256(path))
    for name in ("imp6", "imp7", "imp62"):
        append_manifest(manifest, f"application.offset.post-cut.{name}", post_offsets[name])
        append_manifest(manifest, f"application.offset.end.{name}", post_end[name])
    append_manifest(manifest, "terminal.input-bytes", len(transcript.input_bytes))
    append_manifest(manifest, "terminal.output-bytes", len(transcript.output_bytes))
    append_manifest(manifest, "terminal.profile", "seven-bit-safe-teletype")
    append_manifest(manifest, "terminal.application-link-cut", "control-caret")
    append_manifest(manifest, "application.client", "network-unix-telnet")
    append_manifest(manifest, "application.server", "TELSER")
    append_manifest(manifest, "application.service_user", cut["service_user"])
    append_manifest(manifest, "application.session-mode", "interactive-failover")
    append_manifest(manifest, "application.session-survived-cut", 1)
    append_manifest(manifest, "message-journey.observations", len(journey.observations))
    append_manifest(manifest, "message-journey.state", journey.diagnosis.state.value)
    append_manifest(
        manifest,
        "message-journey.first-boundary",
        journey.diagnosis.first_boundary_id or "none",
    )

    evidence = (
        "connection_open=1\n"
        f"its_service_user={cut['service_user']}\n"
        "session_mode=interactive-failover\n"
        "terminal_profile=seven-bit-safe-teletype\n"
        "operator_cut_control=control-caret\n"
        "pre_cut_remote_time=structured\n"
        "cut_acknowledged=1\n"
        "session_survived_cut=1\n"
        "post_cut_remote_time=structured\n"
        f"pre_cut_message_journey_observations={len(pre_journey.observations)}\n"
        f"message_journey_observations={len(journey.observations)}\n"
        f"message_journey_state={journey.diagnosis.state.value}\n"
        f"message_journey_first_boundary={journey.diagnosis.first_boundary_id}\n"
    )
    (results_dir / "application-evidence.txt").write_text(evidence, encoding="ascii")
    display.milestone(
        "READY",
        "Evidence",
        "one guest session crossed the cut and used the IMP 7 route",
    )


def run(args: argparse.Namespace) -> int:
    validate_environment()
    results_dir = args.results_dir.resolve()
    manifest = args.manifest.resolve()
    topology_path = args.topology.resolve()
    imp7_debug = args.imp7_debug.resolve()
    cut_request = args.cut_request.resolve()
    cut_state_path = args.cut_state.resolve()
    if cut_request.exists() or cut_state_path.exists():
        raise ValueError("application-link cut control files must not pre-exist")
    topology_document = json.loads(topology_path.read_text(encoding="utf-8"))
    shared_topology = shared_topology_from_mapping(topology_document)
    imp62_direct, imp6_direct = pdp11_its_modem_devices(shared_topology)
    alternate = pdp11_its_failover_modem_devices(shared_topology)
    imp62_alternate, imp7_in = alternate.imp62_to_imp7
    imp7_out, imp6_alternate = alternate.imp7_to_imp6
    if imp62_direct == imp62_alternate or imp6_direct == imp6_alternate:
        raise ValueError(
            "direct and alternate routes must use distinct endpoint devices"
        )

    attach_config = results_dir / "host106-attach-only.simh"
    create_host106_attach_config(args.host106_config.resolve(), attach_config)
    append_manifest(
        manifest,
        "sha256.host106-attach-config",
        sha256(attach_config),
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
    display = BootDisplay(sys.stdout) if args.mode == "terminal" else None

    def milestone(state: str, component: str, detail: str) -> None:
        if display is not None:
            display.milestone(state, component, detail)

    def interrupt(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        if interrupted:
            return
        interrupted = True
        raise InterruptedError("controller interrupted")

    old_term = signal.signal(signal.SIGTERM, interrupt)
    old_int = signal.signal(signal.SIGINT, interrupt)
    try:
        milestone("START", "IMP backbone", "launching IMP 62 and IMP 6")
        imp6.launch()
        imp62.launch()
        wait_for_log_marker(imp6, "listening on port", 30)
        wait_for_log_marker(imp62, "listening on port", 30)
        wait_for_trace_devices_ready(
            imp7_debug,
            (imp7_in, imp7_out),
            timeout=90,
        )
        milestone("READY", "IMP backbone", "four-IMP transports listening")

        milestone("START", "Historical hosts", "launching PDP-11 and KA10")
        host106.launch(state="PROMPT")
        pdp11.launch(state="PROMPT")
        host106.expect("sim> ", timeout=60)
        pdp11.expect("sim> ", timeout=60)
        wait_for_imp_devices_ready(
            imp6,
            (imp6_direct, imp6_alternate),
            timeout=90,
        )
        wait_for_imp_devices_ready(
            imp62,
            (imp62_direct, imp62_alternate),
            timeout=90,
        )
        route_settle_deadline = time.monotonic() + args.route_settle
        milestone("READY", "Simulator consoles", "PDP-11 and KA10 attached")

        milestone("BOOT", "Historical hosts", "starting ITS and Network UNIX")
        host106.send(
            'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\r'
        )
        host106.expect("sim> ", timeout=30)
        host106.send("boot ptr\r")
        host106.state = "BOOTING"
        host106.mark_running_after_banner()
        host106.enter_ddt_and_prove_local_time()
        boot_pdp11(pdp11)
        pdp11.send("/usr/net/etc/smalldaemon &\r")
        wait_for_prompt(pdp11, timeout=15)
        time.sleep(args.daemon_settle)
        wait_for_network_unix_host106_ready(pdp11, args.ncp_ready_timeout)
        append_manifest(
            manifest,
            "application.network-unix-host106-ready",
            "host-host-rrp-consumed",
        )
        milestone("READY", "Historical hosts", "ITS, Network UNIX, and NCP ready")

        milestone("WAIT", "ARPANET routes", "settling direct and alternate paths")
        wait_for_imp_devices_ready(
            imp6,
            (imp6_direct, imp6_alternate),
            host_device="hi2",
            timeout=120,
        )
        wait_for_imp_devices_ready(
            imp62,
            (imp62_direct, imp62_alternate),
            host_device="hi2",
            timeout=120,
        )
        remaining = route_settle_deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        for host in hosts:
            ensure_process_alive(host)
            if host.state != "RUNNING":
                raise RuntimeError(f"{host.name} is not RUNNING before TELNET")
        milestone("READY", "ARPANET routes", "direct path up; IMP 7 standby ready")

        pre_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        pre_pdp11_offset = pdp11.position()
        pre_host106_offset = host106.position()
        if args.mode == "terminal":
            assert display is not None
            run_interactive_failover_terminal(
                args=args,
                results_dir=results_dir,
                manifest=manifest,
                topology_document=topology_document,
                pdp11=pdp11,
                host106=host106,
                imp6=imp6,
                imp62=imp62,
                imp7_debug=imp7_debug,
                imp6_direct=imp6_direct,
                imp62_direct=imp62_direct,
                imp6_alternate=imp6_alternate,
                imp7_in=imp7_in,
                imp7_out=imp7_out,
                imp62_alternate=imp62_alternate,
                pre_offsets=pre_offsets,
                pre_pdp11_offset=pre_pdp11_offset,
                pre_host106_offset=pre_host106_offset,
                cut_request=cut_request,
                cut_state_path=cut_state_path,
                display=display,
            )
            outcome = "passed"
            print(
                "PASS: the human-operated Network UNIX TELNET session "
                f"survived the direct-link cut through IMP 7: {results_dir}"
            )
            return 0

        pdp11.send("/usr/bin/telnet - -h 106\r")
        event, _ = pdp11.expect_any(
            (rb"Connection open", rb"Host is Unavailable"),
            timeout=60,
        )
        if event != 0:
            raise RuntimeError("guest TELNET reported Host is Unavailable")
        service_match = host106.expect(SERVICE_PATTERN, timeout=120)
        service_user = service_match.group(1).decode("ascii")
        pdp11.expect(rb"MIT Dynamic[\s\S]*?Modelling PDP-10", timeout=60)
        pdp11.expect(rb"TTY [0-9]+", timeout=60)
        pdp11.expect("Welcome to ITS!", timeout=60)
        pdp11.send(":time\r")
        pdp11.expect(TIME_PATTERN, timeout=60)
        pdp11.expect(DATE_PATTERN, timeout=30)
        pdp11.expect(UPTIME_PATTERN, timeout=30)
        time.sleep(3)

        pre_end = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        pre_imp6 = imp6.debug_path.read_bytes()[pre_offsets["imp6"] : pre_end["imp6"]]
        pre_imp62 = imp62.debug_path.read_bytes()[
            pre_offsets["imp62"] : pre_end["imp62"]
        ]
        pre_failures = application_evidence_failures(
            pdp11.output_from(pre_pdp11_offset),
            host106.output_from(pre_host106_offset),
            pre_imp6,
            pre_imp62,
            imp6_mi_device=imp6_direct,
            imp62_mi_device=imp62_direct,
        )
        if pre_failures:
            raise RuntimeError("pre-cut baseline failed: " + "; ".join(pre_failures))

        manifest_values = read_manifest(manifest)
        provenance = (
            ObservationProvenance(
                "source:controller",
                "pdp11-its-failover-controller",
                manifest_values["repository.revision"],
            ),
            ObservationProvenance(
                "source:h316",
                "h316-simh",
                manifest_values["source.h316-simh.revision"],
            ),
        )
        pre_journey_path = results_dir / "pre-cut-message-journey.jsonl"
        pre_journey = write_pdp11_its_journey_stream(
            pre_journey_path,
            run_id=results_dir.name,
            started_at=manifest_values["started_utc"],
            provenance=provenance,
            topology_document=topology_document,
            transaction_window=(
                _window(
                    source_id="source:imp6:pre-cut",
                    path=imp6.debug_path,
                    start=pre_offsets["imp6"],
                    end=pre_end["imp6"],
                    content=pre_imp6,
                ),
                _window(
                    source_id="source:imp62:pre-cut",
                    path=imp62.debug_path,
                    start=pre_offsets["imp62"],
                    end=pre_end["imp62"],
                    content=pre_imp62,
                ),
            ),
            imp6_trace=pre_imp6,
            imp62_trace=pre_imp62,
            h316_revision=manifest_values["source.h316-simh.revision"],
        )
        if len(pre_journey.observations) != 10:
            raise RuntimeError("pre-cut direct journey did not retain ten observations")

        cut_request.write_text("cut application link\n", encoding="ascii")
        cut_state = wait_for_cut_state(cut_state_path)
        append_manifest(manifest, "application.cut-requested", 1)
        append_manifest(
            manifest,
            "application.fault-started-at",
            str(cut_state["fault_started_at"]),
        )
        wait_for_post_cut_state(
            imp6,
            direct_device=imp6_direct,
            alternate_device=imp6_alternate,
            timeout=120,
        )
        wait_for_post_cut_state(
            imp62,
            direct_device=imp62_direct,
            alternate_device=imp62_alternate,
            timeout=120,
        )
        time.sleep(args.post_cut_settle)
        wait_for_trace_devices_ready(
            imp7_debug,
            (imp7_in, imp7_out),
            timeout=10,
        )

        post_paths = {
            "imp6": imp6.debug_path,
            "imp7": imp7_debug,
            "imp62": imp62.debug_path,
        }
        post_offsets = {name: path.stat().st_size for name, path in post_paths.items()}
        post_pdp11_offset = pdp11.position()
        pdp11.send(":time\r")
        pdp11.expect(TIME_PATTERN, timeout=90)
        pdp11.expect(DATE_PATTERN, timeout=30)
        pdp11.expect(UPTIME_PATTERN, timeout=30)
        time.sleep(3)
        for host in hosts:
            ensure_process_alive(host)
        post_end = {name: path.stat().st_size for name, path in post_paths.items()}
        post_traces = {
            name: path.read_bytes()[post_offsets[name] : post_end[name]]
            for name, path in post_paths.items()
        }
        post_failures = post_cut_application_failures(
            pdp11.output_from(post_pdp11_offset),
            post_traces["imp6"],
            post_traces["imp7"],
            post_traces["imp62"],
            imp6_alternate_device=imp6_alternate,
            imp7_in_device=imp7_in,
            imp7_out_device=imp7_out,
            imp62_alternate_device=imp62_alternate,
        )
        if post_failures:
            raise RuntimeError("; ".join(post_failures))

        journey_path = results_dir / "message-journey.jsonl"
        journey = write_pdp11_its_failover_journey_stream(
            journey_path,
            run_id=results_dir.name,
            started_at=manifest_values["started_utc"],
            provenance=provenance,
            topology_document=topology_document,
            transaction_window=tuple(
                _window(
                    source_id=f"source:{name}:post-cut",
                    path=post_paths[name],
                    start=post_offsets[name],
                    end=post_end[name],
                    content=post_traces[name],
                )
                for name in ("imp6", "imp7", "imp62")
            ),
            imp6_trace=post_traces["imp6"],
            imp7_trace=post_traces["imp7"],
            imp62_trace=post_traces["imp62"],
            h316_revision=manifest_values["source.h316-simh.revision"],
        )
        for label, path in (
            ("pre-cut-message-journey", pre_journey_path),
            ("message-journey", journey_path),
        ):
            append_manifest(manifest, f"path.{label}", path)
            append_manifest(manifest, f"sha256.{label}", sha256(path))
        append_manifest(
            manifest,
            "message-journey.observations",
            len(journey.observations),
        )
        append_manifest(
            manifest,
            "message-journey.state",
            journey.diagnosis.state.value,
        )
        append_manifest(
            manifest,
            "message-journey.first-boundary",
            journey.diagnosis.first_boundary_id or "none",
        )

        evidence = (
            "connection_open=1\n"
            f"its_service_user={service_user}\n"
            "pre_cut_remote_time=structured\n"
            "cut_acknowledged=1\n"
            "session_survived_cut=1\n"
            "post_cut_remote_time=structured\n"
            f"pre_cut_message_journey_observations={len(pre_journey.observations)}\n"
            f"message_journey_observations={len(journey.observations)}\n"
            f"message_journey_state={journey.diagnosis.state.value}\n"
            f"message_journey_first_boundary={journey.diagnosis.first_boundary_id}\n"
        )
        (results_dir / "application-evidence.txt").write_text(
            evidence,
            encoding="ascii",
        )
        append_manifest(manifest, "application.client", "network-unix-telnet")
        append_manifest(manifest, "application.server", "TELSER")
        append_manifest(manifest, "application.service_user", service_user)
        append_manifest(manifest, "application.session-survived-cut", 1)
        outcome = "passed"
        print(
            "PASS: the Network UNIX TELNET session reached ITS after the "
            f"application-link cut through IMP 7: {results_dir}"
        )
        return 0
    finally:
        stop_and_record(results_dir, hosts, imps, force=interrupted)
        (results_dir / "outcome.txt").write_text(outcome + "\n", encoding="ascii")
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except InterruptedError:
        print("Interactive failover interrupted; cleanup completed.", file=sys.stderr)
        return 130
    except (
        OSError,
        RuntimeError,
        TerminalSessionStreamError,
        TimeoutError,
        ValueError,
    ):
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
