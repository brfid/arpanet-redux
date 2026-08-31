#!/usr/bin/env python3
"""Verify that simulator binaries identify with their pinned source commits."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h316", type=Path)
    parser.add_argument("--pdp10-ka", type=Path)
    parser.add_argument("--pdp11", type=Path)
    return parser.parse_args()


def pinned_revisions(lock_path: Path) -> dict[str, str]:
    sources = tomllib.loads(lock_path.read_text(encoding="utf-8"))["source"]
    return {source["name"]: source["revision"] for source in sources}


def verify_binary(label: str, path: Path, expected_revision: str) -> str | None:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        return f"{label}: missing executable {resolved}"
    try:
        result = subprocess.run(
            [resolved, "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"{label}: could not read version: {error}"
    expected_short = expected_revision[:8]
    if result.returncode != 0:
        return f"{label}: version command exited {result.returncode}"
    if f"git commit id: {expected_short}" not in result.stdout:
        return f"{label}: expected embedded commit {expected_short}"
    print(f"{label}: OK embedded commit {expected_short}")
    return None


def main() -> int:
    args = parse_args()
    if args.h316 is None and args.pdp10_ka is None and args.pdp11 is None:
        print("select at least one simulator binary", file=sys.stderr)
        return 64

    repo_root = Path(__file__).resolve().parent.parent
    revisions = pinned_revisions(repo_root / "pins" / "sources.lock.toml")
    checks = []
    if args.h316 is not None:
        checks.append(("h316-simh", args.h316, revisions["h316-simh"]))
    if args.pdp10_ka is not None:
        checks.append(("ka10-simh", args.pdp10_ka, revisions["ka10-simh"]))
    if args.pdp11 is not None:
        checks.append(("imp11a-simh", args.pdp11, revisions["imp11a-simh"]))

    failures = [
        failure
        for label, path, revision in checks
        if (failure := verify_binary(label, path, revision)) is not None
    ]
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
