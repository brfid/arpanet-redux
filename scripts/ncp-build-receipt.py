#!/usr/bin/env python3
"""Write or verify a receipt binding linux-ncp executables to pinned source."""

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
EXECUTABLES = ("src/ncpd", "apps/ncp-ping")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("write", "verify"):
        command = subparsers.add_parser(mode)
        command.add_argument("linux_ncp_root", type=Path)
        command.add_argument("receipt", type=Path)
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
        source["revision"] for source in sources if source["name"] == "linux-ncp"
    )


def current_identity(root: Path) -> dict[str, object]:
    revision = git_output(root, "rev-parse", "HEAD")
    dirty = bool(
        git_output(
            root,
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--ignore-submodules=dirty",
        )
    )
    hashes = {}
    for relative in EXECUTABLES:
        path = root / relative
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"missing executable {path}")
        hashes[relative] = sha256(path)
    return {
        "source_revision": revision,
        "source_tracked_dirty": dirty,
        "executables": hashes,
    }


def compiler_identity() -> str:
    try:
        result = subprocess.run(
            [os.environ.get("CC", "cc"), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    lines = result.stdout.splitlines()
    return lines[0] if result.returncode == 0 and lines else "unavailable"


def write_receipt(root: Path, receipt: Path) -> None:
    identity = current_identity(root)
    expected = pinned_revision()
    if identity["source_revision"] != expected:
        raise ValueError(
            f"linux-ncp source is {identity['source_revision']}, expected {expected}"
        )
    if identity["source_tracked_dirty"]:
        raise ValueError("linux-ncp tracked source is dirty")
    document = {
        "format": FORMAT_VERSION,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "compiler": compiler_identity(),
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


def verify_receipt(root: Path, receipt: Path) -> None:
    document = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("NCP build receipt must be a JSON object")
    if document.get("format") != FORMAT_VERSION:
        raise ValueError("unsupported NCP build-receipt format")
    identity = current_identity(root)
    expected = pinned_revision()
    if identity["source_revision"] != expected:
        raise ValueError(
            f"linux-ncp source is {identity['source_revision']}, expected {expected}"
        )
    if identity["source_tracked_dirty"]:
        raise ValueError("linux-ncp tracked source is dirty")
    for key in ("source_revision", "source_tracked_dirty", "executables"):
        if document.get(key) != identity[key]:
            raise ValueError(f"NCP build receipt no longer matches {key}")


def main() -> int:
    args = parse_args()
    root = args.linux_ncp_root.expanduser().resolve()
    receipt = args.receipt.expanduser().resolve()
    try:
        if args.mode == "write":
            write_receipt(root, receipt)
            print(f"wrote NCP build receipt: {receipt}")
        else:
            verify_receipt(root, receipt)
            print(f"NCP build receipt: OK {receipt}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"NCP build receipt failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
