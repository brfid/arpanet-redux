# Harness design

## Responsibility

The harness supplies isolated resources, exact process ownership, source and executable identity, bounded observation, and durable evidence. The [test plan](test-plan.md) decides what constitutes a pass; the [runbook](runbook.md) explains how to invoke the implemented targets.

The shell layer targets `/bin/sh` on macOS and Linux. Committed Python helpers require Python 3.11 or newer and currently use only the standard library.

## Per-run namespace

Each run atomically creates a unique result-directory leaf and a mode-0700 NCP control-socket directory. An existing leaf is an error, never an overwrite target.

`reserve-udp-ports.py` asks the operating system for ephemeral ports and holds IPv4 plus, when available, IPv6 wildcard UDP sockets on every selected number. Six ports cover two inter-IMP endpoints and two endpoints for each host link. The router oracle uses ten for its two hosts, three IMPs, and deliberately unreachable peer.

Topology-specific environment variables carry the allocated values into the SIMH command files through native `%NAME%` expansion. This avoids mutating tracked configurations or interpolating them with a shell.

Immediately before simulator launch, the harness asks the reservation helper to release its sockets while retaining per-user cooperative locks. SIMH cannot inherit pre-bound descriptors, so a short bind handoff remains unavoidable. A noncooperating local process can win that race; an early bind failure must reject the run rather than reuse partial state.

## Process ownership

Every daemon, simulator, and bounded client is launched as a direct child and registered by exact PID. Cleanup is idempotent: it sends `TERM`, waits for a bounded interval, sends `KILL` only to a surviving owned child, removes known client sockets, releases locks, and finalizes the manifest.

Process names and global kill patterns are never lifecycle authority. Startup, application probes, cleanup, and manifest finalization all have explicit deadlines so a blocked console or NCP client cannot retain a run indefinitely.

The pinned `linux-ncp` client creates a short-lived `/tmp/client.PID` reply socket. The harness records the exact client PID and removes only that path after normal completion, timeout, or interruption. Moving it into the private socket directory would require a pinned upstream change.

## Build and executable identity

After source verification, the diagnostic NCP tools are force-rebuilt under an external atomic lease. A receipt binds source revision and executable hashes. Smoke runs reacquire the same lease, verify the receipt, and hold it through cleanup so a cooperating build cannot replace a running input.

Simulator checks independently require embedded source revisions. Per-run manifests then hash the exact executables, configurations, firmware, base configuration, and receipt used by the launch.

The clean ITS image workflow must apply the same principle: bind clean source and recursive submodule states to every promoted disk, tape, and bootstrap output, then give each guest a distinct copied workspace. A stamp alone is not a sufficient receipt.

## Controller states

A two-ITS controller must distinguish at least `BOOTING`, `RUNNING`, `PROMPT`, and `STOPPED` for each KA10. Console streams must be drained concurrently, and sent control characters must be logged separately from received output.

Cleanup may send the WRU character only to a simulator known to be running. A simulator already at `PROMPT` receives `quit`; a stopped child receives neither. A PID that exists without current guest-level evidence remains unready.

## Evidence

The manifest records repository and source revisions, tracked-dirty flags, executable and configuration hashes, ports, platform, timestamps, outcome, and exit status. Application assertions capture relevant log offsets immediately before the probe so startup traffic cannot satisfy a later gate.

Full console and protocol logs remain outside Git. Only minimal synthetic fixtures belong in the repository, and they must include negative cases for tempting false positives such as partial banners, preexisting IMP traffic, or a connection that opens and then closes before remote proof.

## Repository guard

`check-source-only.py` rejects large indexed blobs, known media names and formats, and content matching the external-asset digest denylist. Its staged mode reads both candidate blobs and the candidate manifest from the index while preventing silent shrinkage relative to `HEAD`.

The repository policy and contributor checks are documented in [`CONTRIBUTING.md`](../CONTRIBUTING.md). The broader provenance and redistribution boundary is documented only in [`NOTICE.md`](../NOTICE.md).
