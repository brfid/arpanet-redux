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

    def test_imp_evidence_requires_post_probe_bidirectional_conversion(self) -> None:
        startup = (
            b"WDT LIGHTS: changed to 075400\n"
            b"HI2 MSG: message received\nHI2 MSG: message sent\n"
            b"Short leader: type=0\nLong leader: type=0\nConverted:\n"
        )
        application = (
            b"HI2 MSG: message received\nHI2 MSG: message sent\n"
            b"Short leader: type=0\nLong leader: type=0\nConverted:\n"
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

    def test_regular_message_ids_ignore_pre_probe_traffic(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "imp.debug.log"
            startup = b"Short leader: flags=0, type=0, host=1, imp=6, id=40\n"
            application = b"Long leader: flags=0, type=0, handling=0, host=1, imp=76, id=100, sub=0\n"
            path.write_bytes(startup + application)
            self.assertEqual(
                CONTROLLER.regular_message_ids(path, len(startup)), {b"100"}
            )

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
