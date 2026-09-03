#!/usr/bin/env python3
"""Wire the IMP11-A PDP-11 guest into the two-IMP topology already used
for the two-ITS smoke, per the "Wiring into the two-IMP topology"
section of docs/research/pdp11-network-unix.md: IMP 6 <-mi1-> IMP 62,
ITS host 106 on IMP 6's hi2, and our green/unix guest (instead of a
second ITS host) on IMP 62's hi2.

Reuses config/imp/its-pair/imp6.simh, config/imp/its-pair/imp62.simh,
and config/hosts/its106-pair.simh from the repo, completely unchanged:
our PDP-11 device attaches to imp62's hi2 exactly the way any host
does (it reuses the same H316 UDP transport and flag-word convention
as the KA10 host it replaces there), so no PDP-11-specific IMP config
was needed.

This is a manual smoke check, not the formal two-its-controller: it
does not hold a port lease, does not write a run manifest, and its
"readiness" checks (grepping console logs for watchdog light values
and the ITS console banner) are informal, not the Gate 4 state
machine in docs/test-plan.md. Ports are plain fixed high ports chosen
by --base-port, not the reservation system in scripts/reserve-udp-ports.py.

Research-phase tool: exploratory, not wired into any make target or
test.
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


def start_background(name: str, argv: list[str], cwd: Path, log_path: Path, env: dict):
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
    p.add_argument("--h316", required=True, type=Path, help="pinned H316 SIMH binary")
    p.add_argument("--pdp10-ka", required=True, type=Path, help="pinned KA10 SIMH binary")
    p.add_argument("--pdp11", required=True, type=Path,
                    help="Open SIMH pdp11 binary built with the IMP11-A device")
    p.add_argument("--mini-root", required=True, type=Path,
                    help="arpanet-in-a-box mini/ dir (impconfig.simh, impcode.simh)")
    p.add_argument("--its-host-media", required=True, type=Path,
                    help="prepared ITS host-106 media dir (dskdmp.rim, rp03.*)")
    p.add_argument("--results-dir", required=True, type=Path)
    p.add_argument("--pdp11-root-image", required=True, type=Path)
    p.add_argument("--pdp11-swap-image", required=True, type=Path)
    p.add_argument("--base-port", type=int, default=19100)
    p.add_argument("--settle", type=float, default=60.0,
                    help="seconds to let the daemon run once started")
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

    its_host_proc, its_host_log = start_background(
        "host106", [str(args.pdp10_ka), str(its_host_cfg)], its_host_work,
        results / "host106.console.log", env)
    procs.append(("host106", its_host_proc, its_host_log))

    # Informal readiness -- not the Gate 4 watchdog-state machine in
    # docs/test-plan.md, just enough to know both IMPs are up before
    # attaching the PDP-11 guest.
    wait_for(results / "imp6.console.log", "077400", 30, "imp6 modem light")
    wait_for(results / "imp62.console.log", "077400", 30, "imp62 modem light")
    wait_for(results / "imp6.console.log", "075400", 30, "imp6 host-link light")
    wait_for(results / "host106.console.log", "SYSTEM JOB USING THIS CONSOLE", 60,
              "ITS host 106 banner")

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
    child.expect("!", timeout=15)  # the RL bootstrap prompts with "!", not "@"
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

    print(f"[driver] settling {args.settle}s to observe traffic", file=sys.stderr)
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
    pdp11_console.close()

    print("[driver] stopping imp6/imp62/host106", file=sys.stderr)
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
