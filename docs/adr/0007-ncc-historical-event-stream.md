# ADR-007: Persist direct passive reports in a dedicated historical-event stream

- **Status:** Accepted
- **Date:** 2026-08-31
- **Decider:** Brad

## Context

The passive IMP 5 ingress now produces genuine, attributed 1973 trouble-report events. Those are direct historical observations, not controller lifecycle evidence and not inferred line conditions. The record must retain their wire report code, source IMP, order, and observation time without committing raw host-interface frames or logs.

ADR-005 fixes the version-1 completed-run schema around formal two-ITS evidence, application gates, and configured topology. ADR-006 explicitly reserves a durable format for genuine report/reducer output until the receiver and shared topology are real. The controller-owned live stream reuses the accepted normalized-observation shape, whose subjects must be topological components, endpoints, links, or routes. Direct historical line subjects such as `imp:5:line:1` are intentionally topology-neutral and do not have to be configured topology identities. Forcing them into either existing contract would either broaden an accepted schema prematurely or make the receiver invent a second topology mapping.

## Decision

Use `ncc.historical_events` for a separate version-1 JSON Lines sidecar. It has one immutable header with the run identity, start time, shared-topology and interface identities, project-authored nominal topology snapshot, and provenance. Later lines are direct `NccEvent` records only. The recorder accepts the reporting IMP, report receipt, host-interface, and local line-endpoint event shapes emitted by the 1973 trouble-report decoder; it validates source attribution, sequential order, nondecreasing observation time, known reporting IMP, JSON-safe details, and its own explicit type/state vocabulary.

The record retains each event's actual report code, including the patched `0303` form. A reader tolerates only an interrupted final line, then validates the entire completed prefix. Replay returns ordered direct-event frames and last-known direct states; it does not calculate a topology edge, timeout, partition, application gate, or completed-run verdict.

The passive proof may write this sidecar after its bounded run when the caller supplies an explicit run identity and external output path. It writes no raw packet words, no simulator log, and no process-control metadata.

## Options considered

### Extend the version-1 completed-run summary

This would alter an accepted schema and entangle genuine historical observations with formal two-ITS application gates before there is an adapter from the new record to a completed result. It would also require a compatibility or migration decision for every current consumer.

### Publish into the controller-owned live stream

The live stream is deliberately constrained to normalized subjects in its topology snapshot. Making the receiver manufacture line subjects or add them to a second controller configuration would blur configured facts and direct historical observations.

### Keep only host-interface proof JSON

The bounded proof result is useful transport evidence, but it is not an append-only event record or replay input. Its message digests and receipt metadata should not become the telemetry contract.

### Use a dedicated direct-event sidecar

This accepted option preserves the existing contracts, gives the passive receiver an auditable derived record, and leaves a future summary/live adapter to an explicit compatibility decision.

## Consequences

- Historical report recording is safe to run beside a passive receiver and remains external laboratory output.
- Consumers can replay direct event order without raw logs or a simulator, but they must not infer complete line state without the separate reducer and its nominal interface mapping.
- A future bridge into the completed-run schema or controller live stream requires a new schema/compatibility decision and fixtures; it cannot silently reinterpret this stream as an application result.
- Type 302 throughput, checksum validation, report-field correlation with IMP state, and a historical route for the IMP 6 proof peer remain out of scope.
