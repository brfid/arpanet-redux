#!/usr/bin/env python3
"""Reject large blobs and known or likely third-party machine assets from Git."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
from pathlib import Path
import subprocess
import sys


MEDIA_PATTERNS = (
    "rp03.*",
    "*.rim",
    "impcode.simh",
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

ASSET_MANIFEST = "pins/arpanet-assets.sha256"


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
    parser.add_argument(
        "--asset-manifest",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
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


def parse_asset_digests(text: str, source: str) -> set[str]:
    digests: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2 or len(fields[0]) != 64:
            raise ValueError(f"invalid asset manifest line {line_number} in {source}")
        digest = fields[0].lower()
        if any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid asset digest on line {line_number} in {source}")
        if digest in digests:
            raise ValueError(f"duplicate asset digest on line {line_number} in {source}")
        digests.add(digest)
    if not digests:
        raise ValueError(f"asset digest denylist is empty: {source}")
    return digests


def known_asset_digests(manifest: Path) -> set[str]:
    return parse_asset_digests(manifest.read_text(encoding="ascii"), os.fspath(manifest))


def repository_asset_digests(root: Path, staged: bool) -> set[str]:
    if staged:
        current_bytes = run_git(root, "show", f":{ASSET_MANIFEST}")
        current_source = f"index:{ASSET_MANIFEST}"
    else:
        manifest = root / ASSET_MANIFEST
        current_bytes = manifest.read_bytes()
        current_source = os.fspath(manifest)
    current = parse_asset_digests(current_bytes.decode("ascii"), current_source)

    try:
        baseline_bytes = run_git(root, "show", f"HEAD:{ASSET_MANIFEST}")
    except subprocess.CalledProcessError:
        return current
    baseline = parse_asset_digests(
        baseline_bytes.decode("ascii"), f"HEAD:{ASSET_MANIFEST}"
    )
    removed = baseline - current
    if removed:
        raise ValueError(
            "asset digest denylist may not shrink; removed "
            + ", ".join(sorted(removed))
        )
    return current


def main() -> int:
    args = parse_args()
    if args.limit_bytes < 1:
        print("check-source-only.py: --limit-bytes must be positive", file=sys.stderr)
        return 64
    try:
        root = Path(os.fsdecode(run_git(None, "rev-parse", "--show-toplevel").strip()))
        if args.asset_manifest is None:
            denied_digests = repository_asset_digests(root, args.staged)
        else:
            denied_digests = known_asset_digests(args.asset_manifest)
        digest_cache: dict[str, str] = {}
        failures: list[str] = []
        for path in candidate_paths(root, args.staged):
            object_id, size = indexed_blob(root, path)
            if size > args.limit_bytes:
                failures.append(
                    f"{path}: indexed blob is {size} bytes; limit is {args.limit_bytes}"
                )
            if is_media(path):
                failures.append(f"{path}: vintage machine media must remain an external asset")
            if size <= args.limit_bytes:
                digest = digest_cache.get(object_id)
                if digest is None:
                    digest = hashlib.sha256(
                        run_git(root, "cat-file", "blob", object_id)
                    ).hexdigest()
                    digest_cache[object_id] = digest
                if digest in denied_digests:
                    failures.append(
                        f"{path}: content matches a known external vintage asset"
                    )
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
