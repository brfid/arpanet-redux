#!/usr/bin/env python3
"""Boot the NOSC green/unix kernel under a pdp11 binary built with the
IMP11-A device (see docs/research/imp11a-device.md), and confirm the
injected NCP files are present on a live boot. This reproduces the
verification recorded there; it is a manual smoke check, not an
automated test with pass/fail assertions like the two-its-controller.

Root and swap must both be attached as RL01 units (major 1, per
green's compiled-in rootdev/swapdev), and the root image's boot block
(block 0) must be RL-native, not copied verbatim from an RK-formatted
source image — see the design doc for why and how that boot block was
obtained. This script does not build or patch images; it only drives
an already-prepared boot.

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
                         help="directory to run pdp11 from (image paths below "
                              "are relative to this)")
    parser.add_argument("--root-image", default="images/ncp_root.rl01")
    parser.add_argument("--swap-image", default="images/ncp_swap.rl01")
    parser.add_argument("--kernel", default="green")
    parser.add_argument("--cpu", default="11/34 256k")
    parser.add_argument("--check", action="append", default=[],
                         help="a guest path to `ls -l` and confirm exists; "
                              "may be repeated. Defaults to the three files "
                              "this project has injected so far.")
    args = parser.parse_args()

    checks = args.check or ["/green", "/dev/ncpkernel", "/usr/net/etc/Largedaemon"]

    child = pexpect.spawn(args.simh, cwd=args.workdir, timeout=15, encoding="utf-8")
    child.logfile = sys.stdout

    child.sendline(f"set cpu {args.cpu}")
    child.sendline("set rl0 rl01")
    child.sendline("set rl1 rl01")
    child.sendline(f"attach rl0 {args.root_image}")
    child.sendline(f"attach rl1 {args.swap_image}")
    child.sendline("boot rl0")
    child.expect("!", timeout=15)  # the RL bootstrap prompts with "!", not "@"
    time.sleep(0.5)
    child.send(f"{args.kernel}\r")
    child.expect("login:", timeout=30)
    time.sleep(0.5)
    child.send("root\r")
    child.expect("#", timeout=10)
    time.sleep(1.0)

    last_check = checks[-1].split("/")[-1]
    child.send("ls -l " + " ".join(checks) + "\r")
    child.expect(last_check, timeout=10)
    time.sleep(1.0)
    child.expect("#", timeout=5)
    print("\n=== ls -l output ===")
    print(child.before)

    child.sendcontrol("e")
    time.sleep(0.5)
    child.sendline("quit")
    child.close(force=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
