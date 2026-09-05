#!/usr/bin/env python3
"""Drive the formal Network UNIX PDP-11 to ITS TELNET acceptance gate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.harness_config import (
    PORT_VARIABLES,
    create_host106_attach_config,
    validate_environment,
)
from ncc.harness_imp import (
    latest_watchdog,
    wait_for_log_marker,
    wait_for_watchdog_devices_ready,
    watchdog_devices_ready,
)
from ncc.harness_manifest import append_manifest, read_manifest, sha256
from ncc.harness_process import ImpProcess, ProcessWatch, PtyProcess, cleanup_signals, ensure_process_alive
from ncc.harness_progress import ControllerProgress
from ncc.message_journey import ObservationProvenance
from ncc.pdp11_its_harness import (
    DATE_PATTERN,
    FATAL_SESSION,
    FATAL_TRANSPORT,
    SERVICE_PATTERN,
    TIME_PATTERN,
    UPTIME_PATTERN,
    application_evidence_failures,
    boot_pdp11,
    create_host106_observation_config,
    create_pdp11_observation_config,
    ordered_pattern_failures,
    stop_and_record,
    wait_for_prompt,
)
from ncc.pdp11_its_journey import (
    pdp11_its_modem_devices,
    transaction_window_source,
    write_pdp11_its_journey_stream,
)
from ncc.shared_topology import shared_topology_from_mapping


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
    parser.add_argument(
        "--ka10-ingress-trace",
        action="store_true",
        help="retain and adapt the versioned KA10 request-ingress trace",
    )
    parser.add_argument(
        "--pdp11-ingress-trace",
        action="store_true",
        help="retain and adapt the versioned IMP11-A reply-ingress trace",
    )
    parser.add_argument("--route-settle", type=float, default=60.0)
    parser.add_argument("--daemon-settle", type=float, default=12.0)
    parser.add_argument("--progress-fd", type=int, help="launcher-owned descriptor for live progress")
    return parser.parse_args()


def run(args: argparse.Namespace, progress: ControllerProgress | None = None) -> int:
    if progress is None:
        progress = ControllerProgress(args.manifest)
    progress.stage("controller input and observation configuration")
    validate_environment()
    results_dir = args.results_dir.resolve()
    manifest = args.manifest.resolve()
    topology_path = args.topology.resolve()
    topology_document = json.loads(topology_path.read_text(encoding="utf-8"))
    shared_topology = shared_topology_from_mapping(topology_document)
    imp62_mi_device, imp6_mi_device = pdp11_its_modem_devices(shared_topology)
    attach_config = results_dir / "host106-attach-only.simh"
    if args.ka10_ingress_trace:
        create_host106_observation_config(args.host106_config.resolve(), attach_config)
    else:
        create_host106_attach_config(args.host106_config.resolve(), attach_config)
    append_manifest(manifest, "sha256.host106-attach-config", sha256(attach_config))
    append_manifest(manifest, "path.host106-attach-config", attach_config)
    pdp11_config = args.pdp11_config.resolve()
    if args.pdp11_ingress_trace:
        pdp11_observation_config = results_dir / "pdp11-input-observation.simh"
        create_pdp11_observation_config(pdp11_config, pdp11_observation_config)
        pdp11_config = pdp11_observation_config
        append_manifest(
            manifest, "sha256.pdp11-observation-config", sha256(pdp11_config)
        )
        append_manifest(manifest, "path.pdp11-observation-config", pdp11_config)

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
        pdp11_config,
        args.pdp11_work.resolve(),
        results_dir / "pdp11.console.log",
        results_dir / "pdp11.sent.log",
        manifest,
    )
    hosts = (pdp11, host106)
    imps = (imp6, imp62)
    watch = ProcessWatch((*hosts, *imps), progress.waiting)
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
        progress.stage("IMP startup")
        imp6.launch()
        imp62.launch()
        wait_for_log_marker(imp6, "listening on port", 30)
        wait_for_log_marker(imp62, "listening on port", 30)

        progress.stage("guest simulator consoles")
        host106.launch(state="PROMPT")
        pdp11.launch(state="PROMPT")
        host106.expect("sim> ", timeout=60)
        pdp11.expect("sim> ", timeout=60)

        progress.stage("inter-IMP modem readiness")
        imp6_modem_up, _ = wait_for_watchdog_devices_ready(
            imp6, modem_device=imp6_mi_device, timeout=60
        )
        imp62_modem_up, _ = wait_for_watchdog_devices_ready(
            imp62, modem_device=imp62_mi_device, timeout=60
        )
        route_settle_deadline = max(imp6_modem_up, imp62_modem_up) + args.route_settle

        progress.stage("ITS boot and local command readiness")
        host106.send(
            'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\r'
        )
        host106.expect("sim> ", timeout=30)
        host106.send("boot ptr\r")
        host106.state = "BOOTING"
        host106.mark_running_after_banner()
        host106.enter_ddt_and_prove_local_time()

        progress.stage("Network UNIX boot and NCP daemon")
        boot_pdp11(pdp11)
        pdp11.send("/usr/net/etc/smalldaemon &\r")
        wait_for_prompt(pdp11, timeout=15)
        watch.sleep(args.daemon_settle, "NCP daemon settling interval")

        progress.stage("host interfaces and route hold-down")
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
            watch.sleep(remaining, "route hold-down interval")
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
        host106_trace_offset = host106_offset if args.ka10_ingress_trace else None
        if host106_trace_offset is not None:
            append_manifest(
                manifest, "application.offset.host106-imp", host106_trace_offset
            )
        host176_trace_offset = pdp11_offset if args.pdp11_ingress_trace else None
        if host176_trace_offset is not None:
            append_manifest(
                manifest, "application.offset.host176-imp", host176_trace_offset
            )

        progress.stage("TELNET connection and remote TIME transaction")
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
        watch.sleep(3, "post-transaction capture interval")

        progress.stage("application and message-journey evidence")
        pdp11_output = pdp11.output_from(pdp11_offset)
        its_output = host106.output_from(host106_offset)
        imp_end_offsets = {imp.name: imp.debug_path.stat().st_size for imp in imps}
        host106_trace_end_offset = (
            host106_trace_offset + len(its_output)
            if host106_trace_offset is not None
            else None
        )
        host176_trace_end_offset = (
            host176_trace_offset + len(pdp11_output)
            if host176_trace_offset is not None
            else None
        )
        imp6_output = imp6.debug_path.read_bytes()[
            imp_offsets["imp6"] : imp_end_offsets["imp6"]
        ]
        imp62_output = imp62.debug_path.read_bytes()[
            imp_offsets["imp62"] : imp_end_offsets["imp62"]
        ]
        host106_trace = its_output if args.ka10_ingress_trace else None
        host176_trace = pdp11_output if args.pdp11_ingress_trace else None
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
            latest = latest_watchdog(imp.debug_path)
            if not watchdog_devices_ready(
                latest, modem_device=modem_device, host_device="hi2"
            ):
                failures.append(f"{imp.name} did not remain host-link ready")
        if failures:
            raise RuntimeError("; ".join(failures))

        manifest_values = read_manifest(manifest)
        journey_path = results_dir / "message-journey.jsonl"
        window = [
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
        ]
        if (
            host106_trace is not None
            and host106_trace_offset is not None
            and host106_trace_end_offset is not None
        ):
            window.append(
                transaction_window_source(
                    source_id="source:host106-imp",
                    artifact=host106.console_log_path.name,
                    start_offset=host106_trace_offset,
                    end_offset=host106_trace_end_offset,
                    content=host106_trace,
                )
            )
        if (
            host176_trace is not None
            and host176_trace_offset is not None
            and host176_trace_end_offset is not None
        ):
            window.append(
                transaction_window_source(
                    source_id="source:host176-imp",
                    artifact=pdp11.console_log_path.name,
                    start_offset=host176_trace_offset,
                    end_offset=host176_trace_end_offset,
                    content=host176_trace,
                )
            )
        provenance = [
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
        ]
        if host106_trace is not None:
            provenance.append(
                ObservationProvenance(
                    "source:host106-imp",
                    "ka10-imp-trace",
                    manifest_values["source.ka10-simh.revision"],
                )
            )
        if host176_trace is not None:
            provenance.append(
                ObservationProvenance(
                    "source:host176-imp",
                    "pdp11-imp11a-trace",
                    manifest_values["source.imp11a-simh.revision"],
                )
            )
        journey = write_pdp11_its_journey_stream(
            journey_path,
            run_id=results_dir.name,
            started_at=manifest_values["started_utc"],
            provenance=provenance,
            topology_document=topology_document,
            transaction_window=window,
            imp6_trace=imp6_output,
            imp62_trace=imp62_output,
            ka10_trace=host106_trace,
            imp11a_trace=host176_trace,
            h316_revision=manifest_values["source.h316-simh.revision"],
            ka10_revision=(
                manifest_values["source.ka10-simh.revision"]
                if host106_trace is not None
                else None
            ),
            imp11a_revision=(
                manifest_values["source.imp11a-simh.revision"]
                if host176_trace is not None
                else None
            ),
        )
        for name in ("imp6", "imp62"):
            append_manifest(
                manifest,
                f"application.offset.end.{name}",
                imp_end_offsets[name],
            )
        if host106_trace_end_offset is not None:
            append_manifest(
                manifest,
                "application.offset.end.host106-imp",
                host106_trace_end_offset,
            )
        if host176_trace_end_offset is not None:
            append_manifest(
                manifest,
                "application.offset.end.host176-imp",
                host176_trace_end_offset,
            )
        append_manifest(manifest, "path.message-journey", journey_path)
        append_manifest(
            manifest, "sha256.message-journey", sha256(journey_path)
        )
        append_manifest(
            manifest, "message-journey.observations", len(journey.observations)
        )
        append_manifest(
            manifest, "message-journey.state", journey.diagnosis.state.value
        )
        append_manifest(
            manifest,
            "message-journey.first-boundary",
            journey.diagnosis.first_boundary_id or "none",
        )

        option_diagnostic = b"Possible protocol error!" in pdp11_output
        first_boundary = journey.diagnosis.first_boundary_id or "none"
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
            f"message_journey_first_boundary={first_boundary}\n"
            f"legacy_option_diagnostic={'observed' if option_diagnostic else 'absent'}\n"
        )
        (results_dir / "application-evidence.txt").write_text(evidence, encoding="ascii")
        append_manifest(manifest, "application.client", "network-unix-telnet")
        append_manifest(manifest, "application.server", "TELSER")
        append_manifest(manifest, "application.service_user", service_user)
        append_manifest(manifest, "application.remote_time", "structured")
        append_manifest(
            manifest,
            "application.legacy_option_diagnostic",
            "observed" if option_diagnostic else "absent",
        )
        outcome = "passed"
    except Exception as error:
        try:
            progress.failure(error)
        except OSError:
            pass
        raise
    finally:
        try:
            with cleanup_signals():
                try:
                    try:
                        progress.stage("controller shutdown: stopping owned guests and IMPs")
                    finally:
                        stop_and_record(results_dir, hosts, imps, force=interrupted)
                except Exception:
                    outcome = "failed"
                    raise
                finally:
                    (results_dir / "outcome.txt").write_text(outcome + "\n", encoding="ascii")
        finally:
            signal.signal(signal.SIGTERM, old_term)
            signal.signal(signal.SIGINT, old_int)
    progress.stage("controller cleanup completed")
    print(f"PASS: Network UNIX PDP-11 reached ITS host 106 through two IMPs: {results_dir}")
    return 0


def main() -> int:
    args = parse_args()
    live_stream = os.fdopen(os.dup(args.progress_fd), "w") if args.progress_fd is not None else None
    progress = ControllerProgress(args.manifest, live_stream)
    try:
        return run(args, progress)
    except (OSError, RuntimeError, TimeoutError, ValueError, InterruptedError) as error:
        # Failure before simulator creation still belongs to this run's manifest.
        try:
            if not progress.failed:
                progress.failure(error)
        except OSError:
            pass
        traceback.print_exc()
        return 1
    finally:
        if live_stream is not None:
            live_stream.close()


if __name__ == "__main__":
    raise SystemExit(main())
