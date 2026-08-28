#!/usr/bin/env python3
"""Reject large blobs and likely third-party machine media from Git."""

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import subprocess
import sys


MEDIA_PATTERNS = (
    "rp03.*",
    "dskdmp.rim",
    "*.tap",
    "*.dsk",
    "*.dsk.gz",
    "*.img",
    "*.raw",
    "*.iso",
    "*.qcow",
    "*.qcow2",
    "*.vhd",
    "*.vhdx",
    "*.vmdk",
)


def run_git(root: Path | None, *arguments: str) -> bytes:
    command = ["git"]
    if root is not None:
        command.extend(("-C", os.fspath(root)))
    command.extend(arguments)
    return subprocess.check_output(command, stderr=subprocess.PIPE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--limit-bytes", type=int, default=1024 * 1024)
    return parser.parse_args()


def candidate_paths(root: Path, staged: bool) -> list[str]:
    if staged:
        output = run_git(
            root,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
        )
    else:
        output = run_git(root, "ls-files", "-z")
    return [os.fsdecode(item) for item in output.split(b"\0") if item]


def indexed_blob(root: Path, path: str) -> tuple[str, int]:
    listing = run_git(root, "ls-files", "--stage", "-z", "--", path)
    entries = [entry for entry in listing.split(b"\0") if entry]
    if not entries:
        raise ValueError(f"path is not indexed: {path}")
    header, _separator, _indexed_path = entries[0].partition(b"\t")
    fields = header.split()
    if len(fields) != 3:
        raise ValueError(f"unexpected index entry for {path}")
    object_id = fields[1].decode("ascii")
    size = int(run_git(root, "cat-file", "-s", object_id).strip())
    return object_id, size


def is_media(path: str) -> bool:
    basename = Path(path).name.lower()
    return any(fnmatch.fnmatchcase(basename, pattern) for pattern in MEDIA_PATTERNS)


def main() -> int:
    args = parse_args()
    if args.limit_bytes < 1:
        print("check-source-only.py: --limit-bytes must be positive", file=sys.stderr)
        return 64
    try:
        root = Path(os.fsdecode(run_git(None, "rev-parse", "--show-toplevel").strip()))
        failures: list[str] = []
        for path in candidate_paths(root, args.staged):
            _object_id, size = indexed_blob(root, path)
            if size > args.limit_bytes:
                failures.append(
                    f"{path}: indexed blob is {size} bytes; limit is {args.limit_bytes}"
                )
            if is_media(path):
                failures.append(f"{path}: vintage machine media must remain an external asset")
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as error:
        print(f"check-source-only.py: {error}", file=sys.stderr)
        return 1

    if failures:
        print("source-only repository guard failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
