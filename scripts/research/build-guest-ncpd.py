#!/usr/bin/env python3
"""Rebuild ncpd's Largedaemon from preserved source, in-guest, with a
one-line fix for the RFNM-bookkeeping deadlock recorded in
docs/research/imp11a-device.md ("The real root cause"): chk_host()'s
defensive RST, sent before every outgoing connection attempt to a host
not yet known to be up, sets the host's rfnm_bm bit via its own
send_pro() call inside ncpd/send_pro.c; the real RFC that kr_ouicp()
(the netopen()-driven path the guest TELNET client uses) queues right
afterward never flushes, because send_pro()'s own first line refuses
to send anything else to a host whose rfnm_bm bit is set, and nothing
in this environment (confirmed: neither the guest's own daemon nor
this project's H316 transport code) ever clears that bit again. Two
prior attempts to work around this without touching the preserved
daemon -- waiting far longer, and having ITS dial the guest first so
it would already look "up" -- were tried and recorded as not working
before this patch.

The fix: clear the just-set rfnm_bm bit immediately after chk_host()
returns, at its two "about to open a new connection" call sites
(kr_ouicp, and kr_odrct, the direct-socket path with the identical
structure) in ncpd/kr_dcode.c -- not at its third call site in
rst_all(), which is startup housekeeping with no immediately-following
send to protect, so leaving it alone changes no other behavior.

Builds all fourteen ncpd/*.c files plus skt_off.s and swab.s with V6's
own cc, entirely in-guest, reusing the technique already proven for
the guest TELNET client (see build-guest-telnet.py): this source's own
historical build recipe (ncpd/compile) expects NOSC's own
/nosc/conf/cc -L search path spanning ncpd/ and h/, which does not
exist on this guest image, so every header this source needs is
staged flat into one directory instead of trying to reproduce that
local path convention. Installs the result over the existing
prelinked /usr/net/etc/Largedaemon (smalldaemon execv()s that same
path, so it needs no separate rebuild).

One real archive gap turned up compiling this source, not caused by
the patch above: ncpd/send_pro.c's rst_all() calls getl() (read one
line from a struct io_buf) to parse /usr/net/hnames, and no
definition of getl() exists anywhere in this preserved tree -- it
must have lived in a local NOSC utility library (plausibly the "-lj"
this source's own linkit recipe links against) that was never
captured. Left unresolved, V6's ld still produces an a.out but with
an "Undefined: _getl" this guest's exec() then refuses to run at all
(smalldaemon's own "Exec of large daemon failed" is what that looks
like from the console) -- so this is fatal here even though rst_all()
only reaches getl() when /usr/net/hnames exists (it does not on this
image; fopen() fails first and that whole loop is skipped at
runtime). GETL_STUB below is a minimal, clearly-marked stand-in
supplying only what the linker needs, not a reconstruction of NOSC's
real one -- correct on this image only because the code path that
would call it for real is never reached here.

Research-phase tool: exploratory, not wired into any make target or
test.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import pexpect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v6fs import V6FS  # noqa: E402

NCPD_C_FILES = [
    "1main.c", "kr_dcode.c", "ir_proc.c", "hr_proc.c",
    "assign.c", "files.c", "hstat.c", "kwrite.c",
    "send_pro.c", "skt_oper.c", "skt_util.c",
    "so_unm.c", "logstat.c", "util.c",
]
NCPD_S_FILES = ["skt_off.s", "swab.s"]
NCPD_H_FILES = [
    "files.h", "globvar.h", "hhi.h", "hstlnk.h", "impi.h",
    "kread.h", "kwrite.h", "leader.h", "measure.h", "probuf.h",
    "socket.h",
]
# Not under ncpd/ in the preserved tree -- these live in the shared h/
# directory (matching the same "system-wide headers live one level up"
# layout build-guest-telnet.py already navigated for net/*.h).
SHARED_H_FILES = ["io_buf.h", "param.h", "user.h"]

# brfid: linker-only stand-in for the missing getl() -- see the module
# docstring for why this is safe on this image and what it is not.
GETL_STUB_C = """/* brfid: minimal stand-in for a missing archive utility.
 * See build-guest-ncpd.py's own module docstring for why this exists
 * and why an unconditional failure return is correct here: rst_all()
 * (send_pro.c) only calls getl() after a successful fopen() of
 * /usr/net/hnames, which does not exist on this image, so this body
 * is never actually reached at runtime -- it exists purely to give
 * the linker a definition to resolve. Not a reconstruction of NOSC's
 * real getl().
 */
getl(line, fbuf)
char *line;
int *fbuf;
{
\treturn(-1);
}
"""

# The exact two lines this patches, both call sites for a fresh
# outbound connection attempt. Reproduced here only as literal
# search anchors for a mechanical one-line insertion, the same way
# build-guest-telnet.py's own usrtelnetin.c include-path rewrite
# already does -- see NCPD_PATCHES below for what each becomes.
NCPD_PATCHES = {
    "kr_dcode.c": [
        (
            "#include\t\"globvar.h\"\n"
            "#include\t\"impi.h\"\n",
            "#include\t\"globvar.h\"\n"
            "#include\t\"probuf.h\"\t/* brfid: for rfnm_bm, needed by the\n"
            "\t\t\t\t   reset_bit() calls added below -- every\n"
            "\t\t\t\t   other file that touches rfnm_bm already\n"
            "\t\t\t\t   pulls this in; kr_dcode.c never had to\n"
            "\t\t\t\t   before now. */\n"
            "#include\t\"impi.h\"\n",
        ),
        (
            "\tif ( host != 0 )\t/* host not wild? */\n"
            "\t\tchk_host();\n",
            "\tif ( host != 0 )\t/* host not wild? */\n"
            "\t{\n"
            "\t\tchk_host();\n"
            "\t\t/* brfid: chk_host()'s own send_pro() call sets\n"
            "\t\t * rfnm_bm for this host as a side effect of\n"
            "\t\t * sending its defensive reset; left set, it\n"
            "\t\t * blocks the real request this function goes on\n"
            "\t\t * to send. Nothing in this environment ever\n"
            "\t\t * clears rfnm_bm on its own for a host that\n"
            "\t\t * never answers, so clear it here instead of\n"
            "\t\t * leaving the connection permanently queued and\n"
            "\t\t * unsent. See docs/research/imp11a-device.md,\n"
            "\t\t * \"The real root cause\". */\n"
            "\t\treset_bit(&rfnm_bm[0],host);\n"
            "\t}\n",
        ),
        (
            "\tchk_host();\t\t\t\t/* check if host is up and take\n"
            "\t\t\t\t\t\t   appropriate action */\n",
            "\tchk_host();\t\t\t\t/* check if host is up and take\n"
            "\t\t\t\t\t\t   appropriate action */\n"
            "\t/* brfid: see the matching comment in kr_odrct() above --\n"
            "\t * same fix, same reason. */\n"
            "\treset_bit(&rfnm_bm[0],host);\n",
        ),
    ],
}


def stage_sources(network_unix_v6_root: Path, stage_dir: Path) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    ncpd = network_unix_v6_root / "nosc-files" / "ncpd"
    h = network_unix_v6_root / "nosc-files" / "h"

    for name in NCPD_C_FILES + NCPD_S_FILES + NCPD_H_FILES:
        shutil.copy(ncpd / name, stage_dir / name)
    for name in SHARED_H_FILES:
        shutil.copy(h / name, stage_dir / name)
    (stage_dir / "getl_stub.c").write_text(GETL_STUB_C)

    for filename, patches in NCPD_PATCHES.items():
        path = stage_dir / filename
        text = path.read_text()
        for old, new in patches:
            if old not in text:
                raise RuntimeError(
                    f"{filename}: expected anchor text not found -- "
                    f"preserved source may not match what this patch "
                    f"was written against: {old!r}")
            text = text.replace(old, new, 1)
        path.write_text(text)


def inject(image: Path, stage_dir: Path) -> None:
    fs = V6FS(str(image))
    fs.mkdir("/tmp/ncpd")
    for path in sorted(stage_dir.iterdir()):
        fs.put_file("/tmp/ncpd", path.name, path.read_bytes())
    fs.clear_inode_cache()
    fs.flush_superblock()
    fs.save()


def build_in_guest(pdp11: Path, workdir: Path, console_log: Path, settle: float) -> None:
    console = open(console_log, "w")
    child = pexpect.spawn(str(pdp11), cwd=str(workdir), timeout=60, encoding="utf-8")
    child.logfile = console

    child.sendline("set cpu 11/34 256k")
    child.sendline("set rl0 rl01")
    child.sendline("set rl1 rl01")
    child.sendline("attach rl0 images/ncp_root.rl01")
    child.sendline("attach rl1 images/ncp_swap.rl01")
    child.sendline("boot rl0")
    child.expect("!", timeout=15)
    time.sleep(0.5)
    child.send("green\r")
    child.expect("login:", timeout=30)
    time.sleep(0.5)
    child.send("root\r")
    child.expect("#", timeout=10)
    time.sleep(1.0)

    child.send("chdir /tmp/ncpd\r")
    child.expect("#", timeout=10)

    for name in ("skt_off", "swab"):
        print(f"[build] assembling {name}.s", file=sys.stderr)
        child.send(f"as {name}.s\r")
        child.expect("#", timeout=60)
        child.send(f"mv a.out {name}.o\r")
        child.expect("#", timeout=10)

    all_c_files = NCPD_C_FILES + ["getl_stub.c"]
    c_files = " ".join(all_c_files)
    print(f"[build] compiling {len(all_c_files)} ncpd sources (this takes a while)",
          file=sys.stderr)
    child.send(f"cc -O -c {c_files}\r")
    child.expect("#", timeout=600)

    print("[build] listing produced object files", file=sys.stderr)
    child.send("ls -l *.o\r")
    child.expect("#", timeout=15)

    # No -n here: ncpd/linkit (this source's own historical link recipe)
    # calls ld directly with no -n either, producing a normal (impure)
    # a.out. A first attempt at -n -x (matching build-guest-telnet.py's
    # single-file build, which does compile and link in one step) linked
    # without any linker error but produced a "separate I&D" binary this
    # guest's exec() refused to run at all -- smalldaemon's own "Exec of
    # large daemon failed" is what that looks like from the console.
    # Matching the real recipe's plain link is the current attempt at
    # fixing that; see docs/research/imp11a-device.md for whether it did.
    o_files = " ".join(f"{Path(name).stem}.o" for name in all_c_files) + " skt_off.o swab.o"
    print("[build] linking Largedaemon", file=sys.stderr)
    child.send(f"cc -O -x {o_files}\r")
    child.expect("#", timeout=120)
    child.send("ls -l a.out\r")
    child.expect("#", timeout=15)

    child.send("cp a.out /usr/net/etc/Largedaemon\r")
    child.expect("#", timeout=10)
    # ncpd/linkit's own install step does exactly this three-command
    # sequence. chown/chgrp matter, not just cosmetically: smalldaemon.c
    # calls setuid(1) before exec'ing this binary, so under mode 544
    # (owner-execute only) it must be owned by that same uid or the
    # exec fails with permission denied -- which is what "Exec of large
    # daemon failed" turned out to be the first two times this build
    # produced an otherwise-valid a.out and just chmod 544'd it while
    # still owned by root.
    child.send("chown daemon /usr/net/etc/Largedaemon\r")
    child.expect("#", timeout=10)
    child.send("chgrp system /usr/net/etc/Largedaemon\r")
    child.expect("#", timeout=10)
    child.send("chmod 544 /usr/net/etc/Largedaemon\r")
    child.expect("#", timeout=10)
    child.send("ls -l /usr/net/etc/Largedaemon\r")
    child.expect("#", timeout=10)
    child.send("sync\r")
    child.expect("#", timeout=10)
    time.sleep(settle)

    print("[build] shutting down cleanly", file=sys.stderr)
    child.sendcontrol("e")
    time.sleep(0.5)
    child.sendline("quit")
    try:
        child.expect(pexpect.EOF, timeout=15)
    except pexpect.TIMEOUT:
        print("[build] simh did not exit on its own, forcing", file=sys.stderr)
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
             "not the original) -- normally the output of "
             "build-guest-telnet.py, so the guest telnet client and "
             "the fixed daemon end up on the same image")
    p.add_argument(
        "--swap-image", required=True, type=Path,
        help="matching swap RL01 image")
    p.add_argument(
        "--work-dir", required=True, type=Path,
        help="scratch directory for staged sources and the guest console log")
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

    print(f"[build] injecting ncpd sources into {root_image}", file=sys.stderr)
    inject(root_image, stage_dir)

    build_in_guest(
        args.pdp11, guest_dir,
        args.work_dir / "build-guest-ncpd.console.log", args.settle)

    print(f"[build] done. built root image: {root_image}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
