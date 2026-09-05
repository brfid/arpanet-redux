from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ncc.guest_workspace import WorkspaceError, write_json
from ncc.harness_manifest import sha256

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("workspace_operator", ROOT / "scripts/workspace.py")
OPERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPERATOR)


class WorkspaceOperatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.result = Path(self.temporary.name).resolve() / "run"
        (self.result / "runtime").mkdir(parents=True)
        self.token = "a" * 32
        self.proof = {
            "format": 1, "run_id": self.result.name, "lease_token": self.token,
            "its": "shutdown-complete", "pdp11": "writers-stopped-and-synced",
        }
        self.proof_path = self.result / "workspace-shutdown.json"
        write_json(self.proof_path, self.proof)
        self.manifest = self.result / "runtime/run.env"
        self.clean = (
            "cleanup_status=passed\npdp11.pid=100\npdp11.exit_status=0\n"
            "host106.pid=101\nhost106.exit_status=0\nsurviving_owned_processes=0\n"
        )
        self.manifest_text = (
            f"workspace.lease-token={self.token}\ncleanup.runtime.exit-status=0\n"
            "process.pdp11.pid=100\nprocess.host106.pid=101\n"
            f"sha256.workspace-shutdown={sha256(self.proof_path)}\n"
        )
        self.manifest.write_text(self.manifest_text)
        (self.result / "cleanup-evidence.txt").write_text(self.clean)

    def test_matching_cleanup_releases_only_this_invocation(self):
        self.assertTrue(OPERATOR.cleanup_proved(self.result, self.token))
        self.assertFalse(OPERATOR.cleanup_proved(self.result, "b" * 32))
        with patch("os.kill", side_effect=AssertionError("old PIDs must not be probed")):
            self.assertTrue(OPERATOR.cleanup_proved(self.result, self.token))

    def test_zero_survivors_cannot_override_failed_or_missing_cleanup(self):
        path = self.result / "cleanup-evidence.txt"
        for text in (
            self.clean.replace("cleanup_status=passed", "cleanup_status=failed"),
            self.clean.replace("surviving_owned_processes=0\n", ""),
            self.clean + "cleanup_status=passed\n",
        ):
            path.write_text(text)
            self.assertFalse(OPERATOR.cleanup_proved(self.result, self.token))
        path.unlink()
        self.assertFalse(OPERATOR.cleanup_proved(self.result, self.token))
        path.write_text(self.clean)
        self.manifest.write_text(self.manifest_text.replace("cleanup.runtime.exit-status=0", "cleanup.runtime.exit-status=1"))
        self.assertFalse(OPERATOR.cleanup_proved(self.result, self.token))

    def test_partial_controller_launch_requires_controller_cleanup(self):
        self.manifest.write_text(f"workspace.lease-token={self.token}\ncleanup.runtime.exit-status=0\n")
        (self.result / "cleanup-evidence.txt").unlink()
        self.assertTrue(OPERATOR.cleanup_proved(self.result, self.token))
        (self.result / "host106-attach-only.simh").write_text("synthetic")
        self.assertFalse(OPERATOR.cleanup_proved(self.result, self.token))

    def test_shutdown_proof_requires_both_clean_guest_exits_and_digest(self):
        self.assertEqual(OPERATOR.shutdown_proved(self.result, self.token), sha256(self.proof_path))
        with self.assertRaises(WorkspaceError):
            OPERATOR.shutdown_proved(self.result, "b" * 32)
        (self.result / "cleanup-evidence.txt").write_text(self.clean.replace("pdp11.exit_status=0", "pdp11.exit_status=-9"))
        with self.assertRaisesRegex(WorkspaceError, "exit successfully"):
            OPERATOR.shutdown_proved(self.result, self.token)
        (self.result / "cleanup-evidence.txt").write_text(self.clean)
        self.manifest.write_text(self.manifest_text.replace(sha256(self.proof_path), "b" * 64))
        with self.assertRaisesRegex(WorkspaceError, "digest"):
            OPERATOR.shutdown_proved(self.result, self.token)

    def test_successful_publication_is_not_inferred_from_partial_proof(self):
        for changes in ({"its": "requested"}, {"pdp11": "sync-requested"}, {"run_id": "another-run"}, {"extra": True}, {"format": True}):
            self.proof_path.unlink()
            write_json(self.proof_path, {**self.proof, **changes})
            with self.assertRaises(WorkspaceError):
                OPERATOR.shutdown_proved(self.result, self.token)


if __name__ == "__main__":
    unittest.main()
