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
TOPOLOGY_PATH = (
    ROOT / "config" / "topologies" / "ncc-pdp11-its-coexistence.json"
)
EVALUATOR_PATH = ROOT / "scripts" / "ncc-evaluate-pdp11-its-coexistence.py"


def load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "ncc_pdp11_its_coexistence_evaluator", EVALUATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load coexistence evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line_event(*, imp: int, neighbor: int, sequence: int) -> NccEvent:
    return NccEvent(
        sequence=sequence,
        observed_at="2026-09-01T12:00:20Z",
        event_type="line-endpoint.state",
        subject=f"imp:{imp}:line:1",
        state="up",
        source=EventSource(kind="imp-trouble-report", imp=imp),
        details={"neighbor_imp": neighbor},
    )


class CoexistenceTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(TOPOLOGY_PATH.read_text(encoding="utf-8"))
        cls.shared = load_shared_topology(TOPOLOGY_PATH)
        cls.nominal = nominal_topology_from_shared(cls.shared)

    def test_combines_the_accepted_application_route_and_ncc_triangle(self) -> None:
        components = {
            component["id"] for component in self.document["topology"]["components"]
        }
        self.assertEqual(
            components,
            {"host:176", "imp:62", "imp:6", "host:106", "imp:7", "imp:5", "host:ncc"},
        )
        routes = {
            route["id"]: route["components"]
            for route in self.document["topology"]["routes"]
        }
        self.assertEqual(
            routes["route:host176-to-host106"],
            ["host:176", "imp:62", "imp:6", "host:106"],
        )
        self.assertEqual(
            routes["route:imp62-to-ncc-alternate"],
            ["imp:62", "imp:6", "imp:7", "imp:5", "host:ncc"],
        )

    def test_preserves_only_the_exact_mapped_imp5_imp6_line(self) -> None:
        self.assertEqual(len(self.nominal.lines), 1)
        self.assertEqual(self.nominal.lines[0].id, "binding:imp5-mi1-imp6-mi1")
        self.assertEqual(self.nominal.lines[0].first, Endpoint(5, 1))
        self.assertEqual(self.nominal.lines[0].second, Endpoint(6, 1))
        mapped = [
            binding
            for binding in self.shared.modem_interfaces
            if binding.first_report_line is not None
        ]
        self.assertEqual([binding.id for binding in mapped], ["binding:imp5-mi1-imp6-mi1"])

    def test_moves_only_the_application_side_of_imp6_to_mi3(self) -> None:
        application = next(
            binding
            for binding in self.shared.modem_interfaces
            if {binding.first_imp_id, binding.second_imp_id} == {"imp:62", "imp:6"}
        )
        self.assertEqual(application.first_simh_device, "mi1")
        self.assertEqual(application.second_simh_device, "mi3")
        self.assertIsNone(application.first_report_line)
        self.assertIsNone(application.second_report_line)
        imp6_config = (ROOT / application.second_simh_config).read_text(encoding="utf-8")
        for device in ("mi1", "mi2", "mi3"):
            self.assertIn(f"set {device} enabled", imp6_config)
        self.assertIn("set hi2 enabled", imp6_config)
        self.assertIn("set hi2 convert", imp6_config)
        self.assertNotIn("deposit 1005", imp6_config.lower())

    def test_every_bound_port_is_consumed_by_the_named_imp_configs(self) -> None:
        config_paths = {
            interface.simh_config for interface in self.shared.interfaces
        }
        config_paths.update(
            path
            for binding in self.shared.modem_interfaces
            for path in (binding.first_simh_config, binding.second_simh_config)
        )
        config_text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8") for path in config_paths
        )
        configured = set(re.findall(r"%([A-Z0-9_]+_PORT)%", config_text))
        expected = {
            name
            for interface in self.shared.interfaces
            for name in (
                interface.imp_listen_environment,
                interface.host_listen_environment,
            )
        }
        expected.update(
            name
            for binding in self.shared.modem_interfaces
            for name in (
                binding.first_listen_environment,
                binding.second_listen_environment,
            )
        )
        self.assertEqual(configured, expected)
        self.assertEqual(len(expected), 14)


class CoexistenceEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluator = load_evaluator()
        cls.topology = nominal_topology_from_shared(load_shared_topology(TOPOLOGY_PATH))

    def test_accepts_application_reports_and_one_direct_up_pair(self) -> None:
        result = self.evaluate()

        self.assertTrue(result["passed"])
        self.assertEqual(result["direct_line"]["observed_state"], "up")
        self.assertEqual(result["direct_line"]["supporting_sequences"], [1, 2])

    def test_rejects_a_missing_imp62_throughput_report(self) -> None:
        receiver = self.receiver()
        receiver["throughput_reports"] = [
            report
            for report in receiver["throughput_reports"]
            if report["source_imp"] != 62
        ]
        result = self.evaluate(receiver=receiver)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["throughput-reports-from-imps-5-6-7-62"])
        self.assertEqual(result["direct_line"]["observed_state"], "up")

    def test_rejects_application_success_without_the_typed_journey(self) -> None:
        application = self.application()
        application["message_journey_observations"] = "9"
        result = self.evaluate(application=application)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["typed-journey-retained"])

    def evaluate(
        self,
        *,
        receiver: dict[str, object] | None = None,
        application: dict[str, str] | None = None,
    ):
        return self.evaluator.evaluate(
            topology=self.topology,
            events=(
                line_event(imp=5, neighbor=6, sequence=1),
                line_event(imp=6, neighbor=5, sequence=2),
            ),
            receiver=receiver or self.receiver(),
            application=application or self.application(),
            cleanup={"surviving_owned_processes": "0"},
            outcome="passed",
            manifest=self.manifest(),
            identities={
                "run_id": "run-1",
                "stream_run_id": "run-1",
                "topology_id": "topology:ncc-pdp11-its-coexistence",
                "stream_topology_id": "topology:ncc-pdp11-its-coexistence",
                "interface_id": "binding:ncc-host0-imp5",
                "stream_interface_id": "binding:ncc-host0-imp5",
            },
        )

    @staticmethod
    def receiver() -> dict[str, object]:
        reports = [{"source_imp": imp} for imp in (5, 6, 7, 62)]
        return {
            "started_at": "2026-09-01T12:00:00Z",
            "topology_id": "topology:ncc-pdp11-its-coexistence",
            "interface_id": "binding:ncc-host0-imp5",
            "trouble_reports": list(reports),
            "throughput_reports": list(reports),
        }

    @staticmethod
    def application() -> dict[str, str]:
        return {
            "connection_open": "1",
            "remote_time": "structured",
            "correlated_inter_imp_traffic": "both-directions",
            "message_journey_observations": "10",
            "message_journey_state": "missing-boundary",
            "message_journey_first_boundary": "boundary:request:6",
        }

    @staticmethod
    def manifest() -> dict[str, str]:
        return {
            "repository.tracked_dirty": "0",
            "source.arpanet-in-a-box.tracked_dirty": "0",
            "source.network-unix-v6.tracked_dirty": "0",
            "source.h316-simh.tracked_dirty": "0",
            "source.ka10-simh.tracked_dirty": "0",
            "source.imp11a-simh.tracked_dirty": "0",
            "cleanup.outer-runtime": "passed",
        }


if __name__ == "__main__":
    unittest.main()
