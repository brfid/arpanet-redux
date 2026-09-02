# NCC observability

## Purpose

The NCC subsystem presents historically grounded network observations without turning the browser into a simulator console or weakening the project's evidence rules. It decodes genuine IMP reports, records validated direct events, derives bounded conclusions in Python, and exposes read-only views.

The historical and wire-format basis is in the dated [telemetry research note](research/2026-08-30-ncc-telemetry.md). This page owns current subsystem scope. The [test plan](test-plan.md) owns pass/fail requirements, and [ADRs](adr/) own accepted contract decisions.

## Supported surfaces

| Surface | Responsibility |
|---|---|
| Shared topology | Names components, interfaces, bindings, routes, display positions, and only explicitly evidenced report-line identities |
| Historical-event stream | Records attributed Type 301 or patched Type 303 trouble reports, Type 302 throughput reports, host-interface events, and local-line events |
| Historical-line reducer | Reconciles explicitly paired report endpoints, freshness, directional state, contradiction, and a narrow partition inference |
| Completed summary | Validates version-1 application results and version-2 application or network-behavior results with evidence-closed verdicts |
| Controller live stream | Publishes direct lifecycle and application observations from a bounded formal run; it has no derived-state or gate authority |
| Message-journey stream | Records typed observations for one named route, exact trace windows, source-local order, provenance, and the terminal reducer diagnosis |
| Interactive TELNET stream | Records one terminal controller's bounded operator commands and exact prompt-framed PDP-11 console results without granting browser authority |
| Historical terminal stream | Records bounded directional bytes and local safety decisions for a character-oriented Network UNIX console without claiming command/result grammar |
| Result adapters | Revalidate supported completed artifacts and derive deterministic in-memory summaries without changing the result |
| Passive displays | Present fixed topology, progressive evidence, completed conclusions, and detailed inspection through loopback GET and HEAD requests |

The default network board shows a restrained topology-first view. It uses the existing historical projection while a result grows and switches to a supported completed projection only after terminal artifacts pass. For the accepted failover, relay and cut-state artifacts color the direct application cable as cut, the typed journey colors only the observed route through IMP 7, and direct historical events light the reporting IMPs. Candidate report-line identities have no drawing authority. The detailed coexistence report remains at `/report`; failover, fault, and loopback results do not acquire that route. Journey, historical-line, and coexistence-specific viewers remain diagnostic surfaces.

## Evidence authority

| Authority | Examples | Rule |
|---|---|---|
| Configured fact | Component, attachment, expected link, intended route | Show structure only; do not imply activity or historical identity |
| Historical observation | Trouble report, throughput report, reported line endpoint | Attribute it to the reporting IMP and retain its source order |
| Harness observation | Process lifecycle, watchdog state, console marker, relay counters | Label it as modern controller or simulator evidence |
| Application evidence | Guest command, remote response, correlated payload | Bind it to the application gate; do not use it to fill an unobserved network boundary |
| Inference | Paired line state, partition-like reachability, journey diagnosis | Retain every supporting observation and the topology used to interpret it |
| Missing evidence | Timeout, absent report, interrupted record, missing boundary | Report unknown, stale, or incomplete; never silently convert absence to down |
| Verdict | Passed application or network-behavior gate | Close over the required direct, harness, identity, lifecycle, and cleanup evidence |

## Contract rules

- Every persisted contract is versioned, validates finite JSON-safe data, uses stable topology identities, and rejects unknown or incoherent references.
- JSON Lines readers accept complete validated prefixes and may ignore only an interrupted final record. Truncation, replacement, restart, or run-identity change starts a new stream generation.
- Type 301/303 and Type 302 ingress validates the semantic 16-bit checksum domain before creating an event. The old-style leader and pad words are outside that domain.
- Report-line identity comes only from reciprocal explicit fields on one configured modem binding. A SIMH name such as `MI1` never supplies that identity.
- An `up` endpoint names its configured peer. An accepted `down` endpoint may name the peer or omit the firmware-cleared neighbor. An accepted `looped` endpoint names its own reporting IMP. Other neighbor combinations are contradictory.
- Missing endpoint evidence is `unknown`; expired evidence is `stale`; neither means `down`. Partition remains a reachability inference requiring fresh down evidence through at least two independent peers.
- Journey boundaries derive from one named route and existing host or modem bindings. Observations retain direct or harness-derived provenance and source-local order. Independent simulator ticks are never compared as a global clock.
- Reducers run in Python. Browser code receives resolved snapshots and performs presentation only.
- Adapters and displays read retained results without repairing, normalizing, or rewriting them. Any identity, digest, topology, lifecycle, reducer, or support mismatch fails closed.
- HTTP servers bind IPv4 loopback, accept GET and HEAD only, expose fixed routes, and provide no simulator, controller, guest-input, relay, arbitrary-file, external-network, or result-mutation method.

The accepted application summary contract is [ADR-005](adr/0005-ncc-run-summary-contract.md). Historical-line reconciliation and topology authority are defined by [ADR-006](adr/0006-ncc-line-reconciliation.md) and [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md). State-specific neighbor rules are in [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md) and [ADR-011](adr/0011-ncc-looped-report-self-neighbor.md). Version-2 network-behavior summaries and the journey sidecar are defined by [ADR-012](adr/0012-ncc-network-behavior-summary-v2.md) and [ADR-013](adr/0013-ncc-message-journey-stream.md). The prompt-framed terminal session stream is defined by [ADR-014](adr/0014-interactive-telnet-session-stream.md); the character-oriented historical terminal and its separate byte stream are defined by [ADR-015](adr/0015-character-oriented-historical-terminal.md).

## Accepted scope

The implemented subsystem supports:

- genuine attributed trouble and throughput reports from recovered 1973 IMP software;
- reciprocal `up`, `down`, and `looped` line conclusions for explicitly mapped endpoints;
- completed two-ITS summaries and a bounded direct-observation stream;
- typed Network UNIX-to-ITS journeys over the direct route and the accepted three-IMP failover route;
- a bounded line-oriented Network UNIX-to-ITS session with strict operator-command and prompt-framed result retention;
- a bounded character-oriented Network UNIX terminal with guest-owned TELNET behavior, exact directional-byte retention, and simulator-control isolation;
- passive progressive and completed displays, including a fail-closed application-failover projection and terminal-owned runner;
- a combined Network UNIX/ITS application and IMP 5/6/7 NCC composition;
- same-session application survival after the controller cuts the direct IMP 62/IMP 6 cable and traffic reroutes through IMP 7.

The dated [fault](experiments/2026-08-31-ncc-alternate-path-fault.md), [loopback](experiments/2026-08-31-ncc-line-loopback.md), [typed journey](experiments/2026-09-01-pdp11-its-message-journey.md), [coexistence](experiments/2026-09-01-ncc-pdp11-its-coexistence.md), [application-failover](experiments/2026-09-01-ncc-pdp11-its-application-failover.md), [failover-board](experiments/2026-09-01-ncc-application-failover-board.md), and [interactive TELNET](experiments/2026-09-01-interactive-pdp11-its-telnet.md) records own exact run identities, counts, failed prerequisites, retained replay, and limits.

The direct and alternate application-link report identities discovered in the accepted failover run remain `candidate-only-one-exact-run`. They are not topology authority. Promotion requires independent fresh reciprocal evidence and a separate decision.

## Explicit exclusions

The browser cannot send TELNET input, switch a link, signal or restart a component, load memory, transfer core, run DDT, or mutate a result. The formal failover controller alone owns its run-local cut request, and the interactive controller alone owns either foreground terminal mode. The character bridge blocks the configured SIMH WRU byte and never exposes `sim>`.

The journey model stops at unproved guest ingress. The accepted direct route retains ten observations and first missing `boundary:request:6`; the failover route retains fourteen observations and first missing `boundary:request:8`. Application success does not fill those boundaries. A complete KA10 or IMP11-A host-ingress grammar requires new directly retained evidence.

Original 1971 NCC System 52 compatibility remains a separate investigation. It is not required for the current observability product.

## Current decision

The accepted failover projection validates the terminal manifest and digests, same-session application facts, thirteen-check verdict, relay lifecycle and cut acknowledgement, fourteen-observation alternate journey, complete historical stream, post-cut report sources, and cleanup. It adds no persisted schema, parser, or simulator authority. `make ncc-failover` launches the unchanged formal smoke beside the passive board, and `make view-ncc-failover` replays the retained canonical result.

Both terminal-side seams are accepted. The prompt-framed mode retains deterministic command/result evidence. The character-oriented mode starts on Network UNIX, delegates connection, option, mode, and protocol behavior to the preserved guest client, retains exact directional bytes, blocks simulator WRU, safely projects output, and closes an application claim only when direct guest, ITS, IMP, and cleanup evidence exists. Neither adds a browser endpoint, message-journey observation, ingress parser, or simulator authority. Passive NCC presentation of session status and any browser input remain separate optional decisions. Candidate mapping promotion, browser-side faults, per-component restart, new hosts or IMPs, complete guest-ingress grammars, and original NCC compatibility also remain separate decisions. See [workstreams](workstreams.md) for current boundaries.
