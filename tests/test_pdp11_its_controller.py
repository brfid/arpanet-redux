from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdp11-its-controller.py"
SPEC = importlib.util.spec_from_file_location("pdp11_its_controller", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


VALID_PDP11 = (
    b"Connection open\r\n"
    b"MIT Dynamic Modelling PDP-10\r\n"
    b"KA ITS.1652. DDT.1549.\r\n"
    b"TTY 53\r\nWelcome to ITS!\r\n"
    b"Possible protocol error! command = 376, option = 3.\r\n"
    b"The time is 16:03:35 EDT.\r\n"
    b"Today is Sunday, the 31st of August, 2025.\r\n"
    b"KA ITS 1652 has run for 51 seconds.\r\n"
)
VALID_ITS = b"LOGIN  53TLNT 0 HST176 16:03:11\r\n"
FORWARD = b"000377 003003 000347 000000 174033"
RETURNED = b"000000 037001 005000 177777 134201"
VALID_IMP6 = (
    b"HI2 MSG: message received\nHI2 MSG: message sent\n"
    b"MI1 MSG: message sent (length=5)\nMI1 MSG: - " + FORWARD + b" \n"
    b"MI1 MSG: message received (length=5)\nMI1 MSG: - " + RETURNED + b" \n"
)
VALID_IMP62 = (
    b"HI2 MSG: message received\nHI2 MSG: message sent\n"
    b"MI1 MSG: message received (length=5)\nMI1 MSG: - " + FORWARD + b" \n"
    b"MI1 MSG: message sent (length=5)\nMI1 MSG: - " + RETURNED + b" \n"
)


def failures(
    pdp11: bytes = VALID_PDP11,
    its: bytes = VALID_ITS,
    imp6: bytes = VALID_IMP6,
    imp62: bytes = VALID_IMP62,
) -> list[str]:
    return CONTROLLER.application_evidence_failures(pdp11, its, imp6, imp62)


class Pdp11ItsEvidenceTests(unittest.TestCase):
    def test_host106_observation_config_enables_only_assembly_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            destination = directory / "host106-attach-only.simh"
            trace = directory / "host106.imp-debug.log"

            CONTROLLER.create_host106_observation_config(
                ROOT / "config" / "hosts" / "its106-pair.simh",
                destination,
                trace,
            )

            text = destination.read_text(encoding="ascii")
            self.assertNotIn("boot ptr", text)
            self.assertNotIn('expect -p "DSKDMP"', text)
            self.assertTrue(
                text.endswith(
                    f"set debug {trace.resolve()}\nset imp debug=ASSEMBLY\n"
                )
            )

    def test_complete_evidence_accepts_nonfatal_legacy_diagnostic(self) -> None:
        self.assertEqual(failures(), [])

    def test_topology_selected_imp6_mi3_correlates_with_imp62_mi1(self) -> None:
        imp6_mi3 = VALID_IMP6.replace(b"MI1", b"MI3")

        result = CONTROLLER.application_evidence_failures(
            VALID_PDP11,
            VALID_ITS,
            imp6_mi3,
            VALID_IMP62,
            imp6_mi_device="mi3",
            imp62_mi_device="mi1",
        )

        self.assertEqual(result, [])
        self.assertTrue(
            any(
                "missing correlated" in failure
                for failure in CONTROLLER.application_evidence_failures(
                    VALID_PDP11,
                    VALID_ITS,
                    imp6_mi3,
                    VALID_IMP62,
                )
            )
        )

    def test_post_probe_watchdog_regression_uses_the_selected_modem(self) -> None:
        imp6_mi3 = VALID_IMP6.replace(b"MI1", b"MI3")
        imp6_other_line_dead = (
            imp6_mi3 + b"WDT LIGHTS: changed to 015400\n"
        )
        imp6_selected_line_dead = (
            imp6_mi3 + b"WDT LIGHTS: changed to 035400\n"
        )

        self.assertEqual(
            CONTROLLER.application_evidence_failures(
                VALID_PDP11,
                VALID_ITS,
                imp6_other_line_dead,
                VALID_IMP62,
                imp6_mi_device="mi3",
                imp62_mi_device="mi1",
            ),
            [],
        )
        self.assertTrue(
            any(
                "post-probe modem-line-dead" in failure
                for failure in CONTROLLER.application_evidence_failures(
                    VALID_PDP11,
                    VALID_ITS,
                    imp6_selected_line_dead,
                    VALID_IMP62,
                    imp6_mi_device="mi3",
                    imp62_mi_device="mi1",
                )
            )
        )

    def test_missing_connection_open_is_rejected(self) -> None:
        result = failures(pdp11=VALID_PDP11.replace(b"Connection open\r\n", b""))
        self.assertIn("missing ordered Connection open evidence", result)

    def test_host_unavailable_is_rejected(self) -> None:
        result = failures(pdp11=b"Host is Unavailable\r\n" + VALID_PDP11)
        self.assertTrue(any("premature close" in failure for failure in result))

    def test_banner_without_remote_command_response_is_rejected(self) -> None:
        banner = VALID_PDP11.split(b"The time is", 1)[0]
        result = failures(pdp11=banner)
        self.assertTrue(any("remote time" in failure for failure in result))

    def test_partial_time_response_is_rejected(self) -> None:
        partial = VALID_PDP11.split(b"KA ITS 1652 has run", 1)[0]
        result = failures(pdp11=partial)
        self.assertTrue(any("remote uptime" in failure for failure in result))

    def test_close_after_partial_output_is_rejected(self) -> None:
        partial = VALID_PDP11.split(b"The time is", 1)[0] + b"Connection closed\r\n"
        result = failures(pdp11=partial)
        self.assertTrue(any("premature close" in failure for failure in result))

    def test_pre_probe_evidence_cannot_satisfy_post_probe_gate(self) -> None:
        pre_probe = (VALID_PDP11, VALID_ITS, VALID_IMP6, VALID_IMP62)
        self.assertEqual(failures(*pre_probe), [])
        post_probe = failures(b"probe began\n", b"", b"", b"")
        self.assertTrue(any("Connection open" in failure for failure in post_probe))
        self.assertTrue(any("post-probe" in failure for failure in post_probe))

    def test_missing_traffic_on_either_imp_is_rejected(self) -> None:
        without_imp6 = failures(imp6=b"")
        self.assertTrue(any("imp6 lacks post-probe" in failure for failure in without_imp6))
        without_imp62 = failures(imp62=b"")
        self.assertTrue(any("imp62 lacks post-probe" in failure for failure in without_imp62))

    def test_child_exit_during_startup_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            executable = directory / "exit-now"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
            executable.chmod(0o755)
            config = directory / "empty.simh"
            config.write_text("", encoding="ascii")
            manifest = directory / "run.env"
            manifest.write_text("", encoding="ascii")
            process = CONTROLLER.PtyProcess(
                "early",
                executable,
                config,
                directory,
                directory / "console.log",
                directory / "sent.log",
                manifest,
            )
            process.launch()
            with self.assertRaisesRegex(RuntimeError, "exited while waiting"):
                process.expect("never", timeout=1)
            process.stop(force=True)

    def test_readiness_timeout_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "imp.debug.log"
            path.write_bytes(b"")
            imp = SimpleNamespace(
                name="imp-test",
                debug_path=path,
                ensure_alive=lambda: None,
            )
            with self.assertRaisesRegex(TimeoutError, "did not report"):
                CONTROLLER.SHARED.wait_for_log_marker(
                    imp, "never-ready", timeout=0.01
                )

    def test_cleanup_records_ordinary_and_interrupted_paths(self) -> None:
        class FakeProcess:
            pid = 12345

            def __init__(self) -> None:
                self.status = None

            def poll(self) -> int | None:
                return self.status

        class FakeHost:
            def __init__(self, name: str) -> None:
                self.name = name
                self.process = FakeProcess()
                self.forced: bool | None = None

            def stop(self, force: bool = False) -> None:
                self.forced = force
                self.process.status = -15 if force else 0

        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            ordinary = FakeHost("ordinary")
            CONTROLLER.stop_and_record(directory, (ordinary,), (), force=False)
            self.assertFalse(ordinary.forced)
            self.assertIn(
                "surviving_owned_processes=0",
                (directory / "cleanup-evidence.txt").read_text(encoding="ascii"),
            )
            interrupted = FakeHost("interrupted")
            CONTROLLER.stop_and_record(directory, (interrupted,), (), force=True)
            self.assertTrue(interrupted.forced)
            self.assertIn(
                "interrupted.exit_status=-15",
                (directory / "cleanup-evidence.txt").read_text(encoding="ascii"),
            )


if __name__ == "__main__":
    unittest.main()
