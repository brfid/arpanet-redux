#!/usr/bin/env python3
"""Extract V6 filesystems directly from a SIMH .tap tape image into disk
image files, at the host level, with no PDP-11 execution involved.

Background: the documented eblanton/unix-v6-install method for this
relies on an in-simulator "tmrk" meta-command that does not exist in
Open SIMH and hangs forever. A SIMH .tap record is just a
length-prefixed byte range, so the filesystems it carries can be read
out directly. See docs/research/imp11a-device.md for how this was
discovered and verified.

The historical Network UNIX / Ancient-Unix V6 distribution tape (as
produced by the eblanton project's enblock tool from the raw TUHS
tape image) lays out as: a 100-record bootstrap area, then one or
more 4,000-record filesystems back to back, each block a fixed 512
bytes. Defaults below match that tape's root/source/doc layout;
override with --target for a differently laid out tape.

Research-phase tool: exploratory, not wired into any make target or
test.
"""
from __future__ import annotations

import argparse
import struct


def read_tap_records(data: bytes) -> list[tuple[int, int]]:
    """Return (byte_offset, length) for each data record in a SIMH .tap
    image, stopping at the first tape mark or end-of-medium marker."""
    pos = 0
    records = []
    while pos < len(data):
        (length,) = struct.unpack_from("<I", data, pos)
        pos += 4
        if length == 0 or length == 0xFFFFFFFF:
            break
        reclen = length & 0x7FFFFFFF
        start = pos
        pos += reclen
        if reclen % 2:
            pos += 1  # odd-length records are word-padded
        pos += 4  # trailing repeated length
        records.append((start, reclen))
    return records


def extract(tap_path: str, out_path: str, tape_offset: int, count: int,
            block_size: int = 512) -> None:
    data = open(tap_path, "rb").read()
    records = read_tap_records(data)
    with open(out_path, "r+b") as out:
        for i in range(count):
            start, reclen = records[tape_offset + i]
            if reclen != block_size:
                raise ValueError(
                    f"record {tape_offset + i} is {reclen} bytes, "
                    f"expected {block_size}"
                )
            out.seek(i * block_size)
            out.write(data[start:start + block_size])


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tap", help="SIMH .tap image to read")
    parser.add_argument(
        "--target", action="append", nargs=3, metavar=("OUT_IMAGE", "TAPE_OFFSET", "COUNT"),
        help="one output image: pre-zeroed target path, starting tape "
             "record offset, and record count. May be repeated. "
             "Defaults to the root/source/doc layout at offsets "
             "100/4100/8100, 4000 records each, if omitted entirely.",
    )
    args = parser.parse_args()

    targets = args.target or [
        ("pristine_root.rk05", "100", "4000"),
        ("pristine_src.rk05", "4100", "4000"),
        ("pristine_doc.rk05", "8100", "4000"),
    ]

    for out_path, tape_offset, count in targets:
        extract(args.tap, out_path, int(tape_offset), int(count))
        print(f"wrote {count} blocks into {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
