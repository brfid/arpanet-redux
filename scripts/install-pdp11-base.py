#!/usr/bin/env python3
"""Verify and install user-supplied PDP-11 base media outside the repository."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile


IMAGE_NAMES = ("ncp_root.rl01", "ncp_swap.rl01")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab_root", type=Path)
    parser.add_argument("root_image", type=Path)
    parser.add_argument("swap_image", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_expected(repo_root: Path) -> dict[str, str]:
    manifest = repo_root / "pins" / "pdp11-base-assets.sha256"
    expected: dict[str, str] = {}
    for line_number, line in enumerate(
        manifest.read_text(encoding="ascii").splitlines(), start=1
    ):
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2 or len(fields[0]) != 64:
            raise ValueError(f"invalid base-media pin at line {line_number}")
        name = Path(fields[1]).name
        if name in expected:
            raise ValueError(f"duplicate base-media pin for {name}")
        expected[name] = fields[0]
    if set(expected) != set(IMAGE_NAMES):
        raise ValueError("base-media pins do not name the required root and swap images")
    return expected


def verify_source(path: Path, expected: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"media source is missing: {resolved}")
    actual = sha256(resolved)
    if actual != expected:
        raise ValueError(f"{resolved}: SHA-256 is {actual}, expected {expected}")
    return resolved


def install_one(source: Path, destination: Path, expected: str) -> str:
    if destination.exists():
        if not destination.is_file() or sha256(destination) != expected:
            raise ValueError(
                f"refusing to replace existing nonmatching media: {destination}"
            )
        return "already installed"

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        if sha256(temporary) != expected:
            raise ValueError(f"copied media failed verification: {temporary}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return "installed"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    try:
        expected = load_expected(repo_root)
        sources = {
            IMAGE_NAMES[0]: verify_source(args.root_image, expected[IMAGE_NAMES[0]]),
            IMAGE_NAMES[1]: verify_source(args.swap_image, expected[IMAGE_NAMES[1]]),
        }
        destination_root = (
            args.lab_root.expanduser().resolve()
            / "work"
            / "unix-v6-install"
            / "images"
        )
        for name in IMAGE_NAMES:
            destination = destination_root / name
            status = install_one(sources[name], destination, expected[name])
            print(f"{name}: {status} at {destination}")
    except (OSError, ValueError) as error:
        print(f"cannot install PDP-11 base media: {error}", file=sys.stderr)
        return 1
    print("Base media remain external to Git and retain their original terms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
