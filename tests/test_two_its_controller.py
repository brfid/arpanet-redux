from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "two-its-controller.py"
SPEC = importlib.util.spec_from_file_location("two_its_controller", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


class TwoItsEvidenceTests(unittest.TestCase):
    def test_watchdog_readiness_selects_bits_instead_of_a_whole_word(self) -> None:
        self.assertTrue(
            CONTROLLER.watchdog_devices_ready(
                "017400", modem_device="mi3"
            )
        )
        self.assertFalse(
            CONTROLLER.watchdog_devices_ready(
                "017400", modem_device="mi4"
            )
        )
        self.assertTrue(
            CONTROLLER.watchdog_devices_ready(
                "015400", modem_device="mi3", host_device="hi2"
            )
        )
        self.assertFalse(
            CONTROLLER.watchdog_devices_ready(
                "017400", modem_device="mi3", host_device="hi2"
            )
        )
        with self.assertRaisesRegex(ValueError, "unsupported watchdog modem"):
            CONTROLLER.watchdog_devices_ready("000000", modem_device="mi5")

    def test_watchdog_regression_uses_the_selected_modem_bit(self) -> None:
        other_line_only = b"WDT LIGHTS: changed to 015400\n"
        selected_line = b"WDT LIGHTS: changed to 035400\n"

        self.assertFalse(
            CONTROLLER.watchdog_reports_modem_dead(other_line_only, "mi3")
        )
        self.assertTrue(
            CONTROLLER.watchdog_reports_modem_dead(selected_line, "mi3")
        )

    def test_client_evidence_rejects_partial_and_closed_sessions(self) -> None:
        partial = b"CONNECT MIT Dynamic Modelling PDP-10\r\nWelcome to ITS!\r\n"
        with self.assertRaisesRegex(RuntimeError, "remote-session evidence"):
            CONTROLLER.assert_client_application_evidence(partial)

        complete = (
            partial
            + b"The time is 12:00\r\nToday is Saturday\r\n"
            + b"KA ITS 1652 has run for 2 minutes\r\n"
        )
        CONTROLLER.assert_client_application_evidence(complete)
        with self.assertRaisesRegex(RuntimeError, "close or error"):
            CONTROLLER.assert_client_application_evidence(
                complete + b"\r\nCLOSED by foreign host\r\n"
            )

    def test_imp_evidence_requires_post_probe_hi2_traffic(self) -> None:
        # "Short leader:"/"Long leader:"/"Converted:"/"type=0" are not
        # asserted here: those fprintf lines only ever came from a
        # hand-instrumented h316_hi.c used during Trial 10's diagnosis and
        # never exist in the clean pinned upstream h316-simh build.
        startup = (
            b"WDT LIGHTS: changed to 075400\n"
            b"HI2 MSG: message received\nHI2 MSG: message sent\n"
        )
        application = (
            b"HI2 MSG: message received\nHI2 MSG: message sent\n"
            b"WDT LIGHTS: changed to 075400\n"
        )
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "imp.debug.log"
            path.write_bytes(startup + b"no application traffic\n")
            imp = SimpleNamespace(name="imp6", debug_path=path)
            with self.assertRaisesRegex(RuntimeError, "post-probe evidence"):
                CONTROLLER.assert_imp_application_evidence(imp, len(startup))

            path.write_bytes(startup + application)
            CONTROLLER.assert_imp_application_evidence(imp, len(startup))

    def test_mi_link_messages_ignore_pre_probe_and_correlate_by_content(self) -> None:
        # Real MI1 (modem-interface) traffic captured from a passing run:
        # the exact word content imp6 logs as "sent" reappears verbatim as
        # what imp62 logs as "received", proving the packet actually
        # crossed the simulated inter-IMP line.
        pre_probe = (
            b"MI1 MSG: message sent (length=1)\n"
            b"MI1 MSG: - 000377 \n"
        )
        imp6_post_probe = (
            b"MI1 MSG: message sent (length=5)\n"
            b"MI1 MSG: - 000377 003003 000347 000000 174033 \n"
        )
        imp62_all = (
            b"MI1 MSG: message received (length=5)\n"
            b"MI1 MSG: - 000377 003003 000347 000000 174033 \n"
        )
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            imp6_path = directory / "imp6.debug.log"
            imp62_path = directory / "imp62.debug.log"
            imp6_path.write_bytes(pre_probe + imp6_post_probe)
            imp62_path.write_bytes(imp62_all)

            imp6_pre_probe_view = CONTROLLER.mi_link_messages(imp6_path, 0)
            self.assertIn(b"000377", imp6_pre_probe_view[b"sent"])

            imp6_messages = CONTROLLER.mi_link_messages(imp6_path, len(pre_probe))
            self.assertNotIn(b"000377", imp6_messages[b"sent"])
            imp62_messages = CONTROLLER.mi_link_messages(imp62_path, 0)

            correlated = (
                CONTROLLER.significant(imp6_messages[b"sent"])
                & CONTROLLER.significant(imp62_messages[b"received"])
            )
            self.assertEqual(
                correlated, {b"000377 003003 000347 000000 174033"}
            )

            short_only = {b"000377"}
            self.assertEqual(CONTROLLER.significant(short_only), set())

    def test_host106_attach_config_cannot_boot_early(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            source = directory / "host106.simh"
            destination = directory / "attach.simh"
            source.write_text(
                "# Boot the host-106 ITS image and connect its NCP interface to IMP 6.\n"
                'expect -p "DSKDMP" send "L\\e2\\eNITS\\rIMPUS=\\eG\\r" ; continue\n\n'
                "set nothrottle\n"
                "boot ptr\n",
                encoding="ascii",
            )
            CONTROLLER.create_host106_attach_config(source, destination)
            generated = destination.read_text(encoding="ascii")
            self.assertEqual(generated, "set nothrottle\n")
            self.assertNotIn("boot ptr", generated)


if __name__ == "__main__":
    unittest.main()
