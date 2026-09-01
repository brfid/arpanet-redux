from __future__ import annotations

import hashlib
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

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


class NccConvenienceTargetTests(unittest.TestCase):
    def test_view_watch_and_run_targets_delegate_to_supported_commands(self) -> None:
        view = run(
            "make",
            "-n",
            "NCC_RESULT=/tmp/ncc-result",
            "NCC_VIEW_PORT=9877",
            "view-ncc",
            cwd=ROOT,
        )
        self.assertEqual(view.returncode, 0, view.stderr)
        self.assertIn("scripts/ncc-serve-board.py", view.stdout)
        self.assertIn("/tmp/ncc-result", view.stdout)
        self.assertIn("--port \"9877\"", view.stdout)

        watch = run(
            "make",
            "-n",
            "NCC_RESULT=/tmp/ncc-result",
            "NCC_WATCH_PORT=9875",
            "watch-ncc",
            cwd=ROOT,
        )
        self.assertEqual(watch.returncode, 0, watch.stderr)
        self.assertIn("scripts/ncc-serve-board.py", watch.stdout)
        self.assertIn("/tmp/ncc-result", watch.stdout)
        self.assertIn("--port \"9875\"", watch.stdout)

        run_target = run(
            "make",
            "-n",
            "RUN_ID=watch-demo",
            "PDP11_BUILD_ROOT=/tmp/pdp11-build",
            "run-ncc",
            cwd=ROOT,
        )
        self.assertEqual(run_target.returncode, 0, run_target.stderr)
        self.assertIn("scripts/smoke-ncc-pdp11-its.sh", run_target.stdout)
        self.assertIn("ncc-pdp11-its-coexistence-watch-demo", run_target.stdout)

        operated = run(
            "make",
            "-n",
            "RUN_ID=operated-demo",
            "PDP11_BUILD_ROOT=/tmp/pdp11-build",
            "NCC_WATCH_PORT=9875",
            "ncc",
            cwd=ROOT,
        )
        self.assertEqual(operated.returncode, 0, operated.stderr)
        self.assertIn("scripts/ncc-operate-pdp11-its.py", operated.stdout)
        self.assertIn('--run-id "operated-demo"', operated.stdout)
        self.assertIn('--port "9875"', operated.stdout)

        failover_view = run(
            "make",
            "-n",
            "NCC_FAILOVER_RESULT=/tmp/ncc-failover-result",
            "NCC_VIEW_PORT=9877",
            "view-ncc-failover",
            cwd=ROOT,
        )
        self.assertEqual(failover_view.returncode, 0, failover_view.stderr)
        self.assertIn("scripts/ncc-serve-board.py", failover_view.stdout)
        self.assertIn("/tmp/ncc-failover-result", failover_view.stdout)
        self.assertIn("ncc-pdp11-its-application-failover.json", failover_view.stdout)

        operated_failover = run(
            "make",
            "-n",
            "RUN_ID=failover-demo",
            "PDP11_BUILD_ROOT=/tmp/pdp11-build",
            "NCC_WATCH_PORT=9875",
            "ncc-failover",
            cwd=ROOT,
        )
        self.assertEqual(operated_failover.returncode, 0, operated_failover.stderr)
        self.assertIn("scripts/ncc-operate-pdp11-its.py", operated_failover.stdout)
        self.assertIn("--scenario failover", operated_failover.stdout)
        self.assertIn("ncc-pdp11-its-application-failover.json", operated_failover.stdout)

    def test_telnet_target_builds_then_delegates_to_terminal_owned_session(self) -> None:
        operated = run(
            "make",
            "-n",
            "RUN_ID=interactive-demo",
            "PDP11_BUILD_ROOT=/tmp/pdp11-build",
            "TELNET_COMMAND_TIMEOUT=45",
            "TELNET_MAX_COMMANDS=12",
            "telnet",
            cwd=ROOT,
        )
        self.assertEqual(operated.returncode, 0, operated.stderr)
        self.assertIn("scripts/build-pdp11-telnet.sh", operated.stdout)
        self.assertIn("scripts/telnet-pdp11-its.sh", operated.stdout)
        self.assertIn('BRFID_TELNET_COMMAND_TIMEOUT="45"', operated.stdout)
        self.assertIn('BRFID_TELNET_MAX_COMMANDS="12"', operated.stdout)
        self.assertIn("pdp11-its-interactive-interactive-demo", operated.stdout)


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

    def test_its_build_lock_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            (root / ".brfid-build.lock").mkdir()
            result = run(
                "sh",
                SCRIPTS / "build-its.sh",
                root,
                root / "receipt.json",
            )
            self.assertEqual(result.returncode, 75)
            self.assertIn("ITS build lock is busy", result.stderr)

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
            (repository / "snapshot.tape").write_bytes(b"synthetic tape\n")
            (repository / "upstream.tar.gz").write_bytes(b"synthetic archive\n")
            (repository / "microcode.rom").write_bytes(b"synthetic rom\n")
            (repository / "bootstrap.bin").write_bytes(b"synthetic firmware\n")
            (repository / "external.txt").write_bytes(
                b"version https://git-lfs.github.com/spec/v1\n"
                b"oid sha256:"
                + b"0" * 64
                + b"\nsize 1234567\n"
            )
            run(
                "git",
                "add",
                "large.dat",
                "rp03.0",
                "impcode.simh",
                "BOOT.RIM",
                "snapshot.tape",
                "upstream.tar.gz",
                "microcode.rom",
                "bootstrap.bin",
                "external.txt",
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
            self.assertIn("snapshot.tape: vintage machine media", failing.stderr)
            self.assertIn("upstream.tar.gz: vintage machine media", failing.stderr)
            self.assertIn("microcode.rom: vintage machine media", failing.stderr)
            self.assertIn("bootstrap.bin: vintage machine media", failing.stderr)
            self.assertIn("external.txt: Git LFS pointers are not permitted", failing.stderr)

    def test_source_guard_checks_every_blob_reachable_from_history_tip(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            repository = Path(directory_name)
            self.assertEqual(run("git", "init", "-q", repository).returncode, 0)
            run("git", "config", "user.name", "Harness Test", cwd=repository)
            run("git", "config", "user.email", "test@example.invalid", cwd=repository)
            manifest = repository / "synthetic-assets.sha256"
            manifest.write_text(
                f"{hashlib.sha256(b'known external asset').hexdigest()}  known.img\n",
                encoding="ascii",
            )
            (repository / "source.txt").write_text("source\n", encoding="ascii")
            run("git", "add", "source.txt", cwd=repository)
            self.assertEqual(
                run("git", "commit", "-q", "-m", "source", cwd=repository).returncode,
                0,
            )

            (repository / "retired.dat").write_bytes(b"x" * 257)
            (repository / "retired.tape").write_bytes(b"synthetic tape\n")
            (repository / "concealed.txt").write_bytes(b"known external asset")
            (repository / "renamed-pointer.txt").write_bytes(
                b"version https://git-lfs.github.com/spec/v1\n"
                b"oid sha256:"
                + b"a" * 64
                + b"\nsize 9000000\n"
            )
            run(
                "git",
                "add",
                "retired.dat",
                "retired.tape",
                "concealed.txt",
                "renamed-pointer.txt",
                cwd=repository,
            )
            self.assertEqual(
                run("git", "commit", "-q", "-m", "unsafe", cwd=repository).returncode,
                0,
            )
            (repository / "retired.dat").unlink()
            (repository / "retired.tape").unlink()
            (repository / "concealed.txt").unlink()
            (repository / "renamed-pointer.txt").unlink()
            run("git", "add", "-u", cwd=repository)
            self.assertEqual(
                run("git", "commit", "-q", "-m", "remove", cwd=repository).returncode,
                0,
            )

            current = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--limit-bytes",
                "256",
                "--asset-manifest",
                manifest,
                cwd=repository,
            )
            self.assertEqual(current.returncode, 0, current.stderr)
            history = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--history",
                "HEAD",
                "--limit-bytes",
                "256",
                "--asset-manifest",
                manifest,
                cwd=repository,
            )
            self.assertNotEqual(history.returncode, 0)
            self.assertIn("retired.dat: historical blob is 257 bytes", history.stderr)
            self.assertIn("retired.tape: vintage machine media", history.stderr)
            self.assertIn(
                "concealed.txt: content matches a known external vintage asset",
                history.stderr,
            )
            self.assertIn(
                "renamed-pointer.txt: Git LFS pointers are not permitted",
                history.stderr,
            )
            self.assertIn("[historical blob ", history.stderr)

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

    def test_source_guard_rejects_committed_denylist_shrinkage_in_history(self) -> None:
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
            run("git", "add", "pins/arpanet-assets.sha256", cwd=repository)
            self.assertEqual(
                run("git", "commit", "-q", "-m", "shrink", cwd=repository).returncode,
                0,
            )
            result = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--history",
                "HEAD",
                cwd=repository,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "asset digest denylist may not shrink across scanned history",
                result.stderr,
            )
            self.assertIn(second, result.stderr)

    def test_source_guard_history_fails_closed_in_shallow_clone(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            origin = directory / "origin"
            shallow = directory / "shallow"
            self.assertEqual(run("git", "init", "-q", origin).returncode, 0)
            run("git", "config", "user.name", "Harness Test", cwd=origin)
            run("git", "config", "user.email", "test@example.invalid", cwd=origin)
            pins = origin / "pins"
            pins.mkdir()
            digest = hashlib.sha256(b"external asset\n").hexdigest()
            (pins / "arpanet-assets.sha256").write_text(
                f"{digest}  upstream/external.img\n",
                encoding="ascii",
            )
            run("git", "add", "pins/arpanet-assets.sha256", cwd=origin)
            self.assertEqual(
                run("git", "commit", "-q", "-m", "first", cwd=origin).returncode,
                0,
            )
            (origin / "source.txt").write_text("source\n", encoding="ascii")
            run("git", "add", "source.txt", cwd=origin)
            self.assertEqual(
                run("git", "commit", "-q", "-m", "second", cwd=origin).returncode,
                0,
            )
            clone = run(
                "git",
                "clone",
                "-q",
                "--depth",
                "1",
                f"file://{origin}",
                shallow,
            )
            self.assertEqual(clone.returncode, 0, clone.stderr)
            result = run(
                sys.executable,
                SCRIPTS / "check-source-only.py",
                "--history",
                "HEAD",
                cwd=shallow,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "history scan requires a complete, non-shallow clone",
                result.stderr,
            )

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
                "#!/bin/sh\nprintf '%s\\n' 'git commit id: feb155fb'\n",
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
            self.assertIn("expected embedded commit feb155fb", failing.stderr)

    def test_simulator_binary_verifier_checks_pdp11_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            executable = Path(directory_name) / "fake-pdp11"
            executable.write_text(
                "#!/bin/sh\nprintf '%s\\n' 'git commit id: 2722eef4'\n",
                encoding="ascii",
            )
            executable.chmod(0o755)
            passing = run(
                sys.executable,
                SCRIPTS / "verify-simulator-binaries.py",
                "--pdp11",
                executable,
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)
            executable.write_text(
                "#!/bin/sh\nprintf '%s\\n' 'git commit id: f1ca562e'\n",
                encoding="ascii",
            )
            failing = run(
                sys.executable,
                SCRIPTS / "verify-simulator-binaries.py",
                "--pdp11",
                executable,
            )
            self.assertNotEqual(failing.returncode, 0)
            self.assertIn("expected embedded commit 2722eef4", failing.stderr)


if __name__ == "__main__":
    unittest.main()
