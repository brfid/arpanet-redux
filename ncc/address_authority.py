"""One dated ARPANET address authority and the lookups it supports.

A topology may name a site identity for a configured host.  That claim is only
as good as the source behind it, so this module loads a transcribed extract of
one dated primary document and refuses any identity that does not match a row
in it.  Addresses are always derived from ``imp_number`` and ``host_number``
using the source's own rule and are never transcribed, so an arithmetic error
in the scan cannot propagate into a configuration.

Site numbering was reused as the network changed, so an authority is only
meaningful with its date attached.  Two authorities may disagree about the same
IMP number without either being wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any


ADDRESS_AUTHORITY_SCHEMA_VERSION = 1
AUTHORITY_DIRECTORY = Path(__file__).resolve().parents[1] / "config" / "authorities"

_AUTHORITY_ID = re.compile(r"authority:[a-z0-9][a-z0-9-]*\Z")
_DATED = re.compile(r"[0-9]{4}-[0-9]{2}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ADDRESS_RULE = "decimal = imp_number + 64 * host_number"

_MAX_IMP_NUMBER = 63
_MAX_HOST_NUMBER = 3


class AddressAuthorityError(ValueError):
    """Raised when an authority document, or a claim against one, is invalid."""


@dataclass(frozen=True)
class HostIdentity:
    """One transcribed host row from a dated primary source."""

    imp_number: int
    host_number: int
    hostname: str
    computer: str | None
    operating_system: str | None
    status: str

    @property
    def address_decimal(self) -> int:
        """Return the source's own decimal host address for this row."""

        return host_address(self.imp_number, self.host_number)

    @property
    def address_octal(self) -> str:
        """Return the octal host address as the source prints it."""

        return format(self.address_decimal, "o")


@dataclass(frozen=True)
class AddressAuthority:
    """A dated address table plus the negative claim its coverage supports."""

    id: str
    title: str
    identifier: str
    dated: str
    url: str
    sha256: str
    highest_imp_number: int
    hosts: tuple[HostIdentity, ...]

    def identity(self, imp_number: int, host_number: int) -> HostIdentity | None:
        """Return the transcribed row for one host position, if it was read."""

        for host in self.hosts:
            if host.imp_number == imp_number and host.host_number == host_number:
                return host
        return None

    def within_network(self, imp_number: int) -> bool:
        """Report whether an IMP number existed when this source was published.

        This is the one negative claim a partial transcription can carry: the
        source's highest IMP number bounds the network, even where individual
        rows were not read.
        """

        return 1 <= imp_number <= self.highest_imp_number


def host_address(imp_number: int, host_number: int) -> int:
    """Return the pre-1976 decimal host address for one host position."""

    if isinstance(imp_number, bool) or not isinstance(imp_number, int):
        raise AddressAuthorityError("imp_number must be an integer")
    if isinstance(host_number, bool) or not isinstance(host_number, int):
        raise AddressAuthorityError("host_number must be an integer")
    if not 1 <= imp_number <= _MAX_IMP_NUMBER:
        raise AddressAuthorityError(
            f"imp_number must be in 1..{_MAX_IMP_NUMBER}; the 1822 leader carries six bits"
        )
    if not 0 <= host_number <= _MAX_HOST_NUMBER:
        raise AddressAuthorityError(
            f"host_number must be in 0..{_MAX_HOST_NUMBER}; the 1822 leader carries two bits"
        )
    return imp_number + 64 * host_number


def host_address_octal(imp_number: int, host_number: int) -> str:
    """Return the octal host address written the way the sources write it."""

    return format(host_address(imp_number, host_number), "o")


def load_address_authority(path: str | Path) -> AddressAuthority:
    """Load one dated authority document from an explicit path."""

    authority_path = Path(path)
    try:
        document = json.loads(authority_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AddressAuthorityError(
            f"could not load address authority {authority_path}: {error}"
        ) from error
    return address_authority_from_mapping(document)


@lru_cache(maxsize=None)
def address_authority(identifier: str) -> AddressAuthority:
    """Load the authority named by a topology's ``address_authority`` field."""

    if not isinstance(identifier, str) or not identifier:
        raise AddressAuthorityError("address authority name must be a non-empty string")
    if "/" in identifier or "\\" in identifier or identifier.startswith("."):
        raise AddressAuthorityError(f"address authority name {identifier!r} must be a bare name")
    path = AUTHORITY_DIRECTORY / f"{identifier}.json"
    if not path.is_file():
        raise AddressAuthorityError(f"no address authority named {identifier!r} in {AUTHORITY_DIRECTORY}")
    authority = load_address_authority(path)
    if authority.id != f"authority:{identifier}":
        raise AddressAuthorityError(
            f"address authority {identifier!r} declares id {authority.id!r}"
        )
    return authority


def address_authority_from_mapping(document: object) -> AddressAuthority:
    """Validate a mapping and return an immutable dated address authority."""

    root = _mapping(document, "address authority")
    _fields(
        root,
        "address authority",
        required={
            "schema_version",
            "id",
            "source",
            "address_rule",
            "highest_imp_number",
            "coverage",
            "coverage_note",
            "hosts",
        },
        optional={"source_notes"},
    )
    if (
        isinstance(root["schema_version"], bool)
        or root["schema_version"] != ADDRESS_AUTHORITY_SCHEMA_VERSION
    ):
        raise AddressAuthorityError(
            f"address authority.schema_version must be {ADDRESS_AUTHORITY_SCHEMA_VERSION}"
        )
    identifier = root["id"]
    if not isinstance(identifier, str) or not _AUTHORITY_ID.fullmatch(identifier):
        raise AddressAuthorityError("address authority.id must be 'authority:<name>'")
    if root["address_rule"] != _ADDRESS_RULE:
        raise AddressAuthorityError(
            f"address authority.address_rule must be {_ADDRESS_RULE!r}; this repository "
            "composes only pre-1976 short-leader addressing"
        )
    if root["coverage"] not in {"partial", "complete"}:
        raise AddressAuthorityError("address authority.coverage must be 'partial' or 'complete'")
    if not isinstance(root["coverage_note"], str) or not root["coverage_note"].strip():
        raise AddressAuthorityError("address authority.coverage_note must describe what was transcribed")
    highest = root["highest_imp_number"]
    if isinstance(highest, bool) or not isinstance(highest, int) or not 1 <= highest <= _MAX_IMP_NUMBER:
        raise AddressAuthorityError(
            f"address authority.highest_imp_number must be an integer in 1..{_MAX_IMP_NUMBER}"
        )
    source = _mapping(root["source"], "address authority.source")
    _fields(
        source,
        "address authority.source",
        required={"title", "identifier", "dated", "holding", "url", "sha256", "tables"},
    )
    for name in ("title", "identifier", "holding", "url"):
        if not isinstance(source[name], str) or not source[name].strip():
            raise AddressAuthorityError(f"address authority.source.{name} must be a non-empty string")
    if not isinstance(source["dated"], str) or not _DATED.fullmatch(source["dated"]):
        raise AddressAuthorityError("address authority.source.dated must be YYYY-MM")
    if not isinstance(source["sha256"], str) or not _SHA256.fullmatch(source["sha256"]):
        raise AddressAuthorityError("address authority.source.sha256 must be a lowercase sha256 digest")
    if not isinstance(source["tables"], list) or not source["tables"]:
        raise AddressAuthorityError("address authority.source.tables must name the tables transcribed")

    hosts: list[HostIdentity] = []
    seen_positions: set[tuple[int, int]] = set()
    seen_hostnames: set[str] = set()
    for index, value in enumerate(_list(root["hosts"], "address authority.hosts")):
        location = f"address authority.hosts[{index}]"
        row = _mapping(value, location)
        _fields(
            row,
            location,
            required={"imp_number", "host_number", "hostname", "status"},
            optional={"computer", "operating_system"},
        )
        imp_number = _bounded(row["imp_number"], 1, _MAX_IMP_NUMBER, f"{location}.imp_number")
        host_number = _bounded(row["host_number"], 0, _MAX_HOST_NUMBER, f"{location}.host_number")
        if imp_number > highest:
            raise AddressAuthorityError(
                f"{location}.imp_number {imp_number} exceeds highest_imp_number {highest}"
            )
        position = (imp_number, host_number)
        if position in seen_positions:
            raise AddressAuthorityError(f"{location} duplicates host position {host_number}/{imp_number}")
        seen_positions.add(position)
        hostname = row["hostname"]
        if not isinstance(hostname, str) or not hostname.strip():
            raise AddressAuthorityError(f"{location}.hostname must be a non-empty string")
        if hostname in seen_hostnames:
            raise AddressAuthorityError(f"{location}.hostname duplicates {hostname!r}")
        seen_hostnames.add(hostname)
        status = row["status"]
        if not isinstance(status, str) or not status.strip():
            raise AddressAuthorityError(f"{location}.status must be a non-empty string")
        hosts.append(
            HostIdentity(
                imp_number=imp_number,
                host_number=host_number,
                hostname=hostname,
                computer=_optional_text(row.get("computer"), f"{location}.computer"),
                operating_system=_optional_text(
                    row.get("operating_system"), f"{location}.operating_system"
                ),
                status=status,
            )
        )
    if not hosts:
        raise AddressAuthorityError("address authority.hosts must not be empty")

    return AddressAuthority(
        id=identifier,
        title=source["title"],
        identifier=source["identifier"],
        dated=source["dated"],
        url=source["url"],
        sha256=source["sha256"],
        highest_imp_number=highest,
        hosts=tuple(hosts),
    )


def _optional_text(value: object, location: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AddressAuthorityError(f"{location} must be a non-empty string when present")
    return value


def _bounded(value: object, low: int, high: int, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise AddressAuthorityError(f"{location} must be an integer in {low}..{high}")
    return value


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AddressAuthorityError(f"{location} must be an object")
    return value


def _list(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise AddressAuthorityError(f"{location} must be an array")
    return value


def _fields(
    value: Mapping[str, Any],
    location: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise AddressAuthorityError(f"{location} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise AddressAuthorityError(f"{location} is missing fields: {', '.join(sorted(missing))}")
