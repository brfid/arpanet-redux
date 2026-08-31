from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import unittest

from ncc.events import EventSource, NccEvent
from ncc.reconciliation import Endpoint, nominal_topology_from_shared
from ncc.shared_topology import load_shared_topology


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_PATH = ROOT / "config" / "topologies" / "ncc-alternate-path-fault.json"
EVALUATOR_PATH = ROOT / "scripts" / "ncc-evaluate-alternate-path.py"


def load_evaluator():
    spec = importlib.util.spec_from_file_location("ncc_alternate_path_evaluator", EVALUATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load alternate-path evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_event(
    *,
    imp: int,
    state: str,
    neighbor_imp: int | None,
    sequence: int,
    observed_at: str,
) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at=observed_at,
        event_type="line-endpoint.state",
        subject=f"imp:{imp}:line:1",
        state=state,
        source=EventSource(kind="imp-trouble-report", imp=imp),
        details={"neighbor_imp": neighbor_imp},
    )


class AlternatePathTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
        cls.shared = load_shared_topology(TOPOLOGY_PATH)
        cls.nominal = nominal_topology_from_shared(cls.shared)
        config_paths = {
            interface["simh_config"] for interface in cls.document["interfaces"]
        }
        config_paths.update(
            binding[field]
            for binding in cls.document["modem_interfaces"]
            for field in ("first_simh_config", "second_simh_config")
        )
        cls.config_text = {
            path: (ROOT / path).read_text(encoding="utf-8") for path in config_paths
        }

    def test_triangle_has_direct_and_alternate_routes_to_the_same_receiver(self) -> None:
        components = {
            component["id"] for component in self.document["topology"]["components"]
        }
        self.assertEqual(components, {"host:ncc", "imp:5", "imp:6", "imp:7"})
        routes = {
            route["id"]: route["components"]
            for route in self.document["topology"]["routes"]
        }
        self.assertEqual(
            routes,
            {
                "route:imp6-to-ncc-direct": ["imp:6", "imp:5", "host:ncc"],
                "route:imp6-to-ncc-alternate": [
                    "imp:6",
                    "imp:7",
                    "imp:5",
                    "host:ncc",
                ],
            },
        )
        self.assertNotIn("historical_site", self.document)
        self.assertNotIn("observations", self.document)

    def test_only_the_evidenced_direct_binding_maps_report_lines(self) -> None:
        self.assertEqual(len(self.shared.modem_interfaces), 3)
        mapped = [
            binding
            for binding in self.shared.modem_interfaces
            if binding.first_report_line is not None
            or binding.second_report_line is not None
        ]
        self.assertEqual([binding.id for binding in mapped], ["binding:imp5-mi1-imp6-mi1"])
        self.assertEqual(len(self.nominal.lines), 1)
        self.assertEqual(self.nominal.lines[0].first, Endpoint(5, 1))
        self.assertEqual(self.nominal.lines[0].second, Endpoint(6, 1))

    def test_configs_use_all_ten_harness_ports_and_the_external_firmware_root(self) -> None:
        configured_ports = {
            match
            for text in self.config_text.values()
            for match in re.findall(r"%([A-Z0-9_]+_PORT)%", text)
        }
        self.assertEqual(
            configured_ports,
            {
                "BRFID_IMP5_DIRECT_PORT",
                "BRFID_IMP6_DIRECT_PORT",
                "BRFID_DIRECT_RELAY5_PORT",
                "BRFID_DIRECT_RELAY6_PORT",
                "BRFID_IMP5_ALT_PORT",
                "BRFID_IMP7_TO5_PORT",
                "BRFID_IMP7_TO6_PORT",
                "BRFID_IMP6_ALT_PORT",
                "BRFID_IMP5_HI_PORT",
                "BRFID_NCC_HI_PORT",
            },
        )
        for text in self.config_text.values():
            self.assertIn("do %BRFID_H316_MINI_ROOT%/impconfig.simh", text)
            self.assertIn("do %BRFID_H316_MINI_ROOT%/impcode.simh", text)


class AlternatePathEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = load_evaluator()
        cls.topology = nominal_topology_from_shared(load_shared_topology(TOPOLOGY_PATH))

    def test_accepts_a_fresh_up_to_reciprocal_down_transition(self) -> None:
        result = self.evaluator.evaluate(
            topology=self.topology,
            events=self._events(),
            receiver=self._receiver(),
            relay=self._relay(),
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["direct_line"]["pre_fault_state"], "up")
        self.assertEqual(result["direct_line"]["pre_fault_supporting_sequences"], [1, 2])
        self.assertEqual(result["direct_line"]["final_state"], "down")
        self.assertEqual(result["direct_line"]["final_supporting_sequences"], [3, 4])

    def test_rejects_missing_post_cut_imp6_report_without_changing_line_evidence(self) -> None:
        receiver = self._receiver()
        receiver["trouble_reports"] = [
            report
            for report in receiver["trouble_reports"]
            if not (
                report["source_imp"] == 6
                and report["observed_at"] > "2026-08-31T12:00:30Z"
            )
        ]
        result = self.evaluator.evaluate(
            topology=self.topology,
            events=self._events(),
            receiver=receiver,
            relay=self._relay(),
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["post-cut-reports-from-imps-5-and-6"])
        self.assertEqual(result["direct_line"]["final_state"], "down")

    @staticmethod
    def _events() -> tuple[NccEvent, ...]:
        return (
            line_event(
                imp=5,
                state="up",
                neighbor_imp=6,
                sequence=1,
                observed_at="2026-08-31T12:00:20Z",
            ),
            line_event(
                imp=6,
                state="up",
                neighbor_imp=5,
                sequence=2,
                observed_at="2026-08-31T12:00:20Z",
            ),
            line_event(
                imp=5,
                state="down",
                neighbor_imp=None,
                sequence=3,
                observed_at="2026-08-31T12:01:00Z",
            ),
            line_event(
                imp=6,
                state="down",
                neighbor_imp=None,
                sequence=4,
                observed_at="2026-08-31T12:01:00Z",
            ),
        )

    @staticmethod
    def _receiver() -> dict[str, object]:
        return {
            "started_at": "2026-08-31T12:00:00Z",
            "trouble_reports": [
                {"source_imp": 5, "observed_at": "2026-08-31T12:00:20Z"},
                {"source_imp": 6, "observed_at": "2026-08-31T12:00:20Z"},
                {"source_imp": 7, "observed_at": "2026-08-31T12:00:25Z"},
                {"source_imp": 5, "observed_at": "2026-08-31T12:01:00Z"},
                {"source_imp": 6, "observed_at": "2026-08-31T12:01:00Z"},
            ],
        }

    @staticmethod
    def _relay() -> dict[str, object]:
        return {
            "fault_started_at": "2026-08-31T12:00:30Z",
            "directions": {
                "a-to-b": {"forwarded": 10, "dropped": 20},
                "b-to-a": {"forwarded": 11, "dropped": 21},
            },
            "unexpected_sources": [],
        }


if __name__ == "__main__":
    unittest.main()
