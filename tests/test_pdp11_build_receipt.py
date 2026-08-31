from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdp11-build-receipt.py"
SPEC = importlib.util.spec_from_file_location("pdp11_build_receipt", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RECEIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECEIPT)


class Pdp11BuildReceiptTests(unittest.TestCase):
    def test_guest_image_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            image = Path(directory_name) / "ncp_root.rl01"
            image.write_bytes(b"receipt-bound guest image\n")
            record = RECEIPT.file_record(image)
            self.assertEqual(
                RECEIPT.verify_file_record("guest root", record), image.resolve()
            )
            image.write_bytes(b"substituted guest image\n")
            with self.assertRaisesRegex(ValueError, "hash is"):
                RECEIPT.verify_file_record("guest root", record)

    def test_staged_source_tree_identity_is_path_relative_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            stage = Path(directory_name)
            (stage / "telnet.c").write_text("main() {}\n", encoding="ascii")
            (stage / "headers").mkdir()
            (stage / "headers" / "telnet.h").write_text(
                "#define TEL_IAC 255\n", encoding="ascii"
            )
            identity = RECEIPT.tree_hashes(stage)
            self.assertEqual(set(identity), {"telnet.c", "headers/telnet.h"})
            (stage / "telnet.c").write_text("main() { return 1; }\n", encoding="ascii")
            self.assertNotEqual(RECEIPT.tree_hashes(stage), identity)


if __name__ == "__main__":
    unittest.main()
