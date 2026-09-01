"""Versioned transcript for one terminal-owned interactive TELNET session.

The stream records operator lines and the exact PDP-11 console bytes captured
through the next ITS DDT prompt. It neither parses guest host ingress nor owns
simulator, browser, or network control.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any


INTERACTIVE_TELNET_STREAM_SCHEMA_VERSION = 1
INTERACTIVE_TELNET_STREAM_KIND = "interactive-telnet-session"
INTERACTIVE_TELNET_RECORD_ORDER = "single-controller-emission-order"
DEFAULT_MAX_COMMAND_BYTES = 256
DEFAULT_MAX_COMMANDS = 100
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_COMMAND_TIMEOUT_SECONDS = 60

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SERVICE_USER = re.compile(r"[0-9]+TLNT\Z")
_RESULT_STATUSES = {
    "complete",
    "interrupted",
    "response-limit",
    "session-closed",
    "timeout",
}
_END_REASONS = {
    "failed",
    "input-eof",
    "interrupted",
    "max-commands",
    "operator-quit",
}


class InteractiveTelnetStreamError(ValueError):
    """Raised when an interactive session transcript cannot be trusted."""


@dataclass(frozen=True)
class InteractiveTelnetExchange:
    """One validated operator command and its bounded captured result."""

    command_id: str
    command: str
    command_observed_at: str
    result_observed_at: str
    status: str
    prompt_id: str | None
    elapsed_ms: int
    captured: bytes
    truncated: bool


@dataclass(frozen=True)
class InteractiveTelnetStream:
    """A validated snapshot of one append-only interactive transcript."""

    _header: Mapping[str, Any]
    exchanges: tuple[InteractiveTelnetExchange, ...]
    is_terminal: bool
    end_reason: str | None
    has_incomplete_final_record: bool = False

    @property
    def run_id(self) -> str:
        return str(self._header["run"]["id"])

    @property
    def completed_commands(self) -> int:
        return sum(exchange.status == "complete" for exchange in self.exchanges)

    @property
    def failed_commands(self) -> int:
        return len(self.exchanges) - self.completed_commands

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh JSON-safe representation for passive consumers."""

        return {
            "header": _copy(self._header),
            "exchanges": [
                {
                    "command_id": exchange.command_id,
                    "command": exchange.command,
                    "command_observed_at": exchange.command_observed_at,
                    "result_observed_at": exchange.result_observed_at,
                    "status": exchange.status,
                    "prompt_id": exchange.prompt_id,
                    "elapsed_ms": exchange.elapsed_ms,
                    "captured_latin1": exchange.captured.decode("latin-1"),
                    "captured_bytes": len(exchange.captured),
                    "captured_sha256": hashlib.sha256(exchange.captured).hexdigest(),
                    "truncated": exchange.truncated,
                }
                for exchange in self.exchanges
            ],
            "is_terminal": self.is_terminal,
            "end_reason": self.end_reason,
            "has_incomplete_final_record": self.has_incomplete_final_record,
        }


class InteractiveTelnetRecorder:
    """Append strict command/result pairs and one terminal session record."""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        started_at: str,
        repository_revision: str,
        service_user: str,
        command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
        max_command_bytes: int = DEFAULT_MAX_COMMAND_BYTES,
        max_commands: int = DEFAULT_MAX_COMMANDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        self.path = Path(path)
        self.max_command_bytes = _positive_integer(
            max_command_bytes, "interactive TELNET max_command_bytes"
        )
        self.max_commands = _positive_integer(
            max_commands, "interactive TELNET max_commands"
        )
        self.max_response_bytes = _positive_integer(
            max_response_bytes, "interactive TELNET max_response_bytes"
        )
        self.command_timeout_seconds = _positive_integer(
            command_timeout_seconds,
            "interactive TELNET command_timeout_seconds",
        )
        header = {
            "schema_version": INTERACTIVE_TELNET_STREAM_SCHEMA_VERSION,
            "kind": INTERACTIVE_TELNET_STREAM_KIND,
            "record_order": INTERACTIVE_TELNET_RECORD_ORDER,
            "record_type": "session-start",
            "sequence": 0,
            "run": {
                "id": run_id,
                "started_at": started_at,
                "repository_revision": repository_revision,
            },
            "route": {
                "client_id": "host:176",
                "server_id": "host:106",
                "route_id": "route:host176-to-host106",
            },
            "application": {
                "client": "network-unix-telnet",
                "server": "TELSER",
                "service_user": service_user,
            },
            "ownership": {
                "controller": "pdp11-its-interactive-controller",
                "input_source": "operator-stdin",
                "response_source": "pdp11-console",
            },
            "framing": {
                "mode": "line-oriented",
                "line_ending": "carriage-return",
                "prompt_id": "its-ddt-star",
                "prompt_pattern": "CRLF ASTERISK",
                "response_encoding": "latin-1",
            },
            "limits": {
                "command_timeout_seconds": self.command_timeout_seconds,
                "max_command_bytes": self.max_command_bytes,
                "max_commands": self.max_commands,
                "max_response_bytes": self.max_response_bytes,
            },
        }
        self._header = _parse_header(header)
        self._next_sequence = 1
        self._command_count = 0
        self._completed_commands = 0
        self._failed_commands = 0
        self._pending: str | None = None
        self._failed = False
        self._terminal = False
        self._closed = False
        try:
            self._stream = self.path.open("x", encoding="utf-8")
        except OSError as error:
            raise InteractiveTelnetStreamError(
                f"could not create interactive TELNET stream {self.path}: {error}"
            ) from error
        self._write(self._header)

    def command(self, text: str, *, observed_at: str) -> str:
        """Append one attributed printable operator line."""

        self._ensure_writable()
        if self._pending is not None:
            raise InteractiveTelnetStreamError(
                "cannot append a command before the pending result"
            )
        if self._failed:
            raise InteractiveTelnetStreamError(
                "cannot append a command after a failed result"
            )
        if self._command_count >= self.max_commands:
            raise InteractiveTelnetStreamError(
                "interactive TELNET command limit has been reached"
            )
        command = validate_operator_command(text, self.max_command_bytes)
        command_id = f"command:{self._command_count + 1}"
        record = {
            "record_type": "command",
            "sequence": self._next_sequence,
            "command_id": command_id,
            "observed_at": observed_at,
            "input_source": "operator-stdin",
            "text": command,
            "encoded_bytes": len(command.encode("ascii")),
        }
        _parse_command(
            record,
            self._next_sequence,
            self._command_count + 1,
            self.max_command_bytes,
        )
        self._write(record)
        self._next_sequence += 1
        self._command_count += 1
        self._pending = command_id
        return command_id

    def result(
        self,
        command_id: str,
        *,
        observed_at: str,
        status: str,
        elapsed_ms: int,
        captured: bytes,
        truncated: bool = False,
    ) -> None:
        """Append the exact bounded console capture for the pending command."""

        self._ensure_writable()
        if self._pending is None or command_id != self._pending:
            raise InteractiveTelnetStreamError(
                "interactive TELNET result does not match the pending command"
            )
        if not isinstance(captured, bytes):
            raise TypeError("interactive TELNET captured response must be bytes")
        if len(captured) > self.max_response_bytes:
            raise InteractiveTelnetStreamError(
                "interactive TELNET captured response exceeds its declared limit"
            )
        if status not in _RESULT_STATUSES:
            raise InteractiveTelnetStreamError(
                f"interactive TELNET result has unknown status {status!r}"
            )
        prompt_id = "its-ddt-star" if status == "complete" else None
        record = {
            "record_type": "result",
            "sequence": self._next_sequence,
            "command_id": command_id,
            "observed_at": observed_at,
            "response_source": "pdp11-console",
            "status": status,
            "prompt_id": prompt_id,
            "elapsed_ms": elapsed_ms,
            "captured_latin1": captured.decode("latin-1"),
            "captured_bytes": len(captured),
            "captured_sha256": hashlib.sha256(captured).hexdigest(),
            "truncated": truncated,
        }
        _parse_result(
            record,
            self._next_sequence,
            command_id,
            self.max_response_bytes,
        )
        self._write(record)
        self._next_sequence += 1
        self._pending = None
        if status == "complete":
            self._completed_commands += 1
        else:
            self._failed_commands += 1
            self._failed = True

    def complete(self, *, observed_at: str, reason: str) -> None:
        """Append the exact counts and reason that close the session."""

        self._ensure_writable()
        if self._pending is not None:
            raise InteractiveTelnetStreamError(
                "cannot complete an interactive TELNET stream with a pending command"
            )
        record = {
            "record_type": "session-end",
            "sequence": self._next_sequence,
            "observed_at": observed_at,
            "reason": reason,
            "command_count": self._command_count,
            "completed_commands": self._completed_commands,
            "failed_commands": self._failed_commands,
        }
        _parse_end(
            record,
            self._next_sequence,
            command_count=self._command_count,
            completed_commands=self._completed_commands,
            failed_commands=self._failed_commands,
        )
        self._write(record)
        self._next_sequence += 1
        self._terminal = True

    def close(self) -> None:
        if not self._closed:
            self._stream.close()
            self._closed = True

    def _ensure_writable(self) -> None:
        if self._closed or self._terminal:
            raise InteractiveTelnetStreamError(
                "cannot append to a closed or terminal interactive TELNET stream"
            )

    def _write(self, record: Mapping[str, Any]) -> None:
        self._stream.write(
            json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
        )
        self._stream.flush()


def validate_operator_command(
    text: str, max_command_bytes: int = DEFAULT_MAX_COMMAND_BYTES
) -> str:
    """Validate one line before it can reach the guest TELNET client."""

    limit = _positive_integer(max_command_bytes, "interactive TELNET command limit")
    if not isinstance(text, str):
        raise InteractiveTelnetStreamError("operator command must be text")
    if not text or not text.strip():
        raise InteractiveTelnetStreamError("operator command must not be blank")
    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as error:
        raise InteractiveTelnetStreamError(
            "operator command must contain only printable ASCII"
        ) from error
    if len(encoded) > limit:
        raise InteractiveTelnetStreamError(
            f"operator command exceeds the {limit}-byte limit"
        )
    if any(byte < 0x20 or byte > 0x7E for byte in encoded):
        raise InteractiveTelnetStreamError(
            "operator command must contain only printable ASCII"
        )
    return text


def read_interactive_telnet_stream(path: str | Path) -> InteractiveTelnetStream:
    """Read complete JSON Lines, ignoring only an interrupted final record."""

    stream_path = Path(path)
    try:
        contents = stream_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InteractiveTelnetStreamError(
            f"could not read interactive TELNET stream {stream_path}: {error}"
        ) from error
    lines = contents.splitlines()
    incomplete = bool(contents and not contents.endswith("\n"))
    if incomplete:
        lines.pop()
    if not lines:
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream has no complete session-start record"
        )
    records: list[object] = []
    for number, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise InteractiveTelnetStreamError(
                f"interactive TELNET stream line {number} is not JSON: {error}"
            ) from error

    header = _parse_header(records[0])
    limits = _mapping(header["limits"], "interactive TELNET session-start.limits")
    max_command_bytes = int(limits["max_command_bytes"])
    max_commands = int(limits["max_commands"])
    max_response_bytes = int(limits["max_response_bytes"])
    expected_sequence = 1
    expected_command_number = 1
    pending: tuple[str, str, str] | None = None
    exchanges: list[InteractiveTelnetExchange] = []
    failed = False
    terminal: Mapping[str, Any] | None = None
    for number, raw_record in enumerate(records[1:], start=2):
        if terminal is not None:
            raise InteractiveTelnetStreamError(
                "interactive TELNET stream has a record after session-end"
            )
        record = _mapping(raw_record, f"interactive TELNET stream line {number}")
        record_type = record.get("record_type")
        if record_type == "command":
            if expected_command_number > max_commands:
                raise InteractiveTelnetStreamError(
                    "interactive TELNET stream exceeds its declared command limit"
                )
            if pending is not None:
                raise InteractiveTelnetStreamError(
                    "interactive TELNET stream has a command before its pending result"
                )
            if failed:
                raise InteractiveTelnetStreamError(
                    "interactive TELNET stream has a command after a failed result"
                )
            command = _parse_command(
                record,
                expected_sequence,
                expected_command_number,
                max_command_bytes,
            )
            pending = (
                command["command_id"],
                command["text"],
                command["observed_at"],
            )
            expected_sequence += 1
            expected_command_number += 1
            continue
        if record_type == "result":
            if pending is None:
                raise InteractiveTelnetStreamError(
                    "interactive TELNET stream has a result without a command"
                )
            result = _parse_result(
                record,
                expected_sequence,
                pending[0],
                max_response_bytes,
            )
            captured = result["captured_latin1"].encode("latin-1")
            exchanges.append(
                InteractiveTelnetExchange(
                    command_id=pending[0],
                    command=pending[1],
                    command_observed_at=pending[2],
                    result_observed_at=result["observed_at"],
                    status=result["status"],
                    prompt_id=result["prompt_id"],
                    elapsed_ms=result["elapsed_ms"],
                    captured=captured,
                    truncated=result["truncated"],
                )
            )
            failed = result["status"] != "complete"
            pending = None
            expected_sequence += 1
            continue
        if record_type == "session-end":
            if pending is not None:
                raise InteractiveTelnetStreamError(
                    "interactive TELNET session ended with a pending command"
                )
            completed = sum(item.status == "complete" for item in exchanges)
            terminal = _parse_end(
                record,
                expected_sequence,
                command_count=len(exchanges),
                completed_commands=completed,
                failed_commands=len(exchanges) - completed,
            )
            expected_sequence += 1
            continue
        raise InteractiveTelnetStreamError(
            f"interactive TELNET stream line {number} has unknown record_type {record_type!r}"
        )

    return InteractiveTelnetStream(
        _header=MappingProxyType(_copy(header)),
        exchanges=tuple(exchanges),
        is_terminal=terminal is not None,
        end_reason=str(terminal["reason"]) if terminal is not None else None,
        has_incomplete_final_record=incomplete,
    )


def _parse_header(record: object) -> dict[str, Any]:
    value = _mapping(record, "interactive TELNET session-start")
    _fields(
        value,
        "interactive TELNET session-start",
        {
            "schema_version",
            "kind",
            "record_order",
            "record_type",
            "sequence",
            "run",
            "route",
            "application",
            "ownership",
            "framing",
            "limits",
        },
    )
    if (
        isinstance(value["schema_version"], bool)
        or value["schema_version"] != INTERACTIVE_TELNET_STREAM_SCHEMA_VERSION
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream has an unsupported schema version"
        )
    if (
        value["kind"] != INTERACTIVE_TELNET_STREAM_KIND
        or value["record_order"] != INTERACTIVE_TELNET_RECORD_ORDER
        or value["record_type"] != "session-start"
        or value["sequence"] != 0
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream has invalid start semantics"
        )

    run = _mapping(value["run"], "interactive TELNET session-start.run")
    _fields(run, "interactive TELNET session-start.run", {"id", "started_at", "repository_revision"})
    _identifier(run["id"], "interactive TELNET run id")
    _timestamp(run["started_at"], "interactive TELNET start time")
    if not isinstance(run["repository_revision"], str) or not _REVISION.fullmatch(
        run["repository_revision"]
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET repository revision must be a full commit id"
        )

    route = _mapping(value["route"], "interactive TELNET session-start.route")
    _fields(route, "interactive TELNET session-start.route", {"client_id", "server_id", "route_id"})
    if route != {
        "client_id": "host:176",
        "server_id": "host:106",
        "route_id": "route:host176-to-host106",
    }:
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream names an unsupported route"
        )

    application = _mapping(
        value["application"], "interactive TELNET session-start.application"
    )
    _fields(
        application,
        "interactive TELNET session-start.application",
        {"client", "server", "service_user"},
    )
    if (
        application["client"] != "network-unix-telnet"
        or application["server"] != "TELSER"
        or not isinstance(application["service_user"], str)
        or not _SERVICE_USER.fullmatch(application["service_user"])
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream has invalid application identity"
        )

    ownership = _mapping(
        value["ownership"], "interactive TELNET session-start.ownership"
    )
    _fields(
        ownership,
        "interactive TELNET session-start.ownership",
        {"controller", "input_source", "response_source"},
    )
    if ownership != {
        "controller": "pdp11-its-interactive-controller",
        "input_source": "operator-stdin",
        "response_source": "pdp11-console",
    }:
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream has invalid ownership"
        )

    framing = _mapping(
        value["framing"], "interactive TELNET session-start.framing"
    )
    _fields(
        framing,
        "interactive TELNET session-start.framing",
        {"mode", "line_ending", "prompt_id", "prompt_pattern", "response_encoding"},
    )
    if framing != {
        "mode": "line-oriented",
        "line_ending": "carriage-return",
        "prompt_id": "its-ddt-star",
        "prompt_pattern": "CRLF ASTERISK",
        "response_encoding": "latin-1",
    }:
        raise InteractiveTelnetStreamError(
            "interactive TELNET stream has invalid framing"
        )

    limits = _mapping(value["limits"], "interactive TELNET session-start.limits")
    _fields(
        limits,
        "interactive TELNET session-start.limits",
        {"command_timeout_seconds", "max_command_bytes", "max_commands", "max_response_bytes"},
    )
    for key in (
        "command_timeout_seconds",
        "max_command_bytes",
        "max_commands",
        "max_response_bytes",
    ):
        _positive_integer(limits[key], f"interactive TELNET {key}")
    return _copy(value)


def _parse_command(
    record: Mapping[str, Any],
    expected_sequence: int,
    expected_number: int,
    max_command_bytes: int,
) -> dict[str, Any]:
    _fields(
        record,
        "interactive TELNET command",
        {"record_type", "sequence", "command_id", "observed_at", "input_source", "text", "encoded_bytes"},
    )
    if record["record_type"] != "command" or record["sequence"] != expected_sequence:
        raise InteractiveTelnetStreamError(
            "interactive TELNET command has invalid sequence"
        )
    expected_id = f"command:{expected_number}"
    if record["command_id"] != expected_id or record["input_source"] != "operator-stdin":
        raise InteractiveTelnetStreamError(
            "interactive TELNET command has invalid identity or attribution"
        )
    text = validate_operator_command(record["text"], max_command_bytes)
    if record["encoded_bytes"] != len(text.encode("ascii")):
        raise InteractiveTelnetStreamError(
            "interactive TELNET command byte count disagrees with its text"
        )
    _timestamp(record["observed_at"], "interactive TELNET command timestamp")
    return _copy(record)


def _parse_result(
    record: Mapping[str, Any],
    expected_sequence: int,
    command_id: str,
    max_response_bytes: int,
) -> dict[str, Any]:
    _fields(
        record,
        "interactive TELNET result",
        {
            "record_type",
            "sequence",
            "command_id",
            "observed_at",
            "response_source",
            "status",
            "prompt_id",
            "elapsed_ms",
            "captured_latin1",
            "captured_bytes",
            "captured_sha256",
            "truncated",
        },
    )
    if (
        record["record_type"] != "result"
        or record["sequence"] != expected_sequence
        or record["command_id"] != command_id
        or record["response_source"] != "pdp11-console"
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET result has invalid sequence, identity, or attribution"
        )
    status = record["status"]
    if status not in _RESULT_STATUSES:
        raise InteractiveTelnetStreamError(
            f"interactive TELNET result has unknown status {status!r}"
        )
    if (status == "complete") != (record["prompt_id"] == "its-ddt-star"):
        raise InteractiveTelnetStreamError(
            "interactive TELNET prompt identity disagrees with result status"
        )
    elapsed_ms = record["elapsed_ms"]
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int) or elapsed_ms < 0:
        raise InteractiveTelnetStreamError(
            "interactive TELNET elapsed_ms must be a non-negative integer"
        )
    if not isinstance(record["truncated"], bool):
        raise InteractiveTelnetStreamError(
            "interactive TELNET truncated flag must be boolean"
        )
    if record["truncated"] != (status == "response-limit"):
        raise InteractiveTelnetStreamError(
            "interactive TELNET truncation disagrees with result status"
        )
    captured_text = record["captured_latin1"]
    if not isinstance(captured_text, str):
        raise InteractiveTelnetStreamError(
            "interactive TELNET captured response must be text"
        )
    try:
        captured = captured_text.encode("latin-1")
    except UnicodeEncodeError as error:
        raise InteractiveTelnetStreamError(
            "interactive TELNET captured response is not Latin-1"
        ) from error
    if record["captured_bytes"] != len(captured):
        raise InteractiveTelnetStreamError(
            "interactive TELNET captured byte count disagrees with its text"
        )
    if len(captured) > max_response_bytes:
        raise InteractiveTelnetStreamError(
            "interactive TELNET captured response exceeds its declared limit"
        )
    digest = record["captured_sha256"]
    if (
        not isinstance(digest, str)
        or not _SHA256.fullmatch(digest)
        or digest != hashlib.sha256(captured).hexdigest()
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET captured response digest disagrees"
        )
    _timestamp(record["observed_at"], "interactive TELNET result timestamp")
    return _copy(record)


def _parse_end(
    record: Mapping[str, Any],
    expected_sequence: int,
    *,
    command_count: int,
    completed_commands: int,
    failed_commands: int,
) -> dict[str, Any]:
    _fields(
        record,
        "interactive TELNET session-end",
        {"record_type", "sequence", "observed_at", "reason", "command_count", "completed_commands", "failed_commands"},
    )
    if record["record_type"] != "session-end" or record["sequence"] != expected_sequence:
        raise InteractiveTelnetStreamError(
            "interactive TELNET session-end has invalid sequence"
        )
    if record["reason"] not in _END_REASONS:
        raise InteractiveTelnetStreamError(
            f"interactive TELNET session-end has unknown reason {record['reason']!r}"
        )
    if (
        record["command_count"] != command_count
        or record["completed_commands"] != completed_commands
        or record["failed_commands"] != failed_commands
        or completed_commands + failed_commands != command_count
    ):
        raise InteractiveTelnetStreamError(
            "interactive TELNET session-end counts disagree with its records"
        )
    if record["reason"] in {"operator-quit", "input-eof", "max-commands"} and failed_commands:
        raise InteractiveTelnetStreamError(
            "interactive TELNET clean end reason follows a failed command"
        )
    _timestamp(record["observed_at"], "interactive TELNET session-end timestamp")
    return _copy(record)


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InteractiveTelnetStreamError(f"{location} must be an object")
    return value


def _fields(value: Mapping[str, Any], location: str, expected: set[str]) -> None:
    if set(value) != expected:
        raise InteractiveTelnetStreamError(f"{location} has an unexpected field set")


def _identifier(value: object, location: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise InteractiveTelnetStreamError(f"{location} is not a valid identifier")
    return value


def _timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise InteractiveTelnetStreamError(
            f"{location} must be an RFC 3339 UTC timestamp"
        )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise InteractiveTelnetStreamError(
            f"{location} must be an RFC 3339 UTC timestamp"
        ) from error


def _positive_integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InteractiveTelnetStreamError(f"{location} must be a positive integer")
    return value


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), allow_nan=False))
