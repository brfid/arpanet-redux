from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prune-media.py"


def run_pruner(lab: Path, *arguments: os.PathLike[str] | str):
    return subprocess.run(
        [sys.executable, SCRIPT, lab, *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PruneMediaTests(unittest.TestCase):
    def make_lab(self, root: Path) -> Path:
        lab = root / "lab"
        (lab / "results").mkdir(parents=True)
        return lab

    def complete(self, run: Path, outcome: str = "passed") -> None:
        (run / "outcome.txt").write_text(f"{outcome}\n", encoding="ascii")

    def test_default_is_a_non_mutating_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            run = lab / "results" / "accepted-run"
            run.mkdir()
            self.complete(run)
            media = run / "rp03.0"
            media.write_bytes(b"staged guest media")

            result = run_pruner(lab)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode: DRY RUN", result.stdout)
            self.assertIn("WOULD PRUNE: accepted-run", result.stdout)
            self.assertTrue(media.exists())
            self.assertFalse((run / "media-pruned.txt").exists())

    def test_make_target_is_always_a_non_mutating_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            run = lab / "results" / "accepted-run"
            run.mkdir()
            self.complete(run)
            media = run / "rp03.0"
            media.write_bytes(b"staged guest media")

            result = subprocess.run(
                ["make", f"LAB_ROOT={lab}", "prune-media"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode: DRY RUN", result.stdout)
            self.assertTrue(media.exists())
            self.assertFalse((run / "media-pruned.txt").exists())

    def test_apply_removes_only_rp03_files_and_records_exact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            run = lab / "results" / "accepted-run"
            nested = run / "runtime"
            nested.mkdir(parents=True)
            first = run / "rp03.0"
            second = nested / "rp03.1"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            preserved = {
                run / "dskdmp.rim": b"rim",
                run / "root.rl01": b"root",
                run / "swap.rl02": b"swap",
                run / "guest.rk05": b"guest",
            }
            for path, contents in preserved.items():
                path.write_bytes(contents)
            self.complete(run)
            preserved[run / "outcome.txt"] = b"passed\n"

            result = run_pruner(lab, "--apply")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mode: APPLY", result.stdout)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
            for path, contents in preserved.items():
                self.assertEqual(path.read_bytes(), contents)
            note = (run / "media-pruned.txt").read_text(encoding="utf-8")
            self.assertIn("Status: completed", note)
            self.assertIn('  - "rp03.0"', note)
            self.assertIn('  - "runtime/rp03.1"', note)
            self.assertIn("Removed: 2 files, 11 apparent bytes.", note)

    def test_a_build_receipt_guards_the_entire_result_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            build = lab / "results" / "pdp11-build"
            build.mkdir()
            media = build / "rp03.0"
            media.write_bytes(b"do not remove")
            (build / "pdp11-build-receipt.json").write_text(
                "{}\n", encoding="ascii"
            )

            result = run_pruner(lab, "--apply")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SKIP build receipt: pdp11-build", result.stdout)
            self.assertTrue(media.exists())
            self.assertFalse((build / "media-pruned.txt").exists())

    def test_an_existing_note_aborts_before_any_media_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            first_run = lab / "results" / "first-run"
            second_run = lab / "results" / "second-run"
            first_run.mkdir()
            second_run.mkdir()
            self.complete(first_run)
            self.complete(second_run)
            first_media = first_run / "rp03.0"
            second_media = second_run / "rp03.0"
            first_media.write_bytes(b"first")
            second_media.write_bytes(b"second")
            existing_note = second_run / "media-pruned.txt"
            existing_note.write_text("operator note\n", encoding="ascii")

            result = run_pruner(lab, "--apply")

            self.assertEqual(result.returncode, 1)
            self.assertIn("no media was removed", result.stderr)
            self.assertTrue(first_media.exists())
            self.assertTrue(second_media.exists())
            self.assertFalse((first_run / "media-pruned.txt").exists())
            self.assertEqual(existing_note.read_text(encoding="ascii"), "operator note\n")

    def test_unknown_option_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            run = lab / "results" / "accepted-run"
            run.mkdir()
            self.complete(run)
            media = run / "rp03.0"
            media.write_bytes(b"staged guest media")

            result = run_pruner(lab, "--aply")

            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized arguments: --aply", result.stderr)
            self.assertTrue(media.exists())
            self.assertFalse((run / "media-pruned.txt").exists())

    def test_results_override_must_stay_inside_the_laboratory(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            lab = self.make_lab(root)
            outside = root / "outside-results"
            outside.mkdir()

            result = run_pruner(lab, "--results-root", outside, "--apply")

            self.assertEqual(result.returncode, os.EX_NOINPUT)
            self.assertIn("outside the laboratory", result.stderr)

    def test_active_or_incomplete_result_is_never_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            run = lab / "results" / "active-run"
            run.mkdir()
            media = run / "rp03.0"
            media.write_bytes(b"simulator may still be writing")

            result = run_pruner(lab, "--apply")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SKIP active or incomplete result: active-run", result.stdout)
            self.assertTrue(media.exists())
            self.assertFalse((run / "media-pruned.txt").exists())

    def test_terminal_run_manifest_is_a_completion_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            lab = self.make_lab(Path(directory_name))
            run = lab / "results" / "legacy-formal-run"
            runtime = run / "runtime"
            runtime.mkdir(parents=True)
            (runtime / "run.env").write_text(
                "format=1\nfinished_utc=2026-09-04T00:00:00Z\n"
                "outcome=passed\nexit_status=0\n",
                encoding="ascii",
            )
            media = run / "rp03.0"
            media.write_bytes(b"staged guest media")

            result = run_pruner(lab, "--apply")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(media.exists())
            self.assertIn(
                "Status: completed",
                (run / "media-pruned.txt").read_text(encoding="utf-8"),
            )

    def test_symlinked_result_entry_is_rejected_without_touching_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            lab = self.make_lab(root)
            outside_run = root / "outside-run"
            outside_run.mkdir()
            media = outside_run / "rp03.0"
            media.write_bytes(b"outside")
            (lab / "results" / "linked-run").symlink_to(
                outside_run, target_is_directory=True
            )

            result = run_pruner(lab, "--apply")

            self.assertEqual(result.returncode, 1)
            self.assertIn("refusing symlinked result entry", result.stderr)
            self.assertTrue(media.exists())
            self.assertFalse((outside_run / "media-pruned.txt").exists())


if __name__ == "__main__":
    unittest.main()
