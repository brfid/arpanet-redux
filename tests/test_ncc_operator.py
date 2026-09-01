from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ncc-operate-pdp11-its.py"
SPEC = importlib.util.spec_from_file_location("ncc_operate_pdp11_its", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
OPERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPERATOR)


class _CooperativeProcess:
    pid = 12345

    def __init__(self) -> None:
        self.terminated = False
        self.wait_timeouts: list[float] = []

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float):
        self.wait_timeouts.append(timeout)
        return 0


class NccOperatorTests(unittest.TestCase):
    def test_result_identity_is_one_safe_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            self.assertEqual(
                OPERATOR.results_directory(root, "demo-20260901T120000Z"),
                root / "ncc-pdp11-its-coexistence-demo-20260901T120000Z",
            )
            for invalid in ("", "../demo", "demo/run", "demo run", "."):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(ValueError):
                        OPERATOR.results_directory(root, invalid)

    def test_command_delegates_to_the_existing_formal_harness(self) -> None:
        arguments = argparse.Namespace(
            arpanet_root=Path("/lab/arpanet"),
            network_unix_root=Path("/lab/network-unix"),
            imp11a_root=Path("/lab/imp11a"),
            h316=Path("/bin/h316"),
            pdp10_ka=Path("/bin/pdp10-ka"),
            pdp11=Path("/bin/pdp11"),
            pdp11_build_root=Path("/lab/pdp11-build"),
        )
        result = Path("/lab/results/ncc-result")

        command = OPERATOR.scenario_command(arguments, result)

        self.assertEqual(command[0], str(ROOT / "scripts" / "smoke-ncc-pdp11-its.sh"))
        self.assertEqual(command[1:8], [
            "/lab/arpanet",
            "/lab/network-unix",
            "/lab/imp11a",
            "/bin/h316",
            "/bin/pdp10-ka",
            "/bin/pdp11",
            "/lab/pdp11-build",
        ])
        self.assertEqual(command[8], str(result))

    def test_stop_allows_the_owned_harness_cleanup_trap_to_finish(self) -> None:
        process = _CooperativeProcess()

        OPERATOR.stop_owned_scenario(process, timeout=12)

        self.assertTrue(process.terminated)
        self.assertEqual(process.wait_timeouts, [12])


if __name__ == "__main__":
    unittest.main()
