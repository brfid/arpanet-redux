#!/usr/bin/env python3
"""Write or verify a receipt for the staged Network UNIX TELNET image."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import tomllib


FORMAT_VERSION = 1
IMAGE_NAMES = ("ncp_root.rl01", "ncp_swap.rl01")
BUILDER_NAMES = (
    "research/build-guest-telnet.py",
    "research/build-guest-ncpd.py",
    "research/v6fs.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    write = subparsers.add_parser("write")
    write.add_argument("network_unix_root", type=Path)
    write.add_argument("imp11a_root", type=Path)
    write.add_argument("pdp11", type=Path)
    write.add_argument("base_root", type=Path)
    write.add_argument("base_swap", type=Path)
    write.add_argument("telnet_build", type=Path)
    write.add_argument("ncpd_build", type=Path)
    write.add_argument("receipt", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("receipt", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, str]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"missing receipt input {resolved}")
    return {"path": os.fspath(resolved), "sha256": sha256(resolved)}


def verify_file_record(label: str, record: object) -> Path:
    if not isinstance(record, dict):
        raise ValueError(f"{label} receipt record is not an object")
    path_value = record.get("path")
    expected = record.get("sha256")
    if not isinstance(path_value, str) or not isinstance(expected, str):
        raise ValueError(f"{label} receipt record is incomplete")
    path = Path(path_value)
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{label} hash is {actual}, expected {expected}")
    return path


def git_output(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", root, *arguments],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()


def git_identity(root: Path) -> dict[str, object]:
    resolved = root.expanduser().resolve()
    return {
        "path": os.fspath(resolved),
        "revision": git_output(resolved, "rev-parse", "HEAD"),
        "tracked_dirty": bool(
            git_output(
                resolved,
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--ignore-submodules=dirty",
            )
        ),
    }


def pinned_revisions() -> dict[str, str]:
    root = Path(__file__).resolve().parent.parent
    sources = tomllib.loads(
        (root / "pins" / "sources.lock.toml").read_text(encoding="utf-8")
    )["source"]
    return {source["name"]: source["revision"] for source in sources}


def validate_source_identity(label: str, identity: dict[str, object]) -> None:
    expected = pinned_revisions()[label]
    if identity["revision"] != expected:
        raise ValueError(
            f"{label} source is {identity['revision']}, expected {expected}"
        )
    if identity["tracked_dirty"]:
        raise ValueError(f"{label} tracked source is dirty")


def simulator_version(path: Path) -> str:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError(f"missing PDP-11 executable {resolved}")
    result = subprocess.run(
        [resolved, "-v"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"PDP-11 version command exited {result.returncode}")
    expected_short = pinned_revisions()["imp11a-simh"][:8]
    if f"git commit id: {expected_short}" not in result.stdout:
        raise ValueError(f"PDP-11 executable does not identify as {expected_short}")
    return result.stdout.strip()


def tree_hashes(path: Path) -> dict[str, str]:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"missing staged-source directory {resolved}")
    files = sorted(candidate for candidate in resolved.rglob("*") if candidate.is_file())
    if not files:
        raise ValueError(f"staged-source directory is empty: {resolved}")
    return {
        candidate.relative_to(resolved).as_posix(): sha256(candidate)
        for candidate in files
    }


def validate_build_logs(telnet_log: Path, ncpd_log: Path) -> None:
    telnet = telnet_log.read_text(encoding="utf-8", errors="replace")
    ncpd = ncpd_log.read_text(encoding="utf-8", errors="replace")
    revision = pinned_revisions()["imp11a-simh"][:8]
    telnet_required = (
        f"git commit id: {revision}",
        "cc -O -n -x telnet.c",
        "cc -O -n -x usrtelnetin.c",
        "1 root     7212",
        "1 root     2454",
        "/usr/bin/telnet",
        "/usr/bin/usrtelnetin",
        "Goodbye",
    )
    ncpd_required = (
        f"git commit id: {revision}",
        "cc -O -c 1main.c kr_dcode.c",
        "cc -O -x 1main.o kr_dcode.o",
        "/usr/net/etc/Largedaemon not found",
        "-r-xr--r--  1 daemon  21422",
        "Goodbye",
    )
    for label, text, required in (
        ("TELNET build log", telnet, telnet_required),
        ("NCP daemon build log", ncpd, ncpd_required),
    ):
        missing = [marker for marker in required if marker not in text]
        if missing:
            raise ValueError(f"{label} lacks required evidence: {missing}")
        if re.search(r"(?:^|\n)(?:fatal|undefined:|[^\n]* error:)", text, re.IGNORECASE):
            raise ValueError(f"{label} contains a rejected tool diagnostic")


def current_project_builders() -> dict[str, dict[str, str]]:
    scripts = Path(__file__).resolve().parent
    return {name: file_record(scripts / name) for name in BUILDER_NAMES}


def build_document(args: argparse.Namespace) -> dict[str, object]:
    network_identity = git_identity(args.network_unix_root)
    imp11a_identity = git_identity(args.imp11a_root)
    validate_source_identity("network-unix-v6", network_identity)
    validate_source_identity("imp11a-simh", imp11a_identity)

    telnet_build = args.telnet_build.expanduser().resolve()
    ncpd_build = args.ncpd_build.expanduser().resolve()
    telnet_log = telnet_build / "build-guest-telnet.console.log"
    ncpd_log = ncpd_build / "build-guest-ncpd.console.log"
    validate_build_logs(telnet_log, ncpd_log)

    artifact_paths = {
        "base_root": args.base_root,
        "base_swap": args.base_swap,
        "telnet_root": telnet_build / "guest" / "images" / IMAGE_NAMES[0],
        "telnet_swap": telnet_build / "guest" / "images" / IMAGE_NAMES[1],
        "final_root": ncpd_build / "guest" / "images" / IMAGE_NAMES[0],
        "final_swap": ncpd_build / "guest" / "images" / IMAGE_NAMES[1],
        "telnet_build_log": telnet_log,
        "ncpd_build_log": ncpd_log,
    }
    artifacts = {name: file_record(path) for name, path in artifact_paths.items()}
    pdp11 = args.pdp11.expanduser().resolve()
    return {
        "format": FORMAT_VERSION,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "sources": {
            "network-unix-v6": network_identity,
            "imp11a-simh": imp11a_identity,
        },
        "simulator": {
            **file_record(pdp11),
            "version": simulator_version(pdp11),
        },
        "builders": current_project_builders(),
        "staged_sources": {
            "telnet": {
                "path": os.fspath((telnet_build / "stage").resolve()),
                "files": tree_hashes(telnet_build / "stage"),
            },
            "ncpd": {
                "path": os.fspath((ncpd_build / "stage").resolve()),
                "files": tree_hashes(ncpd_build / "stage"),
            },
        },
        "artifacts": artifacts,
        "provenance": {
            "telnet_input_root": "base_root",
            "telnet_input_swap": "base_swap",
            "telnet_output_root": "telnet_root",
            "telnet_output_swap": "telnet_swap",
            "ncpd_input_root": "telnet_root",
            "ncpd_input_swap": "telnet_swap",
            "ncpd_output_root": "final_root",
            "ncpd_output_swap": "final_swap",
        },
    }


def write_receipt(args: argparse.Namespace) -> None:
    document = build_document(args)
    receipt = args.receipt.expanduser().resolve()
    receipt.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{receipt.name}.", dir=receipt.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, receipt)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_source_record(label: str, record: object) -> None:
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        raise ValueError(f"{label} source receipt is incomplete")
    current = git_identity(Path(record["path"]))
    validate_source_identity(label, current)
    for key in ("revision", "tracked_dirty"):
        if current[key] != record.get(key):
            raise ValueError(f"{label} receipt no longer matches {key}")


def verify_receipt(receipt: Path) -> None:
    document = json.loads(receipt.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("format") != FORMAT_VERSION:
        raise ValueError("unsupported PDP-11 build-receipt format")
    sources = document.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("PDP-11 build receipt has no source identities")
    for label in ("network-unix-v6", "imp11a-simh"):
        verify_source_record(label, sources.get(label))

    simulator = document.get("simulator")
    simulator_path = verify_file_record("PDP-11 simulator", simulator)
    if not isinstance(simulator, dict) or simulator.get("version") != simulator_version(simulator_path):
        raise ValueError("PDP-11 simulator version output changed")

    builders = document.get("builders")
    if not isinstance(builders, dict):
        raise ValueError("PDP-11 build receipt has no builder identities")
    current_builders = current_project_builders()
    for name, current in current_builders.items():
        recorded = builders.get(name)
        if not isinstance(recorded, dict) or recorded.get("sha256") != current["sha256"]:
            raise ValueError(f"builder {name} no longer matches the receipt")

    staged = document.get("staged_sources")
    if not isinstance(staged, dict):
        raise ValueError("PDP-11 build receipt has no staged-source identities")
    for label in ("telnet", "ncpd"):
        record = staged.get(label)
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError(f"{label} staged-source receipt is incomplete")
        if tree_hashes(Path(record["path"])) != record.get("files"):
            raise ValueError(f"{label} staged sources no longer match the receipt")

    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("PDP-11 build receipt has no artifact identities")
    paths = {
        name: verify_file_record(f"artifact {name}", artifacts.get(name))
        for name in (
            "base_root",
            "base_swap",
            "telnet_root",
            "telnet_swap",
            "final_root",
            "final_swap",
            "telnet_build_log",
            "ncpd_build_log",
        )
    }
    validate_build_logs(paths["telnet_build_log"], paths["ncpd_build_log"])

    expected_provenance = {
        "telnet_input_root": "base_root",
        "telnet_input_swap": "base_swap",
        "telnet_output_root": "telnet_root",
        "telnet_output_swap": "telnet_swap",
        "ncpd_input_root": "telnet_root",
        "ncpd_input_swap": "telnet_swap",
        "ncpd_output_root": "final_root",
        "ncpd_output_swap": "final_swap",
    }
    if document.get("provenance") != expected_provenance:
        raise ValueError("PDP-11 build receipt has an unexpected provenance chain")


def main() -> int:
    args = parse_args()
    try:
        if args.mode == "write":
            write_receipt(args)
            print(f"wrote PDP-11 build receipt: {args.receipt.expanduser().resolve()}")
        else:
            verify_receipt(args.receipt)
            print(f"PDP-11 build receipt: OK {args.receipt.expanduser().resolve()}")
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"PDP-11 build receipt failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
