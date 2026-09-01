# Passive NCC application-failover board projection

- **Date:** 2026-09-01
- **Status:** accepted implementation and read-only retained replay
- **Result read:** `/Users/brf/src/arpanet-redux-lab/results/ncc-pdp11-its-application-failover-canonical-20260901T204637Z`
- **Topology:** `config/topologies/ncc-pdp11-its-application-failover.json`

## Objective

Make the already accepted application-link failover visible on the restrained topology-first NCC board and runnable through the same terminal-owned convenience boundary as coexistence. Do not add a persisted schema, parse raw simulator logs, promote one-run report-line candidates, expose the cut or TELNET session as a browser command, or rerun the settled formal experiment merely to test presentation.

The accepted fault and application evidence remain owned by the [application-failover record](2026-09-01-ncc-pdp11-its-application-failover.md). The board continues the simple operator surface described in [`docs/ncc.md`](../ncc.md); it does not extend the scenario-manual treatment recorded in the [ICCC visual-grammar note](../research/2026-09-01-iccc-scenarios-visual-grammar.md).

## Projection boundary

`ncc.failover_display` constructs one deterministic in-memory snapshot only after validating the terminal manifest, clean pinned identities, supplied topology digest and exact topology identity, pre-cut and post-cut journey digests, verdict digest, application and cleanup key-value records, all thirteen passing verdict checks, relay lifecycle and positive forwarding and dropping counters in both directions, atomic cut acknowledgement, the exact fault timestamp across manifest, relay, cut state, and verdict, the terminal fourteen-observation alternate-route journey, and the complete schema-version-2 historical stream.

The displayed claims retain three independent authorities:

- The direct IMP 62 / IMP 6 application cable becomes `cut` only from the two-ended relay result and matching atomic cut acknowledgement.
- The IMP 62 / IMP 7 and IMP 7 / IMP 6 application cables become `observed` only from the reducer-verified typed post-cut journey for `route:host176-to-host106-alternate`.
- IMP lamps and the short activity tape come only from direct historical events; the adapter independently requires post-cut trouble reports from exactly IMPs 5, 6, 7, and 62.

The verdict's discovered direct and alternate report-line numbers must retain `candidate-only-one-exact-run` and `promoted_to_topology=false`. They are not copied into the snapshot and have no route-drawing authority.

## Retained replay

The accepted result was read in place without modification. Its projection reproduced:

- run `ncc-pdp11-its-application-failover-canonical-20260901T204637Z` and passing cleanup;
- fault start `2026-09-01T20:48:31.683758Z`;
- one passing same-session application result with structured ITS `:TIME` before and after the acknowledged cut;
- fourteen typed post-cut observations, route `route:host176-to-host106-alternate`, and first unresolved boundary `boundary:request:8`;
- 933 complete direct historical events and post-cut trouble-report sources 5, 6, 7, and 62;
- positive relay forward and drop counts in both directions; and
- an unpromoted candidate-only report mapping.

The formal smoke was not rerun. Raw console and simulator traces were not read by the projection or copied into the repository.

## Presentation and operator verification

The loopback board was served directly over the retained result and inspected at its normal desktop viewport and an explicit 420-by-900 narrow viewport. The rendered page showed `DIRECT → CUT → VIA IMP 7`, a fault-colored dashed direct application cable, signal-colored typed alternate legs, four reported IMP lamps, the same-session application summary, the explicit missing host boundary, and a seven-event post-cut report tail. The narrow layout had no body-level horizontal overflow; the intentionally fixed network map remained horizontally scrollable within its own panel. No form, WebSocket, visible `/report` link, or browser control appeared.

Source-only fixtures build an independent synthetic terminal journey and historical stream. They cover deterministic projection, journey-digest refusal, candidate-promotion refusal, cut-timestamp disagreement, failover board selection, coexistence-only `/report`, presentation-only markup, formal-harness command delegation, and stable `ncc-failover` and `view-ncc-failover` Make targets. A direct retained replay exercises the exact accepted artifacts.

## Limits and next step

The board describes one completed validated change; it does not claim a historical NCC display, report-line mapping for either application cable, traffic rate, live route switch, or user-controlled session. During a growing run it continues to show the existing progressive historical snapshot and withholds the completed cut and alternate-route conclusion until terminal validation.

The recommended follow-up is a terminal-side interactive TELNET session seam. It should first prove a typed command/result contract, single process owner, prompt and response framing, timeout behavior, command attribution, retained evidence, and complete cleanup. Browser input remains a separate later authority decision.
