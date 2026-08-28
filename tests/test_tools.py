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
        self.assertIn("set hi2 convert", command_text)
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
    def test_ncp_build_lock_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            (root / ".brfid-build.lock").mkdir()
            result = run(
                "sh",
                SCRIPTS / "build-ncp.sh",
                root,
                root / "receipt.json",
            )
            self.assertEqual(result.returncode, 75)
            self.assertIn("NCP build lock is busy", result.stderr)

    def test_ordered_log_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            router_log = directory / "router.log"
            dead_ping = directory / "dead-ping.log"
            router_log.write_text(
                "startup DEAD for another host\n"
                "IMP: Send #10: type 0/REGULAR, destination 004, 6 words.\n"
                "IMP: Flags are 0003.\n"
                "IMP: Receive #20: type 7/DEAD, source 004, 2 words.\n"
                "IMP: flags 00, link 000, id 00, subtype 01.\n"
                "NCP: Host 004 is not up.\n",
                encoding="ascii",
            )
            dead_ping.write_text(
                "Host is not up.\nNCP PING host 004\n",
                encoding="ascii",
            )
            router = run(
                sys.executable,
                SCRIPTS / "assert-log-evidence.py",
                "router-dead",
                router_log,
                dead_ping,
            )
            self.assertEqual(router.returncode, 0, router.stderr)

            imp_log = directory / "imp.log"
            mixed_ping = directory / "mixed-ping.log"
            imp_log.write_text(
                "Short leader: flags=0, type=0, host=0, imp=76, id=0, sub=0\r\n"
                "Next will not be the first packet.\r\n"
                "Send 16 words\r\n"
                "Long leader: flags=0, type=0, handling=0, host=0, imp=76, id=0, sub=0, length=0\r\n"
                "Host port 2 padding: 5\r\n"
                "Converted: 8 words\r\n",
                encoding="ascii",
            )
            mixed_ping.write_text(
                "Reply from host 106: seq=3 time=1 ms\n",
                encoding="ascii",
            )
            mixed = run(
                sys.executable,
                SCRIPTS / "assert-log-evidence.py",
                "mixed-conversion",
                imp_log,
                mixed_ping,
            )
            self.assertEqual(mixed.returncode, 0, mixed.stderr)

            imp_log.write_text("Short leader only\n", encoding="ascii")
            missing = run(
                sys.executable,
                SCRIPTS / "assert-log-evidence.py",
                "mixed-conversion",
                imp_log,
                mixed_ping,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing completed short-to-long", missing.stderr)

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
                "--asset-manifest",
                ROOT / "pins" / "arpanet-assets.sha256",
                cwd=repository,
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)

            (repository / "large.dat").write_bytes(b"x" * (1024 * 1024 + 1))
            (repository / "rp03.0").write_bytes(b"small but external\n")
            (repository / "impcode.simh").write_bytes(b"synthetic firmware\n")
            (repository / "BOOT.RIM").write_bytes(b"synthetic loader\n")
            run(
                "git",
                "add",
                "large.dat",
                "rp03.0",
                "impcode.simh",
                "BOOT.RIM",
                cwd=repository,
            )
            failing = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--staged",
                "--asset-manifest",
                ROOT / "pins" / "arpanet-assets.sha256",
                cwd=repository,
            )
            self.assertNotEqual(failing.returncode, 0)
            self.assertIn("large.dat: indexed blob", failing.stderr)
            self.assertIn("rp03.0: vintage machine media", failing.stderr)
            self.assertIn("impcode.simh: vintage machine media", failing.stderr)
            self.assertIn("BOOT.RIM: vintage machine media", failing.stderr)

    def test_source_guard_rejects_renamed_known_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            repository = Path(directory_name)
            self.assertEqual(run("git", "init", "-q", repository).returncode, 0)
            payload = b"synthetic external asset fixture\n"
            digest = hashlib.sha256(payload).hexdigest()
            manifest = repository / "synthetic-assets.sha256"
            manifest.write_text(
                f"{digest}  upstream/fictional.img\n",
                encoding="ascii",
            )
            (repository / "renamed-source.txt").write_bytes(payload)
            run("git", "add", "renamed-source.txt", cwd=repository)
            result = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--staged",
                "--asset-manifest",
                manifest,
                cwd=repository,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "renamed-source.txt: content matches a known external vintage asset",
                result.stderr,
            )

    def test_source_guard_rejects_staged_denylist_shrinkage(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            repository = Path(directory_name)
            self.assertEqual(run("git", "init", "-q", repository).returncode, 0)
            run("git", "config", "user.name", "Harness Test", cwd=repository)
            run("git", "config", "user.email", "test@example.invalid", cwd=repository)
            pins = repository / "pins"
            pins.mkdir()
            first = hashlib.sha256(b"first asset\n").hexdigest()
            second = hashlib.sha256(b"second asset\n").hexdigest()
            manifest = pins / "arpanet-assets.sha256"
            manifest.write_text(
                f"{first}  upstream/first.img\n{second}  upstream/second.img\n",
                encoding="ascii",
            )
            run("git", "add", "pins/arpanet-assets.sha256", cwd=repository)
            self.assertEqual(
                run("git", "commit", "-q", "-m", "baseline", cwd=repository).returncode,
                0,
            )
            manifest.write_text(
                f"{first}  upstream/first.img\n",
                encoding="ascii",
            )
            (repository / "renamed.txt").write_text("second asset\n", encoding="ascii")
            run(
                "git",
                "add",
                "pins/arpanet-assets.sha256",
                "renamed.txt",
                cwd=repository,
            )
            result = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--staged",
                cwd=repository,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("asset digest denylist may not shrink", result.stderr)

    def test_real_asset_manifest_has_nine_unique_sha256_digests(self) -> None:
        manifest = ROOT / "pins" / "arpanet-assets.sha256"
        entries = [
            line.split()[0]
            for line in manifest.read_text(encoding="ascii").splitlines()
            if line and not line.startswith("#")
        ]
        self.assertEqual(len(entries), 9)
        self.assertEqual(len(set(entries)), 9)
        for digest in entries:
            self.assertEqual(len(digest), 64)
            self.assertTrue(all(character in "0123456789abcdef" for character in digest))

    def test_simulator_binary_verifier_checks_embedded_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            executable = Path(directory_name) / "fake-h316"
            executable.write_text(
                "#!/bin/sh\nprintf '%s\\n' 'git commit id: 2ccfed85'\n",
                encoding="ascii",
            )
            executable.chmod(0o755)
            passing = run(
                sys.executable,
                SCRIPTS / "verify-simulator-binaries.py",
                "--h316",
                executable,
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)
            executable.write_text(
                "#!/bin/sh\nprintf '%s\\n' 'git commit id: deadbeef'\n",
                encoding="ascii",
            )
            failing = run(
                sys.executable,
                SCRIPTS / "verify-simulator-binaries.py",
                "--h316",
                executable,
            )
            self.assertNotEqual(failing.returncode, 0)
            self.assertIn("expected embedded commit 2ccfed85", failing.stderr)


if __name__ == "__main__":
    unittest.main()
