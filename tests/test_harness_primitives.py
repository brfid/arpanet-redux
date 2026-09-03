from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from ncc.harness_config import (
    PORT_VARIABLES,
    create_host106_attach_config,
    validate_environment,
)
from ncc.harness_imp import (
    latest_watchdog,
    mi_link_messages,
    mi_link_messages_from_bytes,
    significant,
    wait_for_log_marker,
    wait_for_watchdog_devices_ready,
    watchdog_devices_ready,
    watchdog_reports_modem_dead,
    watchdog_states_from_bytes,
)
from ncc.harness_manifest import sha256
from ncc.harness_process import stop_all


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "scripts" / "two-its-controller.py"
SPEC = importlib.util.spec_from_file_location(
    "two_its_controller_primitives", CONTROLLER_PATH
)
assert SPEC is not None and SPEC.loader is not None
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


class FakeImp:
    def __init__(self, debug_path: Path, name: str = "imp-test") -> None:
        self.debug_path = debug_path
        self.name = name
        self.ensure_alive_calls = 0

    def ensure_alive(self) -> None:
        self.ensure_alive_calls += 1


class RecordingProcess:
    def __init__(self, name: str, events: list[tuple[str, object]]) -> None:
        self.name = name
        self.events = events

    def stop(self, force: bool | None = None) -> None:
        self.events.append((self.name, force))


class HarnessPrimitiveContractTests(unittest.TestCase):
    def test_two_its_controller_uses_the_importable_primitive_owners(self) -> None:
        owners = {
            "PORT_VARIABLES": PORT_VARIABLES,
            "create_host106_attach_config": create_host106_attach_config,
            "latest_watchdog": latest_watchdog,
            "mi_link_messages": mi_link_messages,
            "mi_link_messages_from_bytes": mi_link_messages_from_bytes,
            "sha256": sha256,
            "significant": significant,
            "stop_all": stop_all,
            "validate_environment": validate_environment,
            "wait_for_log_marker": wait_for_log_marker,
            "wait_for_watchdog_devices_ready": wait_for_watchdog_devices_ready,
            "watchdog_devices_ready": watchdog_devices_ready,
            "watchdog_reports_modem_dead": watchdog_reports_modem_dead,
            "watchdog_states_from_bytes": watchdog_states_from_bytes,
        }
        for name, owner in owners.items():
            with self.subTest(name=name):
                self.assertIs(getattr(CONTROLLER, name), owner)

    def test_sha256_streams_the_complete_file(self) -> None:
        content = b"a" * (1024 * 1024 + 17) + b"tail"
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "artifact.bin"
            path.write_bytes(content)

            self.assertEqual(
                CONTROLLER.sha256(path),
                hashlib.sha256(content).hexdigest(),
            )

    def test_environment_validation_accepts_only_decimal_udp_ports(self) -> None:
        valid = {
            name: str(index + 1)
            for index, name in enumerate(CONTROLLER.PORT_VARIABLES)
        }
        with patch.dict(os.environ, valid, clear=True):
            CONTROLLER.validate_environment()

        for invalid in ("", "0", "65536", "+1", " 1", "1.0"):
            values = dict(valid)
            values[CONTROLLER.PORT_VARIABLES[0]] = invalid
            with self.subTest(invalid=invalid), patch.dict(
                os.environ, values, clear=True
            ):
                with self.assertRaisesRegex(ValueError, "not a valid UDP port"):
                    CONTROLLER.validate_environment()

    def test_log_marker_search_honors_the_starting_offset(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "imp.debug.log"
            prefix = b"READY before probe\n"
            path.write_bytes(prefix + b"READY after probe\n")
            imp = FakeImp(path)

            observed_at = CONTROLLER.wait_for_log_marker(
                imp, "READY", timeout=1, offset=len(prefix)
            )

            self.assertGreater(observed_at, 0)
            self.assertEqual(imp.ensure_alive_calls, 1)

    def test_log_marker_timeout_checks_liveness_and_names_the_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "imp.debug.log"
            path.write_bytes(b"READY before probe\n")
            imp = FakeImp(path)

            with self.assertRaisesRegex(
                TimeoutError,
                r"imp-test did not report 'READY' within 0\.01s",
            ):
                CONTROLLER.wait_for_log_marker(
                    imp,
                    "READY",
                    timeout=0.01,
                    offset=path.stat().st_size,
                )

            self.assertEqual(imp.ensure_alive_calls, 1)

    def test_stop_all_stops_hosts_before_imps_and_propagates_force(self) -> None:
        events: list[tuple[str, object]] = []
        hosts = (
            RecordingProcess("host-a", events),
            RecordingProcess("host-b", events),
        )
        imps = (
            RecordingProcess("imp-a", events),
            RecordingProcess("imp-b", events),
        )

        CONTROLLER.stop_all(hosts, imps, force=True)

        self.assertEqual(
            events,
            [
                ("host-a", True),
                ("host-b", True),
                ("imp-a", None),
                ("imp-b", None),
            ],
        )


if __name__ == "__main__":
    unittest.main()
