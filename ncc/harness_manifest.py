"""Line-oriented manifest primitives used by the runtime harness."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re


def append_manifest(path: Path, key: str, value: str | int) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
        raise ValueError(f"invalid manifest key: {key}")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{key}={value}\n")


def read_manifest(path: Path) -> dict[str, str]:
    """Read a line-oriented run manifest fail closed."""

    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "=" not in line:
            raise ValueError(f"manifest line {number} has no '=' separator")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise ValueError(f"manifest line {number} has an invalid or duplicate key")
        values[key] = value
    return values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
