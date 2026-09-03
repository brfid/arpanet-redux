from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

from ncc.harness_imp import latest_watchdog, wait_for_log_marker
from ncc.harness_manifest import append_manifest, read_manifest, sha256
from ncc.harness_process import ImpProcess, PtyProcess, ensure_process_alive
from ncc.pdp11_its_harness import (
    application_evidence_failures,
    boot_pdp11,
    stop_and_record,
    wait_for_prompt,
)

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "scripts" / "pdp11-its-failover-controller.py"


def load_controller():
    spec = importlib.util.spec_from_file_location(
        "pdp11_its_failover_controller", CONTROLLER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load failover controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Pdp11ItsFailoverControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.controller = load_controller()

    def test_controller_uses_importable_lifecycle_owners(self) -> None:
        owners = {
            "PtyProcess": PtyProcess,
            "ImpProcess": ImpProcess,
            "append_manifest": append_manifest,
            "read_manifest": read_manifest,
            "sha256": sha256,
            "latest_watchdog": latest_watchdog,
            "wait_for_log_marker": wait_for_log_marker,
            "ensure_process_alive": ensure_process_alive,
            "application_evidence_failures": application_evidence_failures,
            "boot_pdp11": boot_pdp11,
            "stop_and_record": stop_and_record,
            "wait_for_prompt": wait_for_prompt,
        }
        self.assertFalse(hasattr(self.controller, "BASE"))
        self.assertFalse(hasattr(self.controller, "SHARED"))
        for name, owner in owners.items():
            with self.subTest(name=name):
                self.assertIs(getattr(self.controller, name), owner)

    def test_post_cut_evidence_requires_the_second_structured_response(self) -> None:
        pdp11 = (
            b"The time is 12:34:56 EDT.\r\n"
            b"Today is Tuesday, the 1st of September, 2026.\r\n"
            b"KA ITS 1652 has run for 1:23:45.\r\n"
        )
        imp6 = b"HI2 MSG: message received\nHI2 MSG: message sent\n"
        imp62 = b"HI2 MSG: message received\nHI2 MSG: message sent\n"

        self.assertEqual(
            self.controller.post_cut_application_failures(
                pdp11,
                imp6,
                b"",
                imp62,
                imp6_alternate_device="mi2",
                imp7_in_device="mi3",
                imp7_out_device="mi2",
                imp62_alternate_device="mi2",
            ),
            [],
        )
        failures = self.controller.post_cut_application_failures(
            pdp11.split(b"Today is", 1)[0],
            imp6,
            b"",
            imp62,
            imp6_alternate_device="mi2",
            imp7_in_device="mi3",
            imp7_out_device="mi2",
            imp62_alternate_device="mi2",
        )
        self.assertTrue(any("post-cut remote date" in item for item in failures))

    def test_network_unix_readiness_waits_for_guest_consumed_rrp(self) -> None:
        class FakeGuest:
            def __init__(self) -> None:
                self.pattern: bytes | None = None
                self.timeout: float | None = None

            def expect(self, pattern: bytes, timeout: float):
                self.pattern = pattern
                self.timeout = timeout
                return re.search(pattern, b"SKTRACE hh h=106 bytes=1 op=15\n")

        guest = FakeGuest()
        match = self.controller.wait_for_network_unix_host106_ready(guest, 17.0)

        self.assertIsNotNone(match)
        self.assertEqual(
            guest.pattern,
            self.controller.NETWORK_UNIX_HOST106_READY_PATTERN,
        )
        self.assertEqual(guest.timeout, 17.0)
        self.assertIsNone(
            re.search(
                self.controller.NETWORK_UNIX_HOST106_READY_PATTERN,
                b"HI2 MSG: - 000106 000000 000010 000001 000015",
            )
        )

    def test_expected_direct_line_death_is_not_a_fatal_transport_error(self) -> None:
        pdp11 = (
            b"The time is 12:34:56 EDT.\r\n"
            b"Today is Tuesday, the 1st of September, 2026.\r\n"
            b"KA ITS 1652 has run for 1:23:45.\r\n"
        )
        imp6 = (
            b"WDT LIGHTS: changed to 020000\n"
            b"HI2 MSG: message received\nHI2 MSG: message sent\n"
        )
        imp62 = (
            b"WDT LIGHTS: changed to 100000\n"
            b"HI2 MSG: message received\nHI2 MSG: message sent\n"
        )

        failures = self.controller.post_cut_application_failures(
            pdp11,
            imp6,
            b"",
            imp62,
            imp6_alternate_device="mi2",
            imp7_in_device="mi3",
            imp7_out_device="mi2",
            imp62_alternate_device="mi2",
        )

        self.assertEqual(failures, [])

    def test_cut_acknowledgement_is_read_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "cut.state.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "kind": "two-ended-udp-cut-state",
                        "state": "cut",
                        "fault_started_at": "2026-09-01T12:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            value = self.controller.wait_for_cut_state(path, timeout=0.01)
            self.assertEqual(value["state"], "cut")

            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed"):
                self.controller.wait_for_cut_state(path, timeout=0.01)


if __name__ == "__main__":
    unittest.main()
