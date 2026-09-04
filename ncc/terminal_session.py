"""Strict retained byte stream for the foreground historical terminal."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping


TERMINAL_SESSION_SCHEMA_VERSION = 1
TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION = 2
TERMINAL_SESSION_KIND = "historical-terminal-session"
TERMINAL_SESSION_RECORD_ORDER = "controller-sequence"
DEFAULT_MAX_INPUT_BYTES = 1024 * 1024
DEFAULT_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_CHUNK_BYTES = 4096

_ABSOLUTE_MAX_INPUT_BYTES = 16 * 1024 * 1024
_ABSOLUTE_MAX_OUTPUT_BYTES = 64 * 1024 * 1024
_ABSOLUTE_MAX_CHUNK_BYTES = 65536
_DIRECTIONS = {"operator-to-pdp11", "pdp11-to-operator"}
_CONTROLS = {"blocked-simulator-wru", "rejected-non-seven-bit"}
_FAILOVER_CONTROLS = _CONTROLS | {
    "application-link-cut-requested",
    "application-link-cut-not-ready",
    "application-link-cut-already-requested",
}
_END_REASONS = {
    "operator-exit",
    "input-eof",
    "interrupted",
    "process-exit",
    "input-limit",
    "output-limit",
    "failed",
}
_REVISION = re.compile(r"[0-9a-f]{40}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


class TerminalSessionStreamError(ValueError):
    """Raised when a terminal-session stream violates its contract."""


@dataclass(frozen=True)
class TerminalSession:
    """Validated terminal bytes and terminal state."""

    _header: Mapping[str, Any]
    input_bytes: bytes
    output_bytes: bytes
    controls: tuple[tuple[str, int], ...]
    is_terminal: bool
    end_reason: str | None
    has_incomplete_final_record: bool

    @property
    def header(self) -> Mapping[str, Any]:
        return self._header


class TerminalSessionRecorder:
    """Append bounded directional byte chunks and local safety controls."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        started_at: str,
        repository_revision: str,
        max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        max_chunk_bytes: int = DEFAULT_MAX_CHUNK_BYTES,
        failover: bool = False,
    ) -> None:
        self.path = Path(path)
        self.max_input_bytes = _bounded_positive_integer(
            max_input_bytes,
            "terminal max_input_bytes",
            _ABSOLUTE_MAX_INPUT_BYTES,
        )
        self.max_output_bytes = _bounded_positive_integer(
            max_output_bytes,
            "terminal max_output_bytes",
            _ABSOLUTE_MAX_OUTPUT_BYTES,
        )
        self.max_chunk_bytes = _bounded_positive_integer(
            max_chunk_bytes,
            "terminal max_chunk_bytes",
            _ABSOLUTE_MAX_CHUNK_BYTES,
        )
        if self.max_chunk_bytes > max(self.max_input_bytes, self.max_output_bytes):
            raise TerminalSessionStreamError(
                "terminal max_chunk_bytes exceeds both directional limits"
            )
        header = _start_record(
            run_id=run_id,
            started_at=started_at,
            repository_revision=repository_revision,
            max_input_bytes=self.max_input_bytes,
            max_output_bytes=self.max_output_bytes,
            max_chunk_bytes=self.max_chunk_bytes,
            failover=failover,
        )
        self._header = _parse_header(header)
        self._schema_version = int(self._header["schema_version"])
        self._next_sequence = 1
        self._input_bytes = 0
        self._output_bytes = 0
        self._input_hash = hashlib.sha256()
        self._output_hash = hashlib.sha256()
        self._data_records = 0
        self._control_records = 0
        self._terminal = False
        self._closed = False
        try:
            self._stream = self.path.open("x", encoding="utf-8")
        except OSError as error:
            raise TerminalSessionStreamError(
                f"could not create terminal-session stream {self.path}: {error}"
            ) from error
        self._write(self._header)

    def bytes(self, direction: str, data: bytes, *, observed_at: str) -> None:
        """Append one or more chunks without changing their byte sequence."""

        self._ensure_writable()
        if direction not in _DIRECTIONS:
            raise TerminalSessionStreamError(
                f"terminal-session stream has unknown direction {direction!r}"
            )
        if not isinstance(data, bytes):
            raise TypeError("terminal-session data must be bytes")
        if not data:
            return
        for offset in range(0, len(data), self.max_chunk_bytes):
            self._append_chunk(
                direction,
                data[offset : offset + self.max_chunk_bytes],
                observed_at,
            )

    def control(self, control: str, *, observed_at: str, count: int = 1) -> None:
        """Record a controller-owned input decision that sent no guest byte."""

        self._ensure_writable()
        if control not in _controls_for_schema(self._schema_version):
            raise TerminalSessionStreamError(
                f"terminal-session stream has unknown local control {control!r}"
            )
        count = _bounded_positive_integer(count, "terminal local-control count", 65536)
        record = {
            "record_type": "local-control",
            "sequence": self._next_sequence,
            "observed_at": observed_at,
            "control": control,
            "count": count,
        }
        _parse_control(
            record,
            self._next_sequence,
            schema_version=self._schema_version,
        )
        self._write(record)
        self._next_sequence += 1
        self._control_records += 1

    def complete(self, *, observed_at: str, reason: str) -> None:
        """Close the stream with cumulative counts and direction digests."""

        self._ensure_writable()
        if reason not in _END_REASONS:
            raise TerminalSessionStreamError(
                f"terminal-session stream has unknown end reason {reason!r}"
            )
        record = {
            "record_type": "session-end",
            "sequence": self._next_sequence,
            "observed_at": observed_at,
            "reason": reason,
            "input_bytes": self._input_bytes,
            "output_bytes": self._output_bytes,
            "input_sha256": self._input_hash.hexdigest(),
            "output_sha256": self._output_hash.hexdigest(),
            "data_records": self._data_records,
            "control_records": self._control_records,
        }
        _parse_end(
            record,
            self._next_sequence,
            input_bytes=self._input_bytes,
            output_bytes=self._output_bytes,
            input_sha256=self._input_hash.hexdigest(),
            output_sha256=self._output_hash.hexdigest(),
            data_records=self._data_records,
            control_records=self._control_records,
        )
        self._write(record)
        self._next_sequence += 1
        self._terminal = True

    def close(self) -> None:
        if not self._closed:
            self._stream.close()
            self._closed = True

    def _append_chunk(self, direction: str, chunk: bytes, observed_at: str) -> None:
        if direction == "operator-to-pdp11":
            if self._input_bytes + len(chunk) > self.max_input_bytes:
                raise TerminalSessionStreamError(
                    "terminal-session input exceeds its declared limit"
                )
        elif self._output_bytes + len(chunk) > self.max_output_bytes:
            raise TerminalSessionStreamError(
                "terminal-session output exceeds its declared limit"
            )
        record = {
            "record_type": "bytes",
            "sequence": self._next_sequence,
            "observed_at": observed_at,
            "direction": direction,
            "encoding": "base64",
            "data": base64.b64encode(chunk).decode("ascii"),
            "byte_count": len(chunk),
            "sha256": hashlib.sha256(chunk).hexdigest(),
        }
        _parse_bytes(record, self._next_sequence, self.max_chunk_bytes)
        self._write(record)
        self._next_sequence += 1
        self._data_records += 1
        if direction == "operator-to-pdp11":
            self._input_bytes += len(chunk)
            self._input_hash.update(chunk)
        else:
            self._output_bytes += len(chunk)
            self._output_hash.update(chunk)

    def _ensure_writable(self) -> None:
        if self._closed or self._terminal:
            raise TerminalSessionStreamError(
                "cannot append to a closed or terminal terminal-session stream"
            )

    def _write(self, record: Mapping[str, Any]) -> None:
        self._stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        self._stream.flush()


def read_terminal_session_stream(path: str | Path) -> TerminalSession:
    """Read complete records, ignoring only an interrupted final record."""

    stream_path = Path(path)
    try:
        contents = stream_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise TerminalSessionStreamError(
            f"could not read terminal-session stream {stream_path}: {error}"
        ) from error
    lines = contents.splitlines()
    incomplete = bool(contents and not contents.endswith("\n"))
    if incomplete:
        lines.pop()
    if not lines:
        raise TerminalSessionStreamError(
            "terminal-session stream has no complete session-start record"
        )
    records: list[object] = []
    for number, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise TerminalSessionStreamError(
                f"terminal-session stream line {number} is not JSON: {error}"
            ) from error

    header = _parse_header(records[0])
    schema_version = int(header["schema_version"])
    limits = _mapping(header["limits"], "terminal session-start.limits")
    max_input_bytes = int(limits["max_input_bytes"])
    max_output_bytes = int(limits["max_output_bytes"])
    max_chunk_bytes = int(limits["max_chunk_bytes"])
    expected_sequence = 1
    input_data = bytearray()
    output_data = bytearray()
    controls: list[tuple[str, int]] = []
    data_records = 0
    terminal: Mapping[str, Any] | None = None
    for number, raw_record in enumerate(records[1:], start=2):
        if terminal is not None:
            raise TerminalSessionStreamError(
                "terminal-session stream has a record after session-end"
            )
        record = _mapping(raw_record, f"terminal-session stream line {number}")
        record_type = record.get("record_type")
        if record_type == "bytes":
            parsed = _parse_bytes(record, expected_sequence, max_chunk_bytes)
            target = input_data if parsed["direction"] == "operator-to-pdp11" else output_data
            target.extend(parsed["decoded"])
            if len(input_data) > max_input_bytes or len(output_data) > max_output_bytes:
                raise TerminalSessionStreamError(
                    "terminal-session stream exceeds a declared directional limit"
                )
            data_records += 1
        elif record_type == "local-control":
            parsed = _parse_control(
                record,
                expected_sequence,
                schema_version=schema_version,
            )
            controls.append((str(parsed["control"]), int(parsed["count"])))
        elif record_type == "session-end":
            terminal = _parse_end(
                record,
                expected_sequence,
                input_bytes=len(input_data),
                output_bytes=len(output_data),
                input_sha256=hashlib.sha256(input_data).hexdigest(),
                output_sha256=hashlib.sha256(output_data).hexdigest(),
                data_records=data_records,
                control_records=len(controls),
            )
        else:
            raise TerminalSessionStreamError(
                f"terminal-session stream line {number} has unknown record_type {record_type!r}"
            )
        expected_sequence += 1

    return TerminalSession(
        _header=MappingProxyType(_copy(header)),
        input_bytes=bytes(input_data),
        output_bytes=bytes(output_data),
        controls=tuple(controls),
        is_terminal=terminal is not None,
        end_reason=str(terminal["reason"]) if terminal is not None else None,
        has_incomplete_final_record=incomplete,
    )


def _start_record(
    *,
    run_id: str,
    started_at: str,
    repository_revision: str,
    max_input_bytes: int,
    max_output_bytes: int,
    max_chunk_bytes: int,
    failover: bool,
) -> dict[str, Any]:
    header: dict[str, Any] = {
        "schema_version": (
            TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION
            if failover
            else TERMINAL_SESSION_SCHEMA_VERSION
        ),
        "kind": TERMINAL_SESSION_KIND,
        "record_order": TERMINAL_SESSION_RECORD_ORDER,
        "record_type": "session-start",
        "sequence": 0,
        "run": {
            "id": run_id,
            "started_at": started_at,
            "repository_revision": repository_revision,
        },
        "ownership": {
            "controller": (
                "pdp11-its-failover-controller"
                if failover
                else "pdp11-its-interactive-controller"
            ),
            "input_source": "operator-terminal",
            "response_source": "pdp11-console",
        },
        "terminal": {
            "mode": "character-oriented",
            "profile": "seven-bit-safe-teletype",
            "local_exit": "control-right-bracket",
            "simulator_wru": "control-backslash-blocked",
            "line_feed_input": "carriage-return",
            "delete_input": "backspace",
            "high_bit_input": "rejected",
            "unsafe_output_controls": "escaped-hex",
        },
        "limits": {
            "max_input_bytes": max_input_bytes,
            "max_output_bytes": max_output_bytes,
            "max_chunk_bytes": max_chunk_bytes,
        },
    }
    if failover:
        header["route_plan"] = {
            "client_id": "host:176",
            "server_id": "host:106",
            "initial_route_id": "route:host176-to-host106",
            "post_cut_route_id": "route:host176-to-host106-alternate",
        }
        header["terminal"]["application_link_cut"] = "control-caret"
    else:
        header["available_route"] = {
            "client_id": "host:176",
            "server_id": "host:106",
            "route_id": "route:host176-to-host106",
        }
    return header


def _parse_header(record: object) -> dict[str, Any]:
    value = _mapping(record, "terminal session-start")
    schema_version = value.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in {
        TERMINAL_SESSION_SCHEMA_VERSION,
        TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION,
    }:
        raise TerminalSessionStreamError("terminal-session stream has invalid start semantics")
    route_field = (
        "route_plan"
        if schema_version == TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION
        else "available_route"
    )
    _fields(
        value,
        "terminal session-start",
        {
            "schema_version",
            "kind",
            "record_order",
            "record_type",
            "sequence",
            "run",
            route_field,
            "ownership",
            "terminal",
            "limits",
        },
    )
    if (
        value["kind"] != TERMINAL_SESSION_KIND
        or value["record_order"] != TERMINAL_SESSION_RECORD_ORDER
        or value["record_type"] != "session-start"
        or isinstance(value["sequence"], bool)
        or value["sequence"] != 0
    ):
        raise TerminalSessionStreamError("terminal-session stream has invalid start semantics")

    run = _mapping(value["run"], "terminal session-start.run")
    _fields(run, "terminal session-start.run", {"id", "started_at", "repository_revision"})
    if not isinstance(run["id"], str) or not _IDENTIFIER.fullmatch(run["id"]):
        raise TerminalSessionStreamError("terminal-session run id is invalid")
    _timestamp(run["started_at"], "terminal-session start time")
    if not isinstance(run["repository_revision"], str) or not _REVISION.fullmatch(
        run["repository_revision"]
    ):
        raise TerminalSessionStreamError(
            "terminal-session repository revision must be a full commit id"
        )

    route = _mapping(value[route_field], f"terminal session-start.{route_field}")
    if schema_version == TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION:
        _fields(
            route,
            "terminal session-start.route_plan",
            {"client_id", "server_id", "initial_route_id", "post_cut_route_id"},
        )
        expected_route = {
            "client_id": "host:176",
            "server_id": "host:106",
            "initial_route_id": "route:host176-to-host106",
            "post_cut_route_id": "route:host176-to-host106-alternate",
        }
    else:
        _fields(
            route,
            "terminal session-start.available_route",
            {"client_id", "server_id", "route_id"},
        )
        expected_route = {
            "client_id": "host:176",
            "server_id": "host:106",
            "route_id": "route:host176-to-host106",
        }
    if route != expected_route:
        raise TerminalSessionStreamError("terminal-session stream names an unsupported route")

    ownership = _mapping(value["ownership"], "terminal session-start.ownership")
    _fields(
        ownership,
        "terminal session-start.ownership",
        {"controller", "input_source", "response_source"},
    )
    if ownership != {
        "controller": (
            "pdp11-its-failover-controller"
            if schema_version == TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION
            else "pdp11-its-interactive-controller"
        ),
        "input_source": "operator-terminal",
        "response_source": "pdp11-console",
    }:
        raise TerminalSessionStreamError("terminal-session stream has invalid ownership")

    terminal = _mapping(value["terminal"], "terminal session-start.terminal")
    expected_terminal = {
        "mode": "character-oriented",
        "profile": "seven-bit-safe-teletype",
        "local_exit": "control-right-bracket",
        "simulator_wru": "control-backslash-blocked",
        "line_feed_input": "carriage-return",
        "delete_input": "backspace",
        "high_bit_input": "rejected",
        "unsafe_output_controls": "escaped-hex",
    }
    if schema_version == TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION:
        expected_terminal["application_link_cut"] = "control-caret"
    _fields(
        terminal,
        "terminal session-start.terminal",
        set(expected_terminal),
    )
    if terminal != expected_terminal:
        raise TerminalSessionStreamError("terminal-session stream has invalid terminal profile")

    limits = _mapping(value["limits"], "terminal session-start.limits")
    _fields(
        limits,
        "terminal session-start.limits",
        {"max_input_bytes", "max_output_bytes", "max_chunk_bytes"},
    )
    _bounded_positive_integer(
        limits["max_input_bytes"],
        "terminal max_input_bytes",
        _ABSOLUTE_MAX_INPUT_BYTES,
    )
    _bounded_positive_integer(
        limits["max_output_bytes"],
        "terminal max_output_bytes",
        _ABSOLUTE_MAX_OUTPUT_BYTES,
    )
    chunk = _bounded_positive_integer(
        limits["max_chunk_bytes"],
        "terminal max_chunk_bytes",
        _ABSOLUTE_MAX_CHUNK_BYTES,
    )
    if chunk > max(int(limits["max_input_bytes"]), int(limits["max_output_bytes"])):
        raise TerminalSessionStreamError(
            "terminal max_chunk_bytes exceeds both directional limits"
        )
    return _copy(value)


def _parse_bytes(
    record: Mapping[str, Any], expected_sequence: int, max_chunk_bytes: int
) -> dict[str, Any]:
    _fields(
        record,
        "terminal bytes record",
        {
            "record_type",
            "sequence",
            "observed_at",
            "direction",
            "encoding",
            "data",
            "byte_count",
            "sha256",
        },
    )
    if (
        record["record_type"] != "bytes"
        or isinstance(record["sequence"], bool)
        or record["sequence"] != expected_sequence
    ):
        raise TerminalSessionStreamError("terminal bytes record has invalid ordering")
    _timestamp(record["observed_at"], "terminal bytes observation time")
    if record["direction"] not in _DIRECTIONS or record["encoding"] != "base64":
        raise TerminalSessionStreamError("terminal bytes record has invalid direction or encoding")
    if not isinstance(record["data"], str):
        raise TerminalSessionStreamError("terminal bytes record data must be base64 text")
    try:
        decoded = base64.b64decode(record["data"], validate=True)
    except (ValueError, binascii.Error) as error:
        raise TerminalSessionStreamError(
            "terminal bytes record has invalid base64 data"
        ) from error
    if not decoded or len(decoded) > max_chunk_bytes:
        raise TerminalSessionStreamError("terminal bytes record has an invalid chunk size")
    if (
        isinstance(record["byte_count"], bool)
        or record["byte_count"] != len(decoded)
        or not isinstance(record["sha256"], str)
        or not _SHA256.fullmatch(record["sha256"])
        or record["sha256"] != hashlib.sha256(decoded).hexdigest()
    ):
        raise TerminalSessionStreamError("terminal bytes record count or digest disagrees")
    parsed = dict(record)
    parsed["decoded"] = decoded
    return parsed


def _controls_for_schema(schema_version: int) -> set[str]:
    if schema_version == TERMINAL_SESSION_SCHEMA_VERSION:
        return _CONTROLS
    if schema_version == TERMINAL_SESSION_FAILOVER_SCHEMA_VERSION:
        return _FAILOVER_CONTROLS
    raise TerminalSessionStreamError("terminal-session stream has unsupported controls")


def _parse_control(
    record: Mapping[str, Any],
    expected_sequence: int,
    *,
    schema_version: int,
) -> dict[str, Any]:
    _fields(
        record,
        "terminal local-control record",
        {"record_type", "sequence", "observed_at", "control", "count"},
    )
    if (
        record["record_type"] != "local-control"
        or isinstance(record["sequence"], bool)
        or record["sequence"] != expected_sequence
    ):
        raise TerminalSessionStreamError("terminal local-control record has invalid ordering")
    _timestamp(record["observed_at"], "terminal local-control observation time")
    if record["control"] not in _controls_for_schema(schema_version):
        raise TerminalSessionStreamError("terminal local-control record has an unknown control")
    _bounded_positive_integer(record["count"], "terminal local-control count", 65536)
    return dict(record)


def _parse_end(
    record: Mapping[str, Any],
    expected_sequence: int,
    *,
    input_bytes: int,
    output_bytes: int,
    input_sha256: str,
    output_sha256: str,
    data_records: int,
    control_records: int,
) -> dict[str, Any]:
    _fields(
        record,
        "terminal session-end",
        {
            "record_type",
            "sequence",
            "observed_at",
            "reason",
            "input_bytes",
            "output_bytes",
            "input_sha256",
            "output_sha256",
            "data_records",
            "control_records",
        },
    )
    if (
        record["record_type"] != "session-end"
        or isinstance(record["sequence"], bool)
        or record["sequence"] != expected_sequence
    ):
        raise TerminalSessionStreamError("terminal session-end has invalid ordering")
    _timestamp(record["observed_at"], "terminal session-end observation time")
    if record["reason"] not in _END_REASONS:
        raise TerminalSessionStreamError("terminal session-end has an unknown reason")
    expected = {
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
        "data_records": data_records,
        "control_records": control_records,
    }
    for key in ("input_bytes", "output_bytes", "data_records", "control_records"):
        if isinstance(record[key], bool) or not isinstance(record[key], int):
            raise TerminalSessionStreamError(
                "terminal session-end counts or digests disagree"
            )
    for key in ("input_sha256", "output_sha256"):
        if not isinstance(record[key], str) or not _SHA256.fullmatch(record[key]):
            raise TerminalSessionStreamError(
                "terminal session-end counts or digests disagree"
            )
    if any(record[key] != value for key, value in expected.items()):
        raise TerminalSessionStreamError("terminal session-end counts or digests disagree")
    return dict(record)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TerminalSessionStreamError(f"{label} must be an object")
    return value


def _fields(value: Mapping[str, Any], label: str, expected: set[str]) -> None:
    if set(value) != expected:
        raise TerminalSessionStreamError(f"{label} has unexpected or missing fields")


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise TerminalSessionStreamError(f"{label} is invalid")
    return value


def _bounded_positive_integer(value: object, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise TerminalSessionStreamError(f"{label} must be between 1 and {maximum}")
    return value


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    return value
