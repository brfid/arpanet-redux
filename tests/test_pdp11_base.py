from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pdp11_base as BASE  # noqa: E402
from research.v6fs import V6FS  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_record(raw: bytes) -> tuple[bytes, dict]:
    compressed = gzip.compress(raw, mtime=0)
    return compressed, {"name": "input.gz", "url": "https://example.invalid/input.gz",
                        "size": len(compressed), "sha256": digest(compressed),
                        "uncompressed_size": len(raw), "uncompressed_sha256": digest(raw)}


def synthetic_tape() -> bytes:
    """A small original filesystem fixture, padded to the required tape geometry."""
    disk = bytearray(4000 * 512)
    struct.pack_into("<103H", disk, 512, 4, 4000, 100, 0, *range(30, 129))
    for inode, block, links, entries in (
        (1, 6, 4, ((1, "."), (1, ".."), (2, "usr"), (3, "dev"))),
        (2, 7, 2, ((2, "."), (1, ".."))),
        (3, 8, 2, ((3, "."), (1, ".."))),
    ):
        struct.pack_into("<16H", disk, 1024 + (inode - 1) * 32,
                         0o140755, links, 0, len(entries) * 16, block, *([0] * 11))
        for index, (number, name) in enumerate(entries):
            struct.pack_into("<H14s", disk, block * 512 + index * 16, number, name.encode())
    return bytes(100 * 512) + disk + bytes(8000 * 512)


class BaseMediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_pair_identity_rejects_mixing_and_changed_media(self):
        repo = self.root / "repo"
        (repo / "pins").mkdir(parents=True)
        for profile, filename in BASE.PROFILES.items():
            (repo / "pins" / filename).write_text("".join(
                f"{digest((profile + name).encode())}  images/{name}\n" for name in BASE.IMAGE_NAMES))
        paths = [self.root / name for name in BASE.IMAGE_NAMES]
        for profile in BASE.PROFILES:
            for path in paths:
                path.write_bytes((profile + path.name).encode())
            self.assertEqual(BASE.verify_pair(*paths, repo), profile)
        paths[0].write_bytes(("reconstructed-v1" + paths[0].name).encode())
        with self.assertRaisesRegex(ValueError, "one complete pinned pair"):
            BASE.verify_pair(*paths, repo)
        paths[1].write_bytes(b"altered")
        with self.assertRaises(ValueError):
            BASE.verify_pair(*paths, repo)

    def test_pair_identity_refuses_symlinked_images(self):
        actual = self.root / "actual"
        actual.write_bytes(b"content")
        link = self.root / "link"
        link.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "regular files"):
            BASE.verify_pair(link, actual)

    def test_cache_checks_bytes_offline_and_does_not_replace_mismatches(self):
        data, record = archive_record(b"original test data")
        path = self.root / "input.gz"
        with mock.patch.object(BASE.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(ValueError, "offline archive is missing"):
                BASE.acquire_archive(path, record, offline=True)
            path.write_bytes(data)
            self.assertEqual(BASE.acquire_archive(path, record, offline=True), data)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                BASE.acquire_archive(path, record, offline=False)
            self.assertEqual(path.read_bytes(), b"changed")
            request.assert_not_called()

    def test_download_failure_never_publishes_cache_bytes(self):
        _, record = archive_record(b"original")
        path = self.root / "cache/input.gz"
        response = io.BytesIO(b"corrupt")
        response.geturl = lambda: record["url"]
        with mock.patch.object(BASE.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                BASE.acquire_archive(path, record, offline=False)
        self.assertFalse(path.exists())

    def test_unpacked_content_has_its_own_size_and_identity(self):
        data, record = archive_record(b"original")
        self.assertEqual(BASE.unpack_archive(data, record), b"original")
        for altered in (dict(record, uncompressed_size=4),
                        dict(record, uncompressed_sha256="0" * 64)):
            with self.assertRaisesRegex(ValueError, "uncompressed"):
                BASE.unpack_archive(data, altered)
        with self.assertRaises((EOFError, OSError)):
            BASE.unpack_archive(data[:-6], record)

    def test_plan_has_no_writes_and_rejects_repository_destinations(self):
        lab = self.root / "lab"
        BASE.build(lab, lab / "work/network-unix-v6", plan=True)
        self.assertFalse(lab.exists())
        with self.assertRaisesRegex(ValueError, "outside the source repository"):
            BASE.build(ROOT / "lab", self.root / "network", plan=True)

    def test_external_path_checks_follow_parent_symlinks(self):
        lab = self.root / "lab"
        lab.mkdir()
        (lab / "work").symlink_to(ROOT, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            BASE.build(lab, self.root / "network", plan=True)

    def test_default_selects_whole_pair_and_exposes_incomplete_rebuild(self):
        lab = self.root / "lab"
        legacy = lab / "work/unix-v6-install/images"
        rebuilt = lab / "work/pdp11-base/images"
        self.assertEqual(BASE.default_image_dir(lab), rebuilt)
        legacy.mkdir(parents=True)
        self.assertEqual(BASE.default_image_dir(lab), legacy)
        rebuilt.parent.mkdir()
        self.assertEqual(BASE.default_image_dir(lab), rebuilt)

    def test_build_lock_excludes_concurrent_reconstruction(self):
        lock = self.root / "lock"
        with BASE.build_lock(lock):
            with self.assertRaisesRegex(ValueError, "another base-media reconstruction"):
                with BASE.build_lock(lock):
                    self.fail("second builder entered")
        with BASE.build_lock(lock):
            pass

    def test_existing_unreceipted_destination_is_preserved(self):
        lab = self.root / "lab"
        destination = lab / "work/pdp11-base"
        destination.mkdir(parents=True)
        with mock.patch.object(BASE, "source_payloads") as source:
            with self.assertRaisesRegex(ValueError, "existing destination"):
                BASE.build(lab, self.root / "network")
            source.assert_not_called()
        self.assertEqual(list(destination.iterdir()), [])

    def test_assembly_is_deterministic_and_preserves_guest_content_and_links(self):
        tape = synthetic_tape()
        disk = b"original test bootstrap".ljust(2 * BASE.RL01_SIZE, b"\0")
        payloads = dict(zip(BASE.PAYLOADS, (b"kernel" * 1000, b"large daemon", b"small daemon")))
        first, second = self.root / "first", self.root / "second"
        for images in (first, second):
            BASE.assemble(tape, disk, payloads, images)
        for name in BASE.IMAGE_NAMES:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            self.assertEqual((first / name).stat().st_size, BASE.RL01_SIZE)
        self.assertEqual((first / BASE.IMAGE_NAMES[1]).read_bytes(), bytes(BASE.RL01_SIZE))
        fs = V6FS(first / BASE.IMAGE_NAMES[0])
        self.assertEqual(fs.data[:512], disk[:512])
        for name in ("/usr", "/usr/net"):
            self.assertEqual(fs.read_inode(fs.lookup(name))["nlink"], 3)
        device = fs.read_inode(fs.lookup("/dev/ncpkernel"))
        self.assertEqual(device["mode"], 0o120666)
        self.assertEqual(device["addr"][0], 5 << 8)
        kernel = fs.read_inode(fs.lookup("/green"))
        blocks = fs._read_words(kernel["addr"][0], 0, 256)
        content = b"".join(fs.data[block*512:(block+1)*512] for block in blocks if block)
        self.assertEqual(content[:kernel["size"]], payloads["green/unix"])

    def test_failed_assembly_cannot_publish_partial_pair(self):
        lab = self.root / "lab"
        def fail(tape, disk, payloads, images):
            images.mkdir()
            (images / "ncp_root.rl01").write_bytes(b"partial")
            raise ValueError("test assembly failure")
        with mock.patch.object(BASE, "source_payloads", return_value=({}, {})), \
             mock.patch.object(BASE, "acquire_archive", return_value=b""), \
             mock.patch.object(BASE, "unpack_archive", return_value=b""), \
             mock.patch.object(BASE, "assemble", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "test assembly failure"):
                BASE.build(lab, self.root / "network")
        self.assertFalse((lab / "work/pdp11-base").exists())
        self.assertFalse(list((lab / "work").glob(".pdp11-base-*")))

    def test_completed_build_is_verified_and_never_rewritten(self):
        lab = self.root / "lab"
        def fixture(tape, disk, payloads, images):
            images.mkdir()
            for name in BASE.IMAGE_NAMES:
                (images / name).write_bytes(b"fixture")
        profiles = {"reconstructed-v1": {name: digest(b"fixture") for name in BASE.IMAGE_NAMES}}
        with mock.patch.object(BASE, "source_payloads", return_value=({}, {})), \
             mock.patch.object(BASE, "acquire_archive", return_value=b""), \
             mock.patch.object(BASE, "unpack_archive", return_value=b""), \
             mock.patch.object(BASE, "load_profiles", return_value=profiles), \
             mock.patch.object(BASE, "assemble", side_effect=fixture) as assemble:
            destination = BASE.build(lab, self.root / "network")
            before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in destination.rglob("*") if p.is_file()}
            BASE.build(lab, self.root / "network", offline=True)
            self.assertEqual(assemble.call_count, 1)
            self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                                     for p in destination.rglob("*") if p.is_file()})
            receipt = destination / "pdp11-base-receipt.json"
            altered = json.loads(receipt.read_text())
            altered["source"] = {"revision": "wrong"}
            receipt.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "receipt differs"):
                BASE.build(lab, self.root / "network")


if __name__ == "__main__":
    unittest.main()
