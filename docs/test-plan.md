# Test plan

## Purpose

These gates distinguish a networked historical application or observed network condition from simulators that merely boot. A pass requires evidence at the highest layer under test and corroborating evidence from the intended lower-layer route.

This document is the normative pass/fail specification. The [README](../README.md) reports current status; dated [experiments](experiments/) and [research](research/) own exact runs and findings.

## Common preconditions

Every integration run must:

- verify exact source revisions, external-asset hashes, build receipts, simulator identities, and project configuration hashes before launch;
- use independent guest-media workspaces and a new result directory;
- allocate a private port, lock, and control-socket namespace;
- record exact child PIDs and a manifest before accepting traffic;
- reject bind, transport, unrecoverable I/O, and unexpected early-exit errors;
- capture evidence only after the relevant probe offsets or phase boundary;
- finish with bounded cleanup and no surviving owned process, socket, port lock, or build/use lease.

## Gate 1: Source-only repository

The tracked tree must contain no historical media, firmware, simulator binary, build output, source checkout, or raw log. Indexed files must remain below the configured size limit, and no indexed blob may match a known external-asset digest. The staged denylist may grow but must not silently discard a digest protected by `HEAD`.

## NCC contract invariants

The source-only suite enforces these rules across completed summaries, live observations, historical events, message journeys, adapters, reducers, and displays:

- Persisted contracts declare a supported version, run identity, provenance, stable topology identities, finite JSON-safe data, and strict integer order within each source clock. Independent simulator clocks never become a global clock.
- Completed verdicts close over their supporting observation identifiers. A version-1 pass requires direct application evidence. A version-2 network-behavior pass requires a supported harness outcome, an inferential state, and every direct historical observation supporting that state. A passed run contains no failed or incomplete gate.
- JSON Lines readers validate every complete prefix, ignore only an interrupted final record, and start a new generation after truncation, replacement, restart, or run-identity change. Missing or expired evidence remains unknown or stale, never down.
- Historical report ingress attributes each record from its old-style leader and validates the 16-bit semantic checksum before emitting Type 301/303 trouble or Type 302 throughput events. It preserves the received report code and does not infer topology, freshness, or a verdict.
- Historical-line reconciliation uses only reciprocal report-line fields on one configured modem binding. It never derives a report line from a SIMH interface name. An `up` endpoint names its configured peer; an accepted `down` endpoint may name that peer or omit it; an accepted `looped` endpoint names its own reporting IMP. Other neighbor combinations are contradictory. Partition remains a reachability inference that requires missing or stale self evidence plus fresh down observations through at least two independent peers.
- Message-journey boundaries derive from one named route and existing host or modem bindings. Observations retain direct or harness-derived provenance, source-local order, decoded fields, safe correlation fingerprints, and exact trace-window identity. Reducers distinguish complete, missing, contradictory, ambiguous, and wholly unknown paths and retain supporting identifiers.
- Interactive TELNET session records use one controller emission order. A session start binds exact revision, route, application identities, input and response ownership, framing, encoding, and limits. Every accepted command is immediately followed by its bounded exact captured result; terminal counts, byte counts, digests, prompt/status combinations, and contiguous identities must recompute exactly.
- Read-only adapters consume only their declared structured artifacts and exact topology. They re-run the relevant reducer and fail closed on any identity, digest, topology, lifecycle, verdict, state, or support mismatch. They never parse undeclared raw logs, launch a process, or change a result.
- Python produces resolved display snapshots. Browsers perform presentation only. Servers bind IPv4 loopback, accept GET and HEAD only, and expose no arbitrary-file, external-network, simulator, controller, guest-input, relay, or result-mutation route.

Synthetic fixtures must cover passing, incomplete, missing, stale, contradictory, ambiguous, tampered, interrupted-tail, generation-change, and unsupported-version cases. Retained canonical replay owns agreement with accepted external results; source-only fixtures do not require or vendor those results.

## Gate 2: Router oracle

Start diagnostic NCP hosts `002` and `003`, H316 IMPs 2 and 3, and adjacent hostless IMP 4. Accept only if:

1. Host `002` receives the third echo reply from host `003`.
2. A request to host `004` fails with `Host is not up.`
3. The trace after that request contains the matching regular packet, RFNM behavior where applicable, and type-7 DEAD response from host `004`.
4. Every common precondition passes.

## Gate 3: Mixed vintage and diagnostic hosts

Start diagnostic NCP host `076`, IMP 62, IMP 6, and KA10/ITS host `106`. Accept only if:

1. ITS reaches its complete system-console banner and a responsive command state.
2. The diagnostic endpoint receives three echo replies from ITS host `106`.
3. Both IMP logs show traffic on the intended host and modem interfaces after the application probe begins.
4. IMP 6 shows the required long-to-short and short-to-long 1822 leader conversions.
5. Every common precondition passes.

## Gate 4: Two vintage ITS hosts

Start IMPs 6 and 62 before independent KA10 guests `106` and `176`. Before host `176` connects to host `106`, require:

1. Both H316 logs report watchdog lights `077400`, then `075400`.
2. The latest state on both H316s remains `075400`; a pre-probe `175400` invalidates readiness.
3. At least 60 seconds elapse after the later modem-up observation.
4. Both ITS consoles print the complete `SYSTEM JOB USING THIS CONSOLE` banner.
5. Each guest completes local `:TIME`, including time, date, uptime, and return to the DDT prompt.
6. Both controllers report `RUNNING`, and neither simulator is at `sim>`.

Capture both IMP log offsets immediately before host `176` starts `UT`. Accept the application proof only if:

1. `UT` reports `CONNECT`, displays host `106`'s greeting, and does not close or fail before proof completes.
2. Host `106` reports the incoming `nnTLNT` service job, and host `176` reaches host `106`'s DDT through that session.
3. Remote `:TIME` returns the expected time, date, and uptime structure.
4. Both IMP traces contain matching regular traffic and leader conversion after the captured offsets.
5. Both latest watchdog states remain `075400`; a post-probe modem-line-dead transition fails the run.
6. Every common precondition passes.

Boot traffic, reset messages, debugger symbol inspection, a live PID, or a bound UDP socket cannot satisfy this gate. `IMP: Interface-reset msg` is telemetry, not readiness.

## Gate 4H: Network UNIX PDP-11 to ITS

Start ITS host `106` on IMP 6 and SRI/NOSC Network UNIX host `176` on IMP 62. Apply Gate 4's modem, host-link, route-settle, ITS-console, identity, and cleanup requirements. Before launch, verify the receipt binding base media, staged TELNET and daemon sources, intermediate and final images, build logs, builder hashes, Network UNIX revision, and IMP11-A source and executable. The PDP-11 must boot `green/unix`, reach a root shell, and start the preserved NCP before the probe.

Capture both IMP debug-log offsets and both host console offsets immediately before the PDP-11 starts `/usr/bin/telnet - -h 106`. For the direct formal smoke, enable only the versioned observation-only KA10 input-assembly and IMP11-A input-DMA categories and bind their live records to the fixed host-106 and host-176 console windows. Accept only if:

1. The PDP-11 prints `Connection open` after its captured offset.
2. ITS records an incoming `nnTLNT` service job from `HST176` after its captured offset.
3. The PDP-11 receives the ITS machine and monitor greeting, a TTY assignment, `Welcome to ITS!`, and a usable terminal state.
4. Remote `:TIME` returns time with a timezone, a full date, and ITS uptime, in that order.
5. Both IMPs record host-interface traffic, and exact significant inter-IMP packet content correlates in both directions after the captured offsets.
6. Neither IMP's latest watchdog state regresses from `075400`, and no post-probe modem-line-dead transition occurs.
7. No host-unavailable response, premature close, transport error, early child exit, missing response, or other fatal condition occurs before the verdict.
8. The controller validates the shared topology; fixes both H316 end offsets and both host input-trace end offsets; and writes and reads back a hashed `message-journey.jsonl` with exactly twelve observations. The KA10 parser must reconstruct complete version-1 receive, assembly, and matching `DATAI` consumption records; require exactly one canonical normalized message equal to the complete IMP 6 destination-HI request; and directly observe `boundary:request:6`. The IMP11-A parser must reconstruct complete version-1 post-store DMA groups across guest buffers; validate contiguous identities, exact 16-bit wire-to-guest conversion, DMA addresses, source ticks, and final word counts; require exactly one complete message equal to the complete IMP 62 destination-HI reply; and directly observe `boundary:reply:6`. The diagnosis must be `complete` with no first missing boundary; neither topology nor application success may fill either guest-ingress boundary.
9. Every common precondition passes.

Older accepted builds print the legacy client diagnostic `Possible protocol error! command = 376, option = 3.`; it remains evidence rather than a retroactive failure of those successful sessions. The current staged builder repairs the exact missing-break fallthrough that produced it, while retaining the old result semantics for replay. `SKTRACE` and `PBTRACE` may corroborate the path but cannot replace the application and correlated IMP evidence. The complete typed journey remains a separate evidence plane and does not replace the application gate.

## Gate 4I: Interactive Network UNIX-to-ITS TELNET

Start the accepted direct Gate 4H composition and its real Network UNIX `/usr/bin/telnet - -h 106` client under one foreground controller. The controller alone owns operator standard input, every simulator PTY, command dispatch, response framing, transcript emission, evidence checks, and cleanup. Apply Gate 4H's source, executable, build-receipt, topology, readiness, connection, TELSER, bidirectional IMP-correlation, fatal-condition, and cleanup requirements. Accept the interactive extension only if:

1. The session-start record binds the exact run and repository revision, host 176 to host 106 direct route, Network UNIX TELNET client, ITS TELSER server and service user, operator input, PDP-11 console responses, carriage-return lines, Latin-1 capture, CRLF-plus-asterisk DDT prompt, and finite command, timeout, and response limits.
2. At least one nonblank printable-ASCII operator line is sent by the already-open guest TELNET session. Each command has a contiguous controller identity and byte count; its result immediately follows, preserves the exact bounded console capture through the next prompt, and records a matching byte count, SHA-256, elapsed time, response source, complete status, and prompt identity.
3. Local `/help` and `/quit` controls are not sent to the guest or persisted as application commands. The terminal record follows the last result, reports a supported reason, and exactly recomputes total, complete, and failed counts.
4. The controller reads the transcript back through the strict reader, verifies its digest, records the matching application identities and command count, and observes correlated post-start IMP traffic in both directions without reconnecting the guest session.
5. A timeout, session close, interruption, or response limit retains a bounded typed result, stops further input, fails acceptance, and still completes bounded cleanup. Every common precondition passes.

This gate proves line-oriented interaction for commands that return to the documented ITS DDT prompt. It does not prove character-at-a-time behavior, full-screen or paged programs, arbitrary control input, a browser command path, application-link failover during an operator session, or any new host-interface claim of its own. It emits no message-journey sidecar and supplies no new parser or simulator authority.

## Gate 4J: Historical Network UNIX TELNET terminal

Start the accepted direct Gate 4H composition under one foreground terminal controller, but stop at the Network UNIX host-176 root shell instead of automatically opening TELNET. The controller alone owns operator input, every simulator PTY, byte dispatch, retained stream, evidence checks, and cleanup. Apply Gate 4H's source, executable, build-receipt, topology, readiness, connection, TELSER, bidirectional IMP-correlation, fatal-transport, and cleanup requirements whenever the operator opens a connection. Accept the character-oriented extension only if:

1. The session-start record binds the exact run and repository revision, available host-176-to-host-106 route, operator-terminal and PDP-11-console ownership, `seven-bit-safe-teletype` profile, local Control-] exit, blocked octal-034 SIMH WRU, line-feed and Delete mappings, high-bit rejection, safe output-control rendering, and finite directional and chunk limits.
2. Directional byte records preserve exact forwarded bytes with contiguous controller sequence, UTC time, base64 data, byte count, and SHA-256. Local-control records account for every blocked WRU or rejected high-bit byte. The terminal record and strict readback recompute directional bytes and digests plus data and control record counts.
3. The operator reaches the real Network UNIX shell, invokes `/usr/bin/telnet` without arguments, observes the preserved `UNIX User Telnet -- Ver I.5` command interface, and enters `connect - -h 106` through that interface. The controller neither synthesizes this command nor implements TELNET negotiation.
4. The client reports `Connection open`; ITS records the matching `nnTLNT` service job from `HST176`; the PDP-11 receives the ordered ITS machine and monitor greeting, TTY assignment, and welcome; and exact significant post-start inter-IMP content correlates in both directions while both selected host and modem paths remain ready.
5. In the same connection, a remote `:TIME` returns structured time, date, and uptime; the client's literal flag-command path exercises at least one protocol command with documented peer behavior and both message and character mode selection. The accepted retained run uses `^ayt` with an ITS `YES` response, `^msg`, and `^character`.
6. Project-added `SKTRACE` and `PBTRACE` lines may be removed from the human projection only; their bytes remain in the retained directional stream and raw console log. Unsafe output controls never reach the modern terminal unescaped.
7. Control-] ends the run through controller cleanup, octal-034 WRU never enters the guest-input stream, the invoking terminal settings are restored on success, interruption, or failure, and every owned process exits. A directional limit, simulator exit, malformed transcript, incomplete connection claim, transport failure, or surviving process fails acceptance.

An operator may exit before starting or connecting the client; that run may pass the bounded terminal lifecycle but does not satisfy Gate 4J and must retain `connection_open=0`. This gate proves a safe seven-bit teletype interaction with the preserved guest TELNET implementation. It does not prove a particular cursor-addressed terminal type, full-screen or paged ITS programs, browser input, application-link failover during a human session, or any new host-interface claim of its own. It emits no message-journey sidecar and supplies no host-ingress parser or new simulator authority.

## Gate 5: Payload anti-bypass

Generate a unique printable-ASCII sentinel. Inject it only through host A's console or guest application, transfer it through guest NCP, and recover it only through host B's console or guest application. The controller must have no operation that copies the payload between guest workspaces.

Accept only if the recovered sentinel matches the original digest and both IMPs record correlated post-start traffic. For the two-ITS baseline, log host `106` in as `DB`, log the remote pseudo-terminal in under a per-test name, inject the sentinel with DDT `:OSEND`, and recover it only from host `176`'s `UT` transcript. Do not substitute `:SEND`, which invokes a different program in this DDT configuration.

## NCC alternate-path line-fault gate

Start IMPs 5, 6, and 7 with the NCC receiver on IMP 5. Join IMPs 5 and 6 directly through an owned two-ended relay and indirectly through IMP 7. Map report line 1 only on the direct binding. After a bounded forward phase, keep both relay ports bound and drop valid direct-line traffic in both directions. Accept only if:

1. The receiver completes its ready exchange and records a complete IMP-to-host message plus checksum-valid trouble and throughput reports.
2. Before the cut, the relay forwards both directions and fresh reciprocal reports reduce the mapped line to `up`.
3. After the cut, the relay drops both directions, accepts no unexpected source, and never resumes forwarding.
4. Reports arrive from IMPs 5, 6, and 7, including post-cut reports from IMPs 5 and 6; IMP 6 must therefore remain observable through IMPs 7 and 5.
5. Final fresh reciprocal direct-line observations reduce to `down` and retain both supporting event sequences.
6. Every common precondition passes.

A receiver exit, one-sided cut, missing pre-cut `up`, missing post-cut IMP 6 report, or result reconstructed from raw packet logs cannot satisfy this gate.

## NCC alternate-path line-loopback gate

Use the same composition with an owned two-ended reflector. After a bounded forward phase, return each valid direct-line datagram unchanged to the endpoint that sent it. Accept only if:

1. The receiver satisfies the line-fault gate's ready-exchange and report requirement.
2. Before reflection, the instrument forwards both directions and fresh reciprocal reports reduce the mapped line to `up`.
3. After the loop boundary, the reflector records self-reflected traffic in both directions and accepts no unexpected source.
4. Reports arrive from IMPs 5, 6, and 7, including post-loop reports from IMPs 5 and 6.
5. Each latest mapped endpoint is `looped` and names its own reporting IMP; the reciprocal pair reduces to `looped` and retains both supporting sequences.
6. Every common precondition passes.

Configured or missing peer identity in a looped report, one-sided reflection, missing pre-loop `up`, missing post-loop IMP 6 report, or a conclusion derived from reflector phase instead of firmware reports cannot satisfy this gate.

## NCC-observed heterogeneous coexistence gate

Start Network UNIX 176, IMP 62, IMP 6, ITS 106, the IMP 5/6/7 NCC triangle, and the passive receiver as one composition. Preserve only the evidenced IMP 5 line 1 / IMP 6 line 1 mapping. Apply Gate 4H's source, executable, build-receipt, topology, readiness, connection, TELSER, bidirectional IMP-correlation, fatal-condition, and cleanup requirements. This composition retains its separately accepted pre-instrumentation journey window and claim. Accept the additional NCC claim only if:

1. The receiver records complete messages plus checksum-valid Type 303 trouble and Type 302 throughput reports.
2. Both report forms are independently attributed to IMPs 5, 6, 7, and 62.
3. A fresh reciprocal IMP 5/IMP 6 pair reduces the mapped line to `up` and retains its supporting sequences.
4. Application evidence proves TELNET, the ITS service job, structured remote `:TIME`, and exact bidirectional correlation over IMP 62 MI1 / IMP 6 MI3. Readiness tests the selected dead bits, not whole-word equality with a one-link sentinel.
5. The journey retains exactly ten observations and `missing-boundary` at `boundary:request:6`.
6. Unmapped application and alternate links acquire no report-line identity or inferred state, and persisted schemas do not change.
7. The application controller and outer runtime both pass cleanup, no transport error occurs, and every common precondition passes.

Evidence from another run, reports only from the NCC triangle, application traffic inferred from topology, or a report-line mapping inferred from an MI name cannot satisfy this gate. This gate proves coexistence, not failover.

## NCC-observed application-link failover gate

Start the coexistence composition with the direct IMP 62 MI1 / IMP 6 MI3 cable behind a run-owned two-ended cut relay and add the IMP 62 MI2 / IMP 7 MI3 alternate binding. Keep both application bindings report-line-unmapped. The controller may request the cut only after direct-path readiness and application evidence pass. Accept only if:

1. The manifest binds the exact topology, configurations, controller, receiver, relay, evaluator, build receipt, pinned inputs, simulator binaries, and eighteen leased ports with clean tracked state.
2. Network UNIX consumes the host-106 Reset Reply, then one TELNET session opens the ITS service and returns structured `:TIME` before the cut.
3. The relay forwards both directions, accepts no unexpected source, atomically acknowledges the run-local cut request, records one consistent fault timestamp, keeps both ports bound, and drops both directions afterward.
4. Without reconnecting or restarting a guest, the same TELNET session returns a second structured `:TIME` after the cut.
5. Fixed post-cut H316 windows on IMPs 62, 7, and 6 produce exactly fourteen observations for `route:host176-to-host106-alternate`. They prove the configured IMP crossings and retain `missing-boundary` at `boundary:request:8`.
6. The receiver records a post-cut trouble report from IMPs 5, 6, 7, and 62. Direct reports identify unique reciprocal candidates for pre-cut direct `up`, post-cut direct `down`, and post-cut alternate `up`; the verdict keeps them `candidate-only-one-exact-run`, and topology remains unmapped.
7. The application controller, receiver, and relay exit successfully; both cleanup layers pass; no transport or source error occurs; and every common precondition passes.

A second TELNET connection, elapsed-time cut without acknowledgement, one-sided drop, configured topology in place of H316 evidence, reports only before the cut, promoted candidate mapping, or application success without the fourteen-observation sidecar cannot satisfy this gate. The browser has no cut or control authority.

## Passive display acceptance

Passive projections must preserve the NCC contract invariants and these presentation rules:

- One operator console presents growing historical, completed line-state, coexistence, and failover projections. It exposes a 64-position annunciator, ARPA Network Log, Quick Summary, explicit operational and telemetry profiles, and no topology map or second report page.
- IMP REPORTS and directional mapped-line banks use source IMP numbers only. Unmapped application and alternate links acquire no lamp, line identity, or state. The separately labelled RUN PROOF bank may present validated application, journey, cut, alternate-route, and cleanup facts but must not represent them as IMP report fields.
- A completed coexistence projection validates only its declared structured artifacts and keeps application, journey, line-verdict, and later receiver-tail authority separate. A completed failover projection validates the manifest and digests, all thirteen verdict checks, same-session application facts, relay lifecycle and positive forward/drop counters, atomic cut timestamp, fourteen-observation alternate journey, complete historical stream, post-cut report sources 5, 6, 7, and 62, and cleanup.
- AUTO selection prioritizes existing resolved warning and fault state. Bank selection and alarm acknowledgement are browser-local presentation actions. JavaScript performs no artifact parsing, evidence reduction, route inference, or candidate report-line promotion.
- The HTTP surface exposes only `/`, `/api/snapshot`, and the empty favicon response through GET and HEAD; `/report`, arbitrary paths, and mutation methods fail closed.
- Keyboard controls expose consistent focus and pressed state, reduced-motion preferences are honored, and desktop and narrow layouts remain usable.
- The terminal runner selects the existing formal coexistence or failover harness and delegates its launch and stop; it does not add a second lifecycle or any browser command endpoint.

Source-only tests own deterministic snapshots, authority labels, route and method restrictions, accessibility behavior, fail-closed transitions, candidate-promotion refusal, cut-time binding, operator delegation, and stable Make targets. Read-only canonical replay owns agreement with retained evidence.

## Gate 6: Site integration

After Gates 4 and 5 pass, a replacement site stage must preserve the external contracts in [architecture](architecture.md#publication-seam): semantic output, artifact and build-log identity, status, exact source provenance, reuse fingerprints, validation, and fail-closed publication.

## Fault injection

For each production-shaped topology, force one endpoint or IMP to exit after partial startup and force one readiness timeout. Both cases must produce a bounded nonzero result, a failed manifest, and complete cleanup. A result-directory collision and occupied port must fail without overwriting evidence.

Source-only fixtures must reject partial or pre-offset application output, missing traffic on either required IMP, changed source or executable identity, malformed topology or trace windows, incomplete or changed packet correlation, a record after terminal diagnosis, and any persisted diagnosis that disagrees with the reducer.
