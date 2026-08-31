"""Adapt completed formal two-ITS results into read-only NCC summaries."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

from .run_summary import RunSummary, RunSummaryValidationError, run_summary_from_mapping
from .topology import two_its_topology


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_REQUIRED = frozenset(
    {
        "format",
        "topology",
        "started_utc",
        "finished_utc",
        "outcome",
        "exit_status",
        "repository.revision",
        "repository.tracked_dirty",
    }
)
_SENTINEL_REQUIRED = frozenset(
    {
        "source",
        "destination",
        "service_user",
        "remote_user",
        "sentinel",
        "source_sha256",
        "recovered_sha256",
    }
)


class TwoItsSummaryError(ValueError):
    """Raised when formal two-ITS artifacts cannot support a safe summary."""


def summarize_two_its_result(results_dir: str | Path) -> RunSummary:
    """Summarize one completed formal two-ITS result directory.

    Only the line-oriented manifest, controller outcome, and derived sentinel
    evidence are read.  Console and IMP logs remain external evidence and are
    never parsed or embedded in the resulting summary.
    """

    result_path = Path(results_dir)
    run_id = _run_id(result_path)
    manifest_path = result_path / "runtime" / "run.env"
    outcome_path = result_path / "outcome.txt"
    manifest = _load_record(manifest_path, "run manifest")
    _validate_manifest(manifest)
    outcome = _load_outcome(outcome_path)
    if outcome != manifest["outcome"]:
        raise TwoItsSummaryError(
            "controller outcome does not match the terminal manifest outcome"
        )

    document: dict[str, Any] = {
        "schema_version": 1,
        "run": {
            "id": run_id,
            "started_at": manifest["started_utc"],
            "finished_at": manifest["finished_utc"],
            "outcome": "incomplete",
            "provenance": _provenance(run_id, manifest),
        },
        "topology": two_its_topology(),
        "external_evidence": [
            {
                "id": "evidence:manifest",
                "kind": "two-its-run-manifest",
                "locator": "runtime/run.env",
            },
            {
                "id": "evidence:outcome",
                "kind": "two-its-controller-outcome",
                "locator": "outcome.txt",
            },
        ],
        "observations": [
            {
                "id": "observation:manifest-outcome",
                "sequence": 1,
                "observed_at": manifest["finished_utc"],
                "category": "harness",
                "subject_id": "route:host176-to-host106",
                "state": outcome,
                "source": {"id": "source:run-manifest", "kind": "run-manifest"},
                "details": {"exit_status": manifest["exit_status"]},
                "external_evidence_ids": ["evidence:manifest", "evidence:outcome"],
            }
        ],
        "derived_states": [],
        "gates": [],
    }

    if outcome == "passed":
        _add_passing_application_evidence(document, result_path, manifest)
    else:
        _add_incomplete_application_evidence(document, manifest)

    try:
        return run_summary_from_mapping(document)
    except RunSummaryValidationError as error:
        raise TwoItsSummaryError(f"invalid derived two-ITS summary: {error}") from error


def _add_passing_application_evidence(
    document: dict[str, Any], result_path: Path, manifest: dict[str, str]
) -> None:
    for key in ("application.client", "application.server", "application.sentinel_sha256"):
        if key not in manifest:
            raise TwoItsSummaryError(f"passed run manifest is missing {key!r}")
    sentinel = _load_record(result_path / "sentinel-evidence.txt", "sentinel evidence")
    missing = _SENTINEL_REQUIRED - sentinel.keys()
    if missing:
        raise TwoItsSummaryError(
            "sentinel evidence is missing fields: " + ", ".join(sorted(missing))
        )
    if sentinel["source"] != "host106-console" or sentinel["destination"] != "host176-ncp-telnet":
        raise TwoItsSummaryError("sentinel evidence has an unexpected application path")
    source_digest = _digest(sentinel["source_sha256"], "sentinel source digest")
    recovered_digest = _digest(sentinel["recovered_sha256"], "sentinel recovered digest")
    manifest_digest = _digest(
        manifest["application.sentinel_sha256"], "manifest sentinel digest"
    )
    sentinel_digest = hashlib.sha256(sentinel["sentinel"].encode("ascii")).hexdigest()
    if source_digest != recovered_digest or source_digest != manifest_digest:
        raise TwoItsSummaryError("sentinel evidence digests do not agree")
    if sentinel_digest != source_digest:
        raise TwoItsSummaryError("sentinel content does not match its recorded digest")

    document["run"]["outcome"] = "passed"
    document["external_evidence"].append(
        {
            "id": "evidence:sentinel",
            "kind": "two-its-sentinel-evidence",
            "locator": "sentinel-evidence.txt",
        }
    )
    document["observations"].append(
        {
            "id": "observation:application-sentinel",
            "sequence": 2,
            "observed_at": document["run"]["finished_at"],
            "category": "application",
            "subject_id": "route:host176-to-host106",
            "state": "passed",
            "source": {"id": "source:sentinel-evidence", "kind": "application-evidence"},
            "details": {
                "client": manifest["application.client"],
                "server": manifest["application.server"],
                "sentinel_sha256": source_digest,
            },
            "external_evidence_ids": ["evidence:sentinel"],
        }
    )
    document["derived_states"].append(
        {
            "id": "derived:two-its-route",
            "subject_id": "route:host176-to-host106",
            "state": "up",
            "basis": "inference",
            "supporting_observation_ids": [
                "observation:manifest-outcome",
                "observation:application-sentinel",
            ],
        }
    )
    document["gates"].extend(
        [
            {
                "id": "gate:two-its-application",
                "assertion": "The two guest applications completed the formal NCP TELNET proof.",
                "verdict": "passed",
                "evidence_observation_ids": ["observation:application-sentinel"],
            },
            {
                "id": "gate:payload-anti-bypass",
                "assertion": "A guest-originated sentinel crossed the formal two-ITS route.",
                "verdict": "passed",
                "evidence_observation_ids": ["observation:application-sentinel"],
            },
        ]
    )


def _add_incomplete_application_evidence(
    document: dict[str, Any], manifest: dict[str, str]
) -> None:
    document["observations"].append(
        {
            "id": "observation:application-evidence-missing",
            "sequence": 2,
            "observed_at": manifest["finished_utc"],
            "category": "missing-evidence",
            "subject_id": "route:host176-to-host106",
            "state": "absent",
            "source": {"id": "source:controller-outcome", "kind": "controller-outcome"},
            "details": {"manifest_outcome": manifest["outcome"]},
            "external_evidence_ids": ["evidence:manifest", "evidence:outcome"],
        }
    )
    document["derived_states"].append(
        {
            "id": "derived:two-its-route",
            "subject_id": "route:host176-to-host106",
            "state": "incomplete",
            "basis": "inference",
            "supporting_observation_ids": [
                "observation:manifest-outcome",
                "observation:application-evidence-missing",
            ],
        }
    )
    for gate_id, assertion in (
        (
            "gate:two-its-application",
            "The two guest applications completed the formal NCP TELNET proof.",
        ),
        (
            "gate:payload-anti-bypass",
            "A guest-originated sentinel crossed the formal two-ITS route.",
        ),
    ):
        document["gates"].append(
            {
                "id": gate_id,
                "assertion": assertion,
                "verdict": "inconclusive",
                "evidence_observation_ids": ["observation:application-evidence-missing"],
            }
        )


def _provenance(run_id: str, manifest: dict[str, str]) -> list[dict[str, str]]:
    sources = [
        {
            "id": "source:arpanet-redux",
            "kind": "repository",
            "revision": manifest["repository.revision"],
        },
        {"id": run_id, "kind": "two-its-run-manifest"},
    ]
    for key, revision in sorted(manifest.items()):
        source = key.removeprefix("source.").removesuffix(".revision")
        if key.startswith("source.") and key.endswith(".revision"):
            sources.append(
                {"id": f"source:{source}", "kind": "external-source", "revision": revision}
            )
    return sources


def _validate_manifest(manifest: dict[str, str]) -> None:
    missing = _MANIFEST_REQUIRED - manifest.keys()
    if missing:
        raise TwoItsSummaryError(
            "run manifest is missing fields: " + ", ".join(sorted(missing))
        )
    if manifest["format"] != "1":
        raise TwoItsSummaryError("unsupported run manifest format")
    if manifest["topology"] != "two-its-telnet":
        raise TwoItsSummaryError("run manifest is not a formal two-ITS result")
    if manifest["outcome"] not in {"passed", "failed"}:
        raise TwoItsSummaryError("run manifest has an invalid terminal outcome")
    if not manifest["exit_status"].isdigit():
        raise TwoItsSummaryError("run manifest has an invalid terminal exit status")
    exit_status = int(manifest["exit_status"])
    if (manifest["outcome"] == "passed") != (exit_status == 0):
        raise TwoItsSummaryError("run manifest outcome and exit status disagree")
    _revision(manifest["repository.revision"], "repository revision")
    for key, value in manifest.items():
        if key.startswith("source.") and key.endswith(".revision"):
            _revision(value, key)


def _load_outcome(path: Path) -> str:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise TwoItsSummaryError(f"could not read controller outcome {path}: {error}") from error
    if len(lines) != 1 or lines[0] not in {"passed", "failed"}:
        raise TwoItsSummaryError("controller outcome must be exactly passed or failed")
    return lines[0]


def _load_record(path: Path, description: str) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise TwoItsSummaryError(f"could not read {description} {path}: {error}") from error
    record: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        key, separator, value = line.partition("=")
        if not separator or not key or not value:
            raise TwoItsSummaryError(
                f"{description} {path} has an invalid line {line_number}"
            )
        if key in record:
            raise TwoItsSummaryError(
                f"{description} {path} repeats key {key!r}"
            )
        record[key] = value
    if not record:
        raise TwoItsSummaryError(f"{description} {path} is empty")
    return record


def _run_id(result_path: Path) -> str:
    name = result_path.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise TwoItsSummaryError("result directory name is not a stable identifier")
    return f"run:{name}"


def _digest(value: str, description: str) -> str:
    if not _SHA256.fullmatch(value):
        raise TwoItsSummaryError(f"{description} is not a lowercase SHA-256 digest")
    return value


def _revision(value: str, description: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise TwoItsSummaryError(f"{description} is not a Git revision")
