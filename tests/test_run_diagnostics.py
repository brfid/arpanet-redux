from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ncc.run_diagnostics import RunDiagnosticError, diagnose_run, render_diagnostic


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/diagnose-run.py"
START = (
    "format=1\ntopology=pdp11-its-telnet\n"
    "started_utc=2026-09-04T12:00:00Z\n"
    "repository.revision=" + "1" * 40 + "\n"
    "udp.count=6\nprocess.controller.pid=123\n"
)
END = "finished_utc=2026-09-04T12:01:00Z\noutcome={outcome}\nexit_status={code}\n"


class RunDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "a retained run"
        self.root.mkdir()

    def write(self, name: str, data: str | bytes) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        return path

    def manifest(self, outcome: str | None = "passed", code: int = 0, extra: str = "") -> Path:
        ending = END.format(outcome=outcome, code=code) if outcome else ""
        return self.write("runtime/run.env", START + extra + ending)

    def test_recorded_success_has_explicit_authority_and_evidence(self) -> None:
        self.manifest(extra="application.remote_time=structured\ncleanup.outer-runtime=passed\n")
        self.write("outcome.txt", "passed\n")
        self.write("cleanup-evidence.txt", "host.pid=123\nhost.exit_status=0\nsurviving_owned_processes=0\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertIn("no gate revalidation", report["authority"])
        self.assertEqual(report["last_recorded_checkpoint"]["key"], "application.remote_time")
        self.assertIn("runtime/run.env:", report["last_recorded_checkpoint"]["evidence"])
        self.assertEqual(report["cleanup"]["controller"], "recorded-clean")
        self.assertEqual(report["unrecorded_details"], [])
        self.assertIn("Recorded success", render_diagnostic(report))

    def test_controller_success_does_not_mask_later_outer_failure(self) -> None:
        self.manifest("failed", 1)
        self.write("outcome.txt", "passed\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "recorded-failed")
        self.assertEqual(report["recorded_outcomes"]["controller"], "passed")
        self.assertIn("before the outer runtime failed", report["next_steps"][0])

    def test_failed_and_signal_exit_records_keep_cleanup_unknown(self) -> None:
        for code in (1, 124, 130, 143):
            with self.subTest(code=code):
                self.manifest("failed", code)
                report = diagnose_run(self.root)
                self.assertEqual(report["status"], "recorded-failed")
                self.assertEqual(report["cleanup"]["outer_runtime"], "not-recorded")
                self.assertIn("cannot infer the cause", report["next_steps"][0])

    def test_malformed_termination_records_fail_closed(self) -> None:
        valid = "termination.kind=signal\ntermination.signal=TERM\ntermination.exit-status=143\nfailure.reason=Launcher handled TERM\n"
        cases = (
            valid.replace("signal\n", "unknown\n", 1),
            valid.replace("signal=TERM", "signal=KILL"),
            valid.replace("exit-status=143", "exit-status=130"),
            valid.replace("kind=signal", "kind=exit"),
            valid.replace("termination.signal=TERM\n", ""),
            valid.replace("failure.reason=Launcher handled TERM\n", ""),
            valid.replace("Launcher handled TERM", "bad\x1b[2J"),
            valid.replace("Launcher handled TERM", "a" * 1025),
        )
        for extra in cases:
            with self.subTest(extra=extra):
                self.manifest("failed", 143, extra=extra)
                report = diagnose_run(self.root)
                self.assertEqual(report["status"], "inconsistent")
                self.assertNotIn("\x1b", render_diagnostic(report))
        self.manifest("failed", 1, extra=valid)
        self.assertEqual(diagnose_run(self.root)["status"], "inconsistent")
        self.manifest(extra=valid)
        self.assertEqual(diagnose_run(self.root)["status"], "inconsistent")

    def test_incomplete_or_conflicting_runtime_cleanup_cannot_prove_release(self) -> None:
        valid = "cleanup.runtime.exit-status=0\ncleanup.runtime.attempts=1\ncleanup.runtime.failed-resources=none\n"
        cases = (
            valid.replace("exit-status=0", "exit-status=2"),
            valid.replace("attempts=1", "attempts=0"),
            valid.replace("cleanup.runtime.attempts=1\n", ""),
            valid.replace("failed-resources=none", "failed-resources=control-directory"),
            valid.replace("exit-status=0", "exit-status=1"),
            valid + "cleanup.outer-runtime=failed\n",
            valid + "cleanup.completed=0\n",
        )
        for extra in cases:
            with self.subTest(extra=extra):
                self.manifest("failed", 1, extra=extra)
                report = diagnose_run(self.root)
                self.assertEqual(report["status"], "inconsistent")
                self.assertEqual(report["cleanup"]["outer_runtime"], "inconsistent")
        self.manifest("failed", 1, extra=valid + "termination.kind=exit\ntermination.exit-status=0\nfailure.reason=cleanup failed\n")
        self.assertEqual(diagnose_run(self.root)["status"], "inconsistent")

    def test_final_cleanup_can_support_older_scenario_flags(self) -> None:
        cleanup = "cleanup.runtime.exit-status=0\ncleanup.runtime.attempts=1\ncleanup.runtime.failed-resources=none\n"
        self.manifest(extra=cleanup + "cleanup.outer-runtime=passed\ncleanup.completed=1\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")
        self.manifest("failed", 1, extra=cleanup.replace("exit-status=0", "exit-status=1").replace("resources=none", "resources=control-directory") + "cleanup.completed=0\n")
        self.assertEqual(diagnose_run(self.root)["cleanup"]["outer_runtime"], "failed")

    def test_unfinished_run_does_not_claim_running_or_dead(self) -> None:
        self.manifest(None)
        self.write("outcome.txt", "passed\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "unfinished")
        self.assertEqual(report["last_recorded_checkpoint"]["key"], "process.controller.pid")
        self.assertIn("not a current liveness check", report["last_recorded_checkpoint"]["label"])
        self.assertIn("still running or was interrupted", report["next_steps"][0])
        self.assertIn("Runtime exit_status (runtime/run.env)", report["unrecorded_details"])

    def test_partial_manifest_never_promotes_a_completed_prefix(self) -> None:
        path = self.manifest()
        with path.open("ab") as stream:
            stream.write(b"unfinished")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "unfinished")
        self.assertEqual(report["issues"][0]["severity"], "warning")

    def test_invalid_manifest_records_fail_closed(self) -> None:
        cases = (
            START + "format=1\n",
            START + "no separator\n",
            START.replace("format=1", "format=2"),
            START + END.format(outcome="passed", code=1),
            START + END.format(outcome="unknown", code=0),
            START + END.format(outcome="passed", code="-1"),
            START + END.format(outcome="passed", code="256"),
            START + END.format(outcome="passed", code="0").replace("12:01", "11:01"),
            START + END.format(outcome="passed", code="0").replace("12:01:00Z", "12:01:00"),
            (START + END.format(outcome="passed", code="0")).replace("topology=pdp11-its-telnet\n", ""),
        )
        for data in cases:
            with self.subTest(data=data):
                self.write("runtime/run.env", data)
                report = diagnose_run(self.root)
                self.assertIn(report["status"], ("inconsistent", "unavailable"))
                self.assertTrue(any(issue["severity"] == "error" for issue in report["issues"]))
                render_diagnostic(report)

    def test_missing_manifest_and_non_results_are_explicit(self) -> None:
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "unavailable")
        self.assertIn("make doctor", report["next_steps"][0])
        with self.assertRaises(RunDiagnosticError):
            diagnose_run(self.root / "absent")
        with self.assertRaises(RunDiagnosticError):
            diagnose_run(self.write("a-file", ""))

    def test_controller_failure_contradicts_recorded_outer_success(self) -> None:
        self.manifest()
        self.write("outcome.txt", "failed\n")
        self.assertEqual(diagnose_run(self.root)["status"], "inconsistent")

    def test_cleanup_layers_are_independent(self) -> None:
        self.manifest("failed", 1)
        self.write("cleanup-evidence.txt", "surviving_owned_processes=0\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["cleanup"]["controller"], "recorded-clean")
        self.assertEqual(report["cleanup"]["outer_runtime"], "not-recorded")
        self.assertIn("resources is unknown", report["next_steps"][-1])

    def test_surviving_processes_are_recorded_without_pid_control_advice(self) -> None:
        self.manifest("failed", 1)
        self.write("cleanup-evidence.txt", "host.pid=123\nhost.exit_status=None\nsurviving_owned_processes=1\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["cleanup"]["controller"], "recorded-survivors")
        self.assertIn("must not be used as current ownership", report["next_steps"][-1])
        self.manifest()
        self.assertEqual(diagnose_run(self.root)["status"], "inconsistent")

    def test_historical_line_cleanup_flag_is_real_outer_cleanup_evidence(self) -> None:
        self.manifest(extra="result.verdict-exit-status=0\ncleanup.completed=1\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")
        self.assertEqual(report["last_recorded_checkpoint"]["key"], "result.verdict-exit-status")
        self.assertTrue(report["cleanup"]["evidence"][0].startswith("runtime/run.env:"))
        self.manifest("failed", 1, extra="cleanup.completed=0\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["cleanup"]["outer_runtime"], "not-completed")
        self.assertIn("unsuccessful or incomplete", report["next_steps"][-1])

    def test_conflicting_cleanup_formats_and_invalid_flags_fail_closed(self) -> None:
        for extra in (
            "cleanup.outer-runtime=failed\ncleanup.completed=1\n",
            "cleanup.outer-runtime=passed\ncleanup.completed=0\n",
            "cleanup.completed=2\n",
            "cleanup.completed=0\n",
        ):
            with self.subTest(extra=extra):
                self.manifest(extra=extra)
                report = diagnose_run(self.root)
                self.assertEqual(report["status"], "inconsistent")
                render_diagnostic(report)

    def test_contradictory_and_partial_cleanup_records_are_not_clean(self) -> None:
        self.manifest("failed", 1)
        for data in (
            "host.pid=123\nhost.exit_status=None\nsurviving_owned_processes=0\n",
            "host.pid=123\nhost.exit_status=banana\nsurviving_owned_processes=0\n",
            "surviving_owned_processes=-1\n",
        ):
            with self.subTest(data=data):
                self.write("cleanup-evidence.txt", data)
                report = diagnose_run(self.root)
                self.assertEqual(report["status"], "inconsistent")
                self.assertEqual(report["cleanup"]["controller"], "inconsistent")
                render_diagnostic(report)
        self.write("cleanup-evidence.txt", "surviving_owned_processes=0")
        self.assertEqual(diagnose_run(self.root)["cleanup"]["controller"], "not-recorded")
        self.write("cleanup-evidence.txt", "surviving_owned_processes=0\nunfinished")
        self.assertEqual(diagnose_run(self.root)["cleanup"]["controller"], "not-recorded")

    def test_bounded_log_tail_is_uninterpreted_and_terminal_safe(self) -> None:
        self.manifest("failed", 1)
        self.write("controller.stderr.log", b"x" * 20000 + b"\nTimeoutError: no guest prompt\n\x1b[2J\n")
        report = diagnose_run(self.root)
        excerpt = report["diagnostic_output"][0]
        self.assertIn("TimeoutError: no guest prompt", excerpt["excerpt"])
        self.assertIn("not a verdict", excerpt["interpretation"])
        self.assertLess(len(excerpt["excerpt"]), 8192)
        rendered = render_diagnostic(report)
        self.assertNotIn("\x1b", rendered)
        self.assertIn("\\x1b", rendered)
        log_input = next(item for item in report["inputs"] if item["file"] == "controller.stderr.log")
        self.assertGreater(log_input["offset"], 0)

    def test_unsafe_or_oversized_inputs_are_not_read_as_records(self) -> None:
        self.manifest()
        target = Path(self.temporary.name) / "external"
        target.write_text("EXTERNAL-CONTENT-MUST-NOT-BE-READ\n")
        path = self.root / "controller.stderr.log"
        path.symlink_to(target)
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "inconsistent")
        self.assertNotIn("EXTERNAL-CONTENT-MUST-NOT-BE-READ", json.dumps(report))
        path.unlink()
        os.mkfifo(path)
        self.assertEqual(diagnose_run(self.root)["status"], "inconsistent")
        path.unlink()
        self.write("runtime/run.env", b"a" * (256 * 1024 + 1))
        self.assertEqual(diagnose_run(self.root)["status"], "unavailable")

    def test_symlinked_runtime_directory_is_rejected(self) -> None:
        target = Path(self.temporary.name) / "external"
        target.mkdir()
        (target / "run.env").write_text(START + END.format(outcome="passed", code=0))
        (self.root / "runtime").symlink_to(target, target_is_directory=True)
        self.assertEqual(diagnose_run(self.root)["status"], "unavailable")

    def test_manifest_changed_during_inspection_is_not_a_completed_record(self) -> None:
        path = self.manifest()
        original_fstat = os.fstat
        changed = False

        def change_after_open(descriptor: int) -> os.stat_result:
            nonlocal changed
            snapshot = original_fstat(descriptor)
            if not changed:
                changed = True
                with path.open("ab") as stream:
                    stream.write(b"another.field=value\n")
            return snapshot

        with patch("ncc.run_diagnostics.os.fstat", side_effect=change_after_open):
            report = diagnose_run(self.root)
        self.assertEqual(report["status"], "unavailable")
        self.assertTrue(any("changed during inspection" in issue["message"] for issue in report["issues"]))

    def test_manifest_paths_are_never_followed(self) -> None:
        self.manifest(extra="path.terminal-session=/does/not/exist\npath.controller=/not/executed\n")
        report = diagnose_run(self.root)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertEqual(report["issues"], [])

    def test_inspection_is_deterministic_and_does_not_change_results(self) -> None:
        self.manifest("failed", 1)
        self.write("controller.stderr.log", "TimeoutError: no guest prompt\n")
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        before = {path: (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in files}
        first = diagnose_run(self.root)
        self.assertEqual(first, diagnose_run(self.root))
        after = {path: (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in files}
        self.assertEqual(before, after)
        self.assertEqual(files, sorted(path for path in self.root.rglob("*") if path.is_file()))

    def test_cli_and_make_accept_spaces_and_treat_paths_as_data(self) -> None:
        self.manifest("failed", 1)
        result = subprocess.run([sys.executable, str(SCRIPT), "--json", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "recorded-failed")
        moved = self.root.with_name("literal $(touch injected) `touch also-injected` run")
        self.root.rename(moved)
        result = subprocess.run(["make", "--no-print-directory", "diagnose-run", f"RESULT={moved}"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Recorded failure", result.stdout)
        self.assertFalse((ROOT / "injected").exists())
        self.assertFalse((ROOT / "also-injected").exists())

    def test_cli_invalid_records_fail_but_still_deliver_json(self) -> None:
        self.manifest(extra="format=1\n")
        result = subprocess.run([sys.executable, str(SCRIPT), "--json", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "unavailable")
        result = subprocess.run(["make", "--no-print-directory", "diagnose-run"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set RESULT=", result.stderr)


if __name__ == "__main__":
    unittest.main()
