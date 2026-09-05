"""Read retained harness records without evaluating a gate or probing a process."""

from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any


_MANIFEST = "runtime/run.env"
_CLEANUP = "cleanup-evidence.txt"
_LOGS = (
    "runtime/launcher.stderr.log",
    "controller.stderr.log",
    "runtime/lease.stderr.log",
    "receiver.stderr.log",
    "application-relay.stderr.log",
    "direct-relay.stderr.log",
    "direct-reflector.stderr.log",
)
_KEY = re.compile(r"[A-Za-z0-9_.-]+\Z")
_LIMIT = 256 * 1024
_LOG_LIMIT = 8192


class RunDiagnosticError(ValueError):
    """The requested result directory cannot be inspected."""


class _Reader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.issues: list[dict[str, str]] = []
        self.inputs: list[dict[str, Any]] = []
        self.partial: set[str] = set()

    def issue(self, file: str, message: str, severity: str = "error") -> None:
        self.issues.append({"file": file, "message": message, "severity": severity})

    def read(self, file: str, limit: int = _LIMIT, *, tail: bool = False) -> bytes | None:
        """Read only fixed, regular files inside the selected result directory."""

        path = self.root
        try:
            for part in Path(file).parts:
                path = path / part
                if path.is_symlink():
                    raise ValueError("symbolic links are not diagnostic inputs")
            before = path.stat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("expected a regular file")
            if before.st_size > limit and not tail:
                raise ValueError(f"record exceeds the {limit}-byte diagnostic limit")
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            with os.fdopen(os.open(path, flags), "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode):
                    raise ValueError("expected a regular file")
                offset = max(0, opened.st_size - limit) if tail else 0
                stream.seek(offset)
                data = stream.read(limit + 1)
                after = os.fstat(stream.fileno())
            identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
            if identity(before) != identity(opened) or identity(opened) != identity(after):
                raise ValueError("file changed during inspection; retry the diagnostic")
            if len(data) > limit:
                raise ValueError("file grew beyond the diagnostic limit; retry")
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            self.issue(file, str(error))
            return None
        self.inputs.append({
            "file": file,
            "offset": offset,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
        if offset:
            # Do not display a fragment that began before the retained tail.
            data = data.partition(b"\n")[2]
        return data

    def fields(self, file: str) -> dict[str, tuple[str, int]]:
        data = self.read(file)
        if data is None:
            return {}
        if data and not data.endswith(b"\n"):
            self.partial.add(file)
            self.issue(file, "ignored an unfinished final record", "warning")
            data = data.rpartition(b"\n")[0]
        values: dict[str, tuple[str, int]] = {}
        try:
            for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
                key, separator, value = line.partition("=")
                if not separator or not _KEY.fullmatch(key) or key in values:
                    raise ValueError(f"line {number} has an invalid or duplicate field")
                values[key] = (value, number)
        except (UnicodeError, ValueError) as error:
            self.issue(file, str(error))
            return {}
        return values


def _reference(file: str, field: tuple[str, int]) -> str:
    return f"{file}:{field[1]}"


def _integer(value: str, maximum: int = 2147483647) -> int:
    if not re.fullmatch(r"[0-9]{1,10}", value) or int(value) > maximum:
        raise ValueError(f"invalid nonnegative integer: {value!r}")
    return int(value)


def _timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("expected a UTC timestamp ending in Z")
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


def _checkpoints(fields: dict[str, tuple[str, int]]) -> list[dict[str, str]]:
    """Describe recorded writes in manifest order, without inventing phases."""

    points: dict[str, dict[str, str]] = {}
    for key, field in fields.items():
        value = field[0]
        if key == "repository.revision":
            kind, label = "repository", "Repository identity recorded"
        elif re.fullmatch(r"progress\.(launcher|controller)\.[1-9][0-9]*", key):
            kind = ".".join(key.split(".")[:2])
            label = "Recorded stage / awaited condition (not a current activity check)"
        elif key == "failure.controller":
            kind, label = "controller-failure", "Controller failure recorded"
        elif key.startswith("source.") and key.endswith(".revision"):
            kind, label = "sources", "External source identity recorded"
        elif key == "udp.count":
            kind, label = "ports", "Port allocation recorded"
        elif key == "runtime.control-socket-namespace":
            kind, label = "resources", "Private control namespace recorded"
        elif re.fullmatch(r"process\.[A-Za-z0-9_-]+\.pid", key):
            kind, label = key, "Process launch recorded (not a current liveness check)"
        elif key.startswith("application.offset."):
            kind, label = "capture", "Application capture offset recorded"
        elif key == "message-journey.state":
            kind, label = "journey", "Message-journey diagnosis recorded"
        elif key in ("application.remote_time", "application.session-survived-cut"):
            kind, label = "application", "Application result recorded"
        elif key in ("application.client", "application.server", "application.sentinel_sha256"):
            kind, label = "application", "Application metadata recorded"
        elif key in ("sha256.terminal-session", "sha256.interactive-telnet"):
            kind, label = "terminal", "Terminal transcript digest recorded"
        elif re.fullmatch(r"process\.[A-Za-z0-9_-]+\.exit-status", key):
            kind, label = key, "Process exit recorded"
        elif key == "result.verdict-exit-status":
            kind, label = "evaluator", "Scenario evaluator exit recorded"
        else:
            continue
        points.pop(kind, None)
        points[kind] = {
            "label": label,
            "key": key,
            "value": value,
            "evidence": _reference(_MANIFEST, field),
        }
    return list(points.values())


def diagnose_run(results_dir: str | Path) -> dict[str, Any]:
    """Return a bounded evidence inventory; never an application/network verdict."""

    try:
        root = Path(results_dir).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("expected a result directory")
    except (OSError, ValueError, RuntimeError) as error:
        raise RunDiagnosticError(str(error)) from error
    reader = _Reader(root)
    fields = reader.fields(_MANIFEST)
    values = {key: field[0] for key, field in fields.items()}
    if not fields:
        reader.issue(_MANIFEST, "no readable run manifest; select a smoke or terminal result")
    elif values.get("format") != "1":
        reader.issue(_MANIFEST, "missing or unsupported run manifest format")

    progress_sequences: dict[str, int] = {}
    for key, value in values.items():
        if key.startswith("progress."):
            match = re.fullmatch(r"progress\.(launcher|controller)\.([1-9][0-9]{0,5})", key)
            if match is None or not re.fullmatch(r"[ -~]{1,1024}", value):
                reader.issue(_MANIFEST, f"invalid progress record: {key}")
            else:
                owner, sequence = match[1], int(match[2])
                if sequence <= progress_sequences.get(owner, 0):
                    reader.issue(_MANIFEST, f"progress sequence moved backwards: {key}")
                progress_sequences[owner] = sequence
    controller_failure = values.get("failure.controller")
    if controller_failure is not None and not re.fullmatch(r"[ -~]{1,1024}", controller_failure):
        reader.issue(_MANIFEST, "failure.controller must be bounded printable ASCII")

    for key in ("started_utc", "finished_utc"):
        if key in values:
            try:
                _timestamp(values[key])
            except ValueError as error:
                reader.issue(_MANIFEST, f"{key}: {error}")
    if "started_utc" in values and "finished_utc" in values:
        try:
            if _timestamp(values["finished_utc"]) < _timestamp(values["started_utc"]):
                reader.issue(_MANIFEST, "finish timestamp precedes start timestamp")
        except ValueError:
            pass

    runtime_outcome = values.get("outcome")
    exit_status = None
    if "exit_status" in values:
        try:
            exit_status = _integer(values["exit_status"], 255)
        except ValueError as error:
            reader.issue(_MANIFEST, f"exit_status: {error}")
    if runtime_outcome is not None and runtime_outcome not in ("passed", "failed"):
        reader.issue(_MANIFEST, "unsupported recorded runtime outcome")
    if runtime_outcome == "passed" and exit_status not in (None, 0):
        reader.issue(_MANIFEST, "runtime records passed with a nonzero exit status")

    termination = {
        "kind": values.get("termination.kind", "not-recorded"),
        "signal": values.get("termination.signal"),
        "exit_status": None,
        "reason": values.get("failure.reason"),
        "evidence": [
            _reference(_MANIFEST, field)
            for key, field in fields.items()
            if key.startswith("termination.") or key == "failure.reason"
        ],
    }
    if termination["evidence"]:
        try:
            kind = termination["kind"]
            if kind not in ("exit", "signal"):
                raise ValueError("missing or unsupported termination.kind")
            original_status = _integer(values.get("termination.exit-status", ""), 255)
            termination["exit_status"] = original_status
            if kind == "signal":
                expected = {"HUP": 129, "INT": 130, "TERM": 143}.get(termination["signal"])
                if expected is None or original_status != expected:
                    raise ValueError("handled signal and launcher exit status disagree")
            elif termination["signal"] is not None:
                raise ValueError("exit termination cannot record a handled signal")
            if original_status and exit_status not in (None, original_status):
                raise ValueError("terminal exit status did not preserve the launcher failure")
            reason = termination["reason"]
            if reason is not None and not re.fullmatch(r"[ -~]{1,1024}", reason):
                raise ValueError("failure.reason must be bounded printable ASCII")
            if runtime_outcome == "passed" and (reason or original_status):
                raise ValueError("runtime records passed with a launcher failure")
            if runtime_outcome == "failed" and reason is None:
                raise ValueError("new termination records lack failure.reason")
        except ValueError as error:
            reader.issue(_MANIFEST, str(error))

    controller_outcome = None
    outcome_data = reader.read("outcome.txt", 1024)
    if outcome_data is not None:
        if outcome_data not in (b"passed\n", b"failed\n"):
            reader.issue("outcome.txt", "expected one complete passed or failed record")
        else:
            controller_outcome = outcome_data.decode("ascii").strip()
    # A controller can pass before a later outer-runtime failure. That is not
    # a contradiction, and must not be promoted into overall success.
    if runtime_outcome == "passed" and controller_outcome == "failed":
        reader.issue("outcome.txt", "controller failed but outer runtime records passed")

    cleanup_fields = reader.fields(_CLEANUP)
    controller_cleanup = "not-recorded"
    controller_cleanup_error = None
    survivors = None
    cleanup_evidence: list[str] = []
    if "surviving_owned_processes" in cleanup_fields and _CLEANUP not in reader.partial:
        field = cleanup_fields["surviving_owned_processes"]
        try:
            survivors = _integer(field[0])
            controller_cleanup = "recorded-clean" if survivors == 0 else "recorded-survivors"
            cleanup_evidence.append(_reference(_CLEANUP, field))
            process_survivors = 0
            for key, pid_field in cleanup_fields.items():
                if not key.endswith(".pid"):
                    continue
                pid = _integer(pid_field[0])
                status_field = cleanup_fields.get(key.removesuffix(".pid") + ".exit_status")
                if status_field is None:
                    raise ValueError(f"missing exit status for {key}")
                if status_field[0] != "None" and not re.fullmatch(r"-?[0-9]{1,10}", status_field[0]):
                    raise ValueError(f"invalid exit status for {key}")
                if pid and status_field[0] == "None":
                    process_survivors += 1
            if any(key.endswith(".pid") for key in cleanup_fields) and process_survivors != survivors:
                raise ValueError("survivor count disagrees with recorded process statuses")
            if "cleanup_error" in cleanup_fields:
                error_field = cleanup_fields["cleanup_error"]
                controller_cleanup_error = error_field[0]
                cleanup_evidence.append(_reference(_CLEANUP, error_field))
                if not re.fullmatch(r"[ -~]{1,1024}", controller_cleanup_error):
                    raise ValueError("cleanup_error must be bounded printable ASCII")
                if cleanup_fields.get("cleanup_status", (None, 0))[0] != "failed":
                    raise ValueError("controller cleanup error lacks a failed status")
            if "cleanup_status" in cleanup_fields:
                status = cleanup_fields["cleanup_status"]
                cleanup_evidence.append(_reference(_CLEANUP, status))
                if status[0] not in ("passed", "failed"):
                    raise ValueError("unsupported controller cleanup_status")
                if status[0] == "passed" and (survivors or "cleanup_error" in cleanup_fields):
                    raise ValueError("controller cleanup status disagrees with failure evidence")
                if status[0] == "failed":
                    controller_cleanup = "recorded-errors"
        except ValueError as error:
            reader.issue(_CLEANUP, str(error))
            controller_cleanup = "inconsistent"
    outer_cleanup = values.get("cleanup.outer-runtime", "not-recorded")
    if outer_cleanup not in ("passed", "failed", "not-recorded"):
        reader.issue(_MANIFEST, "unsupported outer-runtime cleanup record")
        outer_cleanup = "inconsistent"
    if "cleanup.outer-runtime" in fields:
        cleanup_evidence.append(_reference(_MANIFEST, fields["cleanup.outer-runtime"]))
    if "cleanup.completed" in fields:
        field = fields["cleanup.completed"]
        cleanup_evidence.append(_reference(_MANIFEST, field))
        if field[0] not in ("0", "1"):
            reader.issue(_MANIFEST, "unsupported cleanup.completed record")
            outer_cleanup = "inconsistent"
        else:
            completed = "passed" if field[0] == "1" else "not-completed"
            if outer_cleanup != "not-recorded" and outer_cleanup != completed:
                reader.issue(_MANIFEST, "outer-runtime cleanup records disagree")
                outer_cleanup = "inconsistent"
            else:
                outer_cleanup = completed
    cleanup_status = None
    cleanup_attempts = None
    failed_resources: list[str] = []
    runtime_cleanup_keys = (
        "cleanup.runtime.exit-status", "cleanup.runtime.attempts", "cleanup.runtime.failed-resources",
    )
    if any(key in values for key in runtime_cleanup_keys):
        cleanup_evidence.extend(_reference(_MANIFEST, fields[key]) for key in runtime_cleanup_keys if key in fields)
        try:
            cleanup_status = _integer(values.get("cleanup.runtime.exit-status", ""), 1)
            cleanup_attempts = _integer(values.get("cleanup.runtime.attempts", ""))
            if not cleanup_attempts:
                raise ValueError("cleanup result has no recorded attempt")
            resources = values.get("cleanup.runtime.failed-resources", "")
            if resources != "none":
                if not re.fullmatch(r"[A-Za-z0-9_:-]+(?: [A-Za-z0-9_:-]+)*", resources):
                    raise ValueError("invalid cleanup failed-resources record")
                failed_resources = resources.split(" ")
            if bool(cleanup_status) != bool(failed_resources):
                raise ValueError("cleanup status and failed resources disagree")
            result = "failed" if cleanup_status else "passed"
            if outer_cleanup not in ("not-recorded", result) and not (result == "failed" and outer_cleanup == "not-completed"):
                raise ValueError("outer-runtime cleanup records disagree")
            outer_cleanup = result
        except ValueError as error:
            reader.issue(_MANIFEST, str(error))
            outer_cleanup = "inconsistent"
    if termination["exit_status"] == 0 and exit_status not in (None, 0):
        if exit_status != 1 or cleanup_status != 1:
            reader.issue(_MANIFEST, "changed launcher exit status lacks a cleanup failure")
    if runtime_outcome == "passed" and (survivors or controller_cleanup == "recorded-errors" or outer_cleanup in ("failed", "not-completed")):
        reader.issue(_MANIFEST, "runtime records passed with failed cleanup evidence")
    if runtime_outcome == "passed" and controller_failure:
        reader.issue(_MANIFEST, "runtime records passed with a controller failure")

    logs = []
    for file in _LOGS:
        data = reader.read(file, _LOG_LIMIT, tail=True)
        if data and data.strip():
            logs.append({
                "file": file,
                "excerpt": "\n".join(data.decode("utf-8", "replace").splitlines()[-8:]),
                "interpretation": "uninterpreted diagnostic output, not a verdict",
            })

    complete = all(values.get(key) for key in ("finished_utc", "outcome", "exit_status"))
    if complete:
        for key in ("topology", "started_utc", "repository.revision"):
            if not values.get(key):
                reader.issue(_MANIFEST, f"completed run lacks {key}")
    if not fields:
        state = "unavailable"
    elif any(issue["severity"] == "error" for issue in reader.issues):
        state = "inconsistent"
    elif not complete or _MANIFEST in reader.partial:
        state = "unfinished"
    else:
        state = "recorded-" + str(runtime_outcome)

    next_steps = []
    if state == "unavailable":
        next_steps.append("Select a smoke or terminal result containing runtime/run.env; build directories use make doctor.")
    elif state == "inconsistent":
        next_steps.append("Inspect the listed record problems. If the run is still writing, retry after it stops. Preserve the original result.")
    elif state == "unfinished":
        next_steps.append("Check the terminal that launched this run. Missing final records do not establish whether it is still running or was interrupted.")
    elif state == "recorded-failed":
        if termination["signal"]:
            next_steps.append("The launcher recorded a handled signal. Review the cleanup results before starting a new run.")
        elif termination["reason"]:
            next_steps.append("Review the retained failure reason and diagnostic output below; preserve this result when retrying.")
        elif controller_outcome == "passed":
            next_steps.append("The controller passed before the outer runtime failed; inspect the launch terminal and later validation or cleanup diagnostics.")
        elif logs:
            next_steps.append("Inspect the diagnostic output below and the named files for the recorded failure details.")
        else:
            next_steps.append("The failure reason was not retained in a supported diagnostic log. Inspect the launch terminal; this report cannot infer the cause.")
    else:
        next_steps.append("Use the scenario's documented evaluator or replay for acceptance revalidation; this command reports the recorded outcome only.")
    if controller_cleanup in ("recorded-survivors", "recorded-errors"):
        next_steps.append("The controller recorded cleanup failures or surviving processes. Return to the owning launch session for cleanup; recorded PIDs must not be used as current ownership evidence.")
    elif outer_cleanup == "not-recorded":
        next_steps.append("Outer-runtime cleanup was not recorded. Release of ports, relays, and other outer-run resources is unknown.")
    elif outer_cleanup in ("failed", "not-completed"):
        next_steps.append("Outer-runtime cleanup was recorded as unsuccessful or incomplete. Return to the owning launch session to inspect resource cleanup.")

    checkpoints = _checkpoints(fields)
    missing = [
        f"Runtime {key} ({_MANIFEST})"
        for key in ("finished_utc", "outcome", "exit_status")
        if not values.get(key)
    ]
    if controller_outcome is None:
        missing.append("Controller outcome (outcome.txt)")
    if controller_cleanup == "not-recorded":
        missing.append("Controller cleanup (cleanup-evidence.txt)")
    if outer_cleanup == "not-recorded":
        missing.append("Outer-runtime cleanup (runtime/run.env)")
    return {
        "schema_version": 1,
        "kind": "run-diagnostic",
        "authority": "retained harness records; no gate revalidation or process-liveness check",
        "result_directory": str(root),
        "run": {
            "id": root.name,
            "topology": values.get("topology"),
            "repository_revision": values.get("repository.revision"),
            "started_at": values.get("started_utc"),
            "finished_at": values.get("finished_utc"),
        },
        "status": state,
        "recorded_outcomes": {
            "runtime": runtime_outcome,
            "controller": controller_outcome,
            "exit_status": exit_status,
        },
        "termination": termination,
        "last_recorded_checkpoint": checkpoints[-1] if checkpoints else None,
        "checkpoints": checkpoints,
        "controller_failure": controller_failure,
        "cleanup": {
            "controller": controller_cleanup,
            "controller_error": controller_cleanup_error,
            "surviving_owned_processes": survivors,
            "outer_runtime": outer_cleanup,
            "runtime_exit_status": cleanup_status,
            "runtime_attempts": cleanup_attempts,
            "runtime_failed_resources": failed_resources,
            "evidence": cleanup_evidence,
        },
        "diagnostic_output": logs,
        "issues": reader.issues,
        "unrecorded_details": missing,
        "next_steps": next_steps,
        "inputs": reader.inputs,
    }


def _safe(value: Any) -> str:
    """Keep path names and retained log controls from acting on the terminal."""

    text = "not recorded" if value is None else str(value)
    return "".join(character if character.isprintable() else ascii(character)[1:-1] for character in text)


def render_diagnostic(report: dict[str, Any]) -> str:
    outcomes, cleanup = report["recorded_outcomes"], report["cleanup"]
    labels = {
        "recorded-passed": "Recorded success",
        "recorded-failed": "Recorded failure",
        "unfinished": "Unfinished; current activity unknown",
        "unavailable": "Run records unavailable",
        "inconsistent": "Run records cannot be reconciled",
        "recorded-clean": "Recorded clean",
        "recorded-survivors": "Surviving processes recorded",
        "recorded-errors": "Cleanup failure recorded",
        "not-recorded": "Not recorded",
        "not-completed": "Recorded incomplete",
    }
    lines = [
        f"Run: {_safe(report['run']['id'])}",
        f"Result: {_safe(report['result_directory'])}",
        f"Scenario: {_safe(report['run']['topology'])}",
        f"Status: {labels[report['status']]}",
        f"Runtime outcome: {_safe(outcomes['runtime'])}; exit status: {_safe(outcomes['exit_status'])}",
        f"Controller outcome: {_safe(outcomes['controller'])}",
        "Recorded outcomes are not a fresh acceptance check or a current process check.",
        "",
    ]
    checkpoint = report["last_recorded_checkpoint"]
    termination = report["termination"]
    if termination["kind"] != "not-recorded":
        lines.append(f"Launcher termination: {_safe(termination['kind'])}; original exit status: {_safe(termination['exit_status'])}")
    if termination["signal"]:
        lines.append(f"Handled signal: {_safe(termination['signal'])}")
    if termination["reason"]:
        lines.append(f"Recorded failure reason: {_safe(termination['reason'])}")
    if report.get("controller_failure"):
        lines.append(f"Recorded controller failure: {_safe(report['controller_failure'])}")
    if checkpoint:
        lines.extend([
            f"Last recorded checkpoint: {_safe(checkpoint['label'])}",
            f"  {_safe(checkpoint['key'])}={_safe(checkpoint['value'])} ({checkpoint['evidence']})",
        ])
    else:
        lines.append("Last recorded checkpoint: not recorded")
    lines.extend([
        f"Controller cleanup: {labels[cleanup['controller']]}; recorded survivors: {_safe(cleanup['surviving_owned_processes'])}",
        f"Outer-runtime cleanup: {_safe(labels.get(cleanup['outer_runtime'], cleanup['outer_runtime']))}",
    ])
    if cleanup["runtime_failed_resources"]:
        lines.append("Cleanup failures: " + ", ".join(_safe(value) for value in cleanup["runtime_failed_resources"]))
    if cleanup.get("controller_error"):
        lines.append(f"Controller cleanup error: {_safe(cleanup['controller_error'])}")
    if report["unrecorded_details"]:
        lines.append("Unrecorded details (not necessarily required by this scenario):")
        lines.extend("  " + detail for detail in report["unrecorded_details"])
    for issue in report["issues"]:
        lines.append(f"{issue['severity'].capitalize()}: {_safe(issue['file'])}: {_safe(issue['message'])}")
    for log in report["diagnostic_output"]:
        lines.extend(["", f"Diagnostic excerpt: {log['file']} (uninterpreted)"])
        lines.extend("  " + _safe(line) for line in log["excerpt"].splitlines())
    lines.extend(["", "Next steps:"])
    lines.extend("- " + step for step in report["next_steps"])
    return "\n".join(lines) + "\n"
