#!/usr/bin/env python3
"""Drive one same-session Network UNIX-to-ITS application-link failover."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import signal
import time
import traceback
from pathlib import Path

BASE_PATH = Path(__file__).with_name("pdp11-its-controller.py")
BASE_SPEC = importlib.util.spec_from_file_location("pdp11_its_controller", BASE_PATH)
assert BASE_SPEC is not None and BASE_SPEC.loader is not None
BASE = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(BASE)
SHARED = BASE.SHARED

from ncc.message_journey import ObservationProvenance
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

PtyProcess = BASE.PtyProcess
ImpProcess = BASE.ImpProcess
_FATAL_POST_CUT_TRANSPORT = re.compile(
    rb"bind error|Can't open Datagram socket|UNRECOVERABLE I/O ERROR|"
    rb"tmxr_put_packet_ln\(\) failed|HARDWARE ERROR",
    re.IGNORECASE,
)
NETWORK_UNIX_HOST106_READY_PATTERN = rb"SKTRACE hh h=106 bytes=1 op=15"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h316", required=True, type=Path)
    parser.add_argument("--pdp10-ka", required=True, type=Path)
    parser.add_argument("--pdp11", required=True, type=Path)
    parser.add_argument("--mini-root", required=True, type=Path)
    parser.add_argument("--its-host-work", required=True, type=Path)
    parser.add_argument("--pdp11-work", required=True, type=Path)
    parser.add_argument("--imp6-config", required=True, type=Path)
    parser.add_argument("--imp62-config", required=True, type=Path)
    parser.add_argument("--imp7-debug", required=True, type=Path)
    parser.add_argument("--its-host-config", required=True, type=Path)
    parser.add_argument("--pdp11-config", required=True, type=Path)
    parser.add_argument("--topology", required=True, type=Path)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cut-request", required=True, type=Path)
    parser.add_argument("--cut-state", required=True, type=Path)
    parser.add_argument("--route-settle", type=float, default=60.0)
    parser.add_argument("--post-cut-settle", type=float, default=60.0)
    parser.add_argument("--daemon-settle", type=float, default=12.0)
    parser.add_argument("--ncp-ready-timeout", type=float, default=120.0)
    args = parser.parse_args()
    if (
        args.route_settle <= 0
        or args.post_cut_settle <= 0
        or args.daemon_settle <= 0
        or args.ncp_ready_timeout <= 0
    ):
        parser.error("settle durations must be positive")
    return args


def wait_for_network_unix_its_host_ready(
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
        SHARED.watchdog_devices_ready(
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
        state = (
            SHARED.latest_watchdog(imp.debug_path) if imp.debug_path.exists() else None
        )
        if devices_ready(state, modem_devices, host_device=host_device):
            return
        time.sleep(0.1)
    raise TimeoutError(
        f"{imp.name} did not report {', '.join(modem_devices)} ready; "
        f"latest watchdog state is {SHARED.latest_watchdog(imp.debug_path)}"
    )


def wait_for_trace_devices_ready(
    path: Path,
    modem_devices: tuple[str, ...],
    *,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = SHARED.latest_watchdog(path) if path.exists() else None
        if devices_ready(state, modem_devices):
            return
        time.sleep(0.1)
    state = SHARED.latest_watchdog(path) if path.exists() else None
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
        state = SHARED.latest_watchdog(imp.debug_path)
        direct_dead = not SHARED.watchdog_devices_ready(
            state,
            modem_device=direct_device,
        )
        alternate_ready = SHARED.watchdog_devices_ready(
            state,
            modem_device=alternate_device,
            host_device="hi2",
        )
        if direct_dead and alternate_ready:
            return
        time.sleep(0.1)
    raise TimeoutError(
        f"{imp.name} did not reach direct-dead/alternate-ready state; "
        f"latest watchdog state is {SHARED.latest_watchdog(imp.debug_path)}"
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
        ("remote time", BASE.TIME_PATTERN),
        ("remote date", BASE.DATE_PATTERN),
        ("remote uptime", BASE.UPTIME_PATTERN),
    ):
        if re.search(pattern, pdp11_output, re.DOTALL) is None:
            failures.append(f"missing post-cut {label} evidence")
    if BASE.FATAL_SESSION.search(pdp11_output):
        failures.append("PDP-11 TELNET session closed or failed after the cut")
    for name, output, devices in (
        ("imp6", imp6_output, (imp6_alternate_device,)),
        ("imp7", imp7_output, (imp7_in_device, imp7_out_device)),
        ("imp62", imp62_output, (imp62_alternate_device,)),
    ):
        if _FATAL_POST_CUT_TRANSPORT.search(output):
            failures.append(f"{name} reported a fatal post-cut transport condition")
        for device in devices:
            if SHARED.watchdog_reports_modem_dead(output, device):
                failures.append(f"{name} reported alternate device {device} dead")
    for name, output in (("imp6", imp6_output), ("imp62", imp62_output)):
        for marker in (b"HI2 MSG: message received", b"HI2 MSG: message sent"):
            if marker not in output:
                failures.append(
                    f"{name} lacks post-cut {marker.decode('ascii')} evidence"
                )
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


def run(args: argparse.Namespace) -> int:
    SHARED.validate_environment()
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
    SHARED.create_its_host_attach_config(args.its_host_config.resolve(), attach_config)
    SHARED.append_manifest(
        manifest,
        "sha256.host106-attach-config",
        SHARED.sha256(attach_config),
    )
    SHARED.append_manifest(manifest, "path.host106-attach-config", attach_config)
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
    its_host = PtyProcess(
        "host106",
        args.pdp10_ka.resolve(),
        attach_config,
        args.its_host_work.resolve(),
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
    hosts = (pdp11, its_host)
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
        wait_for_trace_devices_ready(
            imp7_debug,
            (imp7_in, imp7_out),
            timeout=90,
        )

        its_host.launch(state="PROMPT")
        pdp11.launch(state="PROMPT")
        its_host.expect("sim> ", timeout=60)
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

        its_host.send(
            'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\r'
        )
        its_host.expect("sim> ", timeout=30)
        its_host.send("boot ptr\r")
        its_host.state = "BOOTING"
        its_host.mark_running_after_banner()
        its_host.enter_ddt_and_prove_local_time()
        BASE.boot_pdp11(pdp11)
        pdp11.send("/usr/net/etc/smalldaemon &\r")
        BASE.wait_for_prompt(pdp11, timeout=15)
        time.sleep(args.daemon_settle)
        wait_for_network_unix_its_host_ready(pdp11, args.ncp_ready_timeout)
        SHARED.append_manifest(
            manifest,
            "application.network-unix-host106-ready",
            "host-host-rrp-consumed",
        )

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
            BASE.ensure_process_alive(host)
            if host.state != "RUNNING":
                raise RuntimeError(f"{host.name} is not RUNNING before TELNET")

        pre_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        pre_pdp11_offset = pdp11.position()
        pre_its_host_offset = its_host.position()
        pdp11.send("/usr/bin/telnet - -h 106\r")
        event, _ = pdp11.expect_any(
            (rb"Connection open", rb"Host is Unavailable"),
            timeout=60,
        )
        if event != 0:
            raise RuntimeError("guest TELNET reported Host is Unavailable")
        service_match = its_host.expect(BASE.SERVICE_PATTERN, timeout=120)
        service_user = service_match.group(1).decode("ascii")
        pdp11.expect(rb"MIT Dynamic[\s\S]*?Modelling PDP-10", timeout=60)
        pdp11.expect(rb"TTY [0-9]+", timeout=60)
        pdp11.expect("Welcome to ITS!", timeout=60)
        pdp11.send(":time\r")
        pdp11.expect(BASE.TIME_PATTERN, timeout=60)
        pdp11.expect(BASE.DATE_PATTERN, timeout=30)
        pdp11.expect(BASE.UPTIME_PATTERN, timeout=30)
        time.sleep(3)

        pre_end = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        pre_imp6 = imp6.debug_path.read_bytes()[pre_offsets["imp6"] : pre_end["imp6"]]
        pre_imp62 = imp62.debug_path.read_bytes()[
            pre_offsets["imp62"] : pre_end["imp62"]
        ]
        pre_failures = BASE.application_evidence_failures(
            pdp11.output_from(pre_pdp11_offset),
            its_host.output_from(pre_its_host_offset),
            pre_imp6,
            pre_imp62,
            imp6_mi_device=imp6_direct,
            imp62_mi_device=imp62_direct,
        )
        if pre_failures:
            raise RuntimeError("pre-cut baseline failed: " + "; ".join(pre_failures))

        manifest_values = BASE.read_manifest(manifest)
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
        SHARED.append_manifest(manifest, "application.cut-requested", 1)
        SHARED.append_manifest(
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
        pdp11.expect(BASE.TIME_PATTERN, timeout=90)
        pdp11.expect(BASE.DATE_PATTERN, timeout=30)
        pdp11.expect(BASE.UPTIME_PATTERN, timeout=30)
        time.sleep(3)
        for host in hosts:
            BASE.ensure_process_alive(host)
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
            SHARED.append_manifest(manifest, f"path.{label}", path)
            SHARED.append_manifest(manifest, f"sha256.{label}", SHARED.sha256(path))
        SHARED.append_manifest(
            manifest,
            "message-journey.observations",
            len(journey.observations),
        )
        SHARED.append_manifest(
            manifest,
            "message-journey.state",
            journey.diagnosis.state.value,
        )
        SHARED.append_manifest(
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
        SHARED.append_manifest(manifest, "application.client", "network-unix-telnet")
        SHARED.append_manifest(manifest, "application.server", "TELSER")
        SHARED.append_manifest(manifest, "application.service_user", service_user)
        SHARED.append_manifest(manifest, "application.session-survived-cut", 1)
        outcome = "passed"
        print(
            "PASS: the Network UNIX TELNET session reached ITS after the "
            f"application-link cut through IMP 7: {results_dir}"
        )
        return 0
    finally:
        BASE.stop_and_record(results_dir, hosts, imps, force=interrupted)
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
