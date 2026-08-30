#!/usr/bin/env python3
"""Write or verify a receipt binding clean ITS media to source state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import tomllib


FORMAT_VERSION = 1
ARTIFACT_NAMES = ("dskdmp.rim", "rp03.0", "rp03.1", "rp03.2", "rp03.3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("write", "verify"):
        command = subparsers.add_parser(mode)
        command.add_argument("its_root", type=Path)
        command.add_argument("receipt", type=Path)
        command.add_argument("--emulator", default="pdp10-ka")
    return parser.parse_args()


def git_output(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", root, *arguments],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pinned_revision() -> str:
    repo_root = Path(__file__).resolve().parent.parent
    lock_path = repo_root / "pins" / "sources.lock.toml"
    sources = tomllib.loads(lock_path.read_text(encoding="utf-8"))["source"]
    return next(
        source["revision"] for source in sources if source["name"] == "pdp10-its"
    )


def target_is_up_to_date(root: Path, emulator: str) -> bool:
    result = subprocess.run(
        ["make", "-q", f"EMULATOR={emulator}", "its"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise ValueError(f"could not inspect ITS build target: {result.stderr.strip()}")


def current_identity(root: Path, emulator: str) -> dict[str, object]:
    revision = git_output(root, "rev-parse", "HEAD")
    dirty = bool(
        git_output(
            root,
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--ignore-submodules=none",
        )
    )
    submodule_output = git_output(root, "submodule", "status", "--recursive")
    submodules = submodule_output.splitlines() if submodule_output else []
    output_root = root / "out" / emulator
    artifacts = {}
    for name in ARTIFACT_NAMES:
        path = output_root / name
        if not path.is_file():
            raise ValueError(f"missing ITS build artifact {path}")
        artifacts[name] = sha256(path)
    return {
        "source_revision": revision,
        "source_tracked_dirty": dirty,
        "recursive_submodules": submodules,
        "emulator": emulator,
        "make_target": "its",
        "make_target_up_to_date": target_is_up_to_date(root, emulator),
        "artifacts": artifacts,
    }


def validate_identity(identity: dict[str, object]) -> None:
    expected = pinned_revision()
    if identity["source_revision"] != expected:
        raise ValueError(
            f"pdp10-its source is {identity['source_revision']}, expected {expected}"
        )
    if identity["source_tracked_dirty"]:
        raise ValueError("pdp10-its tracked source or initialized submodule is dirty")
    if not identity["make_target_up_to_date"]:
        raise ValueError("make reports that the ITS target is not a no-op rebuild")


def write_receipt(root: Path, receipt: Path, emulator: str) -> None:
    identity = current_identity(root, emulator)
    validate_identity(identity)
    document = {
        "format": FORMAT_VERSION,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        **identity,
    }
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


def verify_receipt(root: Path, receipt: Path, emulator: str) -> None:
    document = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("ITS build receipt must be a JSON object")
    if document.get("format") != FORMAT_VERSION:
        raise ValueError("unsupported ITS build-receipt format")
    identity = current_identity(root, emulator)
    validate_identity(identity)
    for key in (
        "source_revision",
        "source_tracked_dirty",
        "recursive_submodules",
        "emulator",
        "make_target",
        "make_target_up_to_date",
        "artifacts",
    ):
        if document.get(key) != identity[key]:
            raise ValueError(f"ITS build receipt no longer matches {key}")


def main() -> int:
    args = parse_args()
    root = args.its_root.expanduser().resolve()
    receipt = args.receipt.expanduser().resolve()
    try:
        if args.mode == "write":
            write_receipt(root, receipt, args.emulator)
            print(f"wrote ITS build receipt: {receipt}")
        else:
            verify_receipt(root, receipt, args.emulator)
            print(f"ITS build receipt: OK {receipt}")
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"ITS build receipt failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
