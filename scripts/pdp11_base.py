#!/usr/bin/env python3
"""Reconstruct and verify the external, deterministic Network UNIX base pair.

Original orchestration of the settled method in docs/research/imp11a-device.md.
No external installer code, tape, boot block, or guest bytes are embedded here.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request


REPO = Path(__file__).resolve().parents[1]
IMAGE_NAMES = ("ncp_root.rl01", "ncp_swap.rl01")
PROFILES = {
    "reconstructed-v1": "pdp11-reconstructed-base.sha256",
    "legacy-prepared": "pdp11-base-assets.sha256",
}
PAYLOADS = ("green/unix", "ncpd/Largedaemon", "ncpd/smalldaemon")
RL01_SIZE = 5242880
BLOCK = 512


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_profiles(repo: Path = REPO) -> dict[str, dict[str, str]]:
    profiles = {}
    for profile, filename in PROFILES.items():
        pins = {}
        for line in (repo / "pins" / filename).read_text(encoding="ascii").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
                raise ValueError(f"invalid base-media pin in {filename}")
            name = Path(fields[1]).name
            if name in pins:
                raise ValueError(f"duplicate base-media pin in {filename}: {name}")
            pins[name] = fields[0]
        if set(pins) != set(IMAGE_NAMES):
            raise ValueError(f"incomplete base-media pair in {filename}")
        profiles[profile] = pins
    return profiles


def verify_pair(root: Path, swap: Path, repo: Path = REPO) -> str:
    actual = {}
    for name, path in zip(IMAGE_NAMES, (root, swap)):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"base media must be regular files: {path}")
        actual[name] = sha256(path)
    for profile, pins in load_profiles(repo).items():
        if actual == pins:
            return profile
    raise ValueError("base root and swap do not match one complete pinned pair: "
                     + json.dumps(actual, sort_keys=True))


def default_image_dir(lab: Path) -> Path:
    rebuilt = lab / "work/pdp11-base/images"
    legacy = lab / "work/unix-v6-install/images"
    # Select a pair together, including incomplete rebuilds so doctor exposes them.
    if (lab / "work/pdp11-base").exists() or not legacy.exists():
        return rebuilt
    return legacy


def require_external(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    # Reject every checkout of this source repository, including untracked paths.
    probe = resolved
    while not probe.exists():
        probe = probe.parent
    result = subprocess.run(
        ["git", "-C", probe, "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
    )
    if result.returncode == 0:
        checkout = Path(result.stdout.strip())
        if (checkout / "pins/sources.lock.toml").is_file() and (checkout / "Makefile").is_file():
            raise ValueError(f"historical material must remain outside the source repository: {resolved}")
    if resolved == REPO or resolved.is_relative_to(REPO):
        raise ValueError(f"historical material must remain outside the source repository: {resolved}")
    return resolved


def contained_path(lab: Path, relative: str) -> Path:
    path = lab / relative
    if path.is_symlink() or not path.resolve().is_relative_to(lab):
        raise ValueError(f"laboratory path is symlinked or escapes its root: {path}")
    require_external(path)
    return path


def load_archives() -> list[dict]:
    document = tomllib.loads((REPO / "pins/pdp11-base-inputs.lock.toml").read_text())
    if document.get("version") != 1:
        raise ValueError("unsupported base-input lock version")
    records = document["archive"]
    if [record["name"] for record in records] != ["v6.tape.gz", "unix_v6.rl02.gz"]:
        raise ValueError("base-input lock does not name the two required archives")
    for record in records:
        if not record["url"].startswith("https://"):
            raise ValueError("base-input URL must use HTTPS")
        for key in ("sha256", "uncompressed_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", record[key]):
                raise ValueError(f"invalid {key} in base-input lock")
        for key in ("size", "uncompressed_size"):
            if type(record[key]) is not int or not 0 < record[key] <= 16 * 1024 * 1024:
                raise ValueError(f"invalid {key} in base-input lock")
    return records


def checked_bytes(data: bytes, size: int, expected: str, label: str) -> bytes:
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"{label}: size or SHA-256 does not match its pin")
    return data


def acquire_archive(path: Path, record: dict, *, offline: bool) -> bytes:
    if path.is_symlink():
        raise ValueError(f"refusing symlinked cached archive: {path}")
    if path.exists():
        if not path.is_file():
            raise ValueError(f"cached archive is not a regular file: {path}")
        with path.open("rb") as stream:
            data = stream.read(record["size"] + 1)
        return checked_bytes(data, record["size"], record["sha256"], str(path))
    if offline:
        raise ValueError(f"offline archive is missing: {path}")
    print(f"Fetching {record['name']} from {record['url']}", flush=True)
    with urllib.request.urlopen(record["url"], timeout=30) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("archive download redirected away from HTTPS")
        data = response.read(record["size"] + 1)
    checked_bytes(data, record["size"], record["sha256"], record["name"])
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".download-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        # Never replace a cache entry created by another process.
        os.link(temporary, path)
    finally:
        temporary.unlink()
    return data


def unpack_archive(data: bytes, record: dict) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read(record["uncompressed_size"] + 1)
    return checked_bytes(raw, record["uncompressed_size"],
                         record["uncompressed_sha256"], record["name"] + " (uncompressed)")


def source_payloads(checkout: Path) -> tuple[dict, dict[str, bytes]]:
    lock = tomllib.loads((REPO / "pins/sources.lock.toml").read_text())
    pin = next(source for source in lock["source"] if source["name"] == "network-unix-v6")
    def git(*arguments: str) -> bytes:
        return subprocess.check_output(["git", "-C", checkout, *arguments], stderr=subprocess.PIPE)
    if git("rev-parse", "HEAD").decode().strip() != pin["revision"]:
        raise ValueError("Network UNIX checkout does not match its pinned revision; run make lab-setup")
    if git("status", "--porcelain", "--untracked-files=no", "--ignore-submodules=all").strip():
        raise ValueError("Network UNIX tracked source is dirty")
    payloads = {}
    for name in PAYLOADS:
        path = checkout / "nosc-files" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing regular Network UNIX input: {path}")
        data = path.read_bytes()
        if data != git("show", f"{pin['revision']}:nosc-files/{name}"):
            raise ValueError(f"Network UNIX input differs from its pinned Git object: {name}")
        payloads[name] = data
    identity = {"path": str(checkout), "url": pin["url"], "revision": pin["revision"],
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}
    return identity, payloads


def assemble(tape: bytes, rl_disk: bytes, payloads: dict[str, bytes], images: Path) -> None:
    from research.v6fs import V6FS

    if len(tape) != 12100 * BLOCK or len(rl_disk) != 2 * RL01_SIZE:
        raise ValueError("unexpected tape or RL02 geometry")
    images.mkdir()
    root = images / IMAGE_NAMES[0]
    root.write_bytes(tape[100 * BLOCK:4100 * BLOCK] + bytes(RL01_SIZE - 4000 * BLOCK))
    fs = V6FS(root)
    if fs.fsize != 4000:
        raise ValueError("tape root is not the expected 4000-block filesystem")
    fs.data[:BLOCK] = rl_disk[:BLOCK]
    fs.put_file("/", "green", payloads["green/unix"])
    fs.mkdir("/usr/net/etc")
    for name in ("Largedaemon", "smalldaemon"):
        fs.put_file("/usr/net/etc", name, payloads["ncpd/" + name])
    fs.mknod("/dev", "ncpkernel", "c", 5, 0, mode=0o666)
    # The existing injector does not count new subdirectories' '..' links.
    # Correct these two parents without changing the accepted guest builders.
    for parent in ("/usr", "/usr/net"):
        block, offset = fs._inode_loc(fs.lookup(parent))
        word = fs._read_words(block, offset + 1, 1)[0]
        fs._write_words(block, offset + 1, [(word & 0xff00) | ((word & 0xff) + 1)])
    # Flush free-block state, invalidate the inode cache, and set a fixed clock.
    fs.flush_superblock()
    fs.save()
    (images / IMAGE_NAMES[1]).write_bytes(bytes(RL01_SIZE))


def builder_identity() -> dict[str, str]:
    return {name: sha256(REPO / name) for name in (
        "scripts/pdp11_base.py", "scripts/research/v6fs.py",
        "pins/pdp11-base-inputs.lock.toml", "pins/pdp11-reconstructed-base.sha256",
    )}


@contextmanager
def build_lock(path: Path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("another base-media reconstruction owns this laboratory lock") from error
        yield
        # Keep the lock file: removing it would permit concurrent inode locks.


def build(lab: Path, network: Path, *, offline: bool = False, plan: bool = False) -> Path:
    lab = require_external(lab)
    network = require_external(network)
    destination = contained_path(lab, "work/pdp11-base")
    cache = contained_path(lab, "cache/pdp11-base")
    archives = load_archives()
    if plan:
        for record in archives:
            print(f"INPUT {record['url']} -> {cache / record['name']} ({record['sha256']})")
        print(f"SOURCE {network}; OUTPUT {destination}")
        print("Plan complete; no laboratory files were changed.")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with build_lock(contained_path(lab, "work/.pdp11-base.lock")):
        occupied = destination.exists()
        if occupied:
            receipt = destination / "pdp11-base-receipt.json"
            if not receipt.is_file() or receipt.is_symlink():
                raise ValueError(f"refusing existing destination without a build receipt: {destination}")
            if verify_pair(*(destination / "images" / name for name in IMAGE_NAMES)) != "reconstructed-v1":
                raise ValueError("existing destination is not the reconstructed pair")
        source, payloads = source_payloads(network)
        raw = {}
        for record in archives:
            path = cache / record["name"]
            data = acquire_archive(path, record, offline=offline)
            raw[record["name"]] = unpack_archive(data, record)
        document = {
            "format": 1, "profile": "reconstructed-v1", "source": source,
            "archives": archives, "builders": builder_identity(),
            "images": load_profiles()["reconstructed-v1"],
        }
        if occupied:
            if json.loads(receipt.read_text()) != document:
                raise ValueError(f"existing base receipt differs from current inputs or recipe: {receipt}")
            print(f"Verified existing reconstructed pair: {destination}")
            return destination
        temporary = Path(tempfile.mkdtemp(prefix=".pdp11-base-", dir=destination.parent))
        try:
            assemble(raw["v6.tape.gz"], raw["unix_v6.rl02.gz"], payloads, temporary / "images")
            profile = verify_pair(*(temporary / "images" / name for name in IMAGE_NAMES))
            if profile != "reconstructed-v1":
                raise ValueError("reconstruction did not produce its exact output pins")
            (temporary / "pdp11-base-receipt.json").write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if destination.exists() or destination.is_symlink():
                raise ValueError(f"refusing to replace an existing destination: {destination}")
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    print(f"PASS: reconstructed and verified base media at {destination}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    reconstruct = sub.add_parser("build")
    reconstruct.add_argument("lab_root", type=Path)
    reconstruct.add_argument("--network-unix-root", type=Path)
    reconstruct.add_argument("--offline", action="store_true")
    reconstruct.add_argument("--plan", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("root", type=Path)
    verify.add_argument("swap", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            print(f"PDP-11 base pair: OK ({verify_pair(args.root, args.swap)})")
        else:
            lab = args.lab_root.expanduser().resolve()
            network = args.network_unix_root or lab / "work/network-unix-v6"
            build(lab, network.expanduser().resolve(), offline=args.offline, plan=args.plan)
    except (OSError, ValueError, KeyError, RuntimeError, EOFError, subprocess.SubprocessError) as error:
        print(f"PDP-11 base media failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
