# Portable per-run harness

The harness replaces fixed UDP ports and shared NCP daemon socket names with a per-run namespace. It is deliberately source-only: it contains no simulator executable, firmware, disk image, or captured result.

The shell layer targets `/bin/sh` on macOS and Linux. The Python helpers require Python 3.11 or newer and use only the standard library, so no virtual environment is needed.

## Lifecycle

1. Atomically create a new run-directory leaf and a mode-0700 NCP daemon socket directory. An existing leaf is an error rather than an overwrite opportunity.
2. Start `reserve-udp-ports.py`, which asks the operating system for six ephemeral ports and holds simultaneous IPv4 and IPv6 UDP sockets on every selected port. It falls back to IPv4 on hosts where IPv6 is unavailable; `--require-ipv6` turns that into a hard failure.
3. Export the six values under their topology-specific `BRFID_*_PORT` names. SIMH performs the final command-file expansion through its native `%NAME%` syntax, so no generated configuration file is required.
4. Send `USR1` to the reservation helper immediately before launching the simulators. This releases its sockets but keeps the helper and per-port locks alive until cleanup, preventing cooperating runs from selecting the same ports during the small bind handoff window.
5. Launch every process directly, capture its exact child PID, and stop only those PIDs. Cleanup sends `TERM`, waits for a bounded interval, then sends `KILL` only to survivors. NCP application probes have their own deadlines, so a blocking client cannot hold a run indefinitely.
6. Force-rebuild the diagnostic NCP executables after source verification and write an external build receipt. One shared Make prerequisite prevents duplicate builds within an invocation, and the build holds an atomic external lease while it replaces the in-place executables. A smoke reacquires that lease before receipt verification and holds it through cleanup, so a cooperative build cannot replace an executable while the smoke uses it. Make serializes smoke goals that share the checkout; a separate contending process fails closed. A smoke run refuses executables whose hashes or source revision no longer match that receipt; the simulator version checks independently require the pinned embedded commit IDs.
7. Write a run manifest containing the repository and source revisions, tracked-dirty flags, executable and configuration hashes, allocated ports, platform, timestamps, outcome, and exit status.

Six distinct UDP ports cover a two-host, two-IMP topology: two inter-IMP endpoints and two endpoints for each host/IMP link. The router oracle uses ten because it has two NCP endpoints, three IMPs, and one intentionally dead modem peer. The command files use only the required UDP listeners, and every peer address is explicitly loopback. Each NCP daemon uses a private Unix-domain control socket under a short temporary path rather than a fixed socket in an upstream checkout.

The pinned `linux-ncp` client library still creates its short-lived reply socket as `/tmp/client.PID`. The bounded client launcher records that exact PID, removes its socket after normal completion or timeout, and also retains it for trap cleanup during interruption. Moving client sockets into the private directory would require a pinned upstream patch; the current harness documents the limitation instead of describing every NCP socket as private.

The H316 UDP adapter accepts a local port but not a local bind address, so its required listeners bind the wildcard address even though every configured peer is explicitly loopback. The reservation helper checks the same wildcard scope; it does not introduce any additional TCP or UDP service. The private NCP daemon socket is used only for local application control.

There is an unavoidable gap between releasing a UDP reservation and the simulator binding it because SIMH cannot inherit pre-bound file descriptors. Per-port locks under a shared, user-specific temporary directory close the race between cooperating harness runs. A non-cooperating local process could still claim a port during that short interval, so the production launcher should detect an early bind failure and retry the entire run with a new allocation.

## Repository guard

`check-source-only.py` rejects indexed files larger than 1 MiB, known vintage-media filenames such as `rp03.*`, `*.rim`, `impcode.simh`, tape, disk, and VM image formats, and any indexed blob whose content matches a digest in `pins/arpanet-assets.sha256`. The digest rule catches an exact upstream asset even after it is renamed. With `--staged`, both candidate blobs and the manifest come from the index, and the staged denylist may add entries but may not remove a digest already in `HEAD`.

To enable the included hook in a repository, run `git config core.hooksPath hooks`. CI should also invoke `python3 scripts/check-source-only.py` because local hooks are optional.

`sha256-file.sh` normalizes the output of `sha256sum`, `shasum`, or OpenSSL to the manifest form `HEX  PATH`.

## Tests

Run `python3 -m unittest discover -s tests -v` and `tests/test_runtime.sh`. The tests exercise source-policy failures, denylist shrinkage, the cross-process build lock, ordered log evidence, atomic result creation, bounded child cleanup, failed manifest hashing, nonzero outcome coercion, private paths containing spaces, and operating-system-selected ephemeral UDP ports, but do not launch SIMH, KA10, an IMP, or NCP. Run `tests/test-simh-env.sh H316_BIN PDP10_KA_BIN` to prove that both pinned simulator forks expand the native variables; the probe exits before booting a simulated machine.
