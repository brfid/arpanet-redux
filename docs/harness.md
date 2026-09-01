# Harness design

## Responsibility

The harness provides isolated resources, exact process ownership, input identity, bounded observation, durable evidence, and complete cleanup. The [test plan](test-plan.md) defines a pass; the [runbook](runbook.md) documents supported commands.

Shell launchers target `/bin/sh` on macOS and Linux. Committed Python controllers require Python 3.11 or newer and use the standard library.

## Per-run isolation

Each run atomically creates a new result directory and a mode-0700 control-socket directory. Existing paths are errors, never overwrite targets. Guest simulators receive distinct media copies.

The reservation helper selects ephemeral UDP port numbers and holds wildcard sockets on each number until launch. It also retains per-user cooperative locks through the run. SIMH cannot inherit pre-bound descriptors, so the helper must release its sockets immediately before simulator bind. A noncooperating process can win that short handoff; an early bind error rejects the run.

Topology-specific `BRFID_*_PORT` variables carry leased values into SIMH through native `%NAME%` expansion. The harness never rewrites a tracked configuration to assign a port.

The pinned `linux-ncp` client creates `/tmp/client.PID` for its short-lived reply socket. The harness records the exact client PID and removes only that path. Moving the socket into the private namespace requires an upstream change.

## Process ownership

Every daemon, simulator, relay, and bounded client is a direct child registered by exact PID. Process names and global kill patterns are not ownership evidence.

Cleanup is idempotent. It sends `TERM`, waits for a bounded interval, sends `KILL` only to a surviving owned child, removes known sockets and media copies, releases port and build leases, and finalizes the manifest. Startup, probes, controller operations, and cleanup all have deadlines.

Fault instruments accept packets only from the two leased simulator endpoints. A cut relay forwards both directions until its acknowledged fault boundary, then keeps both ports bound while counting and dropping traffic. A loopback reflector instead returns each valid datagram unchanged to its sender. Each instrument writes its phase boundary, per-direction counters, and unexpected sources before cleanup releases its PID.

The application-failover controller alone writes its run-local cut request. The relay acknowledges that request atomically and records the same fault timestamp in its state and terminal result. Browser processes have no path to this control channel.

## Input identity

Diagnostic NCP tools are force-built under an external atomic lease. A receipt binds the pinned source revision and executable hashes. Smokes reacquire the lease, verify the receipt, and retain it until cleanup.

Simulator checks require embedded source revisions. Manifests hash the exact executables, configurations, firmware, generic IMP configuration, shared topology, asset manifest, and build receipts used by the run.

The ITS receipt binds a clean pinned checkout, recursive submodule state, a current `make EMULATOR=pdp10-ka its` target, a successful no-op rebuild, and the bootstrap and runtime-disk hashes. The two-ITS smoke verifies the receipt and boots independent media copies.

The PDP-11 receipt binds the base images, staged TELNET and NCP-daemon sources, intermediate and final media, build logs, builder hashes, Network UNIX revision, IMP11-A revision, and PDP-11 executable. A smoke revalidates every path and digest before copying final media into its run.

## Controller boundary

Controllers distinguish guest execution from simulator prompt and process existence. They drive only known child consoles, record controller writes separately, and do not use a live PID or bound socket as guest readiness.

Application controllers wait for configured modem and host-interface readiness, guest console readiness, and route hold-down before capturing probe offsets. Application assertions use only bytes written after those offsets. Cleanup sends WRU only to a running simulator, sends `quit` only at its prompt, and sends neither to a stopped child.

The heterogeneous controller reuses the established KA10 process, PTY, watchdog, and packet-correlation primitives. It boots ITS and Network UNIX in the required order, starts the preserved NCP, opens a bounded TELNET transaction, and records structured application evidence.

After application proof, the controller fixes H316 trace-window ends and invokes the typed journey adapter. Direct trace evidence and harness-derived peer delivery remain separate. The reducer uses source-local order only and leaves unproved guest-ingress boundaries missing. The controller reads the terminal stream back and records its digest and diagnosis; the sidecar does not gain application-gate authority.

## Evidence boundary

The manifest records source and repository revisions, dirty-state flags, executable and configuration hashes, ports, platform, timestamps, outcome, exit status, and cleanup. Structured sidecars retain application facts, direct network observations, reducer support, relay or reflector counters, and typed journey evidence according to the composition.

Evaluators consume declared structured inputs, not arbitrary raw logs. They require the formal application or network claim, exact identities, consistent digests, supported reducer output, successful owned controllers, and both cleanup layers. One evidence plane cannot fill another plane's missing fact.

Raw console, protocol, receiver, and IMP traces remain in the external result directory. The source-only suite covers parsers, reducers, contracts, lifecycle failures, and tempting false positives with synthetic fixtures.

## Repository guard

`check-source-only.py` rejects large indexed blobs, known media names and formats, and content matching protected external-asset digests. Staged mode reads candidate files and the candidate manifest from the index and prevents silent denylist shrinkage relative to `HEAD`. Complete-history mode checks material that was committed and later deleted.

See [`NOTICE.md`](../NOTICE.md) before publishing derived material. Third-party inputs and raw results remain in the external laboratory.
