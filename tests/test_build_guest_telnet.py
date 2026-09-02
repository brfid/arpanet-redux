from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "research" / "build-guest-telnet.py"
SPEC = importlib.util.spec_from_file_location("build_guest_telnet", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class GuestTelnetSourceAdaptationTests(unittest.TestCase):
    def test_repairs_only_the_dont_branch_fallthrough(self) -> None:
        source = (
            "switch (command) {\n"
            "\tcase tel_do:\tresponse = tel_wont;\n"
            "\t\t\tbreak;\n\n"
            "\tcase tel_dont:\tresponse = tel_wont;\n\n"
            "\tdefault:\treturn;\n"
            "\t}\n"
        )

        repaired = BUILDER.repair_usrtelnetin_dont_fallthrough(source)

        self.assertEqual(repaired.count("\t\t\tbreak;\n"), 2)
        self.assertIn(
            "\tcase tel_dont:\tresponse = tel_wont;\n\t\t\tbreak;\n",
            repaired,
        )
        self.assertEqual(
            repaired,
            source.replace(
                "\tcase tel_dont:\tresponse = tel_wont;\n",
                "\tcase tel_dont:\tresponse = tel_wont;\n\t\t\tbreak;\n",
            ),
        )

    def test_rejects_an_already_repaired_or_changed_source_shape(self) -> None:
        already_repaired = (
            "\tcase tel_dont:\tresponse = tel_wont;\n"
            "\t\t\tbreak;\n\n"
            "\tdefault:\treturn;\n"
        )
        with self.assertRaisesRegex(ValueError, "unique expected DONT fallthrough"):
            BUILDER.repair_usrtelnetin_dont_fallthrough(already_repaired)

    def test_rejects_more_than_one_candidate_branch(self) -> None:
        candidate = (
            "\tcase tel_dont:\tresponse = tel_wont;\n\n"
            "\tdefault:\treturn;\n"
        )
        with self.assertRaisesRegex(ValueError, "unique expected DONT fallthrough"):
            BUILDER.repair_usrtelnetin_dont_fallthrough(candidate + candidate)


if __name__ == "__main__":
    unittest.main()
