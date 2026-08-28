from __future__ import annotations

import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(*arguments: os.PathLike[str] | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.fspath(argument) for argument in arguments],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class ShellSyntaxTests(unittest.TestCase):
    def test_shell_files_parse_with_posix_sh(self) -> None:
        paths = sorted(ROOT.rglob("*.sh")) + [ROOT / "hooks" / "pre-commit"]
        for path in paths:
            with self.subTest(path=path):
                result = run("sh", "-n", path)
                self.assertEqual(result.returncode, 0, result.stderr)


class NativeTemplateTests(unittest.TestCase):
    def test_configs_use_native_simh_environment_expansion(self) -> None:
        configs = sorted((ROOT / "config").rglob("*.simh"))
        self.assertGreaterEqual(len(configs), 6)
        command_text = "\n".join(path.read_text(encoding="utf-8") for path in configs)
        expected = {
            "%BRFID_IMP6_MI_PORT%",
            "%BRFID_IMP62_MI_PORT%",
            "%BRFID_IMP6_HI_PORT%",
            "%BRFID_HOST_A_IMP_PORT%",
            "%BRFID_IMP62_HI_PORT%",
            "%BRFID_HOST_B_IMP_PORT%",
            "%BRFID_IMP2_MI1_PORT%",
            "%BRFID_IMP3_MI1_PORT%",
            "%BRFID_IMP4_MI1_PORT%",
            "%BRFID_NCP2_IMP_PORT%",
            "%BRFID_NCP3_IMP_PORT%",
        }
        for variable in expected:
            self.assertIn(variable, command_text)
        self.assertGreaterEqual(command_text.count("127.0.0.1"), 10)
        self.assertNotIn("0.0.0.0", command_text)
        self.assertNotIn("13106", command_text)
        self.assertNotIn("22001", command_text)


class PortLeaseTests(unittest.TestCase):
    def test_lease_holds_and_hands_off_distinct_dual_stack_udp_ports(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            ready = directory / "ready"
            locks = directory / "locks"
            arguments = [
                    sys.executable,
                    os.fspath(SCRIPTS / "reserve-udp-ports.py"),
                    "--count",
                    "6",
                    "--ready-file",
                    os.fspath(ready),
                    "--lock-root",
                    os.fspath(locks),
                    "--owner-pid",
                    str(os.getpid()),
                ]
            if os.environ.get("BRFID_TEST_REQUIRE_IPV6") == "1":
                arguments.append("--require-ipv6")
            process = subprocess.Popen(
                arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                for _ in range(100):
                    if ready.exists():
                        break
                    if process.poll() is not None:
                        error = process.stderr.read()
                        if (
                            "Operation not permitted" in error
                            and os.environ.get("BRFID_TEST_REQUIRE_IPV6") != "1"
                        ):
                            self.skipTest("test environment prohibits local UDP binds")
                        self.fail(f"lease exited early: {error}")
                    time.sleep(0.02)
                else:
                    self.fail("lease did not become ready")
                metadata = dict(
                    line.split("=", 1)
                    for line in ready.read_text(encoding="ascii").splitlines()
                )
                ports = [int(metadata[f"port_{index}"]) for index in range(6)]
                self.assertEqual(len(set(ports)), 6)
                families = metadata["families"].split(",")
                self.assertIn("ipv4", families)
                for port in ports:
                    ipv4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    with ipv4:
                        with self.assertRaises(OSError):
                            ipv4.bind(("127.0.0.1", port))
                    if "ipv6" in families:
                        ipv6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                        ipv6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                        with ipv6:
                            with self.assertRaises(OSError):
                                ipv6.bind(("::1", port))

                process.send_signal(signal.SIGUSR1)
                released = Path(metadata["released"])
                for _ in range(100):
                    if released.exists():
                        break
                    time.sleep(0.02)
                else:
                    self.fail("lease did not acknowledge socket handoff")
                self.assertIsNone(process.poll())

                for port in ports:
                    ipv4 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    with ipv4:
                        ipv4.bind(("127.0.0.1", port))
                    if "ipv6" in families:
                        ipv6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                        ipv6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                        with ipv6:
                            ipv6.bind(("::1", port))
            finally:
                process.terminate()
                process.wait(timeout=5)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            self.assertFalse(any(locks.glob("udp-*.lock")))


class UtilityTests(unittest.TestCase):
    def test_sha256_output_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            path = Path(directory_name) / "sample"
            path.write_bytes(b"vintage-network\n")
            result = run("sh", SCRIPTS / "sha256-file.sh", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(result.stdout, f"{expected}  {path}\n")

    def test_source_guard_checks_indexed_blob_and_media_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            repository = Path(directory_name)
            self.assertEqual(run("git", "init", "-q", repository).returncode, 0)
            run("git", "config", "user.name", "Harness Test", cwd=repository)
            run("git", "config", "user.email", "test@example.invalid", cwd=repository)
            (repository / "small.txt").write_text("source\n", encoding="ascii")
            self.assertEqual(run("git", "add", "small.txt", cwd=repository).returncode, 0)
            passing = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--staged",
                cwd=repository,
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)

            (repository / "large.dat").write_bytes(b"x" * (1024 * 1024 + 1))
            (repository / "rp03.0").write_bytes(b"small but external\n")
            run("git", "add", "large.dat", "rp03.0", cwd=repository)
            failing = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--staged",
                cwd=repository,
            )
            self.assertNotEqual(failing.returncode, 0)
            self.assertIn("large.dat: indexed blob", failing.stderr)
            self.assertIn("rp03.0: vintage machine media", failing.stderr)


if __name__ == "__main__":
    unittest.main()
