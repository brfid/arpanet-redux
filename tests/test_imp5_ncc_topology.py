from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = ROOT / "config" / "topologies" / "imp5-ncc-host-interface.json"


class Imp5NccTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
        cls.topology = cls.document["topology"]
        cls.components = {
            component["id"]: component for component in cls.topology["components"]
        }
        config_paths = {
            interface["simh_config"] for interface in cls.document["interfaces"]
        }
        config_paths.update(
            binding[key]
            for binding in cls.document["modem_interfaces"]
            for key in ("first_simh_config", "second_simh_config")
        )
        cls.config_text = {
            path: (ROOT / path).read_text(encoding="utf-8") for path in config_paths
        }

    def test_identities_endpoints_and_links_are_unique(self) -> None:
        identity_groups = [
            [self.document["id"]],
            [component["id"] for component in self.topology["components"]],
            [
                endpoint["id"]
                for component in self.topology["components"]
                for endpoint in component["endpoints"]
            ],
            [link["id"] for link in self.topology["links"]],
            [route["id"] for route in self.topology["routes"]],
            [interface["id"] for interface in self.document["interfaces"]],
            [binding["id"] for binding in self.document["modem_interfaces"]],
        ]
        identities = [identity for group in identity_groups for identity in group]
        self.assertEqual(len(identities), len(set(identities)))

        endpoints = set(identity_groups[2])
        linked_endpoints = [
            endpoint
            for link in self.topology["links"]
            for endpoint in link["endpoints"]
        ]
        self.assertEqual(set(linked_endpoints), endpoints)
        self.assertEqual(len(linked_endpoints), len(set(linked_endpoints)))
        self.assertTrue(
            all(len(link["endpoints"]) == 2 for link in self.topology["links"])
        )

    def test_fixed_positions_route_and_proof_scope_are_consistent(self) -> None:
        positions = {
            component_id: component["position"]
            for component_id, component in self.components.items()
        }
        self.assertEqual(
            positions,
            {
                "host:ncc": {"x": 0, "y": 0},
                "imp:5": {"x": 1, "y": 0},
                "imp:6": {"x": 2, "y": 0},
            },
        )
        self.assertEqual(
            len({(position["x"], position["y"]) for position in positions.values()}),
            len(positions),
        )

        routes = self.topology["routes"]
        self.assertEqual(
            routes,
            [
                {
                    "id": "route:imp6-to-ncc",
                    "components": ["imp:6", "imp:5", "host:ncc"],
                }
            ],
        )
        endpoint_owner = {
            endpoint["id"]: component["id"]
            for component in self.topology["components"]
            for endpoint in component["endpoints"]
        }
        link_edges = {
            frozenset(endpoint_owner[endpoint] for endpoint in link["endpoints"])
            for link in self.topology["links"]
        }
        route_edges = {
            frozenset(pair)
            for pair in zip(routes[0]["components"], routes[0]["components"][1:])
        }
        self.assertEqual(route_edges, link_edges)
        self.assertEqual(
            self.document["proof"],
            {
                "kind": "passive-h316-host-interface",
                "requirements": [
                    "host-ready-sent",
                    "imp-ready-received",
                    "complete-imp-message-received",
                ],
            },
        )
        self.assertNotIn("observations", self.document)
        self.assertNotIn("historical_site", self.document)
        serialized = json.dumps(self.document).casefold()
        for historical_or_observed_claim in ("bbn", "historical", "observed", "site"):
            self.assertNotIn(historical_or_observed_claim, serialized)

    def test_ncc_host_zero_maps_to_imp5_hi1(self) -> None:
        interface = self.document["interfaces"]
        self.assertEqual(
            interface,
            [
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
        )
        self.assertIn(
            {
                "id": "link:ncc-imp5",
                "endpoints": ["host:ncc:1822", "imp:5:host:0"],
            },
            self.topology["links"],
        )
        imp5_config = self.config_text[interface[0]["simh_config"]]
        self.assertIn("set imp num=5", imp5_config)
        self.assertIn(
            "attach -u hi1 %BRFID_IMP5_HI_PORT%:127.0.0.1:%BRFID_NCC_HI_PORT%",
            imp5_config,
        )

    def test_imp5_imp6_modem_bindings_are_reciprocal(self) -> None:
        bindings = self.document["modem_interfaces"]
        self.assertEqual(len(bindings), 1)
        binding = bindings[0]
        self.assertEqual(
            {
                "first_imp_id": binding["first_imp_id"],
                "first_endpoint": binding["first_endpoint"],
                "first_simh_device": binding["first_simh_device"],
                "second_imp_id": binding["second_imp_id"],
                "second_endpoint": binding["second_endpoint"],
                "second_simh_device": binding["second_simh_device"],
            },
            {
                "first_imp_id": "imp:5",
                "first_endpoint": "imp:5:mi1",
                "first_simh_device": "mi1",
                "second_imp_id": "imp:6",
                "second_endpoint": "imp:6:mi1",
                "second_simh_device": "mi1",
            },
        )
        first_config = self.config_text[binding["first_simh_config"]]
        second_config = self.config_text[binding["second_simh_config"]]
        self.assertIn(
            "attach -u "
            f"{binding['first_simh_device']} "
            f"%{binding['first_listen_environment']}%:127.0.0.1:"
            f"%{binding['second_listen_environment']}%",
            first_config,
        )
        self.assertIn(
            "attach -u "
            f"{binding['second_simh_device']} "
            f"%{binding['second_listen_environment']}%:127.0.0.1:"
            f"%{binding['first_listen_environment']}%",
            second_config,
        )
        self.assertIn("set imp num=6", second_config)
        self.assertIn("set hi1 disabled", second_config)

    def test_json_port_names_match_simh_and_external_root_is_explicit(self) -> None:
        host_interface = self.document["interfaces"][0]
        modem_interface = self.document["modem_interfaces"][0]
        expected_ports = {
            host_interface["imp_listen_environment"],
            host_interface["host_listen_environment"],
            modem_interface["first_listen_environment"],
            modem_interface["second_listen_environment"],
        }
        configured_ports = {
            match
            for text in self.config_text.values()
            for match in re.findall(r"%([A-Z0-9_]+_PORT)%", text)
        }
        self.assertEqual(configured_ports, expected_ports)

        for text in self.config_text.values():
            self.assertIn("do %BRFID_H316_MINI_ROOT%/impconfig.simh", text)
            self.assertIn("do %BRFID_H316_MINI_ROOT%/impcode.simh", text)
            self.assertNotIn("do impconfig.simh", text)
            self.assertNotIn("do impcode.simh", text)


if __name__ == "__main__":
    unittest.main()
