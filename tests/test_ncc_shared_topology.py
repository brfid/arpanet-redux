from __future__ import annotations

import copy
import unittest

from ncc.shared_topology import (
    SharedTopologyValidationError,
    shared_topology_from_mapping,
)


def imp5_host_interface_topology() -> dict[str, object]:
    return {
        "schema_version": 1,
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
                "first_listen_environment": "BRFID_IMP5_MI1_PORT",
                "first_simh_config": "config/imp/ncc-proof/imp5.simh",
                "second_imp_id": "imp:6",
                "second_endpoint": "imp:6:mi1",
                "second_simh_device": "mi1",
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
        self.assertEqual(modem.second_imp_id, "imp:6")
        self.assertEqual(modem.second_simh_device, "mi1")

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


if __name__ == "__main__":
    unittest.main()
