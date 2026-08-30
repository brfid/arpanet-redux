#!/usr/bin/env python3
"""Minimal V6 filesystem injector: add files, directories, and device
nodes directly into an existing V6 filesystem image, without booting a
guest. Structures (filsys, inode, directory entry, free-list chaining)
are derived from the standard V6 kernel headers (h/filsys.h, h/ino.h,
h/param.h) and verified against a known-good extracted root filesystem
before use; see docs/research/imp11a-device.md for how that image was
produced and docs/research/pdp11-network-unix.md for what it feeds.

V6 on-disk layout: block 0 boot block, block 1 superblock, blocks
2..1+isize inode list (16 32-byte inodes per block), remaining blocks
data. Directories are regular files containing 16-byte entries
(2-byte inode number + 14-byte name). Files under 8 blocks use 8
direct block pointers in i_addr[0:8]; larger files (still under
896KB, the only case implemented here) set ILARG and use i_addr[0]
as a single indirect block of 256 direct pointers.

Research-phase tool: exploratory, not wired into any make target or
test, and not yet exercised beyond what docs/research records.
"""
from __future__ import annotations

import argparse
import struct
import sys

BLOCK = 512
IALLOC = 0o100000
IFDIR = 0o040000
IFCHR = 0o020000
IFBLK = 0o060000
ILARG = 0o010000
DIRSIZ = 14
ROOTINO = 1


class V6FS:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = bytearray(f.read())
        sb = self._read_words(1, 0, 103)
        self.isize = sb[0]
        self.fsize = sb[1]
        self.nfree = sb[2]
        self.free = list(sb[3:103])

    def save(self):
        with open(self.path, "r+b") as f:
            f.seek(0)
            f.write(self.data)

    # -- raw block helpers --------------------------------------------
    def _block_off(self, blkno):
        return blkno * BLOCK

    def _read_words(self, blkno, word_off, count):
        off = self._block_off(blkno) + word_off * 2
        return list(struct.unpack_from(f"<{count}H", self.data, off))

    def _write_words(self, blkno, word_off, words):
        off = self._block_off(blkno) + word_off * 2
        struct.pack_into(f"<{len(words)}H", self.data, off, *words)

    def zero_block(self, blkno):
        off = self._block_off(blkno)
        self.data[off:off + BLOCK] = b"\x00" * BLOCK

    # -- superblock / free list -----------------------------------------
    def flush_superblock(self):
        words = [self.isize, self.fsize, self.nfree] + self.free
        words += [0] * (256 - len(words))  # pad to a full block of words
        self._write_words(1, 0, words[:256])

    def alloc_block(self):
        if self.nfree <= 0:
            raise RuntimeError("V6FS: free list exhausted")
        self.nfree -= 1
        bno = self.free[self.nfree]
        if bno == 0:
            raise RuntimeError("V6FS: free list hit a zero entry")
        if self.nfree <= 0:
            chunk = self._read_words(bno, 0, 101)
            self.nfree = chunk[0]
            self.free = chunk[1:101]
        self.zero_block(bno)
        return bno

    # -- inodes -----------------------------------------------------------
    def _inode_loc(self, inum):
        idx = inum - 1
        blkno = 2 + idx // 16
        word_off = (idx % 16) * 16
        return blkno, word_off

    def read_inode(self, inum):
        blkno, word_off = self._inode_loc(inum)
        w = self._read_words(blkno, word_off, 16)
        mode = w[0]
        nlink = w[1] & 0xFF
        uid = (w[1] >> 8) & 0xFF
        gid = w[2] & 0xFF
        size0 = (w[2] >> 8) & 0xFF
        size1 = w[3]
        size = (size0 << 16) | size1
        addr = w[4:12]
        return {
            "mode": mode, "nlink": nlink, "uid": uid, "gid": gid,
            "size": size, "addr": list(addr),
        }

    def write_inode(self, inum, mode, nlink, uid, gid, size, addr,
                     mtime=0):
        blkno, word_off = self._inode_loc(inum)
        addr = list(addr) + [0] * (8 - len(addr))
        words = [
            mode,
            (uid << 8) | nlink,
            gid | ((size >> 16 & 0xFF) << 8),
            size & 0xFFFF,
        ] + addr + [mtime & 0xFFFF, 0, mtime & 0xFFFF, 0]
        self._write_words(blkno, word_off, words)

    def alloc_inode(self):
        for inum in range(2, self.isize * 16 + 1):
            if self.read_inode(inum)["mode"] == 0:
                return inum
        raise RuntimeError("V6FS: no free inode")

    def clear_inode_cache(self):
        # Force the kernel to rescan the disk for free inodes instead of
        # trusting a stale in-core cache that predates this injection.
        self._write_words(1, 103, [0])

    # -- directories --------------------------------------------------
    def _dir_blocks(self, inum):
        ino = self.read_inode(inum)
        assert ino["mode"] & IFDIR, f"inode {inum} is not a directory"
        nblocks = (ino["size"] + BLOCK - 1) // BLOCK
        return ino, [b for b in ino["addr"][:nblocks] if b]

    def _find_in_dir(self, dir_inum, name):
        ino, blocks = self._dir_blocks(dir_inum)
        for blkno in blocks:
            entries = self._read_words(blkno, 0, 256)
            for i in range(0, 256, 8):
                child_ino = entries[i]
                raw = struct.pack(f"<8H", *entries[i:i + 8])[2:16]
                nm = raw.split(b"\x00")[0].decode("ascii", "replace")
                if child_ino != 0 and nm == name:
                    return child_ino
        return None

    def lookup(self, path):
        parts = [p for p in path.strip("/").split("/") if p]
        inum = ROOTINO
        for p in parts:
            nxt = self._find_in_dir(inum, p)
            if nxt is None:
                return None
            inum = nxt
        return inum

    def _add_dir_entry(self, dir_inum, name, child_inum):
        # A directory's inode size is the kernel's read cutoff: writing an
        # entry into an allocated-but-not-yet-counted slot is invisible to
        # the kernel unless size grows to include it. This holds for both
        # branches below (reusing a deleted in-range slot never changes
        # size; extending past size, whether within the last allocated
        # block or into a freshly allocated one, always must).
        assert len(name) <= DIRSIZ
        ino, blocks = self._dir_blocks(dir_inum)
        name_bytes = name.encode("ascii").ljust(DIRSIZ, b"\x00")
        entry_words = [child_inum] + list(struct.unpack("<7H", name_bytes))
        size = ino["size"]

        # 1. Reuse a deleted (ino==0) slot within the current logical size.
        for bi, blkno in enumerate(blocks):
            entries = self._read_words(blkno, 0, 256)
            for i in range(0, 256, 8):
                entry_offset = bi * BLOCK + (i // 8) * 16
                if entry_offset >= size:
                    break
                if entries[i] == 0:
                    self._write_words(blkno, i, entry_words)
                    return

        # 2. Extend into unused space at the end of the last allocated
        # block, if the directory's size doesn't already fill it.
        if blocks and size % BLOCK != 0:
            blkno = blocks[-1]
            word_off = (size % BLOCK) // 2
            self._write_words(blkno, word_off, entry_words)
            self.write_inode(dir_inum, ino["mode"], ino["nlink"], ino["uid"],
                              ino["gid"], size + 16, ino["addr"])
            return

        # 3. No room left: allocate a new block.
        newblk = self.alloc_block()
        self._write_words(newblk, 0, entry_words)
        addr = ino["addr"]
        nblocks = len(blocks)
        assert nblocks < 8, "directory grew beyond direct blocks (unsupported)"
        addr[nblocks] = newblk
        self.write_inode(dir_inum, ino["mode"], ino["nlink"], ino["uid"],
                          ino["gid"], size + 16, addr)

    def mkdir(self, path, mode=0o40755):
        parts = [p for p in path.strip("/").split("/") if p]
        parent = ROOTINO
        for i, p in enumerate(parts):
            existing = self._find_in_dir(parent, p)
            if existing is not None:
                parent = existing
                continue
            inum = self.alloc_inode()
            blk = self.alloc_block()
            self._write_words(blk, 0, [inum] + list(struct.unpack("<7H", b".\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")))
            self._write_words(blk, 8, [parent] + list(struct.unpack("<7H", b"..\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")))
            self.write_inode(inum, IALLOC | IFDIR | (mode & 0o7777), 2, 0, 0,
                              BLOCK, [blk])
            self._add_dir_entry(parent, p, inum)
            parent = inum
        return parent

    # -- regular files / device nodes ----------------------------------
    def _alloc_and_fill(self, content):
        nblocks = (len(content) + BLOCK - 1) // BLOCK
        blocks = []
        for i in range(nblocks):
            bno = self.alloc_block()
            chunk = content[i * BLOCK:(i + 1) * BLOCK]
            off = self._block_off(bno)
            self.data[off:off + len(chunk)] = chunk
            blocks.append(bno)
        return blocks

    def put_file(self, dirpath, name, content, mode=0o100755):
        dir_inum = self.lookup(dirpath) if dirpath not in ("", "/") else ROOTINO
        assert dir_inum is not None, f"no such directory: {dirpath}"
        blocks = self._alloc_and_fill(content)
        inum = self.alloc_inode()
        if len(blocks) <= 8:
            self.write_inode(inum, IALLOC | (mode & 0o177777), 1, 0, 0,
                              len(content), blocks)
        else:
            assert len(blocks) <= 256, "file too large for one indirect block"
            ind = self.alloc_block()
            self._write_words(ind, 0, blocks + [0] * (256 - len(blocks)))
            self.write_inode(inum, IALLOC | ILARG | (mode & 0o177777), 1, 0,
                              0, len(content), [ind])
        self._add_dir_entry(dir_inum, name, inum)
        return inum

    def mknod(self, dirpath, name, kind, major, minor, mode=0o600):
        dir_inum = self.lookup(dirpath) if dirpath not in ("", "/") else ROOTINO
        assert dir_inum is not None, f"no such directory: {dirpath}"
        inum = self.alloc_inode()
        ifmt = IFCHR if kind == "c" else IFBLK
        # V6 packs (major<<8)|minor into i_addr[0].
        self.write_inode(inum, IALLOC | ifmt | (mode & 0o7777), 1, 0, 0, 0,
                          [(major << 8) | minor])
        self._add_dir_entry(dir_inum, name, inum)
        return inum


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="V6 filesystem image to modify in place")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mkdir = sub.add_parser("mkdir", help="create a directory (and missing parents)")
    p_mkdir.add_argument("path")

    p_put = sub.add_parser("put-file", help="copy a host file into the image")
    p_put.add_argument("host_src")
    p_put.add_argument("dest_dir")
    p_put.add_argument("dest_name")
    p_put.add_argument("--mode", type=lambda s: int(s, 8), default=0o755)

    p_mknod = sub.add_parser("mknod", help="create a character or block device node")
    p_mknod.add_argument("dest_dir")
    p_mknod.add_argument("dest_name")
    p_mknod.add_argument("kind", choices=["c", "b"])
    p_mknod.add_argument("major", type=int)
    p_mknod.add_argument("minor", type=int)
    p_mknod.add_argument("--mode", type=lambda s: int(s, 8), default=0o666)

    p_lookup = sub.add_parser("lookup", help="print the inode number for a path, or nothing")
    p_lookup.add_argument("path")

    args = parser.parse_args()
    fs = V6FS(args.image)

    if args.command == "mkdir":
        fs.mkdir(args.path)
    elif args.command == "put-file":
        with open(args.host_src, "rb") as f:
            content = f.read()
        fs.put_file(args.dest_dir, args.dest_name, content, mode=0o100000 | args.mode)
    elif args.command == "mknod":
        fs.mknod(args.dest_dir, args.dest_name, args.kind, args.major, args.minor,
                  mode=args.mode)
    elif args.command == "lookup":
        inum = fs.lookup(args.path)
        if inum is None:
            print(f"{args.path}: not found", file=sys.stderr)
            return 1
        print(inum)
        return 0

    fs.clear_inode_cache()
    fs.flush_superblock()
    fs.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
