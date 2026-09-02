from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*arguments: os.PathLike[str] | str, cwd: Path | None = None):
    return subprocess.run(
        [os.fspath(argument) for argument in arguments],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class LabStateTests(unittest.TestCase):
    def test_selection_is_atomic_and_overrides_newer_discovery(self) -> None:
        state = load_script("lab-state.py")
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name)
            older = lab / "results" / "older"
            newer = lab / "results" / "newer"
            for build in (older, newer):
                build.mkdir(parents=True)
                (build / "pdp11-build-receipt.json").write_text(
                    "{}\n", encoding="ascii"
                )
            os.utime(older, ns=(1, 1))
            os.utime(newer, ns=(2, 2))

            self.assertEqual(
                state.discover_artifact(lab / "results", "pdp11-build"), newer
            )
            selected = state.write_selection(lab, "pdp11-build", older)

            self.assertEqual(selected, older.resolve())
            self.assertEqual(state.read_selection(lab, "pdp11-build"), older.resolve())
            self.assertEqual(
                (lab / "state" / "pdp11-build").read_text(encoding="utf-8"),
                f"{older.resolve()}\n",
            )

    def test_selection_refuses_a_directory_without_a_receipt(self) -> None:
        state = load_script("lab-state.py")
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name)
            invalid = lab / "results" / "invalid"
            invalid.mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "marker is missing"):
                state.write_selection(lab, "pdp11-build", invalid)

            self.assertFalse((lab / "state" / "pdp11-build").exists())

    def test_ncc_discovery_selects_only_a_completed_passing_result(self) -> None:
        state = load_script("lab-state.py")
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name)
            valid = lab / "results" / "ncc-pdp11-its-coexistence-valid"
            partial = lab / "results" / "ncc-pdp11-its-coexistence-partial"
            for result in (valid, partial):
                result.mkdir(parents=True)
                (result / "verdict.json").write_text(
                    json.dumps(
                        {
                            "kind": "ncc-pdp11-its-coexistence-verdict",
                            "passed": True,
                        }
                    ),
                    encoding="utf-8",
                )
            (valid / "outcome.txt").write_text("passed\n", encoding="ascii")
            os.utime(valid, ns=(1, 1))
            os.utime(partial, ns=(2, 2))

            discovered = state.discover_artifact(
                lab / "results", "ncc-coexistence"
            )

            self.assertEqual(discovered, valid)
            self.assertEqual(
                state.write_selection(lab, "ncc-coexistence", valid),
                valid.resolve(),
            )

    def test_ncc_selection_rejects_the_other_scenario_kind(self) -> None:
        state = load_script("lab-state.py")
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name)
            result = lab / "results" / "ncc-pdp11-its-coexistence-wrong"
            result.mkdir(parents=True)
            (result / "verdict.json").write_text(
                json.dumps(
                    {
                        "kind": "ncc-pdp11-its-application-failover-verdict",
                        "passed": True,
                    }
                ),
                encoding="utf-8",
            )
            (result / "outcome.txt").write_text("passed\n", encoding="ascii")

            with self.assertRaisesRegex(ValueError, "completed passing result"):
                state.write_selection(lab, "ncc-coexistence", result)


class BaseMediaInstallerTests(unittest.TestCase):
    def test_installer_is_idempotent_and_never_replaces_a_mismatch(self) -> None:
        installer = load_script("install-pdp11-base.py")
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            source = root / "source.rl01"
            destination = root / "lab" / "ncp_root.rl01"
            source.write_bytes(b"expected historical bytes")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()

            self.assertEqual(
                installer.install_one(source, destination, expected), "installed"
            )
            self.assertEqual(
                installer.install_one(source, destination, expected),
                "already installed",
            )
            destination.write_bytes(b"different bytes")
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                installer.install_one(source, destination, expected)

            self.assertEqual(destination.read_bytes(), b"different bytes")

    def test_manifest_pins_both_exact_external_images(self) -> None:
        installer = load_script("install-pdp11-base.py")
        expected = installer.load_expected(ROOT)

        self.assertEqual(set(expected), set(installer.IMAGE_NAMES))
        self.assertTrue(all(len(digest) == 64 for digest in expected.values()))


class LabSetupTests(unittest.TestCase):
    def test_runtime_source_plan_covers_only_the_shared_telnet_ncc_inputs(self) -> None:
        setup = load_script("lab-setup.py")
        sources = setup.load_runtime_sources(ROOT)

        self.assertEqual(
            {source["name"] for source in sources}, set(setup.RUNTIME_SOURCE_NAMES)
        )
        self.assertNotIn("pdp10-its", {source["name"] for source in sources})
        self.assertLess(
            next(
                index
                for index, source in enumerate(sources)
                if source["name"] == "linux-ncp"
            ),
            next(
                index
                for index, source in enumerate(sources)
                if source["name"] == "h316-simh"
            ),
        )

    def test_checkout_uses_an_exact_local_pin_and_refuses_tracked_changes(self) -> None:
        setup = load_script("lab-setup.py")
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            upstream = root / "upstream"
            upstream.mkdir()
            self.assertEqual(run("git", "init", upstream).returncode, 0)
            self.assertEqual(
                run("git", "-C", upstream, "config", "user.name", "Test").returncode,
                0,
            )
            self.assertEqual(
                run(
                    "git",
                    "-C",
                    upstream,
                    "config",
                    "user.email",
                    "test@example.invalid",
                ).returncode,
                0,
            )
            (upstream / "input.txt").write_text("pinned\n", encoding="ascii")
            self.assertEqual(run("git", "-C", upstream, "add", "input.txt").returncode, 0)
            self.assertEqual(
                run("git", "-C", upstream, "commit", "-m", "pin").returncode, 0
            )
            revision = run("git", "-C", upstream, "rev-parse", "HEAD").stdout.strip()
            lab = root / "lab"
            source = {
                "name": "local-test",
                "url": os.fspath(upstream),
                "revision": revision,
                "checkout": "work/local-test",
            }

            checkout = setup.ensure_checkout(lab.resolve(), source)
            self.assertEqual(
                run("git", "-C", checkout, "rev-parse", "HEAD").stdout.strip(),
                revision,
            )
            (checkout / "input.txt").write_text("changed\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "refusing to change dirty"):
                setup.ensure_checkout(lab.resolve(), source)


class OnboardingCommandTests(unittest.TestCase):
    def test_help_and_setup_plan_are_available_without_a_lab(self) -> None:
        help_result = run("make", "help", cwd=ROOT)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("make lab-setup", help_result.stdout)
        self.assertIn("make telnet", help_result.stdout)
        self.assertIn("make ncc", help_result.stdout)

        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name) / "lab"
            plan = run(
                sys.executable,
                SCRIPTS / "lab-setup.py",
                lab,
                "--plan",
                "--no-build",
                "--no-venv",
                cwd=ROOT,
            )
            self.assertEqual(plan.returncode, 0, plan.stderr)
            self.assertIn("no external source, firmware, media", plan.stdout)
            self.assertIn("network-unix-v6", plan.stdout)
            self.assertFalse(lab.exists())

    def test_empty_lab_doctor_gives_ordered_next_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name) / "lab"
            result = run(
                sys.executable,
                SCRIPTS / "lab-doctor.py",
                lab,
                "--python",
                sys.executable,
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(f"make LAB_ROOT={lab.resolve()} lab-setup", result.stdout)
            self.assertIn("install-pdp11-base", result.stdout)
            self.assertIn("build-pdp11-telnet", result.stdout)
            self.assertIn("docs/getting-started.md", result.stdout)

    def test_make_resolves_a_persisted_build_for_telnet(self) -> None:
        state = load_script("lab-state.py")
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name)
            build = lab / "results" / "chosen-build"
            build.mkdir(parents=True)
            (build / "pdp11-build-receipt.json").write_text("{}\n", encoding="ascii")
            state.write_selection(lab, "pdp11-build", build)

            result = run(
                "make",
                "-n",
                f"LAB_ROOT={lab}",
                "RUN_ID=onboarding-test",
                "telnet",
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'PDP11_BUILD_ROOT="{build.resolve()}"', result.stdout)
            self.assertIn(
                f'"{build.resolve()}" "{lab}/results/pdp11-its-terminal-onboarding-test"',
                result.stdout,
            )

    def test_build_target_persists_the_new_receipt_bound_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = Path(directory_name)
            build = lab / "results" / "new-build"
            result = run(
                "make",
                "-n",
                f"LAB_ROOT={lab}",
                f"PDP11_BUILD_ROOT={build}",
                "build-pdp11-telnet",
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                f'lab-state.py select "{lab}" pdp11-build "{build}"', result.stdout
            )


if __name__ == "__main__":
    unittest.main()
