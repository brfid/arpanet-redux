# ADR-009: Defer the paired-line shared-topology contract until both endpoints are observed

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The passive NCC topology has a project-authored IMP 5 / IMP 6 modem binding, and an exact checksum-validated run now repeatedly observes `imp:5:line:1` up with neighbor IMP 6. It therefore establishes a direct local endpoint for the configured proof path. The local IMP 6 peer has no reporting host attachment, however, so the run supplies no independently attributed reciprocal endpoint.

[ADR-006](0006-ncc-line-reconciliation.md) deliberately requires both configured endpoint observations before deriving a line state. The shared-topology document currently records simulator modem-device and port bindings but no report-line identities. Inferring a universal mapping from a simulator device name, or adding an untested line-identity schema merely because one local run correlated it, would turn configuration convenience into historical-network evidence.

## Decision

Keep the shared-topology schema and the historical-event stream unchanged for now. Do not feed the one-way IMP 5 observation to the paired-line reducer as a complete line and do not add a durable reducer-output or completed-run/controller-live bridge.

When a second passive receiver yields a separately attributed IMP 6 report, introduce explicit report-line identities on both sides of the shared modem binding and prove the pair through the existing source-only reducer. The identity fields must be validated against their respective report events; a simulator device name alone is not enough.

## Options considered

### Infer report-line number from the simulator device name

The current path makes `MI1` and report line 1 look aligned, but that correlation is evidence for this one configured path, not a reusable topology contract. Implicit mapping would obscure the evidence that must support every future interface binding.

### Add a separate NCC-only report-line map

This would let the reducer run without changing the simulator topology, but it duplicates endpoint identity outside the shared source of truth and risks a port/device path diverging from the report map.

### Extend shared topology immediately

An explicit shared mapping is the eventual direction, but defining it before obtaining the reciprocal report would create a schema without its required end-to-end acceptance proof.

### Defer the contract until both endpoint reports exist

This accepted option keeps the already validated one-way fact available as direct telemetry, preserves the source-only reducer's evidentiary rule, and prevents untested schema from spreading into unrelated NCC contracts.

## Consequences

- Direct IMP 5 line-endpoint events remain recordable and replayable, but they do not establish a complete line.
- The existing shared topology remains sufficient for the passive host-interface and one-way endpoint proofs.
- A future paired-line change must coordinate the NCC and network-expansion worktrees, add explicit report-line identities, attach a second passive reporting path, and run a new exact proof.
- No controller process control, raw-log parsing, historical-route assertion, or accepted run-summary schema change is authorized by this decision.
