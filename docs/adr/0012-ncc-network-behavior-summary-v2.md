# ADR-012: Add an evidence-closed network-behavior profile to completed summaries

- **Status:** Accepted
- **Date:** 2026-08-31
- **Decider:** Brad

## Context

[ADR-005](0005-ncc-run-summary-contract.md) accepts version 1 of the completed-run summary for formal application runs. A passed version-1 gate must cite a passed application observation, and its derived-state vocabulary deliberately predates genuine reciprocal line-loopback evidence. [ADR-007](0007-ncc-historical-event-stream.md) and [ADR-008](0008-ncc-throughput-event-stream-v2.md) separately persist direct Type 301/303 and Type 302 observations without topology inference. The shared topology and source-only reducer now have explicit reciprocal report-line mappings and accepted exact `up`, `down`, and `looped` evidence, but their derived output reaches only run-specific evaluator verdicts rather than the common completed-run viewer.

Changing version 1 in place would make previously valid documents acquire new gate meaning without a version signal. Publishing inferred line state through the live stream would also violate that stream's accepted direct-observation-only authority. A new completed-run profile must retain version-1 compatibility, map only explicitly configured report-line endpoints, and make every passed network conclusion close over both a completed harness observation and the direct historical observations supporting its cited reducer result.

## Decision

Add completed-run summary schema version 2 while continuing to read version 1. Version 2 adds the reducer's `looped`, `minus-down`, `plus-down`, `minus-looped`, and `plus-looped` derived states. Its gates declare either `application` or `network-behavior` kind and explicitly identify both observation evidence and derived-state evidence.

A passed version-2 network-behavior gate must cite at least one inferential derived state, include every direct observation supporting that state, require those supporting observations to be historical-network observations, and include a passed harness observation. Version-1 application-gate validation remains unchanged. The controller-owned live stream stays at schema version 1 and gains no derived-state or gate authority.

Use a read-only adapter for the supported alternate-path fault and line-loopback result forms. It reads only the terminal run manifest, validated historical-event sidecar, supported evaluator verdict, and supplied shared topology. It verifies clean run provenance, topology identity and digest, completed lifecycle, verdict agreement, and the reducer's final state and support sequences. It maps a local report subject to a normalized endpoint only through reciprocal `first_report_line` and `second_report_line` fields, maps the binding to the unique configured link joining those endpoints, and emits a deterministic version-2 summary without modifying the result directory.

The first adapter persists one final reconciliation snapshot. Earlier transition detail remains in the supported verdict and direct event stream; a reducer timeline, live bridge, or historical-event schema change requires a separate decision.

## Options considered

### Extend version 1 in place

This would avoid a compatibility reader but would silently broaden accepted gate and state meaning. Existing consumers could not distinguish the old application-only contract from the new network-behavior profile.

### Persist another dedicated reducer-result contract

This would preserve the existing summary unchanged but create a fourth NCC container beside completed summaries, live observations, and historical direct events. The viewer and every later consumer would need another replay and evidence-closure path.

### Publish reducer conclusions through the live stream

The live stream intentionally carries direct observations only. Adding inferred states or final acceptance verdicts would give a bounded controller publication authority that belongs to completed-run adaptation.

### Add a backward-compatible completed-summary version

This accepted option keeps direct historical recording and inference separate, reuses the existing deterministic viewer, gives the version change an explicit signal, and lets version-1 application summaries retain their exact validation rules.

## Consequences

- Version-1 completed summaries remain readable, and the existing two-ITS adapter continues to write version 1.
- Live observation headers remain version 1 even though the latest completed-summary version is 2.
- Supported historical-line summaries can display genuine final line and IMP conclusions with complete observation traceability and no raw-log access.
- A network-behavior pass cannot be supported by topology, a relay phase, a verdict boolean, or one endpoint alone.
- Unmapped alternate bindings remain configured topology only and never acquire a report-line observation through this adapter.
- Message-journey persistence, live historical publication, reducer timelines, and additional evaluator result forms remain future decisions.
