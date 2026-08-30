#!/usr/bin/env python3
"""Boot the NOSC green/unix kernel under a pdp11 binary built with the
IMP11-A device (see docs/research/imp11a-device.md), log in, and start
smalldaemon (which execs Largedaemon on the same file descriptor)
against the live /dev/ncpkernel. This reproduces the verification
recorded in "Starting the NCP daemon" in that doc: a manual smoke
check, not an automated test with pass/fail assertions.

Requires a pdp11 build with the DEBTAB debug support described in that
doc (SET IMP DEBUG=REG;INT;PKT), and root/swap RL01 images prepared as
described in "Booting green/unix under this device" in the same doc.

--udp-endpoint is passed straight to `ATTACH IMP`. Two mistakes are
easy to make and are recorded in the doc: an endpoint with equal local
and remote ports makes the device receive its own transmissions back
as if a peer were attached, and a bare `localhost` in the endpoint can
resolve to IPv6 `::1`, silently missing an IPv4-bound peer process and
producing confusing "Console Telnet connection lost" send errors. Use
distinct ports and an explicit 127.0.0.1 for a real external peer (see
udp-test-peer.py in this directory for a minimal one).

Research-phase tool: exploratory, not wired into any make target or
test.
"""
from __future__ import annotations

import argparse
import sys
import time

import pexpect


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simh", required=True, help="path to the pdp11 binary")
    parser.add_argument("--workdir", required=True,
                         help="directory to run pdp11 from (image/log paths "
                              "below are relative to this)")
    parser.add_argument("--root-image", default="images/ncp_root.rl01")
    parser.add_argument("--swap-image", default="images/ncp_swap.rl01")
    parser.add_argument("--kernel", default="green")
    parser.add_argument("--cpu", default="11/34 256k")
    parser.add_argument("--udp-endpoint", required=True,
                         help="ATTACH IMP argument, e.g. 9000:127.0.0.1:9002 "
                              "for a real peer bound to 127.0.0.1:9002")
    parser.add_argument("--debug-log", required=True,
                         help="SET DEBUG destination for the register/"
                              "interrupt/packet trace")
    parser.add_argument("--console-log", required=True)
    parser.add_argument("--settle", type=float, default=20.0,
                         help="seconds to let the daemon run before quitting")
    args = parser.parse_args()

    console = open(args.console_log, "w")

    child = pexpect.spawn(args.simh, cwd=args.workdir, timeout=20, encoding="utf-8")
    child.logfile = console

    child.sendline(f"set cpu {args.cpu}")
    child.sendline("set rl0 rl01")
    child.sendline("set rl1 rl01")
    child.sendline(f"attach rl0 {args.root_image}")
    child.sendline(f"attach rl1 {args.swap_image}")
    child.sendline("set imp enabled")
    child.sendline(f"attach imp {args.udp_endpoint}")
    child.sendline(f"set debug -n {args.debug_log}")
    child.sendline("set imp debug=reg;int;pkt")
    child.sendline("boot rl0")
    child.expect("!", timeout=15)  # the RL bootstrap prompts with "!", not "@"
    time.sleep(0.5)
    child.send(f"{args.kernel}\r")
    child.expect("login:", timeout=30)
    time.sleep(0.5)
    child.send("root\r")
    child.expect("#", timeout=10)
    time.sleep(1.0)

    child.send("ls -l /usr/net/etc/smalldaemon /usr/net/etc/Largedaemon /dev/ncpkernel\r")
    child.expect("#", timeout=10)
    time.sleep(0.5)

    print("=== starting smalldaemon ===", file=sys.stderr)
    child.send("/usr/net/etc/smalldaemon &\r")
    child.expect("#", timeout=10)

    time.sleep(args.settle)

    child.send("\r")
    try:
        child.expect("#", timeout=5)
    except pexpect.TIMEOUT:
        pass

    child.sendcontrol("e")  # SIMH console escape
    time.sleep(0.5)
    child.sendline("quit")
    time.sleep(0.5)
    child.close(force=True)
    console.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
