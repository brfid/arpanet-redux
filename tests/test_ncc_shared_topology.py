from __future__ import annotations

import copy
from pathlib import Path
import unittest

from ncc.shared_topology import (
    SharedTopologyValidationError,
    load_shared_topology,
    shared_topology_from_mapping,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT_TOPOLOGY = ROOT / "config" / "topologies" / "imp5-ncc-host-interface.json"


def imp5_host_interface_topology() -> dict[str, object]:
    return {
        "schema_version": 2,
        "address_authority": "nic-32992-1975-07",
        "id": "topology:imp5-ncc-host-interface-proof",
        "topology": {
            "components": [
                {
                    "id": "host:ncc",
                    "kind": "observer",
                    "label": "NCC receiver (host 0)",
                    "position": {"x": 0, "y": 0},
                    "endpoints": [{"id": "host:ncc:1822", "label": "1822"}],
                },
                {
                    "id": "imp:5",
                    "kind": "imp",
                    "label": "IMP 5",
                    "position": {"x": 1, "y": 0},
                    "endpoints": [
                        {"id": "imp:5:host:0", "label": "Host 0"},
                        {"id": "imp:5:mi1", "label": "MI1"},
                    ],
                },
                {
                    "id": "imp:6",
                    "kind": "imp",
                    "label": "IMP 6",
                    "position": {"x": 2, "y": 0},
                    "endpoints": [{"id": "imp:6:mi1", "label": "MI1"}],
                },
            ],
            "links": [
                {
                    "id": "link:ncc-imp5",
                    "endpoints": ["host:ncc:1822", "imp:5:host:0"],
                },
                {
                    "id": "link:imp5-imp6",
                    "endpoints": ["imp:5:mi1", "imp:6:mi1"],
                },
            ],
            "routes": [
                {
                    "id": "route:imp6-to-ncc",
                    "components": ["imp:6", "imp:5", "host:ncc"],
                }
            ],
        },
        "interfaces": [
            {
                "id": "binding:ncc-host0-imp5",
                "kind": "host-interface",
                "imp_id": "imp:5",
                "imp_endpoint": "imp:5:host:0",
                "host_id": "host:ncc",
                "host_endpoint": "host:ncc:1822",
                "host_number": 0,
                "synthetic": True,
                "simh_device": "hi1",
                "imp_listen_environment": "BRFID_IMP5_HI_PORT",
                "host_listen_environment": "BRFID_NCC_HI_PORT",
                "simh_config": "config/imp/ncc-proof/imp5.simh",
            }
        ],
        "modem_interfaces": [
            {
                "id": "binding:imp5-mi1-imp6-mi1",
                "kind": "modem-interface",
                "first_imp_id": "imp:5",
                "first_endpoint": "imp:5:mi1",
                "first_simh_device": "mi1",
                "first_report_line": 1,
                "first_listen_environment": "BRFID_IMP5_MI1_PORT",
                "first_simh_config": "config/imp/ncc-proof/imp5.simh",
                "second_imp_id": "imp:6",
                "second_endpoint": "imp:6:mi1",
                "second_simh_device": "mi1",
                "second_report_line": 1,
                "second_listen_environment": "BRFID_IMP6_MI1_PORT",
                "second_simh_config": "config/imp/ncc-proof/imp6.simh",
            }
        ],
        "proof": {
            "kind": "passive-h316-host-interface",
            "requirements": [
                "host-ready-sent",
                "imp-ready-received",
                "complete-imp-message-received",
            ],
        },
    }


class SharedTopologyTests(unittest.TestCase):
    def test_loads_the_integrated_project_topology_contract(self) -> None:
        topology = load_shared_topology(PROJECT_TOPOLOGY)

        self.assertEqual(topology.id, "topology:imp5-ncc-host-interface-proof")
        self.assertEqual(topology.interface("binding:ncc-host0-imp5").simh_device, "hi1")
        self.assertEqual(len(topology.modem_interfaces), 1)

    def test_binds_host_zero_to_imp5_hi1_without_a_second_port_map(self) -> None:
        topology = shared_topology_from_mapping(imp5_host_interface_topology())

        binding = topology.interface("binding:ncc-host0-imp5")
        self.assertEqual(binding.imp_id, "imp:5")
        self.assertEqual(binding.host_number, 0)
        self.assertEqual(binding.simh_device, "hi1")
        self.assertEqual(binding.imp_listen_environment, "BRFID_IMP5_HI_PORT")
        self.assertEqual(binding.host_listen_environment, "BRFID_NCC_HI_PORT")
        self.assertEqual(
            topology.proof_requirements,
            (
                "host-ready-sent",
                "imp-ready-received",
                "complete-imp-message-received",
            ),
        )
        self.assertEqual(len(topology.modem_interfaces), 1)
        modem = topology.modem_interfaces[0]
        self.assertEqual(modem.first_imp_id, "imp:5")
        self.assertEqual(modem.first_simh_device, "mi1")
        self.assertEqual(modem.first_report_line, 1)
        self.assertEqual(modem.second_imp_id, "imp:6")
        self.assertEqual(modem.second_simh_device, "mi1")
        self.assertEqual(modem.second_report_line, 1)

    def test_rejects_a_host_number_or_endpoint_that_disagrees_with_the_map(self) -> None:
        wrong_device = copy.deepcopy(imp5_host_interface_topology())
        wrong_device["interfaces"][0]["simh_device"] = "hi2"  # type: ignore[index]
        with self.assertRaisesRegex(SharedTopologyValidationError, "simh_device"):
            shared_topology_from_mapping(wrong_device)

        wrong_endpoint = copy.deepcopy(imp5_host_interface_topology())
        wrong_endpoint["interfaces"][0]["imp_endpoint"] = "host:ncc:1822"  # type: ignore[index]
        with self.assertRaisesRegex(SharedTopologyValidationError, "not owned"):
            shared_topology_from_mapping(wrong_endpoint)

    def test_rejects_a_proof_that_omits_complete_imp_message_evidence(self) -> None:
        incomplete_proof = copy.deepcopy(imp5_host_interface_topology())
        incomplete_proof["proof"]["requirements"].pop()  # type: ignore[index]

        with self.assertRaisesRegex(SharedTopologyValidationError, "complete-imp-message-received"):
            shared_topology_from_mapping(incomplete_proof)

    def test_rejects_a_modem_port_name_reused_by_the_host_interface(self) -> None:
        reused_port = copy.deepcopy(imp5_host_interface_topology())
        reused_port["modem_interfaces"][0]["first_listen_environment"] = "BRFID_NCC_HI_PORT"  # type: ignore[index]

        with self.assertRaisesRegex(SharedTopologyValidationError, "reuses port environment"):
            shared_topology_from_mapping(reused_port)

    def test_rejects_a_host_only_topology_for_a_complete_message_proof(self) -> None:
        host_only = copy.deepcopy(imp5_host_interface_topology())
        host_only["modem_interfaces"] = []

        with self.assertRaisesRegex(SharedTopologyValidationError, "must not be empty"):
            shared_topology_from_mapping(host_only)

    def test_requires_reciprocal_report_line_identities(self) -> None:
        one_sided = copy.deepcopy(imp5_host_interface_topology())
        del one_sided["modem_interfaces"][0]["second_report_line"]  # type: ignore[index]

        with self.assertRaisesRegex(SharedTopologyValidationError, "both endpoints"):
            shared_topology_from_mapping(one_sided)

    def test_rejects_an_invalid_report_line_identity(self) -> None:
        invalid = copy.deepcopy(imp5_host_interface_topology())
        invalid["modem_interfaces"][0]["first_report_line"] = 6  # type: ignore[index]

        with self.assertRaisesRegex(SharedTopologyValidationError, "integer in 1..5"):
            shared_topology_from_mapping(invalid)



class SiteIdentityTests(unittest.TestCase):
    """A host position either matches its dated authority, or says it is synthetic."""

    @staticmethod
    def _with_claim(**claim: object) -> dict[str, object]:
        document = copy.deepcopy(imp5_host_interface_topology())
        binding = document["interfaces"][0]  # type: ignore[index]
        binding.pop("site", None)
        binding.pop("synthetic", None)
        binding.update(claim)
        return document

    @staticmethod
    def _at_recorded_position(**claim: object) -> dict[str, object]:
        """Move the binding to 1/5, which the authority records as BBN-11X."""

        document = copy.deepcopy(imp5_host_interface_topology())
        binding = document["interfaces"][0]  # type: ignore[index]
        binding.pop("site", None)
        binding.pop("synthetic", None)
        binding["host_number"] = 1
        binding["simh_device"] = "hi2"
        binding["imp_endpoint"] = "imp:5:host:1"
        binding.update(claim)
        component = document["topology"]["components"][1]  # type: ignore[index]
        component["endpoints"][0] = {"id": "imp:5:host:1", "label": "Host 1"}
        document["topology"]["links"][0]["endpoints"][1] = "imp:5:host:1"  # type: ignore[index]
        return document

    def test_derives_the_address_rather_than_reading_one(self) -> None:
        topology = shared_topology_from_mapping(imp5_host_interface_topology())

        binding = topology.interface("binding:ncc-host0-imp5")
        self.assertEqual(binding.imp_number, 5)
        self.assertEqual(binding.host_number, 0)
        self.assertEqual(binding.address_decimal, 5)
        self.assertEqual(binding.address_octal, "5")

    def test_the_configured_its_host_matches_its_authority_row(self) -> None:
        topology = load_shared_topology(
            ROOT / "config" / "topologies" / "pdp11-its-telnet.json"
        )

        binding = topology.interface("binding:imp6-hi2-host106")
        self.assertEqual(binding.site, "MIT-DMS")
        self.assertFalse(binding.synthetic)
        self.assertEqual(binding.address_octal, "106")

    def test_the_configured_pdp11_host_is_declared_synthetic(self) -> None:
        topology = load_shared_topology(
            ROOT / "config" / "topologies" / "pdp11-its-telnet.json"
        )

        binding = topology.interface("binding:host176-imp62-hi2")
        self.assertIsNone(binding.site)
        self.assertTrue(binding.synthetic)
        self.assertEqual(binding.address_octal, "176")
        self.assertFalse(topology.address_authority.within_network(binding.imp_number))

    def test_accepts_a_site_the_authority_records_at_that_position(self) -> None:
        topology = shared_topology_from_mapping(self._at_recorded_position(site="BBN-11X"))

        binding = topology.interface("binding:ncc-host0-imp5")
        self.assertEqual(binding.site, "BBN-11X")
        self.assertEqual(binding.address_octal, "105")

    def test_rejects_a_site_the_authority_places_elsewhere(self) -> None:
        with self.assertRaisesRegex(SharedTopologyValidationError, "records 'BBN-11X'"):
            shared_topology_from_mapping(self._at_recorded_position(site="MIT-DMS"))

    def test_rejects_a_site_the_authority_never_recorded(self) -> None:
        with self.assertRaisesRegex(SharedTopologyValidationError, "does not record"):
            shared_topology_from_mapping(self._with_claim(site="BBN-NCC"))

    def test_rejects_synthetic_for_a_position_the_authority_identifies(self) -> None:
        with self.assertRaisesRegex(SharedTopologyValidationError, "declares synthetic"):
            shared_topology_from_mapping(self._at_recorded_position(synthetic=True))

    def test_rejects_a_binding_that_claims_both(self) -> None:
        with self.assertRaisesRegex(SharedTopologyValidationError, "one or the other"):
            shared_topology_from_mapping(self._with_claim(site="BBN-11X", synthetic=True))

    def test_rejects_a_binding_that_claims_neither(self) -> None:
        with self.assertRaisesRegex(SharedTopologyValidationError, "declare synthetic"):
            shared_topology_from_mapping(self._with_claim())

    def test_rejects_an_unknown_address_authority(self) -> None:
        document = copy.deepcopy(imp5_host_interface_topology())
        document["address_authority"] = "nic-00000-1999-01"

        with self.assertRaisesRegex(SharedTopologyValidationError, "unusable"):
            shared_topology_from_mapping(document)


if __name__ == "__main__":
    unittest.main()
