"""Load one project-authored topology shared by NCC and simulator harnesses.

The completed-run schema owns labels, component identities, links, routes, and
positions.  This module adds the exact host- and modem-interface bindings
needed by a simulator launcher and a passive NCC receiver, so neither side
needs its own IMP-5 port map.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .run_summary import RunSummaryValidationError, validate_normalized_topology


SHARED_TOPOLOGY_SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_ENVIRONMENT_NAME = re.compile(r"BRFID_[A-Z0-9_]+_PORT\Z")
_SIMH_CONFIG = re.compile(r"config/[A-Za-z0-9._/-]+\.simh\Z")


class SharedTopologyValidationError(ValueError):
    """Raised when a topology cannot safely bind its simulator endpoints."""


@dataclass(frozen=True)
class HostInterfaceBinding:
    """One host-numbered H316 interface with its two run-time port names."""

    id: str
    imp_id: str
    imp_endpoint: str
    host_id: str
    host_endpoint: str
    host_number: int
    simh_device: str
    imp_listen_environment: str
    host_listen_environment: str
    simh_config: str


@dataclass(frozen=True)
class ModemInterfaceBinding:
    """One point-to-point H316 modem interface with its two port names."""

    id: str
    first_imp_id: str
    first_endpoint: str
    first_simh_device: str
    first_listen_environment: str
    first_simh_config: str
    second_imp_id: str
    second_endpoint: str
    second_simh_device: str
    second_listen_environment: str
    second_simh_config: str


@dataclass(frozen=True)
class SharedTopology:
    """A validated nominal topology plus launcher/receiver interface bindings."""

    id: str
    topology: Mapping[str, Any]
    interfaces: tuple[HostInterfaceBinding, ...]
    modem_interfaces: tuple[ModemInterfaceBinding, ...]
    proof_requirements: tuple[str, ...]

    def interface(self, identifier: str) -> HostInterfaceBinding:
        """Return one stable host-interface binding by identifier."""

        for binding in self.interfaces:
            if binding.id == identifier:
                return binding
        raise SharedTopologyValidationError(
            f"shared topology {self.id!r} has no interface {identifier!r}"
        )


def load_shared_topology(path: str | Path) -> SharedTopology:
    """Load one versioned project-authored shared-topology JSON document."""

    topology_path = Path(path)
    try:
        document = json.loads(topology_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SharedTopologyValidationError(
            f"could not load shared topology {topology_path}: {error}"
        ) from error
    return shared_topology_from_mapping(document)


def shared_topology_from_mapping(document: object) -> SharedTopology:
    """Validate a mapping and return an immutable, project-owned binding view."""

    root = _mapping(document, "shared topology")
    _fields(
        root,
        "shared topology",
        required={
            "schema_version",
            "id",
            "topology",
            "interfaces",
            "modem_interfaces",
            "proof",
        },
    )
    if (
        isinstance(root["schema_version"], bool)
        or root["schema_version"] != SHARED_TOPOLOGY_SCHEMA_VERSION
    ):
        raise SharedTopologyValidationError(
            "shared topology.schema_version must be "
            f"{SHARED_TOPOLOGY_SCHEMA_VERSION}"
        )
    topology_id = _identifier(root["id"], "shared topology.id")
    topology = _mapping(root["topology"], "shared topology.topology")
    try:
        component_ids, endpoint_owners, _, _ = validate_normalized_topology(topology)
    except RunSummaryValidationError as error:
        raise SharedTopologyValidationError(f"invalid shared nominal topology: {error}") from error
    interfaces, environment_names = _interfaces(
        root["interfaces"], component_ids, endpoint_owners
    )
    modem_interfaces = _modem_interfaces(
        root["modem_interfaces"],
        component_ids,
        endpoint_owners,
        environment_names,
        {binding.id for binding in interfaces},
    )
    proof = _mapping(root["proof"], "shared topology.proof")
    _fields(proof, "shared topology.proof", required={"kind", "requirements"})
    if proof["kind"] != "passive-h316-host-interface":
        raise SharedTopologyValidationError(
            "shared topology.proof.kind must be 'passive-h316-host-interface'"
        )
    requirements = tuple(
        _identifier(value, f"shared topology.proof.requirements[{index}]")
        for index, value in enumerate(_list(proof["requirements"], "shared topology.proof.requirements"))
    )
    if requirements != (
        "host-ready-sent",
        "imp-ready-received",
        "complete-imp-message-received",
    ):
        raise SharedTopologyValidationError(
            "shared topology proof must require host-ready-sent, imp-ready-received, "
            "and complete-imp-message-received in that order"
        )
    serialized_topology = json.loads(json.dumps(topology, sort_keys=True))
    return SharedTopology(
        id=topology_id,
        topology=serialized_topology,
        interfaces=interfaces,
        modem_interfaces=modem_interfaces,
        proof_requirements=requirements,
    )


def _interfaces(
    value: object, component_ids: set[str], endpoint_owners: Mapping[str, str]
) -> tuple[tuple[HostInterfaceBinding, ...], set[str]]:
    interfaces = _list(value, "shared topology.interfaces")
    if not interfaces:
        raise SharedTopologyValidationError("shared topology.interfaces must not be empty")
    bindings: list[HostInterfaceBinding] = []
    identifiers: set[str] = set()
    environment_names: set[str] = set()
    for index, binding_value in enumerate(interfaces):
        location = f"shared topology.interfaces[{index}]"
        binding = _mapping(binding_value, location)
        _fields(
            binding,
            location,
            required={
                "host_endpoint",
                "host_id",
                "host_listen_environment",
                "host_number",
                "id",
                "imp_endpoint",
                "imp_id",
                "imp_listen_environment",
                "kind",
                "simh_config",
                "simh_device",
            },
        )
        if binding["kind"] != "host-interface":
            raise SharedTopologyValidationError(f"{location}.kind must be 'host-interface'")
        identifier = _identifier(binding["id"], f"{location}.id")
        if identifier in identifiers:
            raise SharedTopologyValidationError(f"{location}.id duplicates {identifier!r}")
        identifiers.add(identifier)
        imp_id = _identifier(binding["imp_id"], f"{location}.imp_id")
        host_id = _identifier(binding["host_id"], f"{location}.host_id")
        imp_endpoint = _identifier(binding["imp_endpoint"], f"{location}.imp_endpoint")
        host_endpoint = _identifier(binding["host_endpoint"], f"{location}.host_endpoint")
        if imp_id not in component_ids or host_id not in component_ids:
            raise SharedTopologyValidationError(f"{location} refers to an unknown component")
        if endpoint_owners.get(imp_endpoint) != imp_id:
            raise SharedTopologyValidationError(
                f"{location}.imp_endpoint is not owned by {imp_id!r}"
            )
        if endpoint_owners.get(host_endpoint) != host_id:
            raise SharedTopologyValidationError(
                f"{location}.host_endpoint is not owned by {host_id!r}"
            )
        host_number = binding["host_number"]
        if isinstance(host_number, bool) or not isinstance(host_number, int) or not 0 <= host_number <= 3:
            raise SharedTopologyValidationError(f"{location}.host_number must be an integer in 0..3")
        simh_device = binding["simh_device"]
        if not isinstance(simh_device, str) or simh_device != f"hi{host_number + 1}":
            raise SharedTopologyValidationError(
                f"{location}.simh_device must be 'hi{host_number + 1}' for host {host_number}"
            )
        imp_environment = _environment_name(
            binding["imp_listen_environment"], f"{location}.imp_listen_environment"
        )
        host_environment = _environment_name(
            binding["host_listen_environment"], f"{location}.host_listen_environment"
        )
        if imp_environment == host_environment:
            raise SharedTopologyValidationError(f"{location} reuses one port environment name")
        for name in (imp_environment, host_environment):
            if name in environment_names:
                raise SharedTopologyValidationError(
                    f"{location} reuses port environment name {name!r}"
                )
            environment_names.add(name)
        simh_config = binding["simh_config"]
        if not isinstance(simh_config, str) or not _SIMH_CONFIG.fullmatch(simh_config):
            raise SharedTopologyValidationError(
                f"{location}.simh_config must name a relative config/*.simh file"
            )
        bindings.append(
            HostInterfaceBinding(
                id=identifier,
                imp_id=imp_id,
                imp_endpoint=imp_endpoint,
                host_id=host_id,
                host_endpoint=host_endpoint,
                host_number=host_number,
                simh_device=simh_device,
                imp_listen_environment=imp_environment,
                host_listen_environment=host_environment,
                simh_config=simh_config,
            )
        )
    return tuple(bindings), environment_names


def _modem_interfaces(
    value: object,
    component_ids: set[str],
    endpoint_owners: Mapping[str, str],
    environment_names: set[str],
    interface_identifiers: set[str],
) -> tuple[ModemInterfaceBinding, ...]:
    interfaces = _list(value, "shared topology.modem_interfaces")
    if not interfaces:
        raise SharedTopologyValidationError(
            "shared topology.modem_interfaces must not be empty for this proof"
        )
    bindings: list[ModemInterfaceBinding] = []
    identifiers = set(interface_identifiers)
    for index, binding_value in enumerate(interfaces):
        location = f"shared topology.modem_interfaces[{index}]"
        binding = _mapping(binding_value, location)
        _fields(
            binding,
            location,
            required={
                "first_endpoint",
                "first_imp_id",
                "first_listen_environment",
                "first_simh_config",
                "first_simh_device",
                "id",
                "kind",
                "second_endpoint",
                "second_imp_id",
                "second_listen_environment",
                "second_simh_config",
                "second_simh_device",
            },
        )
        if binding["kind"] != "modem-interface":
            raise SharedTopologyValidationError(f"{location}.kind must be 'modem-interface'")
        identifier = _identifier(binding["id"], f"{location}.id")
        if identifier in identifiers:
            raise SharedTopologyValidationError(f"{location}.id duplicates {identifier!r}")
        identifiers.add(identifier)
        first = _modem_side(
            binding,
            location,
            "first",
            component_ids,
            endpoint_owners,
            environment_names,
        )
        second = _modem_side(
            binding,
            location,
            "second",
            component_ids,
            endpoint_owners,
            environment_names,
        )
        if first[0] == second[0] or first[1] == second[1]:
            raise SharedTopologyValidationError(
                f"{location} must join two distinct IMPs and endpoints"
            )
        bindings.append(
            ModemInterfaceBinding(
                id=identifier,
                first_imp_id=first[0],
                first_endpoint=first[1],
                first_simh_device=first[2],
                first_listen_environment=first[3],
                first_simh_config=first[4],
                second_imp_id=second[0],
                second_endpoint=second[1],
                second_simh_device=second[2],
                second_listen_environment=second[3],
                second_simh_config=second[4],
            )
        )
    return tuple(bindings)


def _modem_side(
    binding: Mapping[str, Any],
    location: str,
    side: str,
    component_ids: set[str],
    endpoint_owners: Mapping[str, str],
    environment_names: set[str],
) -> tuple[str, str, str, str, str]:
    imp_id = _identifier(binding[f"{side}_imp_id"], f"{location}.{side}_imp_id")
    endpoint = _identifier(binding[f"{side}_endpoint"], f"{location}.{side}_endpoint")
    if imp_id not in component_ids:
        raise SharedTopologyValidationError(f"{location}.{side}_imp_id refers to an unknown component")
    if endpoint_owners.get(endpoint) != imp_id:
        raise SharedTopologyValidationError(
            f"{location}.{side}_endpoint is not owned by {imp_id!r}"
        )
    simh_device = binding[f"{side}_simh_device"]
    if not isinstance(simh_device, str) or not re.fullmatch(r"mi[1-4]", simh_device):
        raise SharedTopologyValidationError(
            f"{location}.{side}_simh_device must be an H316 modem device name"
        )
    environment = _environment_name(
        binding[f"{side}_listen_environment"], f"{location}.{side}_listen_environment"
    )
    if environment in environment_names:
        raise SharedTopologyValidationError(
            f"{location} reuses port environment name {environment!r}"
        )
    environment_names.add(environment)
    simh_config = binding[f"{side}_simh_config"]
    if not isinstance(simh_config, str) or not _SIMH_CONFIG.fullmatch(simh_config):
        raise SharedTopologyValidationError(
            f"{location}.{side}_simh_config must name a relative config/*.simh file"
        )
    return imp_id, endpoint, simh_device, environment, simh_config


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SharedTopologyValidationError(f"{location} must be an object")
    return value


def _list(value: object, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise SharedTopologyValidationError(f"{location} must be an array")
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
        raise SharedTopologyValidationError(
            f"{location} has unknown fields: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise SharedTopologyValidationError(
            f"{location} is missing fields: {', '.join(sorted(missing))}"
        )


def _identifier(value: object, location: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise SharedTopologyValidationError(f"{location} must be a stable identifier")
    return value


def _environment_name(value: object, location: str) -> str:
    if not isinstance(value, str) or not _ENVIRONMENT_NAME.fullmatch(value):
        raise SharedTopologyValidationError(f"{location} must be a BRFID_*_PORT name")
    return value
