#!/usr/bin/env python3
"""Preview or explicitly prune reproducible staged ITS media from retained results."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys


MEDIA_PATTERN = "rp03.*"
BUILD_RECEIPT_PATTERN = "*build-receipt.json"
NOTE_NAME = "media-pruned.txt"
OUTCOMES = frozenset(("passed", "failed"))


class InputError(ValueError):
    """The requested laboratory or results root is unsafe or unavailable."""


class PruneError(RuntimeError):
    """The prune could not complete without violating its safety contract."""


@dataclass(frozen=True)
class MediaFile:
    path: Path
    relative_path: Path
    size: int
    device: int
    inode: int
    modified_ns: int


@dataclass(frozen=True)
class RunPlan:
    path: Path
    media: tuple[MediaFile, ...]

    @property
    def size(self) -> int:
        return sum(item.size for item in self.media)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "lab_root",
        type=Path,
        help="external laboratory root; its results directory is used by default",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        help="results directory inside LAB_ROOT (default: LAB_ROOT/results)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="write an audit note, then remove the listed staged media",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="preview only; this is the default",
    )
    return parser.parse_args()


def resolve_directory(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise InputError(f"refusing a symlinked {label}: {expanded}")
    try:
        resolved = expanded.resolve(strict=True)
    except FileNotFoundError as error:
        raise InputError(f"{label} not found: {expanded}") from error
    if not resolved.is_dir():
        raise InputError(f"{label} is not a directory: {resolved}")
    return resolved


def resolve_results_root(lab_root: Path, override: Path | None) -> Path:
    lab = resolve_directory(lab_root, "laboratory root")
    results = resolve_directory(override or lab / "results", "results root")
    if results == lab:
        raise InputError("refusing to use the laboratory root as the results root")
    if not results.is_relative_to(lab):
        raise InputError(f"results root is outside the laboratory: {results}")
    return results


def contains_build_receipt(run: Path) -> bool:
    return next(run.rglob(BUILD_RECEIPT_PATTERN), None) is not None


def read_regular_text(path: Path, label: str) -> str:
    if path.is_symlink():
        raise PruneError(f"refusing symlinked {label}: {path}")
    if not path.is_file():
        raise PruneError(f"{label} is not a regular file: {path}")
    try:
        return path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise PruneError(f"could not read {label}: {path}: {error}") from error


def has_terminal_manifest(run: Path) -> bool:
    manifest = run / "runtime" / "run.env"
    if not manifest.exists() and not manifest.is_symlink():
        return False
    document = read_regular_text(manifest, "run manifest")
    terminal_keys = ("finished_utc", "outcome", "exit_status")
    values: dict[str, str] = {}
    for line in document.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in terminal_keys:
            if key in values:
                raise PruneError(f"duplicate {key} in run manifest: {manifest}")
            values[key] = value
    if not values:
        return False
    if set(values) != set(terminal_keys):
        raise PruneError(f"incomplete terminal fields in run manifest: {manifest}")
    if not values["finished_utc"]:
        raise PruneError(f"empty finished_utc in run manifest: {manifest}")
    if values["outcome"] not in OUTCOMES:
        raise PruneError(f"invalid outcome in run manifest: {manifest}")
    if not values["exit_status"].isdigit():
        raise PruneError(f"invalid exit_status in run manifest: {manifest}")
    return True


def is_completed_run(run: Path) -> bool:
    outcome = run / "outcome.txt"
    if outcome.exists() or outcome.is_symlink():
        value = read_regular_text(outcome, "formal outcome")
        if value not in {f"{item}\n" for item in OUTCOMES}:
            raise PruneError(f"invalid formal outcome: {outcome}")
        return True
    return has_terminal_manifest(run)


def inspect_media(path: Path, run: Path) -> MediaFile | None:
    if path.is_symlink():
        raise PruneError(f"refusing symlinked staged media: {path}")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        return None
    resolved = path.resolve(strict=True)
    resolved_run = run.resolve(strict=True)
    if not resolved.is_relative_to(resolved_run):
        raise PruneError(f"staged media escapes its result directory: {path}")
    return MediaFile(
        path=path,
        relative_path=path.relative_to(run),
        size=metadata.st_size,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        modified_ns=metadata.st_mtime_ns,
    )


def build_plan(results_root: Path) -> tuple[list[RunPlan], list[Path], list[Path]]:
    plans: list[RunPlan] = []
    skipped_builds: list[Path] = []
    skipped_incomplete: list[Path] = []
    for entry in sorted(results_root.iterdir(), key=lambda path: path.name):
        if entry.is_symlink():
            raise PruneError(f"refusing symlinked result entry: {entry}")
        if not entry.is_dir():
            continue
        if contains_build_receipt(entry):
            skipped_builds.append(entry)
            continue
        media = tuple(
            item
            for item in (
                inspect_media(path, entry)
                for path in sorted(
                    entry.rglob(MEDIA_PATTERN),
                    key=lambda path: os.fspath(path.relative_to(entry)),
                )
            )
            if item is not None
        )
        if not media:
            continue
        if not is_completed_run(entry):
            skipped_incomplete.append(entry)
            continue
        plans.append(RunPlan(entry, media))
    return plans, skipped_builds, skipped_incomplete


def timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def quoted_paths(items: tuple[MediaFile, ...]) -> str:
    return "\n".join(
        f"  - {json.dumps(os.fspath(item.relative_path))}" for item in items
    )


def note_text(
    plan: RunPlan,
    stamp: str,
    *,
    status: str,
    removed: tuple[MediaFile, ...] = (),
    error: str | None = None,
) -> str:
    lines = [
        f"Staged ITS media pruning requested {stamp} per docs/runbook.md (Retain and prune results).",
        "",
        f"Status: {status}",
        f"Selected: {len(plan.media)} rp03 image files, {plan.size} apparent bytes.",
        "Evidence, manifests, logs, structured artifacts, and dskdmp.rim are outside this removal set.",
        "Built PDP-11 media and every directory containing a build receipt are outside this removal set.",
        "",
        "Selected paths:",
        quoted_paths(plan.media),
    ]
    if removed:
        lines.extend(
            (
                "",
                f"Removed: {len(removed)} files, {sum(item.size for item in removed)} apparent bytes.",
            )
        )
    if error is not None:
        lines.extend(("", f"Error: {error}"))
    return "\n".join(lines) + "\n"


def write_exclusive_note(path: Path, contents: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            descriptor = -1
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def replace_note(path: Path, contents: str) -> None:
    temporary = path.with_name(f".{NOTE_NAME}.{os.getpid()}.tmp")
    try:
        write_exclusive_note(temporary, contents)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def remove_provisional_notes(paths: list[Path]) -> None:
    failures: list[str] = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            failures.append(f"{path}: {error}")
    if failures:
        raise PruneError(
            "no media was removed, but provisional note cleanup failed: "
            + "; ".join(failures)
        )


def verify_unchanged(item: MediaFile) -> None:
    try:
        metadata = item.path.lstat()
    except FileNotFoundError as error:
        raise PruneError(f"staged media disappeared before pruning: {item.path}") from error
    identity = (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )
    expected = (item.device, item.inode, item.size, item.modified_ns)
    if not stat.S_ISREG(metadata.st_mode) or identity != expected:
        raise PruneError(f"staged media changed before pruning: {item.path}")


def create_provisional_notes(plans: list[RunPlan], stamp: str) -> list[Path]:
    created: list[Path] = []
    try:
        for plan in plans:
            note = plan.path / NOTE_NAME
            write_exclusive_note(
                note,
                note_text(
                    plan,
                    stamp,
                    status=(
                        "pending; this pre-removal note was flushed before any selected "
                        "path was unlinked"
                    ),
                ),
            )
            created.append(note)
    except OSError as error:
        remove_provisional_notes(created)
        raise PruneError(
            f"cannot write every audit note; no media was removed: {error}"
        ) from error
    return created


def apply_plan(plans: list[RunPlan], stamp: str) -> None:
    notes = create_provisional_notes(plans, stamp)
    try:
        for plan in plans:
            for item in plan.media:
                verify_unchanged(item)
    except (OSError, PruneError):
        remove_provisional_notes(notes)
        raise

    removed_by_run: dict[Path, list[MediaFile]] = {plan.path: [] for plan in plans}
    failure: OSError | None = None
    for plan in plans:
        for item in plan.media:
            try:
                item.path.unlink()
            except OSError as error:
                failure = error
                break
            removed_by_run[plan.path].append(item)
        if failure is not None:
            break

    note_failures: list[str] = []
    for plan in plans:
        removed = tuple(removed_by_run[plan.path])
        if len(removed) == len(plan.media):
            status = "completed"
            note_error = None
        elif removed:
            status = "incomplete; the helper stopped after an unlink failed"
            note_error = str(failure) if failure is not None else "unknown error"
        else:
            status = "aborted before this result was changed"
            note_error = str(failure) if failure is not None else "unknown error"
        try:
            replace_note(
                plan.path / NOTE_NAME,
                note_text(
                    plan,
                    stamp,
                    status=status,
                    removed=removed,
                    error=note_error,
                ),
            )
        except OSError as error:
            note_failures.append(f"{plan.path / NOTE_NAME}: {error}")

    if failure is not None or note_failures:
        details: list[str] = []
        if failure is not None:
            details.append(f"media removal failed: {failure}")
        if note_failures:
            details.append("audit note finalization failed: " + "; ".join(note_failures))
        raise PruneError("; ".join(details))


def print_plan(
    results_root: Path,
    plans: list[RunPlan],
    skipped_builds: list[Path],
    skipped_incomplete: list[Path],
    *,
    apply: bool,
) -> None:
    print(f"Results root: {results_root}")
    print("Mode: APPLY" if apply else "Mode: DRY RUN (default; no files will be removed)")
    for path in skipped_builds:
        print(f"SKIP build receipt: {path.name}")
    for path in skipped_incomplete:
        print(f"SKIP active or incomplete result: {path.name}")
    for plan in plans:
        print(f"{'PRUNE' if apply else 'WOULD PRUNE'}: {plan.path.name}")
        for item in plan.media:
            print(f"  {item.size:12d}  {item.relative_path}")
    file_count = sum(len(plan.media) for plan in plans)
    byte_count = sum(plan.size for plan in plans)
    verb = "Selected for pruning" if apply else "Would prune"
    print(
        f"{verb} {len(plans)} result directories, {file_count} files, "
        f"{byte_count} apparent bytes; skipped {len(skipped_builds)} build-receipt "
        f"and {len(skipped_incomplete)} active or incomplete directories."
    )
    if not apply and plans:
        print("Review this list, then rerun with --apply to remove exactly this class of file.")


def main() -> int:
    args = parse_args()
    try:
        results_root = resolve_results_root(args.lab_root, args.results_root)
        plans, skipped_builds, skipped_incomplete = build_plan(results_root)
        print_plan(
            results_root,
            plans,
            skipped_builds,
            skipped_incomplete,
            apply=args.apply,
        )
        if args.apply and plans:
            apply_plan(plans, timestamp())
            print(
                f"Pruned {len(plans)} result directories, "
                f"{sum(len(plan.media) for plan in plans)} files, "
                f"{sum(plan.size for plan in plans)} apparent bytes."
            )
            print("Audit notes were written before removal and finalized in each changed result.")
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return os.EX_NOINPUT
    except (OSError, PruneError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
