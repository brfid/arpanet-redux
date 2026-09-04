from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdp11-build-receipt.py"
SPEC = importlib.util.spec_from_file_location("pdp11_build_receipt", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RECEIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECEIPT)


class Pdp11BuildReceiptTests(unittest.TestCase):
    def test_receipt_binds_the_shared_clean_shutdown_helper(self) -> None:
        self.assertIn("research/simh_shutdown.py", RECEIPT.BUILDER_NAMES)

    def test_build_log_requires_the_repaired_companion_size(self) -> None:
        telnet_log = (
            "git commit id: 2722eef4\n"
            "cc -O -n -x telnet.c\n"
            "cc -O -n -x usrtelnetin.c\n"
            "1 root     7212 telnet\n"
            "1 root     2390 usrtelnetin\n"
            "/usr/bin/telnet\n"
            "/usr/bin/usrtelnetin\n"
            "Goodbye\n"
        )
        ncpd_log = (
            "git commit id: 2722eef4\n"
            "cc -O -c 1main.c kr_dcode.c\n"
            "cc -O -x 1main.o kr_dcode.o\n"
            "/usr/net/etc/Largedaemon not found\n"
            "-r-xr--r--  1 daemon  21422\n"
            "Goodbye\n"
        )
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            telnet = directory / "telnet.log"
            ncpd = directory / "ncpd.log"
            telnet.write_text(telnet_log, encoding="ascii")
            ncpd.write_text(ncpd_log, encoding="ascii")
            with mock.patch.object(
                RECEIPT,
                "pinned_revisions",
                return_value={"imp11a-simh": "2722eef4" + "0" * 32},
            ):
                RECEIPT.validate_build_logs(telnet, ncpd)
                telnet.write_text(
                    telnet_log.replace("2390", "2454"), encoding="ascii"
                )
                with self.assertRaisesRegex(ValueError, "2390"):
                    RECEIPT.validate_build_logs(telnet, ncpd)

    def test_simulator_version_detaches_interactive_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            executable = Path(directory_name) / "pdp11"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
            executable.chmod(0o755)
            completed = subprocess.CompletedProcess(
                [executable, "-v"],
                0,
                stdout="git commit id: 2722eef4\n",
            )
            with (
                mock.patch.object(
                    RECEIPT.subprocess, "run", return_value=completed
                ) as invoked,
                mock.patch.object(
                    RECEIPT,
                    "pinned_revisions",
                    return_value={"imp11a-simh": "2722eef4" + "0" * 32},
                ),
            ):
                version = RECEIPT.simulator_version(executable)

            self.assertEqual(version, "git commit id: 2722eef4")
            self.assertEqual(invoked.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_guest_image_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            image = Path(directory_name) / "ncp_root.rl01"
            image.write_bytes(b"receipt-bound guest image\n")
            record = RECEIPT.file_record(image)
            self.assertEqual(
                RECEIPT.verify_file_record("guest root", record), image.resolve()
            )
            image.write_bytes(b"substituted guest image\n")
            with self.assertRaisesRegex(ValueError, "hash is"):
                RECEIPT.verify_file_record("guest root", record)

    def test_staged_source_tree_identity_is_path_relative_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            stage = Path(directory_name)
            (stage / "telnet.c").write_text("main() {}\n", encoding="ascii")
            (stage / "headers").mkdir()
            (stage / "headers" / "telnet.h").write_text(
                "#define TEL_IAC 255\n", encoding="ascii"
            )
            identity = RECEIPT.tree_hashes(stage)
            self.assertEqual(set(identity), {"telnet.c", "headers/telnet.h"})
            (stage / "telnet.c").write_text("main() { return 1; }\n", encoding="ascii")
            self.assertNotEqual(RECEIPT.tree_hashes(stage), identity)


if __name__ == "__main__":
    unittest.main()
