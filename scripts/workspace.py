#!/usr/bin/env python3
"""Create, operate, inspect, or roll back a named direct guest workspace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.guest_workspace import (
    MEDIA, Workspace, WorkspaceError, read_json, utc_now, workspace_path, write_json,
)
from ncc.harness_manifest import read_manifest, sha256


def runtime_paths(lab: Path, build: Path) -> dict[str, Path]:
    arpanet = lab / "work/arpanet"
    return {
        "arpanet": arpanet,
        "network_unix": lab / "work/network-unix-v6",
        "imp11a": lab / "work/open-simh",
        "h316": arpanet / "src/linux-ncp/test/simh/BIN/h316",
        "ka10": lab / "work/ka10-simh/BIN/pdp10-ka",
        "pdp11": lab / "work/open-simh/BIN/pdp11",
        "build": build,
    }


def verify_inputs(lab: Path, paths: dict[str, Path]) -> dict:
    scripts = REPOSITORY_ROOT / "scripts"
    commands = (
        [sys.executable, scripts / "verify-sources.py", lab, "--name", "arpanet-in-a-box", "--name", "h316-simh", "--name", "ka10-simh", "--name", "imp11a-simh", "--name", "network-unix-v6"],
        ["sh", scripts / "verify-assets.sh", "mixed", paths["arpanet"]],
        [sys.executable, scripts / "verify-simulator-binaries.py", "--h316", paths["h316"], "--pdp10-ka", paths["ka10"], "--pdp11", paths["pdp11"]],
        [sys.executable, scripts / "pdp11-build-receipt.py", "verify", paths["build"] / "pdp11-build-receipt.json"],
    )
    for command in commands:
        subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)
    files = {key: paths[key] for key in ("h316", "ka10", "pdp11")}
    files["build_receipt"] = paths["build"] / "pdp11-build-receipt.json"
    for name in ("impconfig.simh", "impcode.simh"):
        files[name] = paths["arpanet"] / "mini" / name
    for relative in (
        "pins/sources.lock.toml", "config/topologies/pdp11-its-telnet.json",
        "config/hosts/its106-pair.simh", "config/hosts/pdp11-176.simh",
        "config/imp/its-pair/imp6.simh", "config/imp/pdp11-its/imp62.simh",
    ):
        files[relative] = REPOSITORY_ROOT / relative
    return {name: {"path": str(path), "sha256": sha256(path)} for name, path in files.items()}


def seed_sources(paths: dict[str, Path]) -> dict[str, Path]:
    its = paths["arpanet"] / "mini/host70/106"
    unix = paths["build"] / "ncpd/guest/images"
    return {name: (its if name.startswith("host106/") else unix) / Path(name).name for name in MEDIA}


def create_workspace(workspace: Workspace, lab: Path, build: Path) -> None:
    if workspace.root.exists():
        raise WorkspaceError("workspace already exists; use workspace or choose a new name")
    lease = Path(str(build) + ".lock")
    try:
        lease.mkdir()
    except FileExistsError as error:
        raise WorkspaceError(f"guest build is already leased: {lease}") from error
    try:
        paths = runtime_paths(lab, build)
        inputs = verify_inputs(lab, paths)
        workspace.root.parent.mkdir(parents=True, exist_ok=True)
        workspace.root.mkdir(mode=0o700)
        write_json(workspace.root / "workspace.json", {
            "format": 1, "name": workspace.root.name, "created_utc": utc_now(),
            "lab": str(lab), "build": str(build), "inputs": inputs,
        })
        saved = workspace.publish(seed_sources(paths), parent=None, result=None, shutdown_sha256=None)
        print(f"Created workspace {workspace.root.name}; initial save {saved}.", flush=True)
        print(f"Start with: make workspace WORKSPACE={workspace.root.name}", flush=True)
    finally:
        lease.rmdir()


def cleanup_proved(result: Path, token: str) -> bool:
    """Only this invocation's completed ownership records can release its lease."""
    try:
        manifest = read_manifest(result / "runtime/run.env")
        if manifest.get("workspace.lease-token") != token:
            return False
        if manifest.get("cleanup.runtime.exit-status") != "0":
            return False
        if "process.pdp11.pid" not in manifest and "process.host106.pid" not in manifest:
            # The shell never started a controller. A partial controller launch
            # still requires its own cleanup evidence below.
            if (result / "cleanup-evidence.txt").exists():
                evidence = read_manifest(result / "cleanup-evidence.txt")
                return evidence.get("cleanup_status") == "passed" and evidence.get("surviving_owned_processes") == "0"
            return not (result / "host106-attach-only.simh").exists()
        evidence = read_manifest(result / "cleanup-evidence.txt")
        return evidence.get("cleanup_status") == "passed" and evidence.get("surviving_owned_processes") == "0"
    except (OSError, ValueError):
        return False


def shutdown_proved(result: Path, token: str) -> str:
    cleanup = read_manifest(result / "cleanup-evidence.txt")
    if any(cleanup.get(name + ".exit_status") != "0" for name in ("pdp11", "host106")):
        raise WorkspaceError("guest simulators did not exit successfully; previous save retained")
    proof_path = result / "workspace-shutdown.json"
    proof = read_json(proof_path)
    if (
        set(proof) != {"format", "run_id", "lease_token", "its", "pdp11"}
        or type(proof["format"]) is not int or proof["format"] != 1
        or proof["run_id"] != result.name or proof["lease_token"] != token
        or proof["its"] != "shutdown-complete" or proof["pdp11"] != "writers-stopped-and-synced"
    ):
        raise WorkspaceError("the run has no matching complete guest shutdown proof; previous save retained")
    digest = sha256(proof_path)
    manifest = read_manifest(result / "runtime/run.env")
    if manifest.get("sha256.workspace-shutdown") != digest:
        raise WorkspaceError("guest shutdown proof digest disagrees with the run")
    return digest


def run_workspace(workspace: Workspace, lab: Path, result: Path) -> int:
    if result.exists() or result.is_symlink():
        raise WorkspaceError(f"result path already exists: {result}")
    metadata = workspace.metadata()
    if metadata["lab"] != str(lab):
        raise WorkspaceError("workspace belongs to a different laboratory")
    token = workspace.acquire(result)
    child = None
    safe_to_release = True
    interrupted = False
    handlers = {}

    def interrupt(signum, _frame):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            if child is not None and child.poll() is None:
                try:
                    child.send_signal(signum)
                except ProcessLookupError:
                    pass
            else:
                raise InterruptedError("workspace operation interrupted")

    try:
        parent = workspace.current()
        workspace.verify_generation(parent)
        paths = runtime_paths(lab, Path(metadata["build"]))
        workspace.check_inputs(verify_inputs(lab, paths))
        environment = dict(os.environ)
        environment.update({
            "BRFID_TELNET_MODE": "terminal",
            "BRFID_WORKSPACE_MEDIA": str(workspace.generation_path(parent)),
            "BRFID_WORKSPACE_LEASE_TOKEN": token,
            "BRFID_WORKSPACE_NAME": workspace.root.name,
            "BRFID_WORKSPACE_PARENT": parent,
        })
        command = [
            "sh", str(REPOSITORY_ROOT / "scripts/telnet-pdp11-its.sh"),
            *(str(paths[key]) for key in ("arpanet", "network_unix", "imp11a", "h316", "ka10", "pdp11", "build")),
            str(result),
        ]
        print(f"Opening workspace {workspace.root.name} from save {parent}.", flush=True)
        print("Control-] saves and stops. A failed or interrupted stop keeps the previous save.", flush=True)
        for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            handlers[sig] = signal.signal(sig, interrupt)
        safe_to_release = False
        child = subprocess.Popen(command, cwd=REPOSITORY_ROOT, env=environment)
        status = child.wait()
        # The launcher cannot start simulators before it creates its result.
        safe_to_release = not result.exists() or cleanup_proved(result, token)
        if not safe_to_release:
            raise WorkspaceError(f"cleanup is unproved; previous save retained and workspace remains leased; inspect {result}")
        if status != 0 or interrupted:
            print(f"Workspace save unchanged. Failed/interrupted run retained at {result}.", file=sys.stderr)
            return status if status > 0 else 1
        manifest = read_manifest(result / "runtime/run.env")
        if manifest.get("outcome") != "passed" or manifest.get("workspace.parent") != parent:
            raise WorkspaceError("workspace run did not complete against its selected parent")
        generation = workspace.verify_generation(parent)
        for name in MEDIA:
            prefix = "host106-" if name.startswith("host106/") else "pdp11-"
            if manifest.get("sha256." + prefix + Path(name).name) != generation["media"][name]["sha256"]:
                raise WorkspaceError("run media did not start from the verified parent generation")
        digest = shutdown_proved(result, token)
        saved = workspace.publish(
            {name: result / name for name in MEDIA}, parent=parent, result=result,
            shutdown_sha256=digest,
        )
        print(f"Saved workspace {workspace.root.name}: {saved}", flush=True)
        print(f"Previous save retained: {parent}", flush=True)
        return 0
    finally:
        for sig, old in handlers.items():
            signal.signal(sig, old)
        if safe_to_release:
            workspace.release(token)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "run", "status", "restore"))
    parser.add_argument("lab", type=Path)
    parser.add_argument("name")
    parser.add_argument("--build", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--generation")
    args = parser.parse_args()
    try:
        lab = args.lab.expanduser().resolve()
        workspace = Workspace(workspace_path(lab, args.name, REPOSITORY_ROOT))
        if args.action == "create":
            if args.build is None:
                raise WorkspaceError("create requires --build with a verified guest build directory")
            create_workspace(workspace, lab, args.build.expanduser().resolve())
        elif args.action == "run":
            if args.result is None:
                raise WorkspaceError("run requires a new --result path")
            result = args.result.expanduser().absolute()
            if result.resolve() != result or not result.is_relative_to(lab) or result.is_relative_to(workspace.root):
                raise WorkspaceError("run results must be in the external lab, outside the workspace, without symlinks")
            return run_workspace(workspace, lab, result)
        elif args.action == "restore":
            if args.generation is None:
                raise WorkspaceError("restore requires --generation; inspect workspace-status for saved identifiers")
            with workspace.locked():
                workspace.select(args.generation)
            print(f"Selected save {args.generation}; all other saves remain available.")
        else:
            workspace.metadata()
            current = workspace.current()
            workspace.verify_generation(current)
            print(f"Workspace: {workspace.root}\nCurrent verified save: {current}")
            print(f"Lease: {'present; automatic reclamation is disabled' if (workspace.root / 'lease').exists() else 'available'}")
            for path in sorted((workspace.root / "generations").iterdir()):
                if path.name.startswith("."):
                    continue
                record = read_json(path / "generation.json")
                print(f"  {path.name}  {record.get('created_utc')}  {record.get('kind')}  parent={record.get('parent')}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Workspace: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
