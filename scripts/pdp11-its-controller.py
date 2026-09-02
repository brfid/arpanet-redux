#!/usr/bin/env python3
"""Drive the formal Network UNIX PDP-11 to ITS TELNET acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import signal
import time
import traceback


SHARED_PATH = Path(__file__).with_name("two-its-controller.py")
SHARED_SPEC = importlib.util.spec_from_file_location("two_its_controller", SHARED_PATH)
assert SHARED_SPEC is not None and SHARED_SPEC.loader is not None
SHARED = importlib.util.module_from_spec(SHARED_SPEC)
SHARED_SPEC.loader.exec_module(SHARED)

from ncc.message_journey import ObservationProvenance
from ncc.pdp11_its_journey import (
    pdp11_its_modem_devices,
    transaction_window_source,
    write_pdp11_its_journey_stream,
)
from ncc.shared_topology import shared_topology_from_mapping

PORT_VARIABLES = SHARED.PORT_VARIABLES
PtyProcess = SHARED.PtyProcess
ImpProcess = SHARED.ImpProcess

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
    parser.add_argument("--route-settle", type=float, default=60.0)
    parser.add_argument("--daemon-settle", type=float, default=12.0)
    return parser.parse_args()


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
        if SHARED.watchdog_reports_modem_dead(output, modem_device):
            failures.append(f"{name} reported a post-probe modem-line-dead transition")

    imp6_mi = SHARED.mi_link_messages_from_bytes(
        imp6_output, device=imp6_mi_device
    )
    imp62_mi = SHARED.mi_link_messages_from_bytes(
        imp62_output, device=imp62_mi_device
    )
    forward = SHARED.significant(imp6_mi[b"sent"]) & SHARED.significant(
        imp62_mi[b"received"]
    )
    returned = SHARED.significant(imp62_mi[b"sent"]) & SHARED.significant(
        imp6_mi[b"received"]
    )
    if not forward:
        failures.append("missing correlated post-probe IMP 6 to IMP 62 traffic")
    if not returned:
        failures.append("missing correlated post-probe IMP 62 to IMP 6 traffic")
    return failures


def ensure_process_alive(process: PtyProcess) -> None:
    if process.process is None or process.process.poll() is not None:
        raise RuntimeError(f"{process.name} exited early")


def read_manifest(path: Path) -> dict[str, str]:
    """Read the controller's own line-oriented run manifest fail closed."""

    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "=" not in line:
            raise ValueError(f"manifest line {number} has no '=' separator")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"manifest line {number} has an invalid or duplicate key")
        values[key] = value
    return values


def wait_for_prompt(process: PtyProcess, timeout: float = 30) -> None:
    process.expect(rb"\r\n# ?", timeout=timeout)


def create_host106_observation_config(
    source: Path, destination: Path, trace_path: Path
) -> None:
    """Create the normal attach-only config with observation-only IMP tracing."""

    SHARED.create_host106_attach_config(source, destination)
    with destination.open("a", encoding="ascii") as stream:
        stream.write(f"set debug {trace_path.resolve()}\nset imp debug=ASSEMBLY\n")


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
    SHARED.stop_all(hosts, imps, force=force)
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
        raise RuntimeError("owned simulator processes survived cleanup: " + ", ".join(survivors))


def run(args: argparse.Namespace) -> int:
    SHARED.validate_environment()
    results_dir = args.results_dir.resolve()
    manifest = args.manifest.resolve()
    topology_path = args.topology.resolve()
    topology_document = json.loads(topology_path.read_text(encoding="utf-8"))
    shared_topology = shared_topology_from_mapping(topology_document)
    imp62_mi_device, imp6_mi_device = pdp11_its_modem_devices(shared_topology)
    attach_config = results_dir / "host106-attach-only.simh"
    host106_trace_path = results_dir / "host106.imp-debug.log"
    create_host106_observation_config(
        args.host106_config.resolve(), attach_config, host106_trace_path
    )
    SHARED.append_manifest(manifest, "sha256.host106-attach-config", SHARED.sha256(attach_config))
    SHARED.append_manifest(manifest, "path.host106-attach-config", attach_config)
    SHARED.append_manifest(manifest, "path.host106-imp-debug", host106_trace_path)

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
        imp62.launch()
        SHARED.wait_for_log_marker(imp6, "listening on port", 30)
        SHARED.wait_for_log_marker(imp62, "listening on port", 30)

        host106.launch(state="PROMPT")
        pdp11.launch(state="PROMPT")
        host106.expect("sim> ", timeout=60)
        pdp11.expect("sim> ", timeout=60)

        imp6_modem_up, _ = SHARED.wait_for_watchdog_devices_ready(
            imp6, modem_device=imp6_mi_device, timeout=60
        )
        imp62_modem_up, _ = SHARED.wait_for_watchdog_devices_ready(
            imp62, modem_device=imp62_mi_device, timeout=60
        )
        route_settle_deadline = max(imp6_modem_up, imp62_modem_up) + args.route_settle

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

        SHARED.wait_for_watchdog_devices_ready(
            imp6,
            modem_device=imp6_mi_device,
            host_device="hi2",
            timeout=120,
        )
        SHARED.wait_for_watchdog_devices_ready(
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
            latest = SHARED.latest_watchdog(imp.debug_path)
            if not SHARED.watchdog_devices_ready(
                latest, modem_device=modem_device, host_device="hi2"
            ):
                raise RuntimeError(
                    f"{imp.name} selected modem/host path is not ready: {latest}"
                )
        for host in hosts:
            ensure_process_alive(host)
            if host.state != "RUNNING":
                raise RuntimeError(f"{host.name} is not RUNNING before TELNET")

        imp_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        if not host106_trace_path.is_file():
            raise RuntimeError("KA10 IMP observation trace was not created")
        host106_trace_offset = host106_trace_path.stat().st_size
        pdp11_offset = pdp11.position()
        host106_offset = host106.position()
        for name, offset in (
            ("imp6", imp_offsets["imp6"]),
            ("imp62", imp_offsets["imp62"]),
            ("host106-imp", host106_trace_offset),
            ("pdp11-console", pdp11_offset),
            ("host106-console", host106_offset),
        ):
            SHARED.append_manifest(manifest, f"application.offset.{name}", offset)

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
        pdp11.send(":time\r")
        pdp11.expect(TIME_PATTERN, timeout=60)
        pdp11.expect(DATE_PATTERN, timeout=30)
        pdp11.expect(UPTIME_PATTERN, timeout=30)
        time.sleep(3)

        pdp11_output = pdp11.output_from(pdp11_offset)
        its_output = host106.output_from(host106_offset)
        imp_end_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        host106_trace_end_offset = host106_trace_path.stat().st_size
        imp6_output = imp6.debug_path.read_bytes()[
            imp_offsets["imp6"] : imp_end_offsets["imp6"]
        ]
        imp62_output = imp62.debug_path.read_bytes()[
            imp_offsets["imp62"] : imp_end_offsets["imp62"]
        ]
        host106_trace = host106_trace_path.read_bytes()[
            host106_trace_offset:host106_trace_end_offset
        ]
        failures = application_evidence_failures(
            pdp11_output,
            its_output,
            imp6_output,
            imp62_output,
            imp6_mi_device=imp6_mi_device,
            imp62_mi_device=imp62_mi_device,
        )
        for imp, modem_device in (
            (imp6, imp6_mi_device),
            (imp62, imp62_mi_device),
        ):
            latest = SHARED.latest_watchdog(imp.debug_path)
            if not SHARED.watchdog_devices_ready(
                latest, modem_device=modem_device, host_device="hi2"
            ):
                failures.append(f"{imp.name} did not remain host-link ready")
        if failures:
            raise RuntimeError("; ".join(failures))

        manifest_values = read_manifest(manifest)
        journey_path = results_dir / "message-journey.jsonl"
        window = (
            transaction_window_source(
                source_id="source:imp6",
                artifact=imp6.debug_path.name,
                start_offset=imp_offsets["imp6"],
                end_offset=imp_end_offsets["imp6"],
                content=imp6_output,
            ),
            transaction_window_source(
                source_id="source:imp62",
                artifact=imp62.debug_path.name,
                start_offset=imp_offsets["imp62"],
                end_offset=imp_end_offsets["imp62"],
                content=imp62_output,
            ),
            transaction_window_source(
                source_id="source:host106-imp",
                artifact=host106_trace_path.name,
                start_offset=host106_trace_offset,
                end_offset=host106_trace_end_offset,
                content=host106_trace,
            ),
        )
        journey = write_pdp11_its_journey_stream(
            journey_path,
            run_id=results_dir.name,
            started_at=manifest_values["started_utc"],
            provenance=(
                ObservationProvenance(
                    "source:controller",
                    "formal-pdp11-its-controller",
                    manifest_values["repository.revision"],
                ),
                ObservationProvenance(
                    "source:h316",
                    "h316-simh",
                    manifest_values["source.h316-simh.revision"],
                ),
            ),
            topology_document=topology_document,
            transaction_window=window,
            imp6_trace=imp6_output,
            imp62_trace=imp62_output,
            h316_revision=manifest_values["source.h316-simh.revision"],
        )
        for name in ("imp6", "imp62"):
            SHARED.append_manifest(
                manifest,
                f"application.offset.end.{name}",
                imp_end_offsets[name],
            )
        SHARED.append_manifest(
            manifest,
            "application.offset.end.host106-imp",
            host106_trace_end_offset,
        )
        SHARED.append_manifest(manifest, "path.message-journey", journey_path)
        SHARED.append_manifest(
            manifest, "sha256.message-journey", SHARED.sha256(journey_path)
        )
        SHARED.append_manifest(
            manifest, "message-journey.observations", len(journey.observations)
        )
        SHARED.append_manifest(
            manifest, "message-journey.state", journey.diagnosis.state.value
        )
        SHARED.append_manifest(
            manifest,
            "message-journey.first-boundary",
            journey.diagnosis.first_boundary_id or "none",
        )

        option_diagnostic = b"Possible protocol error!" in pdp11_output
        evidence = (
            "connection_open=1\n"
            f"its_service_user={service_user}\n"
            "its_greeting=1\n"
            "remote_time=structured\n"
            "imp6_post_probe_traffic=1\n"
            "imp62_post_probe_traffic=1\n"
            "correlated_inter_imp_traffic=both-directions\n"
            f"message_journey_observations={len(journey.observations)}\n"
            f"message_journey_state={journey.diagnosis.state.value}\n"
            f"message_journey_first_boundary={journey.diagnosis.first_boundary_id}\n"
            f"legacy_option_diagnostic={'observed' if option_diagnostic else 'absent'}\n"
        )
        (results_dir / "application-evidence.txt").write_text(evidence, encoding="ascii")
        SHARED.append_manifest(manifest, "application.client", "network-unix-telnet")
        SHARED.append_manifest(manifest, "application.server", "TELSER")
        SHARED.append_manifest(manifest, "application.service_user", service_user)
        SHARED.append_manifest(manifest, "application.remote_time", "structured")
        SHARED.append_manifest(
            manifest,
            "application.legacy_option_diagnostic",
            "observed" if option_diagnostic else "absent",
        )
        outcome = "passed"
        print(f"PASS: Network UNIX PDP-11 reached ITS host 106 through two IMPs: {results_dir}")
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
    except (OSError, RuntimeError, TimeoutError, ValueError, InterruptedError):
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
