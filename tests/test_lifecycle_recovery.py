from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ncc.harness_imp import wait_for_watchdog_devices_ready
from ncc.harness_process import ImpProcess, ProcessWatch, PtyProcess
from ncc.pdp11_its_harness import stop_and_record
from ncc.run_diagnostics import diagnose_run

ROOT = Path(__file__).resolve().parents[1]


class LifecycleRecoveryTests(unittest.TestCase):
    def test_wait_checks_peer_exit_before_accepting_buffered_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            program = root / 'guest.py'
            program.write_text('import time\nprint("READY", flush=True)\ntime.sleep(30)\n')
            host = PtyProcess('guest', Path(sys.executable), program, root,
                              root / 'console', root / 'sent', root / 'manifest')
            self.addCleanup(host.stop, True)
            host.launch()
            host.expect('READY', timeout=3)
            peer = SimpleNamespace(name='imp-peer', process=SimpleNamespace(poll=lambda: 7))
            waits = []
            ProcessWatch((host, peer), lambda condition, timeout: waits.append((condition, timeout)))
            host.cursor = 0
            started = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, 'imp-peer exited early .*status=7'):
                host.expect('READY', timeout=5)
            self.assertLess(time.monotonic() - started, 1)
            self.assertIn('guest console', waits[0][0])
            self.assertEqual(waits[0][1], 5)

    def test_watch_checks_peer_during_settling_but_does_not_require_unlaunched_guests(self) -> None:
        status = [None]
        peer = SimpleNamespace(name='peer', process=SimpleNamespace(poll=lambda: status[0]))
        unlaunched = SimpleNamespace(name='future-guest', process=None)
        watch = ProcessWatch((peer, unlaunched), lambda *_: None)
        watch.check()
        def exit_peer(_):
            status[0] = -9
        with patch('ncc.harness_process.time.sleep', side_effect=exit_peer):
            with self.assertRaisesRegex(RuntimeError, 'peer exited early .*status=-9'):
                watch.sleep(30, 'route settling')

    def test_missing_watchdog_log_reports_timeout_and_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp = SimpleNamespace(name='imp', debug_path=Path(tmp) / 'absent', ensure_alive=lambda: None)
            with self.assertRaisesRegex(TimeoutError, 'MI1 and HI2 ready.*latest watchdog state is None'):
                wait_for_watchdog_devices_ready(imp, modem_device='mi1', host_device='hi2', timeout=0.01)

    def test_manifest_failure_after_spawn_stops_child_and_closes_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            program = root / 'guest.py'
            program.write_text('import time\ntime.sleep(30)\n')
            child = PtyProcess('partial', Path(sys.executable), program, root,
                               root / 'console', root / 'sent', root / 'manifest')
            self.addCleanup(child.stop, True)
            with patch('ncc.harness_process.append_manifest', side_effect=OSError('cannot record PID')):
                with self.assertRaisesRegex(OSError, 'cannot record PID'):
                    child.launch()
            self.assertIsNotNone(child.process.poll())
            self.assertIsNone(child.master_fd)
            self.assertTrue(child.console_stream.closed)
            self.assertTrue(child.sent_stream.closed)

    def test_missing_preflight_directory_is_retained_and_collision_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / 'result'
            command = [str(ROOT / 'scripts/smoke-pdp11-its.sh'), *([str(root / 'missing')] * 7), str(result)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 66, completed.stderr)
            report = diagnose_run(result)
            self.assertEqual(report['status'], 'recorded-failed')
            self.assertEqual(report['cleanup']['outer_runtime'], 'passed')
            self.assertEqual(report['cleanup']['controller'], 'not-recorded')
            self.assertIn('input paths', report['last_recorded_checkpoint']['value'])
            self.assertIn('missing required input directory', report['termination']['reason'])
            before = {path: path.read_bytes() for path in result.rglob('*') if path.is_file()}
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 73, second.stderr)
            self.assertEqual(before, {path: path.read_bytes() for path in result.rglob('*') if path.is_file()})

    def test_partial_launch_releases_open_files_and_pty(self) -> None:
        for kind in (PtyProcess, ImpProcess):
            with self.subTest(kind=kind.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if kind is PtyProcess:
                    child = kind('partial', root / 'absent', root / 'config', root,
                                 root / 'console', root / 'sent', root / 'manifest')
                else:
                    child = kind('partial', root / 'absent', root / 'config', root,
                                 root, root / 'manifest')
                try:
                    with self.assertRaises(FileNotFoundError):
                        child.launch()
                    child.stop()
                    self.assertIsNone(child.master_fd)
                    for field in ('console_stream', 'sent_stream', 'debug_stream'):
                        stream = getattr(child, field, None)
                        self.assertTrue(stream is None or stream.closed, field)
                finally:
                    # Test owns these descriptors even on the unfixed implementation.
                    if child.master_fd is not None:
                        os.close(child.master_fd)
                    for field in ('console_stream', 'sent_stream', 'debug_stream'):
                        stream = getattr(child, field, None)
                        if stream is not None:
                            stream.close()

    def test_shutdown_error_does_not_skip_other_owned_children_or_evidence(self) -> None:
        stopped = []

        def stop(name):
            stopped.append(name)
            if name == 'broken':
                raise OSError('synthetic descriptor close failure')

        children = tuple(SimpleNamespace(name=name,
            process=SimpleNamespace(pid=index + 10, poll=lambda: 0),
            stop=lambda force=False, name=name: stop(name))
            for index, name in enumerate(('broken', 'other-host', 'imp')))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, 'broken'):
                stop_and_record(root, children[:2], children[2:], force=True)
            self.assertEqual(stopped, ['broken', 'other-host', 'imp'])
            evidence = (root / 'cleanup-evidence.txt').read_text()
            self.assertIn('surviving_owned_processes=0', evidence)
            self.assertIn('cleanup_status=failed', evidence)
            self.assertTrue(evidence.endswith('surviving_owned_processes=0\n'))

    def test_repeated_signal_during_launcher_cleanup_preserves_first_status_and_leases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'runtime').mkdir()
            helper = root / 'controller.py'
            helper.write_text('''import os, signal, sys, time
from pathlib import Path
root = Path(sys.argv[1])
def stop(*_):
    os.kill(os.getppid(), signal.SIGHUP)
    time.sleep(0.2)
    os.kill(os.getppid(), signal.SIGTERM)
    (root / 'controller-finished').touch()
    sys.exit(1)
signal.signal(signal.SIGTERM, stop)
(root / 'ready').touch()
while True: time.sleep(0.01)
''')
            script = root / 'launcher.sh'
            script.write_text('''set -eu
. "$1/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps
brfid_manifest_init "$2/runtime/run.env" repeated-signal-test "$1"
brfid_acquire_exclusive_lease "$2/build.lock"
brfid_make_private_socket_dir
printf '%s' "$BRFID_SOCKET_DIR" >"$2/socket-dir"
brfid_start_process controller "$2" "$2/controller.out" "$2/controller.err" "$3" "$2/controller.py" "$2"
while [ ! -e "$2/ready" ]; do sleep 0.1; done
kill -TERM "$$"
''')
            completed = subprocess.run(['/bin/sh', str(script), str(ROOT), str(root), sys.executable],
                capture_output=True, text=True, timeout=12)
            socket_dir = Path((root / 'socket-dir').read_text())
            self.addCleanup(lambda: socket_dir.rmdir() if socket_dir.exists() else None)
            self.assertEqual(completed.returncode, 143, completed.stderr)
            self.assertTrue((root / 'controller-finished').exists())
            self.assertFalse((root / 'build.lock').exists())
            self.assertFalse(Path((root / 'socket-dir').read_text()).exists())
            manifest = (root / 'runtime/run.env').read_text()
            self.assertIn('termination.signal=TERM', manifest)
            self.assertIn('cleanup.runtime.exit-status=0', manifest)


if __name__ == '__main__':
    unittest.main()
