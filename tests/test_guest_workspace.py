from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ncc.guest_workspace import MEDIA, Workspace, WorkspaceError, workspace_path, write_json


class GuestWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        root = self.directory / "workspaces" / "test"
        root.mkdir(parents=True)
        self.workspace = Workspace(root)
        self.inputs = {"test-input": {"path": "/external/input", "sha256": "a" * 64}}
        write_json(root / "workspace.json", {
            "format": 1, "name": "test", "created_utc": "2026-09-05T00:00:00+00:00",
            "lab": str(self.directory), "build": "/external/build", "inputs": self.inputs,
        })
        self.sources = {}
        for number, name in enumerate(MEDIA):
            source = self.directory / f"synthetic-{number}"
            source.write_bytes(f"synthetic guest disk {number}\n".encode())
            self.sources[name] = source
        self.seed = self.workspace.publish(self.sources, parent=None, result=None, shutdown_sha256=None)

    def save(self):
        return self.workspace.publish(
            self.sources, parent=self.seed, result=self.directory / "result", shutdown_sha256="b" * 64,
        )

    def test_saved_disk_sets_survive_fresh_store_and_rollback(self):
        before = self.workspace.verify_generation(self.seed)
        self.sources[MEDIA[1]].write_bytes(b"ITS changed\n")
        self.sources[MEDIA[5]].write_bytes(b"UNIX changed\n")
        saved = self.save()
        reopened = Workspace(self.workspace.root)
        self.assertEqual(reopened.current(), saved)
        after = reopened.verify_generation(saved)
        self.assertEqual(after["parent"], self.seed)
        for name in (MEDIA[1], MEDIA[5]):
            self.assertNotEqual(before["media"][name], after["media"][name])
        self.assertEqual(reopened.verify_generation(self.seed), before)
        reopened.select(self.seed)
        self.assertEqual(reopened.current(), self.seed)
        self.assertEqual(reopened.verify_generation(saved), after)

    def test_failed_or_interrupted_copy_preserves_previous_save(self):
        from ncc.guest_workspace import copy_media
        for error in (OSError("disk full"), KeyboardInterrupt()):
            count = 0
            def copying(source, destination):
                nonlocal count
                count += 1
                if count == 4:
                    raise error
                return copy_media(source, destination)
            with self.subTest(error=type(error)), patch("ncc.guest_workspace.copy_media", copying):
                with self.assertRaises(type(error)):
                    self.save()
            self.assertEqual(self.workspace.current(), self.seed)
            self.workspace.verify_generation(self.seed)
            self.assertFalse(list((self.workspace.root / "generations").glob(".pending-*")))

    def test_failed_pointer_publication_keeps_previous_save(self):
        with patch("ncc.guest_workspace.os.replace", side_effect=OSError("interrupted publication")):
            with self.assertRaises(OSError):
                self.save()
        self.assertEqual(self.workspace.current(), self.seed)
        self.workspace.verify_generation(self.seed)
        generations = list((self.workspace.root / "generations").iterdir())
        self.assertEqual(len(generations), 2)
        for generation in generations:
            self.workspace.verify_generation(generation.name)

    def test_tampered_media_cannot_be_selected(self):
        saved = self.save()
        self.workspace.select(self.seed)
        (self.workspace.generation_path(saved) / MEDIA[1]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(WorkspaceError, "verification failed"):
            self.workspace.select(saved)
        self.assertEqual(self.workspace.current(), self.seed)

    def test_complete_media_set_and_current_parent_required(self):
        with self.assertRaises(WorkspaceError):
            self.workspace.publish({}, parent=self.seed, result=self.directory, shutdown_sha256="b" * 64)
        saved = self.save()
        with self.assertRaisesRegex(WorkspaceError, "changed"):
            self.save()
        self.assertEqual(self.workspace.current(), saved)
        with self.assertRaisesRegex(WorkspaceError, "reseeded"):
            self.workspace.publish(self.sources, parent=None, result=None, shutdown_sha256=None)

    def test_exclusive_lease_is_not_reclaimed_using_old_pid(self):
        first = self.workspace.acquire(self.directory / "run")
        with self.assertRaisesRegex(WorkspaceError, "leased"):
            self.workspace.acquire()
        with self.assertRaisesRegex(WorkspaceError, "ownership"):
            self.workspace.release("wrong-token")
        self.workspace.release(first)
        second = self.workspace.acquire()
        with self.assertRaisesRegex(WorkspaceError, "ownership"):
            self.workspace.release(first)
        self.workspace.release(second)

    def test_compatibility_compares_content_not_worktree_paths(self):
        self.workspace.check_inputs({"test-input": {"path": "/another/worktree/input", "sha256": "a" * 64}})
        with self.assertRaisesRegex(WorkspaceError, "migration"):
            self.workspace.check_inputs({"test-input": {"path": "/external/input", "sha256": "b" * 64}})

    def test_unknown_fields_duplicate_keys_and_path_escape_are_rejected(self):
        pointer = self.workspace.root / "current.json"
        for text in (
            '{"format":1,"generation":"../../other"}',
            '{"format":1,"format":1,"generation":"' + self.seed + '"}',
            json.dumps({"format": 1, "generation": self.seed, "extra": 1}),
            json.dumps({"format": True, "generation": self.seed}),
        ):
            pointer.write_text(text)
            with self.assertRaises(WorkspaceError):
                self.workspace.current()

    def test_symlinked_media_and_nested_directory_are_rejected(self):
        root = self.workspace.generation_path(self.seed)
        disk = root / MEDIA[1]
        disk.unlink()
        disk.symlink_to(self.sources[MEDIA[1]])
        with self.assertRaises(WorkspaceError):
            self.workspace.verify_generation(self.seed)
        disk.unlink()
        disk.write_bytes(self.sources[MEDIA[1]].read_bytes())
        host = root / "host106"
        moved = root / "moved"
        host.rename(moved)
        host.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(WorkspaceError):
            self.workspace.verify_generation(self.seed)

    def test_names_and_repository_storage_boundary(self):
        repo = self.directory / "repository"
        for name in ("", "../other", "a/b", "a\n", "-bad"):
            with self.assertRaises(WorkspaceError):
                workspace_path(self.directory, name, repo)
        with self.assertRaisesRegex(WorkspaceError, "outside"):
            workspace_path(repo / "lab", "test", repo)


if __name__ == "__main__":
    unittest.main()
