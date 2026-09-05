"""Verified disk generations for an explicitly owned guest workspace.

Running simulators write only to per-run copies. Published generations are
immutable, and a new current pointer is written only after every file is durable.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterator
import uuid

from ncc.harness_manifest import sha256


MEDIA = (
    "host106/dskdmp.rim",
    "host106/rp03.0",
    "host106/rp03.1",
    "host106/rp03.2",
    "host106/rp03.3",
    "pdp11/images/ncp_root.rl01",
    "pdp11/images/ncp_swap.rl01",
)
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
GENERATION = re.compile(r"[0-9a-f]{32}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class WorkspaceError(ValueError):
    """A workspace cannot safely be used or changed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkspaceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise WorkspaceError(f"missing or symlinked workspace record: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise WorkspaceError(f"invalid workspace record: {path}") from error
    if not isinstance(value, dict):
        raise WorkspaceError(f"workspace record must be an object: {path}")
    return value


def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def copy_media(source: Path, destination: Path) -> dict:
    if source.is_symlink() or not source.is_file():
        raise WorkspaceError(f"missing or symlinked guest media: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # APFS clones keep multiple saves affordable; other systems use real copies.
    clone = subprocess.run(
        ["cp", "-c", "-p", str(source), str(destination)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if clone.returncode:
        shutil.copy2(source, destination)
    with destination.open("rb") as stream:
        os.fsync(stream.fileno())
    return {"size": destination.stat().st_size, "sha256": sha256(destination)}


def workspace_path(lab: Path, name: str, repository: Path) -> Path:
    if not NAME.fullmatch(name):
        raise WorkspaceError("workspace name must be 1–64 letters, digits, underscores, or hyphens")
    lab = lab.expanduser().resolve()
    if lab.is_relative_to(repository.resolve()):
        raise WorkspaceError("guest workspaces must be outside the repository")
    parent = lab / "workspaces"
    root = parent / name
    if parent.is_symlink() or root.is_symlink():
        raise WorkspaceError("workspace directories must not be symlinks")
    return root


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.absolute()
        if self.root.is_symlink():
            raise WorkspaceError("workspace directory must not be a symlink")

    def metadata(self) -> dict:
        value = read_json(self.root / "workspace.json")
        if (
            set(value) != {"format", "name", "created_utc", "lab", "build", "inputs"}
            or type(value["format"]) is not int or value["format"] != 1
            or value["name"] != self.root.name
            or not isinstance(value["created_utc"], str)
            or not all(isinstance(value[key], str) and Path(value[key]).is_absolute() for key in ("lab", "build"))
            or not isinstance(value["inputs"], dict) or not value["inputs"]
        ):
            raise WorkspaceError("unsupported or malformed workspace metadata")
        for item in value["inputs"].values():
            if (
                not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str) or not Path(item["path"]).is_absolute()
                or not isinstance(item["sha256"], str) or not DIGEST.fullmatch(item["sha256"])
            ):
                raise WorkspaceError("invalid workspace input identity")
        return value

    def check_inputs(self, inputs: dict) -> None:
        saved = self.metadata()["inputs"]
        # Repository paths may move with worktrees; content identities may not.
        if {k: v["sha256"] for k, v in inputs.items()} != {k: v["sha256"] for k, v in saved.items()}:
            raise WorkspaceError("workspace inputs differ from this build, topology, or simulator; migration is required")

    def current(self) -> str:
        value = read_json(self.root / "current.json")
        if set(value) != {"format", "generation"} or type(value["format"]) is not int or value["format"] != 1:
            raise WorkspaceError("invalid workspace current pointer")
        return self._generation_id(value["generation"])

    @staticmethod
    def _generation_id(value: object) -> str:
        if not isinstance(value, str) or not GENERATION.fullmatch(value):
            raise WorkspaceError("invalid workspace generation identifier")
        return value

    def generation_path(self, identifier: str) -> Path:
        root = self.root / "generations" / self._generation_id(identifier)
        if root.parent.is_symlink() or root.is_symlink():
            raise WorkspaceError("generation directory must not be a symlink")
        return root

    def verify_generation(self, identifier: str) -> dict:
        root = self.generation_path(identifier)
        value = read_json(root / "generation.json")
        keys = {"format", "id", "parent", "created_utc", "kind", "result", "shutdown_sha256", "media"}
        if (
            set(value) != keys or type(value["format"]) is not int or value["format"] != 1
            or value["id"] != identifier or not isinstance(value["created_utc"], str)
            or value["kind"] not in {"seed", "saved"}
            or not isinstance(value["media"], dict) or set(value["media"]) != set(MEDIA)
        ):
            raise WorkspaceError("invalid workspace generation manifest")
        if value["kind"] == "seed":
            if any(value[key] is not None for key in ("parent", "result", "shutdown_sha256")):
                raise WorkspaceError("seed generation has invalid provenance")
        else:
            self._generation_id(value["parent"])
            if (
                value["parent"] == identifier
                or not isinstance(value["result"], str) or not Path(value["result"]).is_absolute()
                or not isinstance(value["shutdown_sha256"], str) or not DIGEST.fullmatch(value["shutdown_sha256"])
            ):
                raise WorkspaceError("saved generation has invalid provenance")
        for relative, identity in value["media"].items():
            path = root / relative
            if (
                not isinstance(identity, dict) or set(identity) != {"size", "sha256"}
                or type(identity["size"]) is not int or identity["size"] < 1
                or not isinstance(identity["sha256"], str) or not DIGEST.fullmatch(identity["sha256"])
                or path.resolve() != path or not path.is_file()
                or path.stat().st_size != identity["size"] or sha256(path) != identity["sha256"]
            ):
                raise WorkspaceError(f"workspace media verification failed: {relative}")
        return value

    def select(self, identifier: str) -> None:
        self.verify_generation(identifier)
        temporary = self.root / (".current-" + uuid.uuid4().hex)
        try:
            write_json(temporary, {"format": 1, "generation": identifier})
            os.replace(temporary, self.root / "current.json")
            fsync_directory(self.root)
        finally:
            temporary.unlink(missing_ok=True)

    def publish(self, sources: dict[str, Path], *, parent: str | None, result: Path | None, shutdown_sha256: str | None) -> str:
        if set(sources) != set(MEDIA):
            raise WorkspaceError("a generation must contain both complete guest disk sets")
        if parent is None and (self.root / "current.json").exists():
            raise WorkspaceError("an existing workspace cannot be reseeded")
        if parent is not None and self.current() != parent:
            raise WorkspaceError("workspace current generation changed during the run")
        identifier = uuid.uuid4().hex
        generations = self.root / "generations"
        if generations.is_symlink():
            raise WorkspaceError("generation directory must not be a symlink")
        generations.mkdir(exist_ok=True)
        pending = generations / (".pending-" + identifier)
        pending.mkdir()
        try:
            media = {name: copy_media(sources[name], pending / name) for name in MEDIA}
            write_json(pending / "generation.json", {
                "format": 1, "id": identifier, "parent": parent,
                "created_utc": utc_now(), "kind": "seed" if parent is None else "saved",
                "result": str(result) if result is not None else None,
                "shutdown_sha256": shutdown_sha256, "media": media,
            })
            for directory in (pending / "pdp11/images", pending / "pdp11", pending / "host106", pending):
                fsync_directory(directory)
            os.rename(pending, generations / identifier)
            fsync_directory(generations)
            self.select(identifier)
        finally:
            if pending.exists():
                shutil.rmtree(pending)
        return identifier

    def acquire(self, result: Path | None = None) -> str:
        self.metadata()
        lease = self.root / "lease"
        try:
            lease.mkdir(mode=0o700)
        except FileExistsError as error:
            raise WorkspaceError(f"workspace is leased; inspect {lease}; interrupted owners require explicit recovery") from error
        token = uuid.uuid4().hex
        try:
            write_json(lease / "owner.json", {
                "token": token, "pid": os.getpid(), "created_utc": utc_now(),
                "result": str(result) if result is not None else None,
            })
            fsync_directory(lease)
            fsync_directory(self.root)
        except BaseException:
            (lease / "owner.json").unlink(missing_ok=True)
            lease.rmdir()
            raise
        return token

    def release(self, token: str) -> None:
        lease = self.root / "lease"
        if lease.is_symlink() or read_json(lease / "owner.json").get("token") != token:
            raise WorkspaceError("workspace lease ownership changed")
        (lease / "owner.json").unlink()
        lease.rmdir()
        fsync_directory(self.root)

    @contextmanager
    def locked(self) -> Iterator[str]:
        token = self.acquire()
        try:
            yield token
        finally:
            self.release(token)
