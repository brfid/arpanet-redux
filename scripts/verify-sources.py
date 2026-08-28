#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path


def git_output(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} LAB_ROOT", file=sys.stderr)
        return 64

    lab_root = Path(sys.argv[1]).expanduser().resolve()
    repo_root = Path(__file__).resolve().parent.parent
    lock_path = repo_root / "pins" / "sources.lock.toml"
    sources = tomllib.loads(lock_path.read_text(encoding="utf-8"))["source"]
    failures: list[str] = []

    for source in sources:
        checkout = lab_root / source["checkout"]
        if not checkout.is_dir():
            failures.append(f"{source['name']}: missing checkout {checkout}")
            continue
        try:
            actual = git_output(checkout, "rev-parse", "HEAD")
            dirty = git_output(
                checkout,
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--ignore-submodules=dirty",
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
            failures.append(f"{source['name']}: tracked files are modified")
            continue
        print(f"{source['name']}: OK {actual}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
