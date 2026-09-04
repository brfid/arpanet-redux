#!/usr/bin/env python3
"""Build a working guest TELNET client from the preserved NOSC source
and install it, in place, into an existing green/unix root filesystem
image, using V6's own `cc` inside the simulator. See "Building a guest
TELNET client from source" in docs/research/imp11a-device.md for the
full record of why each step here is needed; this reproduces that
work.

Three archive-fidelity gaps had to be bridged, none by inventing new
values:

- ncpp/tel-u/telnet.c in the checked-out tree is a same-sized but
  entirely zero-filled file (a real preservation defect, not a
  boot/attach mistake); ncpp/tel-u/telnet.c.org, 9 bytes smaller, is
  intact source and is what this script actually compiles.
- telnet.c.org expects headers named mkcharset.h and openparms.h at
  /h/net/; the checked-out tree has no files by those names, but
  h/net/mcharset.h and h/net/open.h are byte-for-byte the same
  content under different preservation-copy filenames (confirmed by
  reading their defined symbols against telnet.c.org's own #include
  and struct usage, not by name matching alone).
- telnet.c.org and usrtelnetin.c reference TELNET protocol constants
  in lowercase (tel_iac, otel_echo, to_echo, ...); the preserved
  h/net/telnet.h defines only the uppercase forms (TEL_IAC, ...) --
  a real historical header/source revision mismatch. This script
  appends a lowercase-alias block to its staged copy of telnet.h,
  aliasing to the existing uppercase values rather than restating
  them, and installs that staged copy at /h/net/telnet.h in the
  guest image.
- usrtelnetin.c selects the correct WONT response for a received DONT
  command but omits the switch break, so every valid DONT falls into
  its generic protocol-error diagnostic. This script adds only that
  missing break to its staged copy and fails closed if the pinned
  source no longer has the exact known fallthrough shape.

usrtelnetin.c (the companion process netopen() forks to read the
network and write the terminal) is built too, since a real two-way
session needs it; its "../h/telnet.h" include is rewritten to the
same /h/net/telnet.h path telnet.c.org uses, staged copy only.

/dev/net/anyhost -- the device NCP application opens use to request a
connection by host number (see struct openparams in net/open.h and
netopen() in ncpk/nopcls.c) -- needs a specific kind of device node.
Disassembling the running green kernel's open1() (symbol addresses
from its own a.out symbol table) showed the dispatch to the kernel's
netopen() is gated on the *major* byte of the target inode's device
number reading as a negative signed byte, i.e. octal 0200-0376: a
small major like the ncpkernel's 5 falls through to the ordinary
cdevsw path instead and collides with the already-open ncpkernel
device (ENCP2), which is what "Host is Unavailable" turned out to
mean the first time this was tried. --anyhost-major/--anyhost-minor
default to 0200/0106 (octal 106 = host 106 per docs/test-plan.md's
own convention); minor is advisory only, since a real connect always
passes an explicit -h.

Research-phase tool: exploratory, not wired into any make target or
test.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simh_shutdown import quit_simh_cleanly  # noqa: E402
from v6fs import V6FS  # noqa: E402

LOWERCASE_ALIAS_BLOCK = """
/* lowercase compatibility aliases: this NOSC-preserved telnet.c and
   usrtelnetin.c use lowercase tel_ and otel_ names for these same
   constants; this h/net/telnet.h copy (also NOSC-preserved) only
   defines the uppercase TEL_ and oTEL_ forms. Bridging alias block,
   values taken from the definitions above, not invented. */
#define tel_iac\t\tTEL_IAC
#define tel_dont\tTEL_DONT
#define tel_do\t\tTEL_DO
#define tel_wont\tTEL_WONT
#define tel_will\tTEL_WILL
#define tel_sb\t\tTEL_SB
#define tel_ga\t\tTEL_GA
#define tel_el\t\tTEL_EL
#define tel_ec\t\tTEL_EC
#define tel_ayt\t\tTEL_AYT
#define tel_ao\t\tTEL_AO
#define tel_ip\t\tTEL_IP
#define tel_break\tTEL_BREAK
#define tel_dm\t\tTEL_DM
#define tel_nop\t\tTEL_NOP
#define tel_se\t\tTEL_SE
#define otel_dm\t\toTEL_DM
#define otel_break\toTEL_BREAK
#define otel_nop\toTEL_NOP
#define otel_noecho\tOTEL_NOECHO
#define otel_echo\toTEL_ECho
#define otel_hide\toTEL_HIDE
#define to_echo\t\tTO_ECHO
"""


def repair_usrtelnetin_dont_fallthrough(source: str) -> str:
    """Add the one missing break in the pinned DONT negotiation branch."""

    fallthrough = (
        "\tcase tel_dont:\tresponse = tel_wont;\n"
        "\n"
        "\tdefault:"
    )
    repaired = (
        "\tcase tel_dont:\tresponse = tel_wont;\n"
        "\t\t\tbreak;\n"
        "\n"
        "\tdefault:"
    )
    if source.count(fallthrough) != 1:
        raise ValueError(
            "pinned usrtelnetin.c lacks the unique expected DONT fallthrough"
        )
    return source.replace(fallthrough, repaired, 1)


def stage_sources(network_unix_v6_root: Path, stage_dir: Path) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    ncpp = network_unix_v6_root / "nosc-files" / "ncpp"
    h_net = network_unix_v6_root / "nosc-files" / "h" / "net"

    telnet_h = (h_net / "telnet.h").read_text()
    (stage_dir / "telnet.h").write_text(telnet_h + LOWERCASE_ALIAS_BLOCK)

    shutil.copy(h_net / "mcharset.h", stage_dir / "mkcharset.h")
    shutil.copy(h_net / "open.h", stage_dir / "openparms.h")
    shutil.copy(ncpp / "tel-u" / "telnet.c.org", stage_dir / "telnet.c")

    usrtelnetin = (ncpp / "tel-u" / "usrtelnetin.c").read_text()
    usrtelnetin = usrtelnetin.replace(
        '#include "../h/telnet.h"', '#include "/h/net/telnet.h"'
    )
    usrtelnetin = repair_usrtelnetin_dont_fallthrough(usrtelnetin)
    (stage_dir / "usrtelnetin.c").write_text(usrtelnetin)


def inject(image: Path, stage_dir: Path, anyhost_major: int, anyhost_minor: int) -> None:
    fs = V6FS(str(image))
    fs.mkdir("/h")
    fs.mkdir("/h/net")
    fs.mkdir("/dev/net")
    fs.put_file("/h/net", "telnet.h", (stage_dir / "telnet.h").read_bytes())
    fs.put_file("/h/net", "mkcharset.h", (stage_dir / "mkcharset.h").read_bytes())
    fs.put_file("/h/net", "openparms.h", (stage_dir / "openparms.h").read_bytes())
    fs.put_file("/tmp", "telnet.c", (stage_dir / "telnet.c").read_bytes())
    fs.put_file("/tmp", "usrtelnetin.c", (stage_dir / "usrtelnetin.c").read_bytes())
    fs.mknod("/dev/net", "anyhost", "c", anyhost_major, anyhost_minor, mode=0o666)
    # Each of the calls above only allocates blocks/inodes in memory;
    # the on-disk superblock and the kernel's in-core free-inode cache
    # both need to see the result before the guest boots, or the
    # kernel's own free-list state goes stale relative to the blocks
    # this script actually used and it reports spurious "no space".
    fs.clear_inode_cache()
    fs.flush_superblock()
    fs.save()


def build_in_guest(pdp11: Path, workdir: Path, console_log: Path, settle: float) -> None:
    import pexpect

    console = open(console_log, "w")
    child = pexpect.spawn(str(pdp11), cwd=str(workdir), timeout=30, encoding="utf-8")
    child.logfile = console

    child.sendline("set cpu 11/34 256k")
    child.sendline("set rl0 rl01")
    child.sendline("set rl1 rl01")
    child.sendline("attach rl0 images/ncp_root.rl01")
    child.sendline("attach rl1 images/ncp_swap.rl01")
    child.sendline("boot rl0")
    child.expect("!", timeout=15)  # the RL bootstrap prompts with "!", not "@"
    time.sleep(0.5)
    child.send("green\r")
    child.expect("login:", timeout=30)
    time.sleep(0.5)
    child.send("root\r")
    child.expect("#", timeout=10)
    time.sleep(1.0)

    child.send("chdir /tmp\r")
    child.expect("#", timeout=10)

    print("[build] compiling telnet.c", file=sys.stderr)
    child.send("cc -O -n -x telnet.c\r")
    child.expect("#", timeout=180)
    time.sleep(0.3)
    child.send("mv a.out telnet\r")
    child.expect("#", timeout=10)

    print("[build] compiling usrtelnetin.c", file=sys.stderr)
    child.send("cc -O -n -x usrtelnetin.c\r")
    child.expect("#", timeout=180)
    time.sleep(0.3)
    child.send("mv a.out usrtelnetin\r")
    child.expect("#", timeout=10)

    child.send("ls -l telnet usrtelnetin\r")
    child.expect("#", timeout=10)

    child.send("cp telnet /usr/bin/telnet\r")
    child.expect("#", timeout=10)
    child.send("chmod 1755 /usr/bin/telnet\r")
    child.expect("#", timeout=10)
    child.send("cp usrtelnetin /usr/bin/usrtelnetin\r")
    child.expect("#", timeout=10)
    child.send("chmod 1755 /usr/bin/usrtelnetin\r")
    child.expect("#", timeout=10)
    child.send("ls -l /usr/bin/telnet /usr/bin/usrtelnetin /dev/net/anyhost\r")
    child.expect("#", timeout=10)
    child.send("sync\r")
    child.expect("#", timeout=10)
    time.sleep(settle)

    print("[build] shutting down cleanly", file=sys.stderr)
    try:
        quit_simh_cleanly(child, pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
        console.close()


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--network-unix-v6-root", required=True, type=Path,
        help="checkout of pdp11/network-unix-v6 (pins/sources.lock.toml)")
    p.add_argument(
        "--pdp11", required=True, type=Path,
        help="Open SIMH pdp11 binary built with the IMP11-A device")
    p.add_argument(
        "--root-image", required=True, type=Path,
        help="green/unix root RL01 image to modify in place (a copy, "
             "not the original -- this script writes to it directly)")
    p.add_argument(
        "--swap-image", required=True, type=Path,
        help="matching swap RL01 image (read-only for this step, but "
             "the guest needs it attached to boot)")
    p.add_argument(
        "--work-dir", required=True, type=Path,
        help="scratch directory for staged headers/source and the guest console log")
    p.add_argument(
        "--anyhost-major", type=lambda s: int(s, 8), default=0o200,
        help="octal major for /dev/net/anyhost (default 0200; must be "
             "0200-0376 octal, see module docstring)")
    p.add_argument(
        "--anyhost-minor", type=lambda s: int(s, 8), default=0o106,
        help="octal minor for /dev/net/anyhost, advisory only")
    p.add_argument(
        "--settle", type=float, default=1.0,
        help="seconds to wait after sync before shutting down")
    args = p.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = args.work_dir / "stage"
    stage_sources(args.network_unix_v6_root, stage_dir)

    guest_dir = args.work_dir / "guest"
    (guest_dir / "images").mkdir(parents=True, exist_ok=True)
    root_image = guest_dir / "images" / "ncp_root.rl01"
    swap_image = guest_dir / "images" / "ncp_swap.rl01"
    shutil.copy(args.root_image, root_image)
    shutil.copy(args.swap_image, swap_image)

    print(f"[build] injecting headers/source into {root_image}", file=sys.stderr)
    inject(root_image, stage_dir, args.anyhost_major, args.anyhost_minor)

    build_in_guest(
        args.pdp11, guest_dir,
        args.work_dir / "build-guest-telnet.console.log", args.settle)

    print(f"[build] done. built root image: {root_image}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
