# Portable per-run harness

The harness replaces fixed UDP ports and shared NCP socket names with a private namespace for each run. It is deliberately source-only: it contains no simulator executable, firmware, disk image, or captured result.

The shell layer targets `/bin/sh` on macOS and Linux. The two helpers use only the Python 3 standard library, so no virtual environment is needed.

## Lifecycle

1. Create a run directory and a mode-0700 NCP socket directory.
2. Start `reserve-udp-ports.py`, which asks the operating system for six ephemeral ports and holds simultaneous IPv4 and IPv6 UDP sockets on every selected port. It falls back to IPv4 on hosts where IPv6 is unavailable; `--require-ipv6` turns that into a hard failure.
3. Export the six values under their topology-specific `BRFID_*_PORT` names. SIMH performs the final command-file expansion through its native `%NAME%` syntax, so no generated configuration file is required.
4. Send `USR1` to the reservation helper immediately before launching the simulators. This releases its sockets but keeps the helper and per-port locks alive until cleanup, preventing cooperating runs from selecting the same ports during the small bind handoff window.
5. Launch every process directly, capture its exact child PID, and stop only those PIDs. Cleanup sends `TERM`, waits for a bounded interval, then sends `KILL` only to survivors.

Six distinct UDP ports cover a two-host, two-IMP topology: two inter-IMP endpoints and two endpoints for each host/IMP link. The router oracle uses ten because it has two NCP endpoints, three IMPs, and one intentionally dead modem peer. The command files use only the required UDP listeners, and every peer address is explicitly loopback. NCP application control uses a private Unix-domain socket under a short temporary path rather than a fixed socket in an upstream checkout.

The H316 UDP adapter accepts a local port but not a local bind address, so its required listeners bind the wildcard address even though every configured peer is explicitly loopback. The reservation helper checks the same wildcard scope; it does not introduce any additional TCP or UDP service. The private NCP Unix socket is used only for local application control.

There is an unavoidable gap between releasing a UDP reservation and the simulator binding it because SIMH cannot inherit pre-bound file descriptors. Per-port locks under a shared, user-specific temporary directory close the race between cooperating harness runs. A non-cooperating local process could still claim a port during that short interval, so the production launcher should detect an early bind failure and retry the entire run with a new allocation.

## Repository guard

`check-source-only.py` rejects indexed files larger than 1 MiB and known vintage-media filenames such as `rp03.*`, `dskdmp.rim`, tape, disk, and VM image formats. The check reads staged blobs rather than mutable working-tree files when called with `--staged`.

To enable the included hook in a repository, run `git config core.hooksPath hooks`. CI should also invoke `python3 scripts/check-source-only.py` because local hooks are optional.

`sha256-file.sh` normalizes the output of `sha256sum`, `shasum`, or OpenSSL to the manifest form `HEX  PATH`.

## Tests

Run `python3 -m unittest discover -s tests -v`. The tests bind operating-system-selected ephemeral UDP ports briefly but do not launch SIMH, KA10, an IMP, or NCP. Run `tests/test-simh-env.sh H316_BIN PDP10_KA_BIN` to prove that both pinned simulator forks expand the native variables; the probe exits before booting a simulated machine.
