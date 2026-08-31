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

## NCC derived-summary and live-observation contracts

The source-only suite accepts a version-1 NCC completed-run summary only when it declares a complete run clock and provenance, gives all topology components and endpoints stable unambiguous identities, orders direct observations by strict integer sequence inside that clock, retains only finite JSON-safe data, ties every derived state and gate verdict to known observation identifiers, and distinguishes incomplete or failed gates from a pass. A passed gate must include direct passed application evidence; a passed run must contain only passed gates.

Synthetic fixtures must cover a passing run, missing evidence, a partition-like result, and a rejected assertion/evidence mismatch. The formal two-ITS adapter may read only `runtime/run.env`, `outcome.txt`, and `sentinel-evidence.txt`; a summary pass requires a complete run clock, clean recorded project/source identities, and agreement between their outcomes and sentinel content/digests. A failed formal run without application proof is incomplete, not proof of a network-down state. The local viewer must replay the stored observation order and expose every gate and derived-state evidence identifier without process-control or external-network authority. This is a contract test for derived project data, not a replacement for the two-ITS acceptance gates or a permission to commit external logs.

The bounded live stream must have one validated header containing the version-1 nominal topology, run identity, provenance, and a positive staleness interval. Every complete later line must validate as the same direct-observation envelope used by a summary; it may not introduce a separate controller-specific subject namespace. A passive reader must ignore a partially written final line, retain nominal topology and the last direct state, and label only expired direct observations as stale. Live publication has no derived-state or acceptance-gate authority and must add no raw-log parsing beyond the formal controller's existing readiness and acceptance observations.

The historical-event sidecar must have one validated header with a shared-topology snapshot, topology/interface identities, a run start, and project-authored provenance. Version 1 accepts direct Type 301/303 report, host-interface, and local-line shapes. Version 2 adds an attributed Type 302 throughput-report shape while remaining able to read valid version-1 records; a Type 302 event falsely labelled version 1 must be rejected. Before creating either report event, ingress decoding must reject a semantic body whose 16-bit words, including its checksum, do not sum to zero; old-style leader and pad words are outside that domain. Every complete later line must be ordered, attributed to a known reporting IMP, and preserve the received report code in details. The recorder must reject invalid source/subject/state combinations without appending a partial batch, tolerate only an interrupted final line, and replay direct states without inferring topology edges, timeouts, partitions, gates, or a completed-run verdict.

The source-only historical-line reducer accepts only strictly ordered direct Type 301/patched Type 303 observations and a project-authored typed nominal topology that pairs two distinct `(IMP, interface)` endpoints per line. An existing shared modem binding may carry `first_report_line` and `second_report_line` only as a reciprocal pair of line numbers in 1 through 5; a one-sided or invalid mapping must fail validation, and no report line may be inferred from a SIMH device name. The exact project topology must map IMP 5 line 1 and IMP 6 line 1 to opposite endpoints of its one configured modem binding. Focused fixtures over that loaded project file must exercise fresh reciprocal agreement, configured-neighbor contradiction, missing evidence, and staleness through the existing reducer. The reducer must identify lower-numbered IMPs as the minus end, require matching source identity, apply the recovered firmware's state-specific neighbor rules, and retain supporting event sequences for every conclusion. An up endpoint must name the configured peer. An explicitly mapped down endpoint may name that peer or omit its remembered neighbor, matching the exact recovered-firmware behavior in the alternate-path fault experiment. An explicitly mapped looped endpoint must name its own reporting IMP, matching the exact two-ended reflection experiment; the configured peer, an absent neighbor, or a third IMP is contradictory for looped, and self-neighbor has no accepted meaning for up or down. Two fresh matching endpoints may establish up, complete down/looped, or a directional plus/minus condition. Missing evidence is unknown and expired evidence is stale; neither is down. A configuration/report mismatch is contradictory. A partitioned IMP requires a missing or stale report and fresh down observations from every incident line through at least two independent peers, and remains a reachability inference rather than a hardware diagnosis. This source-only gate does not authorize a persisted reducer result or a bridge to the completed-run or live-stream contracts.

The source-only message-journey diagnostic must derive request and reply boundaries from one named route plus the shared topology's existing host and modem bindings; an unbound crossing, unknown route, component, interface, direction, malformed correlation fingerprint, or incoherent source-local order must fail closed. Direct observations must retain stable topology identity, source-local sequence, normalized decoded 1822/NCP fields, a safe content fingerprint, provenance, optional source-local transport/tick values, and optional opaque external evidence references. Independent simulator ticks must never be compared as a global clock. The pure reducer must retain supporting direct-observation identifiers and distinguish a complete request/reply path, the first missing boundary, contradictory decoded destination or interface evidence, ambiguous duplicates or incomplete decoding, and wholly absent evidence that remains unknown. Synthetic coverage must include the PDP-11-shaped result in which ITS's reply is observed through the return path but its leader is contradictory only at the guest input boundary. The H316 adapter may consume only established literal `HI`/`MI` trace transfers and must reject compressed or incomplete word content; KA10 and IMP11-A parsers remain out of scope until their extraction formats are proven.

## NCC alternate-path line-fault gate

Start IMPs 5, 6, and 7 with the NCC receiver on IMP 5. Join IMPs 5 and 6 both directly through the owned two-ended relay and indirectly through IMP 7. The shared topology may map report line 1 only on the direct IMP 5/6 binding; the alternate bindings remain routing composition and must not acquire inferred report-line identities. After a bounded forwarding interval, keep both relay ports bound but drop every valid direct-line packet in both directions. Accept only if:

1. The receiver completes its ready exchange and records at least one complete IMP-to-host message plus checksum-valid trouble and throughput reports.
2. Before the cut, the relay forwards traffic in both directions and fresh reciprocal reports reconcile the direct IMP 5/6 line as `up`.
3. After the cut timestamp, the relay records dropped traffic in both directions, accepts no unexpected packet source, and never resumes forwarding.
4. The receiver records reports from IMPs 5, 6, and 7, including at least one post-cut report from both IMP 5 and IMP 6. Because the direct relay is dropping all packets, the latter is direct evidence that IMP 6 remained observable through IMP 7 and IMP 5.
5. The final fresh reciprocal direct-line observations reconcile as `down`, with the supporting event sequences retained in the verdict.
6. Every identity, transport, lifecycle, and cleanup precondition passes, including clean recorded source trees, exact configuration and helper hashes, no simulator transport errors, no surviving owned process, and released ports and locks.

A receiver exit, a line-state transition without post-cut IMP 6 evidence, a one-sided cut, missing pre-cut `up` evidence, or a result reconstructed from raw packet logs cannot satisfy this gate. The relay counters and structured receiver outputs stay in the external immutable result directory; Git retains only the composition, evaluator, tests, and concise dated conclusions.

## NCC alternate-path line-loopback gate

Start the same IMP 5/6/7 composition and passive receiver used by the line-fault gate. Join IMPs 5 and 6 directly through the owned two-ended reflector and indirectly through IMP 7. The shared topology again maps report line 1 only on the direct binding. After a bounded forwarding interval, return each valid direct-line datagram byte for byte to the endpoint that sent it, using the same bound relay socket, without inspecting or modifying its content. Accept only if:

1. The receiver completes its ready exchange and records at least one complete IMP-to-host message plus checksum-valid trouble and throughput reports.
2. Before reflection, the relay forwards traffic in both directions and fresh reciprocal reports reconcile the direct IMP 5/6 line as `up`.
3. After the loop timestamp, the reflector records self-reflected traffic in both directions and accepts no unexpected packet source.
4. The receiver records reports from IMPs 5, 6, and 7, including at least one post-loop report from both IMP 5 and IMP 6. Because every direct datagram is then returned to its sender, the latter is direct evidence that IMP 6 remained observable through IMP 7 and IMP 5.
5. The latest post-loop raw observation from each direct endpoint is `looped` and names its own source IMP as neighbor, and the final fresh reciprocal pair reconciles as `looped`; both direct event sequences remain in the verdict.
6. Every identity, transport, lifecycle, and cleanup precondition passes, including clean recorded source trees, exact configuration and helper hashes, no simulator transport errors, no surviving owned process, and released ports and locks.

A receiver exit, configured or missing peer identity on a looped report, a transition without post-loop IMP 6 evidence, one-sided reflection, missing pre-loop `up` evidence, or a conclusion derived from reflector phase instead of firmware reports cannot satisfy this gate. The reflector counters and structured receiver outputs remain in the external immutable result directory; Git retains only project-authored composition inputs, controllers, tests, and concise dated conclusions.

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
