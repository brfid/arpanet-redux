#!/usr/bin/env python3
"""Select and resolve stable artifacts in the external laboratory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


ARTIFACTS = {
    "pdp11-build": {
        "marker": "pdp11-build-receipt.json",
        "pattern": "*/pdp11-build-receipt.json",
    },
    "ncc-coexistence": {
        "marker": "verdict.json",
        "pattern": "ncc-pdp11-its-coexistence-*/verdict.json",
        "kind": "ncc-pdp11-its-coexistence-verdict",
    },
    "ncc-failover": {
        "marker": "verdict.json",
        "pattern": "ncc-pdp11-its-application-failover-*/verdict.json",
        "kind": "ncc-pdp11-its-application-failover-verdict",
    },
}
KEYS = tuple(ARTIFACTS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    select = subparsers.add_parser("select", help="persist one artifact selection")
    select.add_argument("lab_root", type=Path)
    select.add_argument("key", choices=KEYS)
    select.add_argument("path", type=Path)

    resolve = subparsers.add_parser(
        "resolve",
        help="print the selected artifact, or discover the newest usable one",
    )
    resolve.add_argument("lab_root", type=Path)
    resolve.add_argument("key", choices=KEYS)
    resolve.add_argument("--results-root", type=Path)
    resolve.add_argument("--no-discover", action="store_true")
    return parser.parse_args()


def state_path(lab_root: Path, key: str) -> Path:
    return lab_root.expanduser().resolve() / "state" / key


def validate_artifact(key: str, path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"{key} directory is missing: {resolved}")
    specification = ARTIFACTS[key]
    marker = resolved / specification["marker"]
    if not marker.is_file():
        raise ValueError(f"{key} marker is missing: {marker}")
    expected_kind = specification.get("kind")
    if expected_kind is not None:
        verdict = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(verdict, dict):
            raise ValueError(f"{key} verdict is not an object: {marker}")
        if verdict.get("kind") != expected_kind or verdict.get("passed") is not True:
            raise ValueError(f"{key} verdict is not a completed passing result: {marker}")
        outcome = resolved / "outcome.txt"
        if not outcome.is_file() or outcome.read_text(encoding="ascii") != "passed\n":
            raise ValueError(f"{key} outcome is not exactly passed: {outcome}")
    return resolved


def read_selection(lab_root: Path, key: str) -> Path | None:
    selection = state_path(lab_root, key)
    if not selection.exists():
        return None
    text = selection.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0] or "\x00" in lines[0]:
        raise ValueError(f"invalid {key} selection file: {selection}")
    return validate_artifact(key, Path(lines[0]))


def discover_artifact(results_root: Path, key: str) -> Path | None:
    candidates = []
    for marker in results_root.expanduser().glob(ARTIFACTS[key]["pattern"]):
        if not marker.is_file():
            continue
        try:
            validate_artifact(key, marker.parent)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        candidates.append(marker.parent)
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def write_selection(lab_root: Path, key: str, path: Path) -> Path:
    resolved = validate_artifact(key, path)
    destination = state_path(lab_root, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"{resolved}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return resolved


def main() -> int:
    args = parse_args()
    try:
        if args.command == "select":
            selected = write_selection(args.lab_root, args.key, args.path)
            print(f"Selected {args.key}: {selected}")
            return 0

        selected = read_selection(args.lab_root, args.key)
        if selected is None and not args.no_discover:
            results_root = args.results_root or args.lab_root / "results"
            selected = discover_artifact(results_root, args.key)
        if selected is None:
            return 1
        print(selected)
        return 0
    except (OSError, ValueError) as error:
        print(f"cannot resolve laboratory state: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
