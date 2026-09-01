# Harness design

## Responsibility

The harness supplies isolated resources, exact process ownership, source and executable identity, bounded observation, and durable evidence. The [test plan](test-plan.md) decides what constitutes a pass; the [runbook](runbook.md) explains how to invoke the implemented targets.

The shell layer targets `/bin/sh` on macOS and Linux. Committed Python helpers require Python 3.11 or newer and currently use only the standard library.

## Per-run namespace

Each run atomically creates a unique result-directory leaf and a mode-0700 NCP control-socket directory. An existing leaf is an error, never an overwrite target.

`reserve-udp-ports.py` asks the operating system for ephemeral ports and holds IPv4 plus, when available, IPv6 wildcard UDP sockets on every selected number. Six ports cover two inter-IMP endpoints and two endpoints for each host link. The router oracle uses ten for its two hosts, three IMPs, and deliberately unreachable peer. The NCC alternate-path fault harness also uses ten: two NCC host-link endpoints, four endpoints for the two alternate-path modem cables, two direct-line simulator endpoints, and two direct-line relay endpoints.

Topology-specific environment variables carry the allocated values into the SIMH command files through native `%NAME%` expansion. This avoids mutating tracked configurations or interpolating them with a shell.

Immediately before simulator launch, the harness asks the reservation helper to release its sockets while retaining per-user cooperative locks. SIMH cannot inherit pre-bound descriptors, so a short bind handoff remains unavoidable. A noncooperating local process can win that race; an early bind failure must reject the run rather than reuse partial state.

## Process ownership

Every daemon, simulator, and bounded client is launched as a direct child and registered by exact PID. Cleanup is idempotent: it sends `TERM`, waits for a bounded interval, sends `KILL` only to a surviving owned child, removes known client sockets, releases locks, and finalizes the manifest.

The NCC alternate-path harness owns its receiver, all three IMP simulators, and a two-ended UDP relay. The relay accepts packets only from the two recorded simulator ports, forwards both directions for a bounded interval, then keeps both relay sockets bound while counting and discarding traffic in both directions. Termination makes it write the cut timestamp, per-direction receive/forward/drop counters, and any unexpected source addresses before its PID is released.

Process names and global kill patterns are never lifecycle authority. Startup, application probes, cleanup, and manifest finalization all have explicit deadlines so a blocked console or NCP client cannot retain a run indefinitely.

The pinned `linux-ncp` client creates a short-lived `/tmp/client.PID` reply socket. The harness records the exact client PID and removes only that path after normal completion, timeout, or interruption. Moving it into the private socket directory would require a pinned upstream change.

## Build and executable identity

After source verification, the diagnostic NCP tools are force-rebuilt under an external atomic lease. A receipt binds source revision and executable hashes. Smoke runs reacquire the same lease, verify the receipt, and hold it through cleanup so a cooperating build cannot replace a running input.

Simulator checks independently require embedded source revisions. Per-run manifests then hash the exact executables, configurations, firmware, base configuration, and receipt used by the launch.

`its-build-receipt.py` applies the same principle to promoted ITS media. It binds the pinned main revision, exact recursive submodule status, clean tracked state, an up-to-date `make EMULATOR=pdp10-ka its` target, and the SHA-256 values of the bootstrap and four runtime disks. The two-ITS launcher verifies that receipt while holding the ITS build/use lease, then gives each guest a distinct copied workspace. A stamp alone is not accepted.

`pdp11-build-receipt.py` binds the heterogeneous guest's complete two-stage build instead of treating a final disk hash as provenance. `build-pdp11-telnet.sh` records the base root and swap hashes, runs the preserved-source TELNET and companion-reader build under the pinned IMP11-A simulator, records the intermediate media, stages and builds the trace-only NCP daemon from the pinned Network UNIX checkout, then records the final media, both staged-source trees, both console logs, all builder hashes, and source and simulator identities. A smoke reacquires the build/use lease and revalidates every recorded path and hash before copying the final root and swap into its run directory.

## Controller states

`two-its-controller.py` distinguishes `BOOTING`, `RUNNING`, `PROMPT`, and `STOPPED` for each KA10. Its standard-library PTY reader threads drain both consoles concurrently, while separate sent logs record every controller write as hexadecimal bytes with timestamps.

The controller starts host `106` with an attach-only derivative of the tracked configuration so both guest UDP endpoints bind before the recovered IMPs can send their first host-link NOP. It boots host `106` only after both modem watchdogs are up. Cleanup sends the WRU character only to a simulator known to be running; a simulator already at `PROMPT` receives `quit`, and a stopped child receives neither. A PID that exists without current guest-level evidence remains unready.

`pdp11-its-controller.py` imports and reuses that PTY, process, watchdog, and MI1 correlation implementation. It starts both host simulators in attach-only `PROMPT` state, waits for both IMP modem paths, boots ITS host `106`, proves a local ITS `:TIME`, boots the PDP-11, starts its preserved NCP, and waits for both latest watchdog states to reach `075400` plus the route hold-down. The committed PDP-11 configuration uses the same six-port topology and sets IMP 62's host interface to the already-proven short-leader `noconvert` mode; it does not change the shared two-ITS configuration.

After Gate 4H application evidence passes, the controller fixes an end offset for each H316 debug log and sends only those post-probe byte windows to the typed message-journey adapter. The adapter derives its twelve expected request/reply boundaries from `config/topologies/pdp11-its-telnet.json`, correlates literal MI packet equality across the two IMPs, and uses only increasing source-local order for adjacent HI/MI transfers. It emits ten observations to `message-journey.jsonl`: H316 transfers remain direct trace evidence, connected-host egress remains separately labeled harness-derived peer delivery, and both destination-host ingress boundaries remain missing. The controller reads the terminal stream back through the existing reducer before recording its digest and diagnosis in the manifest. It never compares the independent simulator ticks or grants the sidecar application-gate authority.

## Evidence

The manifest records repository and source revisions, tracked-dirty flags, executable and configuration hashes, ports, platform, timestamps, outcome, and exit status. Application assertions capture relevant log offsets immediately before the probe so startup traffic cannot satisfy a later gate.

The heterogeneous reducer operates only on post-offset console and IMP bytes. It requires ordered connection, greeting, TTY, welcome, time, date, and uptime evidence; the ITS `HST176` service job; host-interface traffic on both IMPs; and exact significant MI1 packets correlated across the inter-IMP hop in both directions. It rejects application, modem, bind, and transport failures while explicitly preserving the known non-fatal legacy option diagnostic. The controller records child cleanup separately, and the shell layer does not mark the run passed until all internal children are gone, the outer runtime has released its sockets and locks, and the retained evidence files agree.

The typed journey sidecar is an additional evidence artifact, not a looser application test. The formal smoke checks the topology input hash, sidecar digest, ten-observation count, `missing-boundary` terminal state, and first unresolved `boundary:request:6`. A malformed window, failed exact correlation, stream/reducer disagreement, or missing sidecar fails the run. The unobserved host-ingress boundary remains explicit even though the independent guest application evidence passes.

The NCC alternate-path evaluator consumes only the shared topology, the receiver's structured sidecar and historical-event stream, and the relay's structured counters. It requires bidirectional forwarding before the cut, reciprocal direct-line `up` evidence before the cut, bidirectional drops after the cut, no unexpected relay source, reports from all three IMPs, post-cut reports from IMPs 5 and 6, and a final reciprocal direct-line `down` result. It does not inspect packet logs or infer report-line identities from simulator device names. The receiver independently requires a complete IMP-to-host message plus checksum-valid trouble and throughput reports before it can exit successfully.

Full console and protocol logs remain outside Git. The source-only tests cover the tempting false positives directly: partial remote output, a connection that closes before proof, startup IMP traffic before the captured offsets, and an attach-only host configuration that accidentally boots early.

## Repository guard

`check-source-only.py` rejects large indexed blobs, known media names and formats, and content matching the external-asset digest denylist. Its staged mode reads both candidate blobs and the candidate manifest from the index while preventing silent shrinkage relative to `HEAD`.

The repository policy and contributor checks are documented in [`CONTRIBUTING.md`](../CONTRIBUTING.md). The broader provenance and redistribution boundary is documented only in [`NOTICE.md`](../NOTICE.md).
