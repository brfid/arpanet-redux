#!/usr/bin/env python3
"""Test whether having ITS host 106 dial the PDP-11 guest first (host 176,
the network address IMP 62's hi2 has carried since the its_peer-pair.simh
ITS occupied it -- see docs/test-plan.md's "Host B must identify as octal
176") unblocks the guest's own later TELNET attempt to host 106, per the
RFNM-bookkeeping deadlock recorded in docs/research/imp11a-device.md
("The real root cause").

Rationale: the guest's ncpd only marks a remote host "up" (h_up_bm) when
it *receives* a host-host protocol message from that host -- see
hs_alive()'s callers in the pinned network-unix-v6 checkout's ncpd/hr_proc.c.
ITS's own UT (user TELNET) issuing a real RFC toward host 176 should reach
the guest's daemon as an inbound RFC regardless of whether ITS's own
connection attempt ever completes at the application level, and
ncpd/hr_proc.c's hr_rfc() calls hs_alive() for the sender. If that lands
before the guest calls chk_host(), chk_host() should see the host already
up and skip the defensive RST that otherwise consumes the RFNM slot the
real RFC needs.

Drives its_host's ITS console interactively (boot, DDT, login, UT) using
the same expect sequence proven in scripts/two-its-controller.py, then
reuses two-imp-its-pdp11-telnet.py's own PDP-11 guest sequence unchanged.

Research-phase tool: exploratory, not wired into any make target or test.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pexpect


def start_background(name, argv, cwd, log_path, env):
    log = open(log_path, "wb", buffering=0)
    print(f"[driver] starting {name}: {' '.join(str(a) for a in argv)} (cwd={cwd})",
          file=sys.stderr)
    proc = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                             env=env, start_new_session=True)
    return proc, log


def tail_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return needle in path.read_text(errors="replace")


def wait_for(path: Path, needle: str, timeout: float, label: str) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tail_contains(path, needle):
            print(f"[driver] {label}: saw {needle!r} in {path.name}", file=sys.stderr)
            return True
        time.sleep(1.0)
    print(f"[driver] {label}: TIMEOUT waiting for {needle!r} in {path.name}", file=sys.stderr)
    return False


def _main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", required=True, type=Path)
    p.add_argument("--h316", required=True, type=Path)
    p.add_argument("--pdp10-ka", required=True, type=Path)
    p.add_argument("--pdp11", required=True, type=Path)
    p.add_argument("--mini-root", required=True, type=Path)
    p.add_argument("--its-host-media", required=True, type=Path)
    p.add_argument("--results-dir", required=True, type=Path)
    p.add_argument("--pdp11-root-image", required=True, type=Path)
    p.add_argument("--pdp11-swap-image", required=True, type=Path)
    p.add_argument("--base-port", type=int, default=19200)
    p.add_argument("--host-number", default="106")
    p.add_argument("--guest-host-number", default="176",
                    help="octal host number ITS should dial to reach the "
                         "guest, per docs/test-plan.md's host176 convention "
                         "for IMP 62's hi2")
    p.add_argument("--pdp11-hi-convert", action="store_true",
                    help="retain the shared IMP 62 HI2 long-leader conversion "
                         "instead of using the PDP-11's native short leader")
    p.add_argument("--daemon-settle", type=float, default=12.0)
    p.add_argument("--its-dial-settle", type=float, default=20.0,
                    help="seconds to watch ITS's UT output after dialing "
                         "the guest, before moving on to the guest's own "
                         "telnet attempt")
    p.add_argument("--telnet-settle", type=float, default=25.0)
    args = p.parse_args()

    results = args.results_dir
    results.mkdir(parents=True, exist_ok=True)

    ports = {
        "BRFID_IMP6_MI_PORT": args.base_port + 1,
        "BRFID_IMP62_MI_PORT": args.base_port + 2,
        "BRFID_IMP6_HI_PORT": args.base_port + 3,
        "BRFID_HOST_A_IMP_PORT": args.base_port + 4,
        "BRFID_IMP62_HI_PORT": args.base_port + 5,
        "BRFID_HOST_B_IMP_PORT": args.base_port + 6,
    }
    env = os.environ.copy()
    env.update({k: str(v) for k, v in ports.items()})
    for k, v in ports.items():
        print(f"[driver] {k}={v}", file=sys.stderr)

    its_host_work = results / "host106"
    its_host_work.mkdir(exist_ok=True)
    for asset in ("dskdmp.rim", "rp03.0", "rp03.1", "rp03.2", "rp03.3"):
        shutil.copy(args.its_host_media / asset, its_host_work / asset)

    pdp11_work = results / "pdp11"
    (pdp11_work / "images").mkdir(parents=True, exist_ok=True)
    shutil.copy(args.pdp11_root_image, pdp11_work / "images" / "ncp_root.rl01")
    shutil.copy(args.pdp11_swap_image, pdp11_work / "images" / "ncp_swap.rl01")

    imp6_cfg = args.repo_root / "config/imp/its-pair/imp6.simh"
    imp62_cfg = args.repo_root / "config/imp/its-pair/imp62.simh"
    if not args.pdp11_hi_convert:
        # This shared configuration normally hosts ITS, which uses long
        # leaders.  The PDP-11 guest supplies and expects the old short
        # leader itself, so keep a run-local configuration without the
        # bidirectional HI2 conversion rather than changing the ITS config.
        imp62_cfg = results / "imp62-pdp11-noconvert.simh"
        imp62_text = (args.repo_root / "config/imp/its-pair/imp62.simh").read_text()
        expected = "set hi2 convert\n"
        if expected not in imp62_text:
            raise RuntimeError("IMP 62 configuration no longer has the expected HI2 conversion line")
        imp62_cfg.write_text(imp62_text.replace(expected, "set hi2 noconvert\n", 1))
    its_host_cfg = args.repo_root / "config/hosts/its106-pair.simh"

    procs = []
    imp6_proc, imp6_log = start_background(
        "imp6", [str(args.h316), str(imp6_cfg)], args.mini_root,
        results / "imp6.console.log", env)
    procs.append(("imp6", imp6_proc, imp6_log))
    imp62_proc, imp62_log = start_background(
        "imp62", [str(args.h316), str(imp62_cfg)], args.mini_root,
        results / "imp62.console.log", env)
    procs.append(("imp62", imp62_proc, imp62_log))

    time.sleep(2.0)

    print("[driver] starting host106 (ITS) interactively", file=sys.stderr)
    its_host_console = open(results / "host106.console.log", "w")
    its = pexpect.spawn(str(args.pdp10_ka), [str(its_host_cfg)], cwd=str(its_host_work),
                         timeout=60, encoding="utf-8", env=env)
    its.logfile = its_host_console

    wait_for(results / "imp6.console.log", "077400", 30, "imp6 modem light")
    wait_for(results / "imp62.console.log", "077400", 30, "imp62 modem light")
    wait_for(results / "imp6.console.log", "075400", 30, "imp6 host-link light")

    # Boot and start the guest's daemon FIRST -- it must already be
    # listening on /dev/ncpkernel before ITS dials it, or there is
    # nothing on the guest side to receive the inbound RFC and mark
    # host 106 up. Getting this ordering backwards was this script's
    # first bug: ITS's UT dial (confirmed by its own "CONNECT ISE0"
    # response) went out before smalldaemon existed to see it.
    print("[driver] settling 5s before attaching the PDP-11 guest", file=sys.stderr)
    time.sleep(5.0)

    pdp11_console = open(results / "pdp11.console.log", "w")
    child = pexpect.spawn(str(args.pdp11), cwd=str(pdp11_work), timeout=20,
                            encoding="utf-8", env=env)
    child.logfile = pdp11_console

    child.sendline("set cpu 11/34 256k")
    child.sendline("set rl0 rl01")
    child.sendline("set rl1 rl01")
    child.sendline("attach rl0 images/ncp_root.rl01")
    child.sendline("attach rl1 images/ncp_swap.rl01")
    child.sendline("set imp enabled")
    child.sendline(
        f"attach imp {ports['BRFID_HOST_B_IMP_PORT']}:127.0.0.1:{ports['BRFID_IMP62_HI_PORT']}")
    child.sendline(f"set debug -n {results / 'pdp11-imp-debug.log'}")
    child.sendline("set imp debug=reg;int;pkt")
    child.sendline("boot rl0")
    child.expect("!", timeout=15)
    time.sleep(0.5)
    child.send("green\r")
    child.expect("login:", timeout=30)
    time.sleep(0.5)
    child.send("root\r")
    child.expect("#", timeout=10)
    time.sleep(1.0)

    print("[driver] starting smalldaemon on the PDP-11 guest", file=sys.stderr)
    child.send("/usr/net/etc/smalldaemon &\r")
    child.expect("#", timeout=10)

    print(f"[driver] settling {args.daemon_settle}s for the daemon/IMP handshake",
          file=sys.stderr)
    time.sleep(args.daemon_settle)
    child.send("\r")
    try:
        child.expect("#", timeout=5)
    except pexpect.TIMEOUT:
        pass

    # Now that the guest's daemon is up and listening, drive ITS through
    # login and have it dial the guest (host 176) first. Each step below
    # waits past its own prompt before sending the next input -- SIMH's
    # emulated ITS can still be flushing output when pexpect's regex
    # matches, and sending too early interleaves keystrokes into ITS's own
    # echo (this is what produced the garbled "UT.71766"/"GUNNER
    # 0:login dbut" lines the first time this script ran without these
    # pauses).
    print("[driver] waiting for ITS system-job banner", file=sys.stderr)
    its.expect("SYSTEM JOB USING THIS CONSOLE", timeout=900)
    time.sleep(1.0)

    print("[driver] entering DDT on ITS", file=sys.stderr)
    its.send("\x1a")
    its.expect("Welcome to ITS!", timeout=120)
    time.sleep(1.0)
    its.send(":time\r")
    its.expect("The time is", timeout=60)
    its.expect(r"\r\n\*", timeout=30)
    time.sleep(1.0)

    print("[driver] waiting for automatic GUNNER login banner", file=sys.stderr)
    its.expect(r"LOGIN  GUNNER 0", timeout=180)
    time.sleep(2.0)
    its.send(":login db\r")
    its.expect(r"LOGIN  DB", timeout=30)
    time.sleep(2.0)

    print(f"[driver] dialing UT toward guest host {args.guest_host_number}", file=sys.stderr)
    its.send("ut")
    its.send("\x0b")
    its.expect(r"UT\.\d+", timeout=45)
    time.sleep(1.0)
    its.send(f"{args.guest_host_number}\r")

    print(f"[driver] watching ITS's UT output for {args.its_dial_settle}s", file=sys.stderr)
    deadline = time.time() + args.its_dial_settle
    while time.time() < deadline:
        try:
            its.expect([pexpect.TIMEOUT], timeout=2)
        except pexpect.TIMEOUT:
            pass

    print(f"[driver] running guest telnet: telnet - -h {args.host_number}", file=sys.stderr)
    child.send(f"/usr/bin/telnet - -h {args.host_number}\r")

    print(f"[driver] watching for {args.telnet_settle}s of console output", file=sys.stderr)
    deadline = time.time() + args.telnet_settle
    while time.time() < deadline:
        try:
            child.expect([r"\*", "#", pexpect.TIMEOUT], timeout=3)
        except pexpect.TIMEOUT:
            pass
        time.sleep(0.5)

    print("[driver] sending a command line into the connection: 'time\\r'", file=sys.stderr)
    child.send("time\r")
    time.sleep(8.0)
    child.send("\r")
    time.sleep(3.0)

    print("[driver] closing telnet session", file=sys.stderr)
    child.send("close\r")
    time.sleep(2.0)
    child.send("bye\r")
    try:
        child.expect("#", timeout=10)
    except pexpect.TIMEOUT:
        pass

    child.sendcontrol("e")
    time.sleep(0.5)
    child.sendline("quit")
    try:
        child.expect(pexpect.EOF, timeout=15)
    except pexpect.TIMEOUT:
        child.close(force=True)
    pdp11_console.close()

    print("[driver] stopping ITS", file=sys.stderr)
    try:
        its.sendcontrol("e")
        time.sleep(0.5)
        its.sendline("quit")
        its.expect(pexpect.EOF, timeout=15)
    except (pexpect.TIMEOUT, OSError):
        its.close(force=True)
    its_host_console.close()

    print("[driver] stopping imp6/imp62", file=sys.stderr)
    for name, proc, log in procs:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
    time.sleep(1.0)
    for name, proc, log in procs:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        log.close()

    print(f"[driver] done. results in {results}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
