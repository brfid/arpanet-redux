# ADR-018: Compose the historical terminal with controller-owned application failover

- **Status:** Accepted
- **Date:** 2026-09-04
- **Decider:** Brad

## Context

[ADR-015](0015-character-oriented-historical-terminal.md) gives a human the preserved Network UNIX TELNET command interface through a bounded character adapter while one foreground controller retains every simulator PTY, exact directional bytes, safety controls, evidence checks, and cleanup. Its accepted composition has only the direct IMP 62 / IMP 6 application route and explicitly excludes application-link failover.

The separately accepted [application-failover composition](../experiments/2026-09-01-ncc-pdp11-its-application-failover.md) proves that an automatically driven TELNET session survives a controller-owned two-ended cut of that direct cable and continues through IMP 62 / IMP 7 / IMP 6. It also runs a passive NCC receiver and requires post-cut reports from every IMP. Those report and browser surfaces are not necessary to let a person perform the same application demonstration, and the browser still must not gain control authority.

Combining these existing capabilities requires a new local control, an explicit two-route terminal identity, and proof that a post-cut response belongs to the already-open guest session. It does not require another topology, simulator configuration, TELNET implementation, report-line mapping, or host-interface parser.

## Decision

Add `make telnet-failover` as a distinct foreground experience. Keep `make telnet` on the accepted direct route and keep `make telnet-check` on its deterministic prompt-framed contract. The new target reuses the exact four-IMP application-failover topology, relay, host build, simulator configurations, route timing, controller lifecycle, direct journey reducer, and alternate journey reducer. The formal `make smoke-ncc-pdp11-its-failover` behavior remains the default profile.

The terminal controller alone owns standard input, every simulator PTY, and the run-local relay request. In failover mode only, it reserves Control-^ as the cut request and does not forward that byte to Network UNIX. It refuses the request without cutting unless the preserved no-argument TELNET client has opened exactly one connection to ITS, returned one structured `:TIME`, produced a matching TELSER service job, and generated correlated direct-route traffic. A refused or repeated request is retained as a distinct local-control record.

After an accepted key, the controller creates the exclusive request file, requires the relay's atomic cut acknowledgement, waits until both endpoint IMPs report their direct devices dead and alternate devices ready, applies the accepted route-settle interval, and then tells the operator that the IMP 7 route is ready. The operator enters a second `:TIME` in the same guest session and finishes with Control-]. Acceptance requires exactly one `Connection open`, a complete structured post-cut response, bidirectional alternate-route traffic, a ten-observation direct pre-cut journey, a fourteen-observation post-cut journey with its existing missing request-ingress boundary, and complete cleanup.

Extend `terminal-session.jsonl` additively with schema version 2. Version 1 retains its exact direct-route shape and control vocabulary. Version 2 replaces `available_route` with a `route_plan` naming the initial direct route and post-cut alternate route, identifies the failover controller, declares Control-^, and admits typed requested, not-ready, and already-requested cut controls. The same strict reader validates both versions and rejects cross-version fields and controls.

The human profile does not start the passive NCC receiver and its evaluator makes no report-source or report-line claim. It closes only over terminal identity and digest, the relay and cut acknowledgement, guest application evidence, the typed alternate journey, clean pinned inputs, outcome, and inner and outer lifecycle cleanup. IMP 5 remains part of the reused four-IMP configured composition, not a historical-site claim or a source of required human-session evidence.

## Options considered

### Add the cut key to every historical terminal run

The direct terminal has no cut relay or alternate route. Reserving Control-^ there would silently narrow the accepted seven-bit guest-input profile and advertise authority the composition does not own.

### Drive a second connection after the cut

A reconnect would demonstrate post-fault reachability but not preservation of one live guest application session. Exactly one observed connection is therefore part of acceptance.

### Put the cut in the NCC browser

That would turn a passive projection into a network-control surface and require a separate authenticated authority, request, lifecycle, and audit contract. A terminal-local key keeps the action with the controller that already owns the exact run.

### Duplicate the failover topology and launcher for the terminal

A second set of configurations, port wiring, and route reducers would create two implementations of the same composition. A profile on the existing launcher keeps formal report evidence and human terminal evidence explicit while reusing one lifecycle.

## Consequences

- A person can observe one real Network UNIX TELNET connection before the fault, request the physical-link simulation fault, wait for controller-confirmed rerouting, and continue the same ITS session.
- Direct terminal input is unchanged: Control-^ remains a guest byte under `make telnet` and becomes a local control only under `make telnet-failover`.
- The terminal stream's version distinguishes one-route and two-route semantics without weakening version-1 replay.
- The new evaluator cannot promote report-line candidates or imply passive NCC observation because it has no receiver input.
- The failover journey retains its existing fourteen observations and missing `boundary:request:8`; application success does not fill that boundary.
- Browser input, simulator control, new topology identities, historical address claims, full-screen terminal behavior, and another TELNET stack remain out of scope.

## Evidence basis

- [ADR-015](0015-character-oriented-historical-terminal.md) owns the preserved-client terminal, seven-bit safety adapter, directional-byte stream, and sole-controller boundary.
- [ADR-014](0014-interactive-telnet-session-stream.md) owns the separate deterministic prompt-framed interface and explains why operator sessions do not belong in NCC persistence.
- The [accepted application-failover experiment](../experiments/2026-09-01-ncc-pdp11-its-application-failover.md) owns the relay cut, direct-dead/alternate-ready transition, three-IMP route, and fourteen-observation journey.
- [ADR-009](0009-ncc-paired-line-topology-boundary.md) keeps discovered report-line identities out of shared topology without independent reciprocal evidence.
