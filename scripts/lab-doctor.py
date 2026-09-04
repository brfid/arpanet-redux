#!/usr/bin/env python3
"""Diagnose whether the external lab can start TELNET and the NCC console."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdp11_base import default_image_dir, verify_pair  # noqa: E402

RUNTIME_SOURCE_NAMES = (
    "arpanet-in-a-box",
    "linux-ncp",
    "h316-simh",
    "ka10-simh",
    "imp11a-simh",
    "network-unix-v6",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab_root", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--arpanet-root", type=Path)
    parser.add_argument("--linux-ncp-root", type=Path)
    parser.add_argument("--h316-root", type=Path)
    parser.add_argument("--ka10-root", type=Path)
    parser.add_argument("--imp11a-root", type=Path)
    parser.add_argument("--network-unix-root", type=Path)
    parser.add_argument("--h316", type=Path)
    parser.add_argument("--pdp10-ka", type=Path)
    parser.add_argument("--pdp11", type=Path)
    parser.add_argument("--base-root", type=Path)
    parser.add_argument("--base-swap", type=Path)
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--pdp11-build-root", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(checkout: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", os.fspath(checkout), *arguments],
        stderr=subprocess.STDOUT,
        text=True,
    ).rstrip()


def report(ok: bool, label: str, details: str) -> bool:
    print(f"[{'ok' if ok else 'missing'}] {label}: {details}")
    return ok


def load_sources(repo_root: Path) -> dict[str, dict[str, str]]:
    lock_path = repo_root / "pins" / "sources.lock.toml"
    sources = tomllib.loads(lock_path.read_text(encoding="utf-8"))["source"]
    return {source["name"]: source for source in sources}


def check_source(
    name: str, checkout: Path, expected_revision: str
) -> tuple[bool, str]:
    if not checkout.is_dir():
        return False, f"checkout not found at {checkout}"
    try:
        actual = git_output(checkout, "rev-parse", "HEAD")
        # Nested runtime checkouts are independently pinned and may intentionally
        # differ from the parent's historical gitlink.
        dirty = git_output(
            checkout,
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--ignore-submodules=all",
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"cannot inspect {checkout}: {error}"
    if actual != expected_revision:
        return False, f"found {actual}; expected {expected_revision}"
    if dirty:
        changed = ", ".join(line[3:] for line in dirty.splitlines())
        return False, f"tracked files changed: {changed}"
    return True, actual


def load_hash_manifest(path: Path) -> list[tuple[str, Path]]:
    records: list[tuple[str, Path]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="ascii").splitlines(), start=1
    ):
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2 or len(fields[0]) != 64:
            raise ValueError(f"invalid hash manifest line {line_number} in {path}")
        records.append((fields[0], Path(fields[1])))
    if not records:
        raise ValueError(f"empty hash manifest: {path}")
    return records


def check_hashes(
    root: Path,
    records: list[tuple[str, Path]],
    *,
    prefix: str | None = None,
) -> tuple[bool, str]:
    selected = [
        (expected, relative)
        for expected, relative in records
        if prefix is None or relative.as_posix().startswith(prefix)
    ]
    failures: list[str] = []
    for expected, relative in selected:
        candidate = root / relative
        if not candidate.is_file():
            failures.append(f"missing {candidate}")
        else:
            actual = sha256(candidate)
            if actual != expected:
                failures.append(f"{candidate} has SHA-256 {actual}")
    if failures:
        return False, "; ".join(failures)
    return True, f"{len(selected)} exact SHA-256 identities"


def check_simulator(
    label: str, binary: Path, expected_revision: str
) -> tuple[bool, str]:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return False, f"executable not found at {binary}"
    try:
        result = subprocess.run(
            [binary, "-v"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"cannot read version: {error}"
    expected_short = expected_revision[:8]
    if result.returncode != 0:
        return False, f"version command exited {result.returncode}"
    if f"git commit id: {expected_short}" not in result.stdout:
        return False, f"does not identify pinned commit {expected_short}"
    return True, f"embedded commit {expected_short}"


def read_state_build(lab_root: Path) -> tuple[Path | None, str | None]:
    selection = lab_root / "state" / "pdp11-build"
    if not selection.exists():
        return None, None
    try:
        lines = selection.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return None, f"cannot read {selection}: {error}"
    if len(lines) != 1 or not lines[0] or "\x00" in lines[0]:
        return None, f"invalid selection file {selection}"
    return Path(lines[0]).expanduser().resolve(), None


def discover_build(results_root: Path) -> Path | None:
    candidates = [
        marker.parent
        for marker in results_root.glob("*/pdp11-build-receipt.json")
        if marker.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def verify_build_receipt(
    repo_root: Path, python: Path, build_root: Path
) -> tuple[bool, str]:
    receipt = build_root / "pdp11-build-receipt.json"
    if not receipt.is_file():
        return False, f"receipt not found at {receipt}"
    result = subprocess.run(
        [python, repo_root / "scripts" / "pdp11-build-receipt.py", "verify", receipt],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    detail = result.stdout.strip().splitlines()
    if result.returncode != 0:
        return False, detail[-1] if detail else f"verification exited {result.returncode}"
    return True, os.fspath(build_root)


def check_python(python: Path) -> tuple[bool, bool, str]:
    if not python.is_file() or not os.access(python, os.X_OK):
        return False, False, f"interpreter not found at {python}"
    version = subprocess.run(
        [python, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if version.returncode != 0:
        return False, False, f"interpreter failed: {version.stdout.strip()}"
    version_ok = tuple(int(part) for part in version.stdout.strip().split(".")) >= (
        3,
        11,
        0,
    )
    pexpect = subprocess.run(
        [
            python,
            "-c",
            "import importlib.metadata as m; print(m.version('pexpect'), m.version('ptyprocess'))",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    details = f"Python {version.stdout.strip()}"
    dependency_versions = pexpect.stdout.strip()
    dependency_ok = (
        pexpect.returncode == 0 and dependency_versions == "4.9.0 0.7.0"
    )
    if pexpect.returncode == 0:
        details += f", pexpect/ptyprocess {dependency_versions}"
    else:
        details += ", pexpect unavailable"
    return version_ok, dependency_ok, details


def resolved_paths(args: argparse.Namespace) -> dict[str, Path]:
    lab = args.lab_root.expanduser().resolve()
    arpanet = (args.arpanet_root or lab / "work" / "arpanet").expanduser().resolve()
    linux_ncp = (
        args.linux_ncp_root or arpanet / "src" / "linux-ncp"
    ).expanduser().resolve()
    h316_root = (args.h316_root or linux_ncp / "test" / "simh").expanduser().resolve()
    ka10_root = (
        args.ka10_root or lab / "work" / "ka10-simh"
    ).expanduser().resolve()
    imp11a_root = (
        args.imp11a_root or lab / "work" / "open-simh"
    ).expanduser().resolve()
    network_unix = (
        args.network_unix_root or lab / "work" / "network-unix-v6"
    ).expanduser().resolve()
    python_input = args.python or lab / ".venv" / "bin" / "python3"
    if args.python is not None and len(args.python.parts) == 1:
        located_python = shutil.which(os.fspath(args.python))
        if located_python is not None:
            python_input = Path(located_python)
    return {
        "lab": lab,
        "arpanet": arpanet,
        "linux_ncp": linux_ncp,
        "h316_root": h316_root,
        "ka10_root": ka10_root,
        "imp11a_root": imp11a_root,
        "network_unix": network_unix,
        "h316": (args.h316 or h316_root / "BIN" / "h316").expanduser().resolve(),
        "pdp10_ka": (args.pdp10_ka or ka10_root / "BIN" / "pdp10-ka").expanduser().resolve(),
        "pdp11": (args.pdp11 or imp11a_root / "BIN" / "pdp11").expanduser().resolve(),
        "base_root": (
            args.base_root
            or default_image_dir(lab) / "ncp_root.rl01"
        ).expanduser().resolve(),
        "base_swap": (
            args.base_swap
            or default_image_dir(lab) / "ncp_swap.rl01"
        ).expanduser().resolve(),
        "results": (args.results_root or lab / "results").expanduser().resolve(),
        "python": Path(os.path.abspath(python_input.expanduser())),
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    paths = resolved_paths(args)
    print("ARPANET Redux laboratory doctor")
    print(f"lab: {paths['lab']}")
    failures = False
    setup_problem = False
    base_problem = False
    build_problem = False

    missing_commands = [name for name in ("git", "make", "cc") if shutil.which(name) is None]
    host_ok = not missing_commands
    failures |= not report(
        host_ok,
        "host tools",
        "git, make, and C compiler" if host_ok else "missing " + ", ".join(missing_commands),
    )
    setup_problem |= not host_ok

    python_ok, pexpect_ok, python_details = check_python(paths["python"])
    failures |= not report(python_ok, "lab Python", python_details)
    setup_problem |= not python_ok

    sources = load_sources(repo_root)
    source_paths = {
        "arpanet-in-a-box": paths["arpanet"],
        "linux-ncp": paths["linux_ncp"],
        "h316-simh": paths["h316_root"],
        "ka10-simh": paths["ka10_root"],
        "imp11a-simh": paths["imp11a_root"],
        "network-unix-v6": paths["network_unix"],
    }
    for name in RUNTIME_SOURCE_NAMES:
        ok, details = check_source(name, source_paths[name], sources[name]["revision"])
        failures |= not report(ok, name, details)
        setup_problem |= not ok

    try:
        asset_records = load_hash_manifest(repo_root / "pins" / "arpanet-assets.sha256")
        assets_ok, assets_details = check_hashes(
            paths["arpanet"], asset_records, prefix="mini/"
        )
    except (OSError, ValueError) as error:
        assets_ok, assets_details = False, str(error)
    failures |= not report(assets_ok, "historical runtime assets", assets_details)
    setup_problem |= not assets_ok

    try:
        profile = verify_pair(paths["base_root"], paths["base_swap"])
        bases_ok = report(True, "PDP-11 base media", f"exact pinned pair ({profile})")
    except (OSError, ValueError, KeyError) as error:
        bases_ok = False
        report(False, "PDP-11 base media", str(error))
    failures |= not bases_ok
    base_problem |= not bases_ok

    simulator_checks = (
        ("H316 simulator", paths["h316"], sources["h316-simh"]["revision"]),
        ("KA10 simulator", paths["pdp10_ka"], sources["ka10-simh"]["revision"]),
        ("PDP-11 simulator", paths["pdp11"], sources["imp11a-simh"]["revision"]),
    )
    for label, binary, revision in simulator_checks:
        ok, details = check_simulator(label, binary, revision)
        failures |= not report(ok, label, details)
        setup_problem |= not ok

    state_error = None
    if args.pdp11_build_root is not None:
        build_root = args.pdp11_build_root.expanduser().resolve()
    else:
        build_root, state_error = read_state_build(paths["lab"])
        if build_root is None and state_error is None:
            build_root = discover_build(paths["results"])
    if state_error is not None:
        build_ok, build_details = False, state_error
    elif build_root is None:
        build_ok, build_details = False, "no selected or discoverable receipt-bound build"
    elif not python_ok:
        build_ok, build_details = False, "cannot verify a build without Python 3.11+"
    else:
        build_ok, build_details = verify_build_receipt(
            repo_root, paths["python"], build_root
        )
    failures |= not report(build_ok, "selected PDP-11 TELNET build", build_details)
    build_problem |= not build_ok

    if not pexpect_ok:
        if build_ok:
            print("[info] pexpect is needed only when rebuilding the selected PDP-11 media")
        else:
            failures |= not report(
                False,
                "PDP-11 build dependency",
                "pexpect is unavailable; `make lab-setup` installs the pinned version",
            )
            setup_problem = True

    print()
    lab_argument = f"LAB_ROOT={paths['lab']}"
    if failures:
        print("Next actions, in order:")
        if setup_problem:
            print(f"  make {lab_argument} lab-setup")
        if base_problem:
            print(f"  make {lab_argument} build-pdp11-base")
            print(
                "  Or install an existing legacy pair: make "
                f"{lab_argument} "
                "PDP11_BASE_SOURCE_ROOT=/path/to/ncp_root.rl01 "
                "PDP11_BASE_SOURCE_SWAP=/path/to/ncp_swap.rl01 "
                "install-pdp11-base"
            )
        if build_problem:
            print(f"  make {lab_argument} build-pdp11-telnet")
        print(f"  make {lab_argument} doctor")
        print("See docs/getting-started.md for acquisition and licensing boundaries.")
        return 1

    print("Ready for both foreground entry points:")
    print(f"  make {lab_argument} telnet")
    print(f"  make {lab_argument} ncc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
