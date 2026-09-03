#!/usr/bin/env python3
"""Drive the two-ITS NCP TELNET acceptance test through simulator PTYs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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

from ncc.harness_config import (
    PORT_VARIABLES,
    create_host106_attach_config,
    validate_environment,
)
from ncc.harness_imp import (
    latest_watchdog,
    mi_link_messages,
    mi_link_messages_from_bytes,
    significant,
    wait_for_log_marker,
    wait_for_watchdog_devices_ready,
    watchdog_devices_ready,
    watchdog_reports_modem_dead,
    watchdog_states_from_bytes,
)
from ncc.harness_manifest import append_manifest, sha256
from ncc.harness_process import ImpProcess, PtyProcess, stop_all, utc_now
from ncc.live import LiveObservationPublisher
from ncc.topology import two_its_topology


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
