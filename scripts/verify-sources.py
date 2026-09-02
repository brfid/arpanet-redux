#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path


def git_output(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args],
        stderr=subprocess.STDOUT,
        text=True,
    ).rstrip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("lab_root", type=Path)
    parser.add_argument(
        "--name",
        action="append",
        default=[],
        help="verify only this named source; may be repeated",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lab_root = args.lab_root.expanduser().resolve()
    repo_root = Path(__file__).resolve().parent.parent
    lock_path = repo_root / "pins" / "sources.lock.toml"
    sources = tomllib.loads(lock_path.read_text(encoding="utf-8"))["source"]
    known_names = {source["name"] for source in sources}
    requested_names = set(args.name)
    unknown_names = requested_names - known_names
    if unknown_names:
        print(
            "unknown source name(s): " + ", ".join(sorted(unknown_names)),
            file=sys.stderr,
        )
        return 64
    if requested_names:
        sources = [source for source in sources if source["name"] in requested_names]
    failures: list[str] = []

    for source in sources:
        checkout = lab_root / source["checkout"]
        if not checkout.is_dir():
            failures.append(f"{source['name']}: missing checkout {checkout}")
            continue
        try:
            actual = git_output(checkout, "rev-parse", "HEAD")
            # Nested checkouts have their own exact lock rows and can intentionally
            # differ from a parent repository's historical gitlink. Their own rows
            # supply the replacement revision and tracked-state evidence.
            dirty = git_output(
                checkout,
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--ignore-submodules=all",
            )
        except subprocess.CalledProcessError as error:
            details = error.output.strip() or f"git exited {error.returncode}"
            failures.append(f"{source['name']}: {details}")
            continue

        if actual != source["revision"]:
            failures.append(
                f"{source['name']}: expected {source['revision']}, found {actual}"
            )
            continue
        if dirty:
            changed = ", ".join(line[3:] for line in dirty.splitlines())
            failures.append(
                f"{source['name']}: tracked files are modified: {changed}"
            )
            continue
        print(f"{source['name']}: OK {actual}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
