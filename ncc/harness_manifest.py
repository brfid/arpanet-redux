"""Line-oriented manifest primitives used by the runtime harness."""

from __future__ import annotations

from pathlib import Path
import re


def append_manifest(path: Path, key: str, value: str | int) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
        raise ValueError(f"invalid manifest key: {key}")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{key}={value}\n")
