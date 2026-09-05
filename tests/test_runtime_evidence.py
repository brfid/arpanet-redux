from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ncc.run_diagnostics import diagnose_run, render_diagnostic


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/lib/runtime.sh"
PREAMBLE = '''set -eu
. "$1"
brfid_runtime_init
brfid_install_cleanup_traps
result=$3
brfid_manifest_init "$result/runtime/run.env" runtime-evidence-test "$2"
'''


class RuntimeEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="brfid evidence ")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.number = 0

    def run_script(self, body: str, *, existing: bytes | None = None, input: str = "") -> tuple[subprocess.CompletedProcess[str], Path]:
        self.number += 1
        result = self.base / str(self.number)
        (result / "runtime").mkdir(parents=True)
        if existing is not None:
            (result / "runtime/run.env").write_bytes(existing)
        script = result / "launcher.sh"
        script.write_text(PREAMBLE + body)
        completed = subprocess.run(
            ["/bin/sh", str(script), str(RUNTIME), str(ROOT), str(result), sys.executable],
            input=input, text=True, capture_output=True, timeout=20,
        )
        return completed, result

    def report(self, result: Path) -> dict:
        report = diagnose_run(result)
        self.assertEqual(report["issues"], [])
        render_diagnostic(report)
        records = (result / "runtime/run.env").read_text().splitlines()
        keys = [line.partition("=")[0] for line in records]
        self.assertEqual(len(keys), len(set(keys)), "duplicate manifest records")
        return report

    def test_normal_cleanup_stops_owned_child_and_releases_resources_once(self) -> None:
        completed, result = self.run_script('''
brfid_make_private_socket_dir
printf '%s' "$BRFID_SOCKET_DIR" >"$result/socket-dir"
brfid_acquire_exclusive_lease "$result/build.lock"
brfid_start_process sleeper "$result" "$result/child.out" "$result/child.err" "$4" -c 'import time; time.sleep(30)'
printf '%s' "$BRFID_LAST_PID" >"$result/child.pid"
brfid_cleanup
brfid_manifest_append cleanup.outer-runtime passed
brfid_mark_run_passed
''')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(result)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertEqual(report["termination"]["kind"], "exit")
        self.assertIsNone(report["termination"]["reason"])
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")
        self.assertEqual(report["cleanup"]["runtime_attempts"], 1)
        self.assertFalse((result / "build.lock").exists())
        self.assertFalse(Path((result / "socket-dir").read_text()).exists())
        with self.assertRaises(ProcessLookupError):
            os.kill(int((result / "child.pid").read_text()), 0)

    def test_failed_external_check_retains_reason_and_original_exit_status(self) -> None:
        completed, result = self.run_script('''
printf 'failed\n' >"$result/outcome.txt"
brfid_require "Required controller outcome missing" grep -Fxq passed "$result/outcome.txt"
touch "$result/should-not-execute"
''')
        self.assertEqual(completed.returncode, 1)
        report = self.report(result)
        self.assertEqual(report["status"], "recorded-failed")
        self.assertEqual(report["termination"]["exit_status"], 1)
        self.assertIn("Required controller outcome missing", report["termination"]["reason"])
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")
        self.assertFalse((result / "should-not-execute").exists())
        self.assertIn("Required controller outcome missing", (result / "runtime/launcher.stderr.log").read_text())

    def test_checks_preserve_standard_input_and_output(self) -> None:
        completed, result = self.run_script('brfid_require "input copy" cat\nbrfid_mark_run_passed\n', input="terminal input\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "terminal input\n")
        self.assertEqual(self.report(result)["status"], "recorded-passed")

    def test_helper_error_retained_without_inventing_a_terminal_cause(self) -> None:
        completed, result = self.run_script('brfid_manifest_add_file missing "$result/absent" "$2/scripts/sha256-file.sh"\n')
        self.assertEqual(completed.returncode, 1)
        report = self.report(result)
        self.assertIn("no more specific reason", report["termination"]["reason"])
        self.assertIn("could not hash", report["diagnostic_output"][0]["excerpt"])
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")

    def test_handled_helper_error_does_not_become_a_failure(self) -> None:
        completed, result = self.run_script('''
if brfid_assign_two_host_ports; then exit 99; fi
brfid_mark_run_passed
''')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(result)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertIsNone(report["termination"]["reason"])
        self.assertIn("exactly six", report["diagnostic_output"][0]["excerpt"])

    def test_handled_signals_are_recorded_explicitly_and_clean_up(self) -> None:
        for name, code in (("HUP", 129), ("INT", 130), ("TERM", 143)):
            with self.subTest(signal=name):
                completed, result = self.run_script(f'''
brfid_acquire_exclusive_lease "$result/build.lock"
kill -{name} "$$"
''')
                self.assertEqual(completed.returncode, code, completed.stderr)
                report = self.report(result)
                self.assertEqual(report["termination"]["kind"], "signal")
                self.assertEqual(report["termination"]["signal"], name)
                self.assertEqual(report["termination"]["reason"], f"Launcher handled {name}")
                self.assertEqual(report["cleanup"]["outer_runtime"], "passed")
                self.assertFalse((result / "build.lock").exists())

    def test_interruption_allows_controller_cleanup_to_outlast_a_leaf_deadline(self) -> None:
        completed, result = self.run_script('''
brfid_start_process controller "$result" "$result/controller.out" "$result/controller.err" "$4" -c '
import signal, sys, time
from pathlib import Path
def stop(*_):
    time.sleep(6)
    Path(sys.argv[1]).write_text("delegated cleanup complete\\n")
    raise SystemExit(1)
signal.signal(signal.SIGTERM, stop)
print("ready", flush=True)
while True: time.sleep(0.1)
' "$result/controller-finished"
while [ ! -s "$result/controller.out" ]; do sleep 1; done
kill -TERM "$$"
''')
        self.assertEqual(completed.returncode, 143, completed.stderr)
        self.assertTrue((result / "controller-finished").exists(), "controller was killed before finishing delegated cleanup")
        report = self.report(result)
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")

    def test_forced_controller_exit_cannot_prove_delegated_cleanup(self) -> None:
        completed, result = self.run_script('''
brfid_stop_pid_bounded() { BRFID_STOP_FORCED=1; return 0; }
BRFID_MANAGED_PIDS=123
BRFID_CONTROLLER_PID=123
if brfid_cleanup; then exit 99; fi
brfid_stop_pid_bounded() { BRFID_STOP_FORCED=0; return 0; }
brfid_mark_run_passed
''')
        self.assertEqual(completed.returncode, 1)
        report = self.report(result)
        self.assertEqual(report["cleanup"]["outer_runtime"], "failed")
        self.assertEqual(report["cleanup"]["runtime_failed_resources"], ["controller-cleanup:123"])
        self.assertEqual(report["cleanup"]["runtime_attempts"], 2)

    def test_numeric_signal_exit_does_not_claim_a_handled_signal(self) -> None:
        completed, result = self.run_script("exit 130\n")
        self.assertEqual(completed.returncode, 130)
        report = self.report(result)
        self.assertEqual(report["termination"]["kind"], "exit")
        self.assertIsNone(report["termination"]["signal"])

    def test_uncatchable_kill_leaves_cleanup_and_termination_unknown(self) -> None:
        completed, result = self.run_script('kill -KILL "$$"\n')
        self.assertEqual(completed.returncode, -9)
        report = self.report(result)
        self.assertEqual(report["status"], "unfinished")
        self.assertEqual(report["termination"]["kind"], "not-recorded")
        self.assertEqual(report["cleanup"]["outer_runtime"], "not-recorded")

    def test_cleanup_failure_rejects_success_and_preserves_primary_failures(self) -> None:
        for primary_status in (0, 7):
            with self.subTest(primary_status=primary_status):
                ending = 'brfid_mark_run_passed\n' if primary_status == 0 else 'brfid_fail 7 "primary controller failure"\n'
                completed, result = self.run_script('''
BRFID_SOCKET_DIR="$result/control"
mkdir "$BRFID_SOCKET_DIR"
touch "$BRFID_SOCKET_DIR/unowned-file"
''' + ending)
                self.assertEqual(completed.returncode, primary_status or 1)
                report = self.report(result)
                self.assertEqual(report["status"], "recorded-failed")
                self.assertEqual(report["termination"]["exit_status"], primary_status)
                self.assertEqual(report["cleanup"]["outer_runtime"], "failed")
                self.assertEqual(report["cleanup"]["runtime_failed_resources"], ["control-directory"])
                if primary_status:
                    self.assertEqual(report["termination"]["reason"], "primary controller failure")
                self.assertTrue((result / "control/unowned-file").exists())

    def test_cleanup_records_failed_child_and_continues_releasing_other_resources(self) -> None:
        completed, result = self.run_script('''
brfid_acquire_exclusive_lease "$result/build.lock"
brfid_stop_pid_bounded() { return 1; }
BRFID_MANAGED_PIDS=123
BRFID_PORT_LEASE_PID=456
brfid_mark_run_passed
''')
        self.assertEqual(completed.returncode, 1)
        report = self.report(result)
        self.assertEqual(report["cleanup"]["runtime_failed_resources"], ["child:123", "port-lease:456"])
        self.assertFalse((result / "build.lock").exists())

    def test_successful_cleanup_retry_keeps_prior_error_as_log_only(self) -> None:
        completed, result = self.run_script('''
BRFID_SOCKET_DIR="$result/control"
mkdir "$BRFID_SOCKET_DIR"
touch "$BRFID_SOCKET_DIR/blocker"
if brfid_cleanup; then exit 99; fi
rm "$BRFID_SOCKET_DIR/blocker"
brfid_mark_run_passed
''')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(result)
        self.assertEqual(report["status"], "recorded-passed")
        self.assertEqual(report["cleanup"]["runtime_attempts"], 2)
        self.assertEqual(report["cleanup"]["outer_runtime"], "passed")
        self.assertIsNone(report["termination"]["reason"])

    def test_cleanup_retry_does_not_reuse_released_process_or_lease_ownership(self) -> None:
        completed, result = self.run_script('''
brfid_acquire_exclusive_lease "$result/build.lock"
brfid_make_private_socket_dir
control=$BRFID_SOCKET_DIR
brfid_stop_pid_bounded() {
  BRFID_STOP_FORCED=0
  printf '%s\\n' "$1" >>"$result/stopped"
}
BRFID_MANAGED_PIDS=123
BRFID_PORT_LEASE_PID=456
BRFID_CONTROLLER_CLEANUP_LOST=123
if brfid_cleanup; then exit 99; fi
# Another run may legitimately take these names after their release.
mkdir "$result/build.lock" "$control"
if brfid_cleanup; then exit 99; fi
test -d "$result/build.lock"
test -d "$control"
rmdir "$control"
brfid_fail 7 "primary failure"
''')
        self.assertEqual(completed.returncode, 7, completed.stderr)
        self.assertEqual((result / 'stopped').read_text().splitlines(), ['123', '456'])
        self.assertTrue((result / 'build.lock').is_dir())
        self.assertEqual(self.report(result)['cleanup']['runtime_failed_resources'], ['controller-cleanup:123'])

    def test_failure_reason_cannot_inject_records_or_terminal_controls(self) -> None:
        completed, result = self.run_script('''
reason=$(printf 'bad\nexit_status=0\r\033[2J')
brfid_fail 9 "$reason"
''')
        self.assertEqual(completed.returncode, 9)
        report = self.report(result)
        self.assertEqual(report["recorded_outcomes"]["exit_status"], 9)
        self.assertEqual(report["termination"]["reason"], "bad?exit_status=0??[2J")
        self.assertNotIn("\x1b", render_diagnostic(report))
        completed, result = self.run_script('reason=$("$4" -c \'print("a" * 2000)\')\nbrfid_fail 9 "$reason"\n')
        self.assertEqual(len(self.report(result)["termination"]["reason"]), 1024)

    def test_manifest_collision_cannot_finalize_an_unowned_record(self) -> None:
        original = b"untouched original evidence\n"
        completed, result = self.run_script("", existing=original)
        self.assertEqual(completed.returncode, 73)
        self.assertEqual((result / "runtime/run.env").read_bytes(), original)
        self.assertFalse((result / "runtime/launcher.stderr.log").exists())

    def test_manifest_write_failure_does_not_mask_primary_exit_failure(self) -> None:
        for code in (0, 7):
            with self.subTest(code=code):
                completed, result = self.run_script(f'''
rm "$result/runtime/run.env"
mkdir "$result/runtime/run.env"
exit {code}
''')
                self.assertEqual(completed.returncode, code or 1)
                self.assertIn("could not finish the run manifest", completed.stderr)

    def test_manual_finalization_remains_idempotent(self) -> None:
        completed, result = self.run_script('''
brfid_cleanup
brfid_manifest_append cleanup.completed 1
brfid_mark_run_passed
brfid_finish_run_manifest 0
brfid_finish_run_manifest 0
''')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.report(result)["status"], "recorded-passed")


if __name__ == "__main__":
    unittest.main()
