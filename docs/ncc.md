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
| Result adapters | Revalidate supported completed artifacts and derive deterministic in-memory summaries without changing the result |
| Passive displays | Present fixed topology, progressive evidence, completed conclusions, and detailed inspection through loopback GET and HEAD requests |

The default network board shows a restrained topology-first view. It uses the existing historical projection while a result grows and switches to a validated completed projection only after terminal artifacts pass. The detailed coexistence report remains at `/report`. Fault, loopback, journey, historical-line, and coexistence-specific viewers remain diagnostic surfaces.

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

The accepted application summary contract is [ADR-005](adr/0005-ncc-run-summary-contract.md). Historical-line reconciliation and topology authority are defined by [ADR-006](adr/0006-ncc-line-reconciliation.md) and [ADR-009](adr/0009-ncc-paired-line-topology-boundary.md). State-specific neighbor rules are in [ADR-010](adr/0010-ncc-down-report-neighbor-absence.md) and [ADR-011](adr/0011-ncc-looped-report-self-neighbor.md). Version-2 network-behavior summaries and the journey sidecar are defined by [ADR-012](adr/0012-ncc-network-behavior-summary-v2.md) and [ADR-013](adr/0013-ncc-message-journey-stream.md).

## Accepted scope

The implemented subsystem supports:

- genuine attributed trouble and throughput reports from recovered 1973 IMP software;
- reciprocal `up`, `down`, and `looped` line conclusions for explicitly mapped endpoints;
- completed two-ITS summaries and a bounded direct-observation stream;
- typed Network UNIX-to-ITS journeys over the direct route and the accepted three-IMP failover route;
- passive progressive and completed displays;
- a combined Network UNIX/ITS application and IMP 5/6/7 NCC composition;
- same-session application survival after the controller cuts the direct IMP 62/IMP 6 cable and traffic reroutes through IMP 7.

The dated [fault](experiments/2026-08-31-ncc-alternate-path-fault.md), [loopback](experiments/2026-08-31-ncc-line-loopback.md), [typed journey](experiments/2026-09-01-pdp11-its-message-journey.md), [coexistence](experiments/2026-09-01-ncc-pdp11-its-coexistence.md), and [application-failover](experiments/2026-09-01-ncc-pdp11-its-application-failover.md) records own exact run identities, counts, failed prerequisites, and limits.

The direct and alternate application-link report identities discovered in the accepted failover run remain `candidate-only-one-exact-run`. They are not topology authority. Promotion requires independent fresh reciprocal evidence and a separate decision.

## Explicit exclusions

The browser cannot send TELNET input, switch a link, signal or restart a component, load memory, transfer core, run DDT, or mutate a result. The formal failover controller alone owns its run-local cut request.

The journey model stops at unproved guest ingress. The accepted direct route retains ten observations and first missing `boundary:request:6`; the failover route retains fourteen observations and first missing `boundary:request:8`. Application success does not fill those boundaries. A complete KA10 or IMP11-A host-ingress grammar requires new directly retained evidence.

Original 1971 NCC System 52 compatibility remains a separate investigation. It is not required for the current observability product.

## Current decision

No NCC implementation follow-up is required for the accepted slice. Candidate mapping promotion, interactive guest input, browser-side faults, per-component restart, new hosts or IMPs, complete guest-ingress grammars, and original NCC compatibility are separate bounded decisions. See [workstreams](workstreams.md) for the current selected tasks.
