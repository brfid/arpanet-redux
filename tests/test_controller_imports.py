from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ControllerImportTests(unittest.TestCase):
    def test_production_controllers_do_not_load_sibling_scripts(self) -> None:
        controllers = sorted((ROOT / "scripts").glob("*controller.py"))
        self.assertTrue(controllers)
        for path in controllers:
            with self.subTest(controller=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("spec_from_file_location", source)
                self.assertNotIn("module_from_spec", source)


if __name__ == "__main__":
    unittest.main()
