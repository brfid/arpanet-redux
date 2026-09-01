# ADR-013: Persist bounded formal message journeys in a separate stream

- **Status:** Accepted
- **Date:** 2026-09-01
- **Decider:** Brad

## Context

The source-only message-journey model already derives request and reply boundaries from one shared-topology route, retains source-local order and provenance, and diagnoses complete, missing, contradictory, ambiguous, or unknown evidence through one pure reducer. The accepted Gate 4H PDP-11-to-ITS TELNET harness also has the post-probe H316 trace windows needed to populate ten of the twelve route boundaries without changing either guest or simulator.

The accepted completed-run summaries describe application or network-behavior gates, the controller-live stream carries direct lifecycle observations, and the historical-event stream carries direct 1973 IMP reports. None of those contracts represents correlated packet boundaries from independent trace sources. Extending one in place would either broaden an accepted schema or confuse a typed diagnostic with gate authority. Recomputing the journey in a browser would introduce a second reducer and a second topology interpretation.

The H316 evidence is intentionally incomplete at the guest boundary. Receipt of a host message by the connected IMP supports a harness-derived peer egress observation, while the H316 host and modem transfers are direct trace observations. No accepted KA10 or IMP11-A extraction grammar proves the final destination-host ingress on either leg.

## Decision

Persist one additive version-1 JSON Lines sidecar named `message-journey.jsonl`. Its immutable header contains the formal run identity and start time, source provenance, the complete project-authored shared topology, the expected request/reply journey derived from its named route, and exact source-local transaction windows. Each window records an artifact basename, start and end byte offsets, and SHA-256 of the consumed slice.

Observation records use the existing `MessageJourneyObservation` contract. The stream preserves emission order only and explicitly declares that it has no global clock. Every observation retains its own source-local sequence, optional source-local transport or tick, decoded fields, correlation fingerprint, evidence reference, and provenance. A terminal record persists the exact diagnosis recomputed by the existing reducer. The reader rejects any disagreement, record after completion, invalid topology identity, malformed observation, or incoherent source-local order; it ignores only an incomplete final JSONL record.

The formal Gate 4H controller validates the shared topology before launch, captures fixed end offsets after the accepted application evidence is present, extracts the first exact TELNET-open request and its first exactly correlated control reply, writes the sidecar, reads it back, and records its hash, offsets, observation count, state, and first unresolved boundary in the manifest. The smoke requires that evidence before it can pass.

Cross-process correlation requires literal equality of the complete inter-IMP packet. Within one H316 trace, an MI packet may represent an adjacent HI transfer only through the established literal containment relation and increasing source-local sequence. Independent simulator ticks are never compared. Direct H316 transfers and harness-derived connected-peer delivery remain visibly different authorities.

The accepted formal result emits ten observations and stops with `missing-boundary` at `boundary:request:6`, the unproved host-106 ingress. The analogous reply host ingress is also unobserved. Those gaps do not overturn the independently accepted application gate and are not filled from application success, configured topology, a synthetic event, or a speculative host parser.

## Options considered

### Extend a completed-summary, live, or historical-event schema

This would give an existing contract a new evidence category and authority. It would also require compatibility changes for consumers that correctly assume those schemas contain completed gates, controller observations, or direct historical reports.

### Reconstruct the journey in JavaScript

This would duplicate route expansion, correlation, validation, and reducer semantics in a presentation layer. It could diverge from source-only replay and would make exact provenance harder to inspect.

### Retain only raw logs and manifest offsets

Offsets make a transaction window reproducible but do not provide a validated, typed, progressively readable observation contract. Every consumer would need raw-log access and its own parser.

### Add KA10 or IMP11-A parsers now

Neither full extraction format is proven. Adding a partial parser to make the display look complete would overstate the evidence and couple the bounded emission slice to new simulator authority.

### Add a separate typed journey stream

This accepted option preserves every existing contract, reuses the shared topology and pure reducer, makes the exact trace window auditable, and lets a later passive consumer render resolved observations without parsing logs or controlling a run.

## Consequences

- Existing completed-summary, controller-live, and historical-event schemas remain backward compatible.
- A formal Gate 4H pass now includes a reducer-verified, read-back-verified typed journey sidecar and its manifest digest.
- Retained passing Gate 4H results can be adapted read-only into the same sidecar outside their immutable result directories.
- Direct, harness-derived, configured, missing, and contradictory evidence remain distinct.
- The terminal journey diagnosis is diagnostic evidence, not a replacement for the Gate 4H application verdict.
- A passive journey display can consume Python-resolved stream data later without adding browser-side inference.
- Closing the two guest-ingress gaps requires a separately justified, fully proven KA10 or IMP11-A extraction format.
