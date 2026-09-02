# ADR-016: Accept versioned KA10 evidence for direct request ingress

- **Status:** Accepted
- **Date:** 2026-09-02
- **Decider:** Brad

## Context

[ADR-013](0013-ncc-message-journey-stream.md) accepted a typed Gate 4H journey built from fixed H316 trace windows. It deliberately left host-106 request ingress and host-176 reply ingress missing because application success and connected-peer delivery do not prove what either guest consumed.

The [KA10 extraction-grammar feasibility result](../experiments/2026-09-01-ka10-host-ingress-grammar.md) established the exact obstacle at host 106. Existing `DATAI` debug output contains the value later read by ITS, but not the receive message identity, assembled word index, 32- or 36-bit width, final valid-bit count, or the direct relationship between assembly and consumption. Reconstructing those facts from guest control flow or the already-known IMP 6 egress would make the desired conclusion an inference rather than an independent observation.

The feasibility result also defined a sufficient revisit condition: directly retain those missing assembly properties in the exact target transaction, bind each assembled word to its subsequent `DATAI`, and add a parser only if the consumed words independently reconstruct the accepted request.

## Decision

Pin KA10 simulator fork commit [`4b59f21d00355a7a917fa7cd54ef8a1123b515b2`](https://github.com/brfid/ka10-simh/commit/4b59f21d00355a7a917fa7cd54ef8a1123b515b2). It adds one opt-in `ASSEMBLY` debug category to the NCP-mode IMP device. The trace state is observational: it does not participate in status, interrupt, buffering, scheduling, transport, leader-conversion, or guest-visible data decisions.

Version 1 records identify each complete received NCP input message and its bit count. Every presented input word records the message and word identities, source bit offset, 32- or 36-bit assembly width, valid-bit count, final-word state, and left-aligned value. The corresponding `DATAI` record repeats the complete word identity and metadata plus the value actually returned to ITS. A record is evidence only when the assembly and consumption forms agree exactly.

Accept a strict source-only parser for this versioned grammar. It rejects unknown or malformed records, noncontiguous message or word identities, backward source ticks, changed message sizes, impossible widths or alignment, incorrect valid/final state, mismatched assembly and consumption, and an incomplete terminal message. It reconstructs octets only from valid bits of words proven consumed by `DATAI`.

Normalize a reconstructed message to the recovered IMP network's short form only when its 96-bit long leader is canonical for the pinned H316 conversion. The parser validates the format flag, supported flags, address and type fields, declared data length, zero host padding, and exact trailing data. It then reverses the documented flag, host, type, identifier, and subtype mapping. The Gate 4H adapter requires exactly one fully consumed normalized message to equal the complete destination-HI request emitted by IMP 6. It never uses the known request fingerprint to select an ambiguous reconstruction and never compares independent simulator clocks.

Enable this trace only in the direct Gate 4H smoke. Capture the KA10 console's fixed start and end byte offsets alongside the two existing H316 windows, retain the slice digest and simulator revision in the sidecar, and create `observation:request:6` with direct `ka10-imp-trace` provenance. Historical results and compositions that do not declare the KA10 window continue to replay under the ten-observation adapter path.

The accepted exact run is recorded in the [bounded instrumentation result](../experiments/2026-09-02-ka10-request-ingress.md). It reconstructs one 304-bit request from six 36-bit words and three 32-bit words, proves matching `DATAI` consumption for every word, normalizes to the exact IMP 6 request, and advances the direct journey from ten to eleven observations. The first missing boundary is now `boundary:reply:6`, host-176 reply ingress.

## Options considered

### Infer assembly from the old `DATAI` trace

The earlier trace admits more than one width interpretation and omits the last word's valid-bit count. Supplying those values from ITS control flow, H316 egress, or the expected fingerprint would answer the question with the conclusion being tested.

### Instrument the ITS guest

Changing recovered guest code would create a new historical artifact and a much larger validation boundary. The simulator already owns the assembly operation and can report it without modifying guest-visible behavior.

### Log every internal IMP-device transition

A broad trace would increase evidence volume and parser surface without improving the bounded claim. Message identity, word assembly, and matching `DATAI` consumption are sufficient for this boundary.

### Accept application success as host ingress

The successful TELSER exchange proves the application path but not the exact packet-level boundary. Keeping those evidence planes separate is a core journey invariant.

### Add the bounded versioned trace and strict parser

This accepted option records the missing fact at the component that creates it, preserves the existing protocol path, fails closed, and limits the new authority to one exact direct-route boundary.

## Consequences

- Direct Gate 4H now requires eleven observations and stops at missing `boundary:reply:6`; host-106 request ingress is direct trace evidence rather than an application inference.
- The version-1 message-journey schema remains unchanged. A third transaction-window source and an additional existing observation record are additive values within that contract.
- The KA10 fork and executable become part of the evidence identity for this claim, and the project pin must remain fetchable at the accepted commit.
- Retained pre-instrumentation results remain immutable and replay as ten observations. The coexistence and failover journeys retain their accepted ten- and fourteen-observation contracts until each is separately rerun with an exact KA10 window.
- Host-176 reply ingress, KA10 reply egress, IMP11-A request egress, and any complete bidirectional guest grammar remain unproved. This decision authorizes none of them.
- Raw simulator output remains in the external laboratory. Only the versioned parser, typed observation, exact identities, and derived result are published here.

## Sources

- [KA10 extraction-grammar feasibility result](../experiments/2026-09-01-ka10-host-ingress-grammar.md), the settled missing-property analysis and revisit requirement.
- [Bounded KA10 request-ingress result](../experiments/2026-09-02-ka10-request-ingress.md), the exact instrumentation, run identity, reconstruction, replay, and limits.
- KA10 simulator, [`PDP10/kx10_imp.c` at accepted revision `4b59f21d`](https://github.com/brfid/ka10-simh/blob/4b59f21d00355a7a917fa7cd54ef8a1123b515b2/PDP10/kx10_imp.c), the versioned receive-assembly and consumption records.
- H316 simulator, [`H316/h316_hi.c` at pinned revision `feb155fb`](https://github.com/larsbrinkhoff/simh/blob/feb155fbc49333e879ab082d481e6dcce27d2d91/H316/h316_hi.c#L401-L449), the short-to-long leader conversion reversed by the bounded adapter.
