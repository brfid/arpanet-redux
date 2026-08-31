# Test plan

## Purpose

These gates distinguish a genuinely networked vintage application from simulators that merely boot. A pass requires evidence at the highest layer under test and corroborating evidence that the intended lower-layer route carried it.

The [README](../README.md) summarizes the current result, and the dated [two-ITS readiness note](experiments/2026-08-28-two-its-readiness.md) owns its evidence trail. This document is the normative pass/fail specification.

## Common preconditions

Every integration run must:

- verify the exact source revisions, external-asset hashes, build receipts, simulator identities, and project configuration hashes before launch;
- use independent guest-media workspaces and a newly created result directory;
- allocate a private port and control-socket namespace;
- record exact child PIDs and a run manifest before accepting traffic;
- reject simulator bind, transport, and unrecoverable I/O errors;
- finish with bounded cleanup and no surviving owned process, socket, or port lock.

## Gate 1: Source-only repository

The tracked tree must contain no vintage media, firmware, simulator binary, build output, source checkout, or raw log. Indexed files must remain below the configured size limit, and no indexed blob may match a known external-asset digest. The staged denylist may grow but must not silently discard a digest already protected by `HEAD`.

## NCC derived-summary contract

The source-only suite accepts a version-1 NCC completed-run summary only when it declares a complete run clock and provenance, gives all topology components and endpoints stable unambiguous identities, orders direct observations inside that clock, ties every derived state and gate verdict to known observation identifiers, and distinguishes incomplete or failed gates from a pass. A passed gate must include direct passed application evidence; a passed run must contain only passed gates.

Synthetic fixtures must cover a passing run, missing evidence, a partition-like result, and a rejected assertion/evidence mismatch. The formal two-ITS adapter may read only `runtime/run.env`, `outcome.txt`, and `sentinel-evidence.txt`; a summary pass requires their outcomes and sentinel content/digests to agree. A failed formal run without application proof is incomplete, not proof of a network-down state. The local viewer must replay the stored observation order and expose every gate and derived-state evidence identifier without process-control or external-network authority. This is a contract test for derived project data, not a replacement for the two-ITS acceptance gates or a permission to commit external logs.

## Gate 2: Router oracle

Start diagnostic NCP hosts `002` and `003`, H316 IMPs 2 and 3, and adjacent IMP 4 with no attached host. Accept only if:

1. Host `002` receives the third echo reply from host `003`.
2. A request to host `004` fails with `Host is not up.`
3. The trace after that request contains the matching regular packet, RFNM behavior where applicable, and type-7 DEAD response from host `004`.
4. Every identity, lifecycle, and cleanup precondition passes.

## Gate 3: Mixed vintage and diagnostic hosts

Start diagnostic NCP host `076`, IMP 62, IMP 6, and KA10/ITS host `106`. Accept only if:

1. ITS reaches its complete system-console banner and a responsive command state.
2. The diagnostic endpoint receives three echo replies from ITS host `106`.
3. Both IMP logs show traffic on the intended host and modem interfaces after the application probe begins.
4. IMP 6 shows the required long-to-short and short-to-long 1822 leader conversions.
5. Every identity, lifecycle, and cleanup precondition passes.

## Gate 4: Two vintage ITS hosts

Start IMPs 6 and 62 before two independent KA10 guests. Host A must identify as octal `106`; host B must identify as octal `176`. Before host `176` opens an application connection to host `106`, require:

1. Both H316 logs report watchdog lights `077400`, showing the modem path is up.
2. Both H316 logs subsequently report watchdog lights `075400`, showing the attached HI2 host link is up.
3. The most recent watchdog state on both H316s remains `075400` immediately before the application probe. A change to `175400` before the probe begins invalidates readiness even if `075400` appeared earlier; a cleanup transition after the verdict does not retroactively fail the proof.
4. At least 60 seconds elapse after the later modem-up observation, covering the recovered firmware's peer-route hold-down.
5. Both ITS consoles print the complete `SYSTEM JOB USING THIS CONSOLE` banner.
6. Each guest completes local `:TIME`, including time, date, uptime, and return to the DDT prompt.
7. Both controller states are `RUNNING`, and neither simulator is at `sim>`.

Capture the two IMP log offsets immediately before host `176` starts `UT` and connects to host `106`. Accept the application proof only if:

1. `UT` reports `CONNECT`, displays host `106`'s server greeting, and does not subsequently report an explicit close or error before proof completes.
2. Host `106` reports the incoming `nnTLNT` service job, and host `176` reaches host `106`'s DDT through that live remote session.
3. A remote `:TIME` response contains the expected time, date, and uptime structure.
4. Both IMP traces contain matching regular traffic and leader conversion after the captured offsets.
5. The most recent watchdog state on both IMPs remains `075400` throughout the application proof; any modem-line-dead transition fails the run at the network layer.
6. Every identity, lifecycle, and cleanup precondition passes.

Boot traffic, reset messages, debugger symbol inspection, a live PID, or a bound UDP socket cannot satisfy this gate. `IMP: Interface-reset msg` is telemetry, not a readiness condition.

## Gate 4H: Network UNIX PDP-11 to ITS

Start IMPs 6 and 62 with ITS host `106` on IMP 6 and the SRI/NOSC Network UNIX PDP-11 as host `176` on IMP 62. Apply Gate 4's modem-up, host-link-ready, latest-watchdog, 60-second route-settle, and complete ITS system-console requirements to this heterogeneous topology. In addition to the common preconditions, require the pinned IMP11-A simulator to boot `green/unix`, reach a root shell, and start the preserved NCP before the application probe.

Before launch, verify the receipt that binds the base PDP-11 media, exact staged TELNET sources, intermediate images, exact staged daemon sources, final root and swap images, build logs, builder hashes, Network UNIX revision, and IMP11-A source and executable identity. Hash the receipt, final run-specific media copies, all three simulator executables, both IMP configurations, both host configurations, recovered firmware, base IMP configuration, and external asset manifest into a newly created run manifest. Record all six leased UDP ports and every child PID.

Capture both IMP debug-log offsets and both host console offsets immediately before the PDP-11 starts `/usr/bin/telnet - -h 106`. Accept only if:

1. The PDP-11 prints `Connection open` after its captured console offset.
2. ITS records an incoming `nnTLNT` service job from `HST176` after its captured console offset.
3. The PDP-11 receives the ITS machine and monitor greeting, a TTY assignment, `Welcome to ITS!`, and a usable remote terminal state.
4. A remote `:TIME` response contains time with a timezone, a full date, and ITS uptime, in that order after the connection opens.
5. Both IMPs record host-interface send and receive traffic after their captured offsets, and exact significant MI1 packet content correlates across the inter-IMP link in both directions.
6. Neither IMP's latest watchdog state regresses from `075400`, and no post-probe modem-line-dead transition occurs.
7. No `Host is Unavailable`, premature close, transport error, early child exit, missing response, or other fatal condition occurs before the complete application verdict.
8. Bounded cleanup leaves no owned process, control-socket namespace, UDP socket, cooperative port lock, or build/use lease.

The legacy client diagnostic `Possible protocol error! command = 376, option = 3.` is retained as evidence but is not by itself a failure. It becomes relevant only if the session loses one of the required application behaviors. `SKTRACE` and `PBTRACE` may corroborate the guest path, but neither trace can replace the application and correlated IMP evidence above.

## Gate 5: Payload anti-bypass

Generate a unique printable-ASCII sentinel. Inject it only through host A's console or guest application, transfer it using guest NCP, and extract it only through host B's console or guest application. The controller must have no operation that copies the payload between guest workspaces.

Accept only if the recovered sentinel matches the original digest and both IMPs record correlated post-start traffic. A test that writes the sentinel into both guest workspaces fails by construction even if its reported digests match.

For the two-ITS TELNET baseline, log host `106`'s console in as `DB`, log the remote pseudo-terminal in under a per-test name, and inject the sentinel with DDT `:OSEND` only after the remote session is interactive. Recover it solely from host `176`'s `UT` transcript. Do not substitute `:SEND`: this DDT configuration redirects that name to a mail-aware program, while `:OSEND` selects DDT's original real-time terminal-send path.

## Gate 6: Site integration

After the vintage-to-vintage and payload gates pass, the replacement stage must preserve the external contracts in the [architecture](architecture.md): semantic output, artifact identity, status, build-log identity, exact source provenance, reuse fingerprints, validation, and fail-closed publication.

## Fault injection

For each production-shaped topology, force at least one endpoint or IMP to exit after partial startup and force one readiness timeout. Both cases must produce a bounded nonzero result, a failed manifest, and complete cleanup. A result-directory collision and a noncooperating occupied port must fail without overwriting prior evidence. Gate 4H's source-only reducer fixtures additionally reject a missing open, explicit host-unavailable result, greeting without remote command output, partial `:TIME`, close after partial output, evidence that appears only before the captured offsets, missing traffic on either IMP, and substituted simulator or guest-image identity.
