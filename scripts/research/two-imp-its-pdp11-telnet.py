#!/usr/bin/env python3
"""Wire a PDP-11 guest already carrying a built /usr/bin/telnet (see
build-guest-telnet.py) into the two-IMP topology proven for the
two-ITS smoke and the plain PDP-11 wiring in
two-imp-its-with-pdp11.py, start the NCP daemon, and attempt a real
guest TELNET connection to ITS host 106 -- the application-level proof
pdp11-network-unix.md's "First experiment" step 6 calls for.

Reuses the IMP 6 configuration unchanged.  It makes run-local copies of
the shared IMP 62 and ITS configurations: the IMP 62 copy disables HI2's
long-leader conversion because this guest uses the original short leader
directly, while the ITS copy enables a KA10 IMP-device trace so traffic can
be correlated across the IMP 6/ITS attachment.

The PDP-11's IMP11-A interface sends the high bit of every DMA word
first, so this requires a PDP-11 binary with the corresponding output
byte-order handling.  See docs/research/imp11a-device.md for the
historical source and the controlled run evidence.

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
    p.add_argument("--h316", required=True, type=Path, help="pinned H316 SIMH binary")
    p.add_argument("--pdp10-ka", required=True, type=Path, help="pinned KA10 SIMH binary")
    p.add_argument("--pdp11", required=True, type=Path,
                    help="Open SIMH pdp11 binary built with the IMP11-A device")
    p.add_argument("--mini-root", required=True, type=Path,
                    help="arpanet-in-a-box mini/ dir (impconfig.simh, impcode.simh)")
    p.add_argument("--host106-media", required=True, type=Path,
                    help="prepared ITS host-106 media dir (dskdmp.rim, rp03.*)")
    p.add_argument("--results-dir", required=True, type=Path)
    p.add_argument("--pdp11-root-image", required=True, type=Path,
                    help="root image built by build-guest-telnet.py "
                         "(has /usr/bin/telnet, /usr/bin/usrtelnetin, "
                         "/dev/net/anyhost)")
    p.add_argument("--pdp11-swap-image", required=True, type=Path)
    p.add_argument("--base-port", type=int, default=19100)
    p.add_argument("--pdp11-hi-convert", action="store_true",
                    help="retain the shared IMP 62 HI2 long-leader conversion "
                         "instead of using the PDP-11's native short leader")
    p.add_argument("--host-number", default="106",
                    help="octal NCP host number to connect to, per "
                         "docs/test-plan.md's convention (default 106 = ITS)")
    p.add_argument("--daemon-settle", type=float, default=12.0,
                    help="seconds to let smalldaemon/Largedaemon come up "
                         "against the live IMP before attempting to connect")
    p.add_argument("--telnet-settle", type=float, default=25.0,
                    help="seconds to watch console output after issuing telnet")
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

    host106_work = results / "host106"
    host106_work.mkdir(exist_ok=True)
    for asset in ("dskdmp.rim", "rp03.0", "rp03.1", "rp03.2", "rp03.3"):
        shutil.copy(args.host106_media / asset, host106_work / asset)

    pdp11_work = results / "pdp11"
    (pdp11_work / "images").mkdir(parents=True, exist_ok=True)
    shutil.copy(args.pdp11_root_image, pdp11_work / "images" / "ncp_root.rl01")
    shutil.copy(args.pdp11_swap_image, pdp11_work / "images" / "ncp_swap.rl01")

    imp6_cfg = args.repo_root / "config/imp/its-pair/imp6.simh"
    imp62_cfg = args.repo_root / "config/imp/its-pair/imp62.simh"
    if not args.pdp11_hi_convert:
        # The shared configuration normally hosts ITS, which uses long
        # leaders.  The PDP-11 supplies and expects the old short leader
        # itself, so keep a run-local configuration without the bidirectional
        # conversion rather than changing the ITS configuration.
        imp62_cfg = results / "imp62-pdp11-noconvert.simh"
        imp62_text = (args.repo_root / "config/imp/its-pair/imp62.simh").read_text()
        expected = "set hi2 convert\n"
        if expected not in imp62_text:
            raise RuntimeError("IMP 62 configuration no longer has the expected HI2 conversion line")
        imp62_cfg.write_text(imp62_text.replace(expected, "set hi2 noconvert\n", 1))
    host106_cfg = results / "host106-imp-trace.simh"
    host106_text = (args.repo_root / "config/hosts/its106-pair.simh").read_text()
    expected = "attach -u imp %BRFID_HOST_A_IMP_PORT%:127.0.0.1:%BRFID_IMP6_HI_PORT%\n"
    if expected not in host106_text:
        raise RuntimeError("ITS host configuration no longer has the expected IMP attach line")
    host106_trace = (
        expected
        + f"set debug {results / 'host106-imp-device-debug.log'}\n"
        + "set imp debug=CONI;CONO;DATAIO\n"
    )
    host106_cfg.write_text(host106_text.replace(expected, host106_trace, 1))

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

    host106_proc, host106_log = start_background(
        "host106", [str(args.pdp10_ka), str(host106_cfg)], host106_work,
        results / "host106.console.log", env)
    procs.append(("host106", host106_proc, host106_log))

    # Informal readiness -- not the Gate 4 watchdog-state machine in
    # docs/test-plan.md, just enough to know both IMPs and ITS are up
    # before attaching the PDP-11 guest.
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

    print(f"[driver] settling {args.daemon_settle}s for the daemon/IMP handshake",
          file=sys.stderr)
    time.sleep(args.daemon_settle)
    child.send("\r")
    try:
        child.expect("#", timeout=5)
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

    child.sendcontrol("e")  # SIMH console escape
    time.sleep(0.5)
    child.sendline("quit")
    try:
        child.expect(pexpect.EOF, timeout=15)
    except pexpect.TIMEOUT:
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
