#!/usr/bin/env python3
"""Reject large blobs and known or likely third-party machine assets from Git."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import fnmatch
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys


MEDIA_PATTERNS = (
    "rp03.*",
    "*.rim",
    "impcode.simh",
    "*.tap",
    "*.tape",
    "*.magtape",
    "*.tu56",
    "*.tu58",
    "*.dsk",
    "*.dsk.gz",
    "*.disk",
    "*.rk05",
    "*.rl01",
    "*.rl02",
    "*.img",
    "*.raw",
    "*.iso",
    "*.dmg",
    "*.imd",
    "*.td0",
    "*.qcow",
    "*.qcow2",
    "*.vhd",
    "*.vhdx",
    "*.vmdk",
    "*.rom",
    "*.bin",
    "*.hex",
    "*.s19",
    "*.srec",
    "*.sav",
    "*.core",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.tar.bz2",
    "*.tbz",
    "*.tbz2",
    "*.tar.xz",
    "*.txz",
    "*.tar.zst",
    "*.tzst",
    "*.gz",
    "*.bz2",
    "*.xz",
    "*.zst",
    "*.7z",
    "*.rar",
    "*.cpio",
)

ASSET_MANIFEST = "pins/arpanet-assets.sha256"
LFS_VERSION = b"version https://git-lfs.github.com/spec/v1"
LFS_OID = re.compile(rb"oid sha256:[0-9a-f]{64}\Z")
LFS_SIZE = re.compile(rb"size [0-9]+\Z")


@dataclass(frozen=True)
class Candidate:
    path: str
    object_id: str
    size: int
    historical: bool = False


def run_git(root: Path | None, *arguments: str) -> bytes:
    command = ["git"]
    if root is not None:
        command.extend(("-C", os.fspath(root)))
    command.extend(arguments)
    return subprocess.check_output(command, stderr=subprocess.PIPE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="reject external machine assets from a source-only Git repository"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--staged",
        action="store_true",
        help="check only paths added or changed in the index",
    )
    mode.add_argument(
        "--history",
        action="store_true",
        help="check every blob and historical path reachable from REVISION",
    )
    parser.add_argument("--limit-bytes", type=int, default=1024 * 1024)
    parser.add_argument(
        "--asset-manifest",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "revisions",
        metavar="REVISION",
        nargs="*",
        help="history tips to scan (default: HEAD; valid only with --history)",
    )
    args = parser.parse_args()
    if args.revisions and not args.history:
        parser.error("REVISION arguments require --history")
    return args


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


def indexed_candidates(root: Path, staged: bool) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in candidate_paths(root, staged):
        object_id, size = indexed_blob(root, path)
        candidates.append(Candidate(path, object_id, size))
    return candidates


def resolved_commits(root: Path, revisions: list[str]) -> list[str]:
    if run_git(root, "rev-parse", "--is-shallow-repository").strip() == b"true":
        raise ValueError("history scan requires a complete, non-shallow clone")
    tips: list[str] = []
    for revision in revisions or ["HEAD"]:
        resolved = run_git(
            root,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{revision}^{{commit}}",
        ).strip()
        if not resolved or b"\n" in resolved:
            raise ValueError(f"revision does not resolve to one commit: {revision}")
        tips.append(resolved.decode("ascii"))
    return [
        line.decode("ascii")
        for line in run_git(root, "rev-list", *tips).splitlines()
        if line
    ]


def historical_candidates(root: Path, commits: list[str]) -> list[Candidate]:
    """Return every distinct blob/path pair in the reachable commit trees."""

    candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    size_cache: dict[str, int] = {}
    for commit in commits:
        tree = run_git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            metadata, separator, encoded_path = entry.partition(b"\t")
            fields = metadata.split()
            if not separator or len(fields) != 3:
                raise ValueError(f"unexpected tree entry in commit {commit}")
            _mode, object_type, encoded_object_id = fields
            if object_type != b"blob":
                continue
            object_id = encoded_object_id.decode("ascii")
            path = os.fsdecode(encoded_path)
            key = (object_id, path)
            if key in seen:
                continue
            seen.add(key)
            size = size_cache.get(object_id)
            if size is None:
                size = int(run_git(root, "cat-file", "-s", object_id).strip())
                size_cache[object_id] = size
            candidates.append(Candidate(path, object_id, size, historical=True))
    return candidates


def is_media(path: str) -> bool:
    basename = Path(path).name.lower()
    return any(fnmatch.fnmatchcase(basename, pattern) for pattern in MEDIA_PATTERNS)


def is_git_lfs_pointer(content: bytes) -> bool:
    lines = content.splitlines()
    return (
        bool(lines)
        and lines[0] == LFS_VERSION
        and any(LFS_OID.fullmatch(line) for line in lines[1:])
        and any(LFS_SIZE.fullmatch(line) for line in lines[1:])
    )


def historical_suffix(candidate: Candidate) -> str:
    if not candidate.historical:
        return ""
    return f" [historical blob {candidate.object_id[:12]}]"


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


def include_historical_asset_digests(
    root: Path, commits: list[str], current: set[str]
) -> set[str]:
    historical: set[str] = set()
    for commit in commits:
        try:
            manifest_bytes = run_git(root, "show", f"{commit}:{ASSET_MANIFEST}")
        except subprocess.CalledProcessError:
            continue
        historical.update(
            parse_asset_digests(
                manifest_bytes.decode("ascii"),
                f"{commit}:{ASSET_MANIFEST}",
            )
        )
    removed = historical - current
    if removed:
        raise ValueError(
            "asset digest denylist may not shrink across scanned history; removed "
            + ", ".join(sorted(removed))
        )
    return current | historical


def main() -> int:
    args = parse_args()
    if args.limit_bytes < 1:
        print("check-source-only.py: --limit-bytes must be positive", file=sys.stderr)
        return 64
    try:
        root = Path(os.fsdecode(run_git(None, "rev-parse", "--show-toplevel").strip()))
        commits = resolved_commits(root, args.revisions) if args.history else []
        if args.asset_manifest is None:
            denied_digests = repository_asset_digests(root, args.staged)
            if args.history:
                denied_digests = include_historical_asset_digests(
                    root, commits, denied_digests
                )
        else:
            denied_digests = known_asset_digests(args.asset_manifest)
        digest_cache: dict[str, str] = {}
        content_cache: dict[str, bytes] = {}
        failures: list[str] = []
        if args.history:
            candidates = historical_candidates(root, commits)
        else:
            candidates = indexed_candidates(root, args.staged)
        for candidate in candidates:
            suffix = historical_suffix(candidate)
            if candidate.size > args.limit_bytes:
                blob_kind = "historical blob" if candidate.historical else "indexed blob"
                failures.append(
                    f"{candidate.path}: {blob_kind} is {candidate.size} bytes; "
                    f"limit is {args.limit_bytes}{suffix}"
                )
            if is_media(candidate.path):
                failures.append(
                    f"{candidate.path}: vintage machine media or archives must remain "
                    f"external assets{suffix}"
                )
            if candidate.size <= args.limit_bytes:
                content = content_cache.get(candidate.object_id)
                if content is None:
                    content = run_git(root, "cat-file", "blob", candidate.object_id)
                    content_cache[candidate.object_id] = content
                if is_git_lfs_pointer(content):
                    failures.append(
                        f"{candidate.path}: Git LFS pointers are not permitted in the "
                        f"source-only repository{suffix}"
                    )
                digest = digest_cache.get(candidate.object_id)
                if digest is None:
                    digest = hashlib.sha256(content).hexdigest()
                    digest_cache[candidate.object_id] = digest
                if digest in denied_digests:
                    failures.append(
                        f"{candidate.path}: content matches a known external vintage "
                        f"asset{suffix}"
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
