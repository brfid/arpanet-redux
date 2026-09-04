# ADR-017: Accept versioned IMP11-A evidence for direct reply ingress

- **Status:** Accepted
- **Date:** 2026-09-04
- **Decider:** Brad

## Context

[ADR-016](0016-ka10-request-ingress-evidence.md) accepted direct KA10 evidence for ITS host-106 request ingress and advanced the typed Gate 4H journey to eleven observations. It deliberately left `boundary:reply:6`, Network UNIX host-176 reply ingress, missing because the successful application exchange and IMP 62 destination-HI egress did not independently prove delivery across the IMP11-A DMA boundary.

The pinned IMP11-A device already owns the relevant hardware operation: it preserves an input message across guest DMA buffers, converts each network-order word to the PDP-11 memory representation, calls `Map_WriteW`, and completes input only after a full buffer or the real final marker. Its existing packet debug output did not retain every word, message identity, or a completion relationship, so it could not reconstruct the complete reply without borrowing the conclusion from IMP 62.

## Decision

Pin IMP11-A simulator fork commit [`c74e7040e186a6ea11d9cd816b94edc235959e27`](https://github.com/brfid/imp11a-simh/commit/c74e7040e186a6ea11d9cd816b94edc235959e27). It adds one opt-in `INPUT` debug category to `PDP11/pdp11_imp.c`. Its counters and records are observational: they do not participate in registers, interrupts, buffering, scheduling, transport, conversion, completion, or guest-visible data decisions.

Version 1 records identify the start of each input message, every word after the corresponding `Map_WriteW`, and the real final completion. Each word carries a contiguous message-local index, the 18-bit DMA address, the network-order word, the PDP-11 memory word, and the simulator tick supplied by the existing debug prefix. A completion carries the exact stored-word count and is emitted only after the retained message reaches its final marker, including messages split across guest buffers.

Accept a strict source-only parser for this versioned grammar. It rejects unknown or malformed relevant records, nonpositive or noncontiguous message identities, noncontiguous word identities, backward source ticks, odd or out-of-range DMA addresses, non-16-bit values, a PDP-11 value that is not the exact byte-swapped network word, an incorrect or empty completion count, and an incomplete terminal message.

The direct Gate 4H adapter requires exactly one complete reconstructed IMP11-A message to equal the complete destination-HI reply independently parsed from IMP 62. It does not use a fingerprint to choose among duplicate candidates and does not compare independent simulator clocks. Only after literal equality does it derive the existing reply fingerprint and add `observation:reply:6` with direct `pdp11-imp11a-trace` provenance.

Enable the trace only in direct Gate 4H through a run-local derived PDP-11 configuration. Capture fixed start and end offsets from the already retained live PDP-11 console, bind that fourth source window and simulator revision into `message-journey.jsonl`, and require the combined KA10 and IMP11-A evidence to reduce to `complete` with no first missing boundary. Results without one or both optional guest trace windows continue to use their existing compatible extraction paths.

The accepted exact run is recorded in the [bounded IMP11-A reply-ingress result](../experiments/2026-09-04-imp11a-reply-ingress.md). It reconstructs one 13-word message from post-store DMA records spanning two guest buffers, equals the IMP 62 reply word for word, and advances the direct journey from eleven observations to twelve and `complete`.

## Options considered

### Infer ingress from application success

The successful TELNET session proves the application path, but using it to populate a packet boundary would collapse two distinct evidence planes and repeat the inference ADR-013 excluded.

### Treat IMP 62 destination-HI egress as connected-peer delivery

The existing harness-derived peer observation proves the configured handoff from IMP 62, not the separate IMP11-A memory write. It remains a distinct observation with its own provenance.

### Instrument the Network UNIX guest

Changing recovered kernel or daemon code would create a new historical artifact and expand the validation boundary. The simulator already performs the physical-interface DMA operation and can report it after the store without changing the guest.

### Reuse the existing one-line packet trace

That diagnostic records only the first wire and guest words for each DMA operation. It cannot reconstruct the full message, join multiple guest buffers, or prove a real final completion.

### Add the bounded versioned trace and strict parser

This accepted option records the missing fact where it occurs, retains only the fields necessary to reconstruct and validate complete messages, and limits the new authority to one exact direct-route reply-ingress boundary.

## Consequences

- Direct Gate 4H now requires twelve observations and a `complete` diagnosis with no first missing boundary.
- The version-1 message-journey schema remains unchanged. A fourth transaction-window source and one additional existing observation record are additive values within that contract.
- The IMP11-A fork and executable become part of the evidence identity for this claim, and the project pin must remain fetchable at the accepted commit.
- Retained earlier direct results remain immutable and replay with their recorded ten- or eleven-observation diagnoses. Coexistence and failover retain their accepted journey windows and counts until separately rerun under a new decision.
- This decision proves the exact reply crossed the simulated IMP11-A interface into PDP-11 memory. It does not prove Network UNIX daemon interpretation, host-176 request egress, KA10 reply construction, alternate-route guest ingress, a complete bidirectional guest grammar, a global clock, browser control, or a new application verdict.
- Raw simulator output, executables, and generated media remain in the external laboratory. Only the parser, typed observation, source pin, exact identities, and derived result are published here.

## Sources

- [ADR-013](0013-ncc-message-journey-stream.md), the message-journey evidence boundary this decision completes for direct Gate 4H.
- [ADR-016](0016-ka10-request-ingress-evidence.md), the independent request-ingress decision and the preceding eleven-observation result.
- [Bounded IMP11-A reply-ingress result](../experiments/2026-09-04-imp11a-reply-ingress.md), the exact instrumentation, build, run, reconstruction, replay, and limits.
- IMP11-A simulator, [`PDP11/pdp11_imp.c` at accepted revision `c74e7040`](https://github.com/brfid/imp11a-simh/blob/c74e7040e186a6ea11d9cd816b94edc235959e27/PDP11/pdp11_imp.c), the versioned post-store DMA records.
