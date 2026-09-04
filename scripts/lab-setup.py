#!/usr/bin/env python3
"""Fetch pinned runtime sources and build host tools in the external lab."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


RUNTIME_SOURCE_NAMES = (
    "arpanet-in-a-box",
    "linux-ncp",
    "h316-simh",
    "ka10-simh",
    "imp11a-simh",
    "network-unix-v6",
)

SIMULATOR_BUILDS = (
    ("h316-simh", "h316", Path("BIN/h316")),
    ("ka10-simh", "pdp10-ka", Path("BIN/pdp10-ka")),
    ("imp11a-simh", "pdp11", Path("BIN/pdp11")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lab_root", type=Path)
    parser.add_argument(
        "--no-build", action="store_true", help="fetch sources without building SIMH"
    )
    parser.add_argument(
        "--no-venv", action="store_true", help="do not create the lab Python venv"
    )
    parser.add_argument(
        "--plan", action="store_true", help="describe writes without performing them"
    )
    return parser.parse_args()


def load_runtime_sources(repo_root: Path) -> list[dict[str, str]]:
    lock_path = repo_root / "pins" / "sources.lock.toml"
    document = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    by_name = {source["name"]: source for source in document["source"]}
    missing = set(RUNTIME_SOURCE_NAMES) - set(by_name)
    if missing:
        raise ValueError(f"source lock is missing runtime inputs: {sorted(missing)}")
    sources = [by_name[name] for name in RUNTIME_SOURCE_NAMES]
    return sorted(sources, key=lambda source: len(Path(source["checkout"]).parts))


def command_text(arguments: list[os.PathLike[str] | str]) -> str:
    return " ".join(repr(os.fspath(argument)) for argument in arguments)


def run(
    arguments: list[os.PathLike[str] | str],
    *,
    plan: bool = False,
    cwd: Path | None = None,
) -> None:
    if plan:
        prefix = f"(in {cwd}) " if cwd is not None else ""
        print(f"PLAN: {prefix}{command_text(arguments)}")
        return
    subprocess.run(
        [os.fspath(argument) for argument in arguments],
        cwd=cwd,
        check=True,
    )


def git_output(checkout: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", os.fspath(checkout), *arguments],
        stderr=subprocess.STDOUT,
        text=True,
    ).rstrip()


def is_git_checkout(path: Path) -> bool:
    try:
        return git_output(path, "rev-parse", "--is-inside-work-tree") == "true"
    except (OSError, subprocess.CalledProcessError):
        return False


def tracked_changes(checkout: Path) -> str:
    # Every nested runtime checkout is verified against its own lock record. Some
    # exact child pins intentionally differ from the parent's historical gitlink.
    return git_output(
        checkout,
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--ignore-submodules=all",
    )


def safe_checkout_path(lab_root: Path, relative: str) -> Path:
    unresolved = lab_root / relative
    if unresolved.is_symlink():
        raise ValueError(f"refusing a symlinked source checkout: {unresolved}")
    resolved = unresolved.resolve()
    if not resolved.is_relative_to(lab_root):
        raise ValueError(f"source checkout escapes the laboratory: {unresolved}")
    return resolved


def ensure_checkout(
    lab_root: Path,
    source: dict[str, str],
    *,
    plan: bool = False,
) -> Path:
    checkout = safe_checkout_path(lab_root, source["checkout"])
    created = False
    if not is_git_checkout(checkout):
        if checkout.exists() and (
            not checkout.is_dir() or any(checkout.iterdir())
        ):
            raise ValueError(
                f"refusing to replace non-Git path for {source['name']}: {checkout}"
            )
        if plan:
            print(f"{source['name']}: would clone {source['url']} into {checkout}")
            return checkout
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--no-checkout", source["url"], checkout])
        created = True

    if plan:
        print(
            f"{source['name']}: would verify or select {source['revision']} at {checkout}"
        )
        return checkout

    if not created:
        dirty = tracked_changes(checkout)
        if dirty:
            changed = ", ".join(line[3:] for line in dirty.splitlines())
            raise ValueError(
                f"refusing to change dirty {source['name']} checkout; tracked paths: {changed}"
            )
    actual = git_output(checkout, "rev-parse", "HEAD")
    if created:
        run(
            ["git", "-C", checkout, "checkout", "--detach", source["revision"]]
        )
        actual = git_output(checkout, "rev-parse", "HEAD")
    elif actual != source["revision"]:
        run(
            [
                "git",
                "-C",
                checkout,
                "fetch",
                "--no-tags",
                source["url"],
                source["revision"],
            ]
        )
        run(
            ["git", "-C", checkout, "checkout", "--detach", source["revision"]]
        )
        actual = git_output(checkout, "rev-parse", "HEAD")
    if actual != source["revision"]:
        raise ValueError(
            f"{source['name']} is {actual}, expected {source['revision']}"
        )
    if tracked_changes(checkout):
        raise ValueError(f"{source['name']} became dirty while selecting its pin")
    print(f"{source['name']}: ready at {actual}")
    return checkout


def prepare_venv(repo_root: Path, lab_root: Path, *, plan: bool = False) -> Path:
    venv_root = lab_root / ".venv"
    python = venv_root / "bin" / "python3"
    if not python.is_file():
        run([sys.executable, "-m", "venv", venv_root], plan=plan)
    if not plan and python.is_file():
        versions = subprocess.run(
            [
                python,
                "-c",
                "import importlib.metadata as m; print(m.version('pexpect'), m.version('ptyprocess'))",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if versions.returncode == 0 and versions.stdout.strip() == "4.9.0 0.7.0":
            print(f"lab Python: {python} (pexpect 4.9.0, ptyprocess 0.7.0)")
            return python
    run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            repo_root / "requirements-lab.txt",
        ],
        plan=plan,
    )
    if not plan:
        result = subprocess.run(
            [
                python,
                "-c",
                "import importlib.metadata as m; print(m.version('pexpect'), m.version('ptyprocess'))",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        print(f"lab Python: {python} (pexpect/ptyprocess {result.stdout.strip()})")
    return python


def simulator_build_arguments(
    source_name: str, target: str, checkout: Path, platform_name: str
) -> list[os.PathLike[str] | str]:
    arguments: list[os.PathLike[str] | str] = ["make", "-C", checkout]
    if (
        (source_name, target)
        in {("ka10-simh", "pdp10-ka"), ("imp11a-simh", "pdp11")}
        and platform_name == "darwin"
    ):
        # The pinned legacy probe looks for a physical libz.dylib, while Apple
        # provides zlib to the linker through its SDK stub and shared cache.
        # Both pinned legacy simulator trees need the explicit link.
        arguments.append("LDFLAGS_O=-lz")
    arguments.append(target)
    return arguments


def build_simulators(
    checkouts: dict[str, Path], *, plan: bool = False
) -> None:
    for source_name, target, relative_binary in SIMULATOR_BUILDS:
        checkout = checkouts[source_name]
        run(
            simulator_build_arguments(source_name, target, checkout, sys.platform),
            plan=plan,
        )
        binary = checkout / relative_binary
        if not plan and (not binary.is_file() or not os.access(binary, os.X_OK)):
            raise ValueError(f"{source_name} build did not produce {binary}")
        print(f"{target}: {'would build' if plan else 'built'} {binary}")


def check_host_tools() -> None:
    missing = [name for name in ("git", "make", "cc") if shutil.which(name) is None]
    if missing:
        raise ValueError("missing host command(s): " + ", ".join(missing))
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required")


def print_external_notice(sources: list[dict[str, str]], lab_root: Path) -> None:
    print("External laboratory setup")
    print(f"  destination: {lab_root}")
    print("  source bytes come directly from their recorded upstream URLs")
    print("  no external source, firmware, media, binary, or result enters Git")
    print("  review NOTICE.md and each upstream project's terms before continuing")
    for source in sources:
        print(f"  - {source['name']}: {source['redistribution']}")
    print()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    lab_root = args.lab_root.expanduser().resolve()
    try:
        check_host_tools()
        sources = load_runtime_sources(repo_root)
        print_external_notice(sources, lab_root)
        if not args.plan:
            (lab_root / "work").mkdir(parents=True, exist_ok=True)
            (lab_root / "results").mkdir(parents=True, exist_ok=True)
        checkouts = {
            source["name"]: ensure_checkout(lab_root, source, plan=args.plan)
            for source in sources
        }
        if not args.no_venv:
            prepare_venv(repo_root, lab_root, plan=args.plan)
        if not args.no_build:
            build_simulators(checkouts, plan=args.plan)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"laboratory setup failed: {error}", file=sys.stderr)
        return 1

    print()
    if args.plan:
        print("Plan complete; no laboratory files were changed.")
    else:
        print("Pinned runtime sources and host tools are ready.")
        print("Run `make doctor` to see the remaining media/build step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
