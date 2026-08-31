"""Bounded, append-only publication of live NCC harness observations.

The stream has one header followed by JSON Lines direct observations. Its
topology and observation fields reuse the accepted version-1 completed-run
contract, but it deliberately contains no derived states or gate verdicts:
those require a completed formal result. Reading a stream never controls the
harness and preserves the configured topology even when observations go stale.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

from .run_summary import (
    RUN_SUMMARY_SCHEMA_VERSION,
    RunSummaryValidationError,
    validate_normalized_observations,
    validate_normalized_topology,
)


LIVE_OBSERVATION_STREAM_SCHEMA_VERSION = RUN_SUMMARY_SCHEMA_VERSION
_STREAM_KIND = "ncc-observation-stream"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")


class LiveObservationStreamError(ValueError):
    """Raised when an append-only NCC observation stream is not trustworthy."""


@dataclass(frozen=True)
class LiveObservationStream:
    """A validated snapshot of a bounded live observation stream."""

    _header: Mapping[str, Any]
    _observations: tuple[Mapping[str, Any], ...]

    @property
    def run_id(self) -> str:
        """Return the stable identity of the bounded harness run."""

        return str(self._header["run"]["id"])

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh, JSON-safe stream copy for read-only consumers."""

        return {
            "header": _copy(self._header),
            "observations": [_copy(observation) for observation in self._observations],
        }

    def snapshot(self, now: datetime | None = None) -> "LiveObservationSnapshot":
        """Return current direct states, marking expired observations stale."""

        current_time = _utc_datetime(now)
        stale_after_seconds = float(self._header["stale_after_seconds"])
        current_states: dict[str, str] = {}
        last_known_states: dict[str, str] = {}
        last_observed_at: dict[str, datetime] = {}
        for observation in self._observations:
            subject_id = str(observation["subject_id"])
            last_known_states[subject_id] = str(observation["state"])
            last_observed_at[subject_id] = _parse_timestamp(
                str(observation["observed_at"]),
                "observation.observed_at",
            )
            current_states[subject_id] = str(observation["state"])
        stale_subject_ids = tuple(
            sorted(
                subject_id
                for subject_id, observed_at in last_observed_at.items()
                if (current_time - observed_at).total_seconds() > stale_after_seconds
            )
        )
        for subject_id in stale_subject_ids:
            current_states[subject_id] = "stale"
        return LiveObservationSnapshot(
            run_id=self.run_id,
            started_at=str(self._header["run"]["started_at"]),
            topology=MappingProxyType(_copy(self._header["topology"])),
            observations=tuple(MappingProxyType(_copy(item)) for item in self._observations),
            current_states=MappingProxyType(current_states),
            last_known_states=MappingProxyType(last_known_states),
            stale_subject_ids=stale_subject_ids,
        )


@dataclass(frozen=True)
class LiveObservationSnapshot:
    """The direct state view available to a passive live consumer."""

    run_id: str
    started_at: str
    topology: Mapping[str, Any]
    observations: tuple[Mapping[str, Any], ...]
    current_states: Mapping[str, str]
    last_known_states: Mapping[str, str]
    stale_subject_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without process-control data."""

        return {
            "run": {"id": self.run_id, "started_at": self.started_at},
            "topology": _copy(self.topology),
            "observations": [_copy(observation) for observation in self.observations],
            "current_states": dict(self.current_states),
            "last_known_states": dict(self.last_known_states),
            "stale_subject_ids": list(self.stale_subject_ids),
        }


class LiveObservationPublisher:
    """Write one controller-owned live stream without process-control authority."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        started_at: str,
        provenance: Sequence[Mapping[str, str]],
        topology: Mapping[str, Any],
        stale_after_seconds: float,
    ) -> None:
        self.path = Path(path)
        header = {
            "schema_version": LIVE_OBSERVATION_STREAM_SCHEMA_VERSION,
            "kind": _STREAM_KIND,
            "run": {
                "id": run_id,
                "started_at": started_at,
                "provenance": [dict(item) for item in provenance],
            },
            "topology": _copy(topology),
            "stale_after_seconds": stale_after_seconds,
        }
        _validate_header(header)
        self._header = header
        self._observations: list[dict[str, Any]] = []
        self._closed = False
        self._stream = self.path.open("x", encoding="utf-8")
        self._write(header)

    def publish(
        self,
        *,
        category: str,
        subject_id: str,
        state: str,
        source: Mapping[str, str],
        details: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
    ) -> None:
        """Append one direct observation and flush it for a passive reader."""

        if self._closed:
            raise LiveObservationStreamError("cannot publish to a closed observation stream")
        observation: dict[str, Any] = {
            "id": f"observation:live:{len(self._observations) + 1}",
            "sequence": len(self._observations) + 1,
            "observed_at": observed_at or utc_now(),
            "category": category,
            "subject_id": subject_id,
            "state": state,
            "source": dict(source),
        }
        if details:
            observation["details"] = dict(details)
        candidate = [*self._observations, observation]
        try:
            validate_normalized_observations(
                self._header["topology"],
                candidate,
                started_at=str(self._header["run"]["started_at"]),
                finished_at=str(observation["observed_at"]),
            )
        except RunSummaryValidationError as error:
            raise LiveObservationStreamError(f"invalid live observation: {error}") from error
        self._observations.append(observation)
        self._write(observation)

    def close(self) -> None:
        """Close the stream without changing simulator or result state."""

        if not self._closed:
            self._stream.close()
            self._closed = True

    def _write(self, record: Mapping[str, Any]) -> None:
        self._stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        self._stream.flush()


def read_live_observation_stream(path: str | Path) -> LiveObservationStream:
    """Read complete JSON Lines only, tolerating a writer's partial final line."""

    stream_path = Path(path)
    try:
        contents = stream_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LiveObservationStreamError(
            f"could not read live observation stream {stream_path}: {error}"
        ) from error
    lines = contents.splitlines()
    if contents and not contents.endswith("\n"):
        lines.pop()
    if not lines:
        raise LiveObservationStreamError("live observation stream has no complete header")
    records = []
    for number, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise LiveObservationStreamError(
                f"live observation stream line {number} is not JSON: {error}"
            ) from error
    header = records[0]
    _validate_header(header)
    observations = records[1:]
    if observations:
        try:
            validate_normalized_observations(
                header["topology"],
                observations,
                started_at=header["run"]["started_at"],
                finished_at=observations[-1]["observed_at"],
            )
        except (KeyError, RunSummaryValidationError) as error:
            raise LiveObservationStreamError(
                f"invalid live observation stream: {error}"
            ) from error
    return LiveObservationStream(
        _header=MappingProxyType(_copy(header)),
        _observations=tuple(MappingProxyType(_copy(item)) for item in observations),
    )


def utc_now() -> str:
    """Return an RFC 3339 UTC timestamp at the stream's supported precision."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_header(header: object) -> None:
    if not isinstance(header, Mapping):
        raise LiveObservationStreamError("live observation stream header must be an object")
    expected = {"schema_version", "kind", "run", "topology", "stale_after_seconds"}
    if header.keys() != expected:
        raise LiveObservationStreamError(
            "live observation stream header fields must be " + ", ".join(sorted(expected))
        )
    schema_version = header["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != LIVE_OBSERVATION_STREAM_SCHEMA_VERSION
    ):
        raise LiveObservationStreamError(
            "live observation stream has unsupported schema version "
            f"{schema_version!r}"
        )
    if header["kind"] != _STREAM_KIND:
        raise LiveObservationStreamError("live observation stream header has unexpected kind")
    run = header["run"]
    if not isinstance(run, Mapping) or run.keys() != {"id", "started_at", "provenance"}:
        raise LiveObservationStreamError("live observation stream header has an invalid run record")
    _identifier(run["id"], "live observation stream.run.id")
    _parse_timestamp(run["started_at"], "live observation stream.run.started_at")
    provenance = run["provenance"]
    if not isinstance(provenance, list) or not provenance:
        raise LiveObservationStreamError(
            "live observation stream.run.provenance must be a non-empty list"
        )
    for index, item in enumerate(provenance):
        if not isinstance(item, Mapping) or set(item) - {"id", "kind", "revision"} or {
            "id",
            "kind",
        } - set(item):
            raise LiveObservationStreamError(
                f"live observation stream.run.provenance[{index}] is invalid"
            )
        _identifier(item["id"], f"live observation stream.run.provenance[{index}].id")
        _nonempty_text(item["kind"], f"live observation stream.run.provenance[{index}].kind")
        if "revision" in item:
            _nonempty_text(
                item["revision"],
                f"live observation stream.run.provenance[{index}].revision",
            )
    stale_after = header["stale_after_seconds"]
    if isinstance(stale_after, bool) or not isinstance(stale_after, (int, float)) or not math.isfinite(stale_after) or stale_after <= 0:
        raise LiveObservationStreamError(
            "live observation stream.stale_after_seconds must be a positive number"
        )
    try:
        validate_normalized_topology(header["topology"])
    except RunSummaryValidationError as error:
        raise LiveObservationStreamError(
            f"invalid live observation stream topology: {error}"
        ) from error


def _identifier(value: object, location: str) -> None:
    _nonempty_text(value, location)
    if not _IDENTIFIER.fullmatch(str(value)):
        raise LiveObservationStreamError(f"{location} is not a stable identifier: {value!r}")


def _nonempty_text(value: object, location: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveObservationStreamError(f"{location} must be a non-empty string")


def _parse_timestamp(value: object, location: str) -> datetime:
    _nonempty_text(value, location)
    if not str(value).endswith("Z"):
        raise LiveObservationStreamError(f"{location} must be an RFC 3339 UTC timestamp")
    try:
        return datetime.fromisoformat(str(value).removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise LiveObservationStreamError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error


def _utc_datetime(value: datetime | None) -> datetime:
    current_time = value or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("live snapshot time must be timezone-aware")
    return current_time.astimezone(timezone.utc)


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy(item) for item in value]
    return value
