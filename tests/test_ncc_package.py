from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (ROOT / "ncc", ROOT / "scripts", ROOT / "tests")


class NccPackageBoundaryTests(unittest.TestCase):
    def test_focused_import_loads_only_its_dependency_closure(self) -> None:
        command = "\n".join(
            (
                "import json",
                "import sys",
                "import ncc.events",
                "print(json.dumps(sorted(name for name in sys.modules "
                "if name == 'ncc' or name.startswith('ncc.'))))",
            )
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            [
                "ncc",
                "ncc.events",
                "ncc.report_checksum",
                "ncc.throughput_report",
                "ncc.trouble_report",
            ],
        )

    def test_repository_imports_contracts_from_owning_submodules(self) -> None:
        package_initializer = ROOT / "ncc" / "__init__.py"
        violations: list[str] = []
        for source_root in SOURCE_ROOTS:
            for path in sorted(source_root.rglob("*.py")):
                if path == package_initializer:
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import) and any(
                        alias.name == "ncc" for alias in node.names
                    ):
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")
                    if isinstance(node, ast.ImportFrom) and node.module == "ncc":
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
