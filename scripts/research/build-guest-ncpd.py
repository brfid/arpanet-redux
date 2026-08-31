#!/usr/bin/env python3
"""Rebuild ncpd's Largedaemon from preserved source, in-guest, with
narrowly-scoped ``PBTRACE`` records for host 106 around protocol
queueing, transmission, and control-link RFNM processing.  The records
expose the relationship between h_pb_sent and h_pb_q without changing
the external simulator, topology, firmware, ITS configuration, or
adapter behavior.

An earlier version of this builder cleared rfnm_bm immediately after
chk_host() sent its defensive RST.  That compatibility patch was based
on runs made before the IMP11-A output-order correction, when the RST
never reached the addressed IMP and therefore could not earn an RFNM.
The exact ``imp11a-telnet-pbtrace-20260831T160605Z`` rerun against the
corrected adapter proved that the clear changed only rfnm_bm: it left
the sent RST in h_pb_q and h_pb_sent, so send_pro() counted the RST a
second time beside the RFC and ir_rfnm() later saw three sent buffers
but only two queue elements.  This builder no longer patches
kr_dcode.c.  The corrected adapter returns the RST's real RFNM, allowing
the preserved daemon to retire that buffer before sending the queued
RFC through its original accounting path.

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

# Exact preserved-source anchors for the staged evidence trace.  The
# external source remains in the laboratory; this repository retains
# only the small mechanical instrumentation insertions below.
NCPD_PATCHES = {
    "send_pro.c": [
        (
            "\t/* check rfnm bit, return if set */\n"
            "\tif ( bit_on(&rfnm_bm[0],host) )\t\t/* rfnm outstanding for host? */\n",
            "\tif (host == 0106)\n"
            "\t\tprintf(\"PBTRACE send-enter h=%o sent=%d q=%o first=%o rfnm=%d\\n\",\n"
            "\t\t\thost,h_pb_sent[host],h_pb_q[host],\n"
            "\t\t\th_pb_q[host] ? h_pb_q[host]->pb_link : 0,\n"
            "\t\t\tbit_on(&rfnm_bm[0],host) != 0);\n"
            "\t/* check rfnm bit, return if set */\n"
            "\tif ( bit_on(&rfnm_bm[0],host) )\t\t/* rfnm outstanding for host? */\n",
        ),
        (
            "\t\t\th_pb_sent[host]++;\t/* inc probufs sent count */\n",
            "\t\t\th_pb_sent[host]++;\t/* inc probufs sent count */\n"
            "\t\t\tif (host == 0106)\n"
            "\t\t\t\tprintf(\"PBTRACE send-copy h=%o op=%o sent=%d q=%o\\n\",\n"
            "\t\t\t\t\thost,pb_p->pb_text[0]&0377,\n"
            "\t\t\t\t\th_pb_sent[host],h_pb_q[host]);\n",
        ),
        (
            "\tq_enter(&h_pb_q[host],pb_p);\t/* enter probuf in host's probuf q */\n"
            "\tpro2send = 1;\t\t\t/* set send flag */\n",
            "\tq_enter(&h_pb_q[host],pb_p);\t/* enter probuf in host's probuf q */\n"
            "\tif (host == 0106)\n"
            "\t\tprintf(\"PBTRACE queue h=%o op=%o sent=%d q=%o first=%o\\n\",\n"
            "\t\t\thost,pb_p->pb_text[0]&0377,h_pb_sent[host],\n"
            "\t\t\th_pb_q[host],h_pb_q[host]->pb_link);\n"
            "\tpro2send = 1;\t\t\t/* set send flag */\n",
        ),
    ],
    "ir_proc.c": [
        (
            "\th_pb_rtry[h] = 0;\t\t/* set retry count to zero */\n"
            "\treset_bit(&rfnm_bm[0],h);\t/* reset host's rfnm bit */\n",
            "\tif (h == 0106)\n"
            "\t\tprintf(\"PBTRACE rfnm-enter h=%o sent=%d q=%o first=%o\\n\",\n"
            "\t\t\th,h_pb_sent[h],h_pb_q[h],\n"
            "\t\t\th_pb_q[h] ? h_pb_q[h]->pb_link : 0);\n"
            "\th_pb_rtry[h] = 0;\t\t/* set retry count to zero */\n"
            "\treset_bit(&rfnm_bm[0],h);\t/* reset host's rfnm bit */\n",
        ),
        (
            "\twhile ( h_pb_sent[h] )\t\t/* loop while probufs sent != 0 */\n"
            "\t{\n"
            "\t\tq_enter(&pb_fr_q,q_dlink(&h_pb_q[h]));\n",
            "\twhile ( h_pb_sent[h] )\t\t/* loop while probufs sent != 0 */\n"
            "\t{\n"
            "\t\tif (h == 0106)\n"
            "\t\t\tprintf(\"PBTRACE rfnm-free h=%o sent=%d q=%o first=%o\\n\",\n"
            "\t\t\t\th,h_pb_sent[h],h_pb_q[h],\n"
            "\t\t\t\th_pb_q[h] ? h_pb_q[h]->pb_link : 0);\n"
            "\t\tq_enter(&pb_fr_q,q_dlink(&h_pb_q[h]));\n",
        ),
        (
            "\tif ( h_pb_q[h] != 0 )\t\t/* still have prbufs to send? */\n",
            "\tif (h == 0106)\n"
            "\t\tprintf(\"PBTRACE rfnm-done h=%o sent=%d q=%o\\n\",\n"
            "\t\t\th,h_pb_sent[h],h_pb_q[h]);\n"
            "\tif ( h_pb_q[h] != 0 )\t\t/* still have prbufs to send? */\n",
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
