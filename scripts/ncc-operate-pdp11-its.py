#!/usr/bin/env python3
"""Run a formal PDP-11/ITS NCC scenario beside its passive network board."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.board_display import NccBoardDisplay, NccBoardError
from ncc.board_server import create_ncc_board_server


SCENARIOS = {
    "coexistence": {
        "result_prefix": "ncc-pdp11-its-coexistence",
        "script": "smoke-ncc-pdp11-its.sh",
        "has_report": True,
    },
    "failover": {
        "result_prefix": "ncc-pdp11-its-application-failover",
        "script": "smoke-ncc-pdp11-its-failover.sh",
        "has_report": False,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIOS),
        default="coexistence",
    )
    parser.add_argument("--arpanet-root", required=True, type=Path)
    parser.add_argument("--network-unix-root", required=True, type=Path)
    parser.add_argument("--imp11a-root", required=True, type=Path)
    parser.add_argument("--h316", required=True, type=Path)
    parser.add_argument("--pdp10-ka", required=True, type=Path)
    parser.add_argument("--pdp11", required=True, type=Path)
    parser.add_argument("--pdp11-build-root", required=True, type=Path)
    parser.add_argument("--results-root", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--topology", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def results_directory(
    results_root: Path,
    run_id: str,
    scenario: str = "coexistence",
) -> Path:
    """Resolve one stable result name without creating or replacing it."""

    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id) is None:
        raise ValueError("run id must use only letters, digits, dot, underscore, or hyphen")
    try:
        prefix = SCENARIOS[scenario]["result_prefix"]
    except KeyError as error:
        raise ValueError(f"unsupported NCC operator scenario {scenario!r}") from error
    return results_root / f"{prefix}-{run_id}"


def scenario_command(args: argparse.Namespace, result: Path) -> list[str]:
    """Build the existing formal harness command without changing its inputs."""

    scenario = getattr(args, "scenario", "coexistence")
    try:
        script = SCENARIOS[scenario]["script"]
    except KeyError as error:
        raise ValueError(f"unsupported NCC operator scenario {scenario!r}") from error
    return [
        os.fspath(REPOSITORY_ROOT / "scripts" / str(script)),
        os.fspath(args.arpanet_root),
        os.fspath(args.network_unix_root),
        os.fspath(args.imp11a_root),
        os.fspath(args.h316),
        os.fspath(args.pdp10_ka),
        os.fspath(args.pdp11),
        os.fspath(args.pdp11_build_root),
        os.fspath(result),
    ]


def stop_owned_scenario(process: subprocess.Popen[bytes], timeout: float = 45) -> None:
    """Stop the exact new-session harness and allow its cleanup trap to finish."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.getpgid(process.pid) == process.pid:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def main() -> int:
    args = parse_args()
    try:
        result = results_directory(args.results_root, args.run_id, args.scenario)
        display = NccBoardDisplay(result, args.topology)
        server = create_ncc_board_server(display, port=args.port)
    except (NccBoardError, OSError, ValueError) as error:
        print(f"cannot prepare NCC operated run: {error}", file=sys.stderr)
        return 1

    environment = dict(os.environ)
    environment["PYTHON"] = sys.executable
    command = scenario_command(args, result)
    process = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        start_new_session=True,
    )
    completed_status: list[int] = []

    def monitor() -> None:
        status = process.wait()
        completed_status.append(status)
        if status == 0:
            address = f"http://{server.server_address[0]}:{server.server_address[1]}/"
            print(
                f"\nNCC scenario completed. The board remains open at {address}",
                flush=True,
            )
            if SCENARIOS[args.scenario]["has_report"]:
                print(
                    "Open /report for the retained detailed run report. "
                    "Press Control-C to close the board.",
                    flush=True,
                )
            else:
                print(
                    "The completed board now shows the validated cut and alternate "
                    "route. Press Control-C to close it.",
                    flush=True,
                )
        else:
            print(f"\nNCC scenario exited with status {status}; inspect the terminal and partial result at {result}.", file=sys.stderr, flush=True)

    monitor_thread = threading.Thread(target=monitor, name="ncc-scenario-monitor", daemon=True)
    monitor_thread.start()
    host, port = server.server_address
    print(f"NCC network board: http://{host}:{port}/", flush=True)
    print(f"Owned scenario result: {result}", flush=True)
    print("Press Control-C to stop the exact scenario and its board.", flush=True)
    interrupted_running_scenario = False
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        interrupted_running_scenario = process.poll() is None
    finally:
        server.server_close()
        stop_owned_scenario(process)
        monitor_thread.join(timeout=1)
    if interrupted_running_scenario:
        return 130
    if completed_status:
        return completed_status[0]
    return process.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())
